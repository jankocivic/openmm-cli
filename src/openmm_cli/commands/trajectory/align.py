"""Align trajectory frames to a reference structure by RMSD fit."""

from pathlib import Path
from typing import Annotated

import mdtraj as md
import typer


def command(
    trajectory: Annotated[Path, typer.Argument(help="Input trajectory file.")],
    topology: Annotated[
        Path, typer.Option("--top", help="Topology file (parm7, pdb, ...).")
    ],
    output: Annotated[Path, typer.Option("--out", help="Output trajectory.")] = Path(
        "aligned.dcd"
    ),
    reference: Annotated[
        Path | None,
        typer.Option(
            "--ref", help="Reference structure (default: first frame of trajectory)."
        ),
    ] = None,
    selection: Annotated[
        str,
        typer.Option(
            "--sel", help="Atoms to use for the fit (mdtraj selection syntax)."
        ),
    ] = "name CA",
) -> None:
    """Align each frame to a reference by RMSD fit on the selected atoms."""
    traj = md.load(str(trajectory), top=str(topology))
    ref = md.load(str(reference), top=str(topology)) if reference else traj[0]

    atom_indices = traj.topology.select(selection)
    if len(atom_indices) == 0:
        raise typer.BadParameter(f"Selection {selection!r} matched no atoms")

    traj.superpose(ref, atom_indices=atom_indices)
    traj.save(str(output))
    print(
        f"Aligned {traj.n_frames} frames on {len(atom_indices)} atoms; wrote {output}"
    )
