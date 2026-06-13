"""Run a trajectory analysis command as a pipeline stage."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import get_type_hints

from .config import AnalysisStage


def cli_args_to_kwargs(func, args: dict) -> dict:
    """Translate YAML keys (matching ``--flag`` names) to Python parameter names."""
    cli_to_py = {}
    hints = get_type_hints(func, include_extras=True)
    for py_name, hint in hints.items():
        cli_name = py_name
        for meta in getattr(hint, "__metadata__", ()):
            # Typer stores positional flag args in `default` until command-building time.
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


def run_analysis(stage: AnalysisStage, output_dir: Path) -> None:
    """Invoke a ``trajectory`` subcommand from within the output directory."""
    module = importlib.import_module(f"openmm_cli.commands.trajectory.{stage.command}")
    kwargs = cli_args_to_kwargs(module.command, stage.args)
    cwd = os.getcwd()
    try:
        os.chdir(output_dir)
        module.command(**kwargs)
    finally:
        os.chdir(cwd)
