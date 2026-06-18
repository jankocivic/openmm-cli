"""Compute the angle between three atom selections (by center of mass) over time."""

from pathlib import Path
from typing import Annotated

import typer


def command(
    trajectory: Annotated[Path, typer.Argument()],
    topology: Annotated[Path, typer.Option("--top")],
    selection_a: Annotated[str, typer.Option("--a", help="First selection.")],
    selection_b: Annotated[
        str, typer.Option("--b", help="Second selection (the vertex).")
    ],
    selection_c: Annotated[str, typer.Option("--c", help="Third selection.")],
    output: Annotated[Path, typer.Option("--out")] = Path("angle.csv"),
    degrees: Annotated[bool, typer.Option("--degrees/--radians")] = True,
) -> None:
    """Angle A-B-C over time, using the center of mass of each selection (B is the vertex)."""
    import mdtraj as md
    import numpy as np

    traj = md.load(str(trajectory), top=str(topology))

    def com_of(sel: str) -> np.ndarray:
        idx = traj.topology.select(sel)
        if len(idx) == 0:
            raise typer.BadParameter(f"Selection {sel!r} matched no atoms")
        return md.compute_center_of_mass(traj.atom_slice(idx))  # (n_frames, 3)

    a, b, c = com_of(selection_a), com_of(selection_b), com_of(selection_c)

    v1 = a - b
    v2 = c - b
    cos_angle = (v1 * v2).sum(axis=1) / (
        np.linalg.norm(v1, axis=1) * np.linalg.norm(v2, axis=1)
    )
    angles = np.arccos(np.clip(cos_angle, -1.0, 1.0))
    if degrees:
        angles = np.degrees(angles)

    unit = "deg" if degrees else "rad"
    with open(output, "w") as f:
        f.write(f"frame,angle_{unit}\n")
        for i, r in enumerate(angles):
            f.write(f"{i},{r}\n")
    print(f"Wrote {output} ({traj.n_frames} frames)")
