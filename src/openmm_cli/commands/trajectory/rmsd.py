"""Compute RMSD vs a reference structure over time."""
from pathlib import Path
from typing import Annotated, Optional

import mdtraj as md
import typer


def command(
    trajectory: Annotated[Path, typer.Argument()],
    topology: Annotated[Path, typer.Option("--top")],
    output: Annotated[Path, typer.Option("--out")] = Path("rmsd.csv"),
    reference: Annotated[Optional[Path], typer.Option("--ref",
        help="Reference structure (default: first frame).")] = None,
    selection: Annotated[str, typer.Option("--sel",
        help="Atoms for the fit and RMSD calculation.")] = "name CA",
) -> None:
    """RMSD (nm) of each frame versus a reference, after optimal alignment."""
    traj = md.load(str(trajectory), top=str(topology))
    ref = md.load(str(reference), top=str(topology)) if reference else traj[0]

    atom_indices = traj.topology.select(selection)
    if len(atom_indices) == 0:
        raise typer.BadParameter(f"Selection {selection!r} matched no atoms")

    rmsd = md.rmsd(traj, ref, atom_indices=atom_indices)

    with open(output, "w") as f:
        f.write("frame,rmsd_nm\n")
        for i, r in enumerate(rmsd):
            f.write(f"{i},{r}\n")
    print(f"Wrote {output} ({traj.n_frames} frames)")
