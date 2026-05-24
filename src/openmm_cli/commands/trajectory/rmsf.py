"""Compute per-atom root-mean-square fluctuations (RMSF)."""
from pathlib import Path
from typing import Annotated

import mdtraj as md
import numpy as np
import typer


def command(
    trajectory: Annotated[Path, typer.Argument()],
    topology: Annotated[Path, typer.Option("--top")],
    output: Annotated[Path, typer.Option("--out")] = Path("rmsf.csv"),
    selection: Annotated[str, typer.Option("--sel")] = "name CA",
    align: Annotated[bool, typer.Option("--align/--no-align",
        help="RMSD-fit trajectory to frame 0 before computing RMSF.")] = True,
) -> None:
    """Per-atom RMSF (nm) of the selected atoms over the trajectory."""
    traj = md.load(str(trajectory), top=str(topology))
    atom_indices = traj.topology.select(selection)
    if len(atom_indices) == 0:
        raise typer.BadParameter(f"Selection {selection!r} matched no atoms")

    if align:
        traj.superpose(traj, frame=0, atom_indices=atom_indices)

    # RMSF = sqrt(mean over frames of squared deviation from mean position)
    positions = traj.xyz[:, atom_indices, :]                  # (frames, atoms, 3)
    mean_pos = positions.mean(axis=0)                         # (atoms, 3)
    rmsf = np.sqrt(((positions - mean_pos) ** 2).sum(axis=2).mean(axis=0))

    with open(output, "w") as f:
        f.write("atom_index,residue,atom_name,rmsf_nm\n")
        for i, val in zip(atom_indices, rmsf):
            atom = traj.topology.atom(int(i))
            f.write(f"{int(i)},{atom.residue},{atom.name},{val}\n")
    print(f"Wrote {output} ({len(atom_indices)} atoms)")
