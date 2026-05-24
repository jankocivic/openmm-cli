"""Wrap molecules back into the primary unit cell (periodic imaging)."""
from pathlib import Path
from typing import Annotated

import mdtraj as md
import typer


def command(
    trajectory: Annotated[Path, typer.Argument()],
    topology: Annotated[Path, typer.Option("--top")],
    output: Annotated[Path, typer.Option("--out")] = Path("imaged.dcd"),
) -> None:
    """Image molecules into the primary unit cell, keeping them whole across boundaries."""
    traj = md.load(str(trajectory), top=str(topology))
    if traj.unitcell_lengths is None:
        raise typer.BadParameter("Trajectory has no periodic box; nothing to image.")

    traj.image_molecules(inplace=True)
    traj.save(str(output))
    print(f"Imaged {traj.n_frames} frames; wrote {output}")
