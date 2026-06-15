"""Analysis stage: run a trajectory command as a pipeline step."""

from __future__ import annotations

import importlib
import os
from typing import TYPE_CHECKING, Any, Literal, get_type_hints

from . import StageBase, register_stage

if TYPE_CHECKING:
    from ..runner import Runner


def _cli_args_to_kwargs(func, args: dict) -> dict:
    """Translate YAML keys (matching ``--flag`` names) to Python parameter names."""
    cli_to_py = {}
    hints = get_type_hints(func, include_extras=True)
    for py_name, hint in hints.items():
        cli_name = py_name
        for meta in getattr(hint, "__metadata__", ()):
            # Typer stores positional flag args in `default` until build time.
            decls = list(getattr(meta, "param_decls", None) or [])
            default = getattr(meta, "default", None)
            if isinstance(default, str) and default.startswith("-"):
                decls.insert(0, default)

            for decl in decls:
                if decl and decl.startswith("--"):
                    cli_name = decl.lstrip("-")
                    break
        cli_to_py[cli_name] = py_name
    return {cli_to_py.get(k, k): v for k, v in args.items()}


@register_stage
class AnalysisStage(StageBase):
    type: Literal["analysis"]
    command: str  # which trajectory command, e.g. "rmsd"
    args: dict[str, Any] = {}  # YAML keys match the command's CLI flags

    def run(self, runner: "Runner") -> None:
        """Invoke a ``trajectory`` subcommand from within the output directory."""
        module = importlib.import_module(
            f"openmm_cli.commands.trajectory.{self.command}"
        )
        kwargs = _cli_args_to_kwargs(module.command, self.args)
        cwd = os.getcwd()
        try:
            os.chdir(runner.output_dir)
            module.command(**kwargs)
        finally:
            os.chdir(cwd)
