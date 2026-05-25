import importlib
import pkgutil

import typer

from openmm_cli import commands as commands_pkg

app = typer.Typer(help="OpenMM command line interface.")


def _discover(parent_pkg, parent_app):
    for _, modname, ispkg in pkgutil.iter_modules(parent_pkg.__path__):
        if modname.startswith("_"):
            continue
        module = importlib.import_module(f"{parent_pkg.__name__}.{modname}")
        if hasattr(module, "command"):
            parent_app.command(name=modname)(module.command)
        elif ispkg:
            help_text = (module.__doc__ or f"{modname} commands").strip()
            sub_app = typer.Typer(help=help_text)
            _discover(module, sub_app)
            parent_app.add_typer(sub_app, name=modname)


_discover(commands_pkg, app)

if __name__ == "__main__":
    app()
