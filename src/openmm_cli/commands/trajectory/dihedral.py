"""Compute the dihedral angle between four atom selections (by center of mass) over time."""
from pathlib import Path
from typing import Annotated

import mdtraj as md
import numpy as np
import typer


def command(
    trajectory: Annotated[Path, typer.Argument()],
    topology: Annotated[Path, typer.Option("--top")],
    selection_a: Annotated[str, typer.Option("--a")],
    selection_b: Annotated[str, typer.Option("--b")],
    selection_c: Annotated[str, typer.Option("--c")],
    selection_d: Annotated[str, typer.Option("--d")],
    output: Annotated[Path, typer.Option("--out")] = Path("dihedral.csv"),
    degrees: Annotated[bool, typer.Option("--degrees/--radians")] = True,
) -> None:
    """Dihedral angle A-B-C-D over time, using the center of mass of each selection."""
    traj = md.load(str(trajectory), top=str(topology))

    def com_of(sel: str) -> np.ndarray:
        idx = traj.topology.select(sel)
        if len(idx) == 0:
            raise typer.BadParameter(f"Selection {sel!r} matched no atoms")
        return md.compute_center_of_mass(traj.atom_slice(idx))  # (n_frames, 3)

    p_a = com_of(selection_a)
    p_b = com_of(selection_b)
    p_c = com_of(selection_c)
    p_d = com_of(selection_d)

    # Standard dihedral formula (atan2-based, numerically stable)
    b1 = p_b - p_a
    b2 = p_c - p_b
    b3 = p_d - p_c

    n1 = np.cross(b1, b2)
    n2 = np.cross(b2, b3)
    b2_norm = b2 / np.linalg.norm(b2, axis=1, keepdims=True)
    m1 = np.cross(n1, b2_norm)

    x = (n1 * n2).sum(axis=1)
    y = (m1 * n2).sum(axis=1)
    dihedrals = np.arctan2(y, x)
    if degrees:
        dihedrals = np.degrees(dihedrals)

    unit = "deg" if degrees else "rad"
    with open(output, "w") as f:
        f.write(f"time_ps,dihedral_{unit}\n")
        for t, val in zip(traj.time, dihedrals):
            f.write(f"{t},{val}\n")
    print(f"Wrote {output} ({traj.n_frames} frames)")
