"""Print a summary of a trajectory: frames, atoms, box."""

from pathlib import Path
from typing import Annotated

import mdtraj as md
import typer


def command(
    trajectory: Annotated[Path, typer.Argument()],
    topology: Annotated[Path, typer.Option("--top")],
) -> None:
    """Print frames, atoms, residues, chains, and box information."""
    traj = md.load(str(trajectory), top=str(topology))
    top = traj.topology

    print(f"Trajectory: {trajectory}")
    print(f"Topology:   {topology}")
    print(f"Frames:     {traj.n_frames}")

    print(f"Atoms:      {traj.n_atoms}")
    print(f"Residues:   {top.n_residues}")
    print(f"Chains:     {top.n_chains}")

    if traj.unitcell_lengths is not None:
        a, b, c = traj.unitcell_lengths[0]
        print(f"Box:        {a:.3f} x {b:.3f} x {c:.3f} nm")
    else:
        print("Box:        none (non-periodic)")
