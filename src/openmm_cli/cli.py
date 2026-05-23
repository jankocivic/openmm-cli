import typer

from openmm_cli.commands.run import run

app = typer.Typer(help="OpenMM command line interface.")

prepare_app = typer.Typer(help="Prepare simulation inputs.")
analyze_app = typer.Typer(help="Analyze trajectories.")

# Register top-level groups
app.add_typer(prepare_app, name="prepare")
app.add_typer(analyze_app, name="analyze")

# Register general commands
app.command(name="run")(run)

if __name__ == "__main__":
    app()
