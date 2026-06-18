"""Compute the distance between two atom selections over time."""

from pathlib import Path
from typing import Annotated

import typer


def command(
    trajectory: Annotated[Path, typer.Argument()],
    topology: Annotated[Path, typer.Option("--top")],
    selection_a: Annotated[str, typer.Option("--a", help="First atom selection.")],
    selection_b: Annotated[str, typer.Option("--b", help="Second atom selection.")],
    output: Annotated[Path, typer.Option("--out")] = Path("distance.csv"),
) -> None:
    """Distance (nm) between two atom selections over time."""
    import mdtraj as md
    import numpy as np

    traj = md.load(str(trajectory), top=str(topology))

    idx_a = traj.topology.select(selection_a)
    idx_b = traj.topology.select(selection_b)
    if len(idx_a) == 0 or len(idx_b) == 0:
        raise typer.BadParameter("One or both selections matched no atoms")

    pos_a = md.compute_center_of_mass(traj.atom_slice(idx_a))
    pos_b = md.compute_center_of_mass(traj.atom_slice(idx_b))
    distances = np.linalg.norm(pos_a - pos_b, axis=1)

    with open(output, "w") as f:
        f.write("frame,distance_nm\n")
        for i, r in enumerate(distances):
            f.write(f"{i},{r}\n")
    print(f"Wrote {output} ({traj.n_frames} frames)")
