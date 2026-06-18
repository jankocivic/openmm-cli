"""Convert a trajectory between file formats."""

from pathlib import Path
from typing import Annotated

import typer


def command(
    trajectory: Annotated[Path, typer.Argument(help="Input trajectory.")],
    topology: Annotated[Path, typer.Option("--top")],
    output: Annotated[
        Path,
        typer.Option(
            "--out",
            help="Output trajectory; format inferred from extension (.dcd, .xtc, .trr, .nc, .h5).",
        ),
    ] = Path("converted.xtc"),
) -> None:
    """Convert a trajectory between formats. Output format is inferred from the extension."""
    import mdtraj as md

    traj = md.load(str(trajectory), top=str(topology))
    traj.save(str(output))
    print(f"Converted {traj.n_frames} frames: {trajectory} -> {output}")
