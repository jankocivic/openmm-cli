"""Launch the openmm-cli dashboard."""
import subprocess
import sys
from importlib.resources import files
from pathlib import Path
from typing import Annotated

import typer


def command(
    directory: Annotated[Path, typer.Argument(
        help="Directory to display. Defaults to the current directory.",
    )] = Path("."),
    port: Annotated[int, typer.Option("--port", help="Port to serve on.")] = 8501,
) -> None:
    """Launch a web dashboard that plots CSV output files"""
    try:
        import streamlit  # noqa: F401
    except ImportError:
        typer.echo(
            "Dashboard dependencies not installed. "
            "Install with: uv sync --extra dashboard",
            err=True,
        )
        raise typer.Exit(1)

    app_path = files("openmm_cli.dashboard").joinpath("app.py")
    subprocess.run(
        [
            sys.executable, "-m", "streamlit", "run", str(app_path),
            "--server.port", str(port),
            "--",                                     # separates streamlit args from script args
            "--directory", str(directory.resolve()),
        ],
        check=True,
    )
