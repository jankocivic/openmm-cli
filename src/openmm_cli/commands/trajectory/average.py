"""Compute the average structure of a trajectory."""

from pathlib import Path
from typing import Annotated

import typer


def command(
    trajectory: Annotated[Path, typer.Argument(help="Input trajectory.")],
    topology: Annotated[Path, typer.Option("--top", help="Topology file.")],
    selection: Annotated[
        str, typer.Option("--sel", help="Atoms to superpose on before averaging.")
    ] = "name CA",
    output: Annotated[
        Path, typer.Option("--out", help="Output structure file (format by extension).")
    ] = Path("average.pdb"),
    iterations: Annotated[
        int,
        typer.Option("--iterations", help="Re-superpose onto the running average N times."),
    ] = 2,
) -> None:
    """Average a trajectory's coordinates into a single structure."""
    import mdtraj as md

    traj = md.load(str(trajectory), top=str(topology))
    atom_indices = traj.topology.select(selection)
    if len(atom_indices) == 0:
        raise typer.BadParameter(f"Selection {selection!r} matched no atoms")

    reference = traj[0]
    for _ in range(max(1, iterations)):
        traj.superpose(reference, atom_indices=atom_indices)
        avg_xyz = traj.xyz.mean(axis=0, keepdims=True)   # (1, n_atoms, 3)
        reference = md.Trajectory(avg_xyz, traj.topology)

    reference.save(str(output))
    typer.echo(f"Averaged {traj.n_frames} frames -> {output}")
