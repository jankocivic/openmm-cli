import importlib
import pkgutil

import typer

from openmm_cli.commands import trajectory as trajectory_pkg
from openmm_cli.commands.run import run

app = typer.Typer(help="OpenMM command line interface.")

# Top-level commands
app.command(name="run")(run)

# Trajectory subcommands -- auto-discovered from commands/trajectory/
trajectory_app = typer.Typer(help="Trajectory analysis and processing.")
for _, modname, _ in pkgutil.iter_modules(trajectory_pkg.__path__):
    if modname.startswith("_"):
        continue
    module = importlib.import_module(f"{trajectory_pkg.__name__}.{modname}")
    if hasattr(module, "command"):
        trajectory_app.command(name=modname)(module.command)
app.add_typer(trajectory_app, name="trajectory")

# Other groups (empty for now)
prepare_app = typer.Typer(help="Prepare simulation inputs.")
app.add_typer(prepare_app, name="prepare")

if __name__ == "__main__":
    app()
