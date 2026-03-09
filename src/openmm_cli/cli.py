import typer

from openmm_cli.commands.run.minimization import minimization

app = typer.Typer(help="OpenMM command line interface.")

prepare_app = typer.Typer(help="Prepare simulation inputs.")
run_app = typer.Typer(help="Run simulations.")
analyze_app = typer.Typer(help="Analyze trajectories.")

# Register top-level groups
app.add_typer(prepare_app, name="prepare")
app.add_typer(run_app, name="run")
app.add_typer(analyze_app, name="analyze")

# Register run commands
run_app.command()(minimization)

if __name__ == "__main__":
    app()
