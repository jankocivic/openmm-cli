"""Remove atoms from a trajectory; write a smaller trajectory and topology."""
from pathlib import Path
from typing import Annotated

import mdtraj as md
import typer


def command(
    trajectory: Annotated[Path, typer.Argument()],
    topology: Annotated[Path, typer.Option("--top")],
    output: Annotated[Path, typer.Option("--out")] = Path("stripped.dcd"),
    keep: Annotated[str, typer.Option("--keep",
        help="Atoms to keep (mdtraj selection).")] = "not water",
    topology_out: Annotated[Path, typer.Option("--top-out",
        help="Where to write the stripped topology (PDB).")] = Path("stripped.pdb"),
) -> None:
    """Keep only the selected atoms; write a stripped trajectory and matching topology."""
    traj = md.load(str(trajectory), top=str(topology))
    indices = traj.topology.select(keep)
    if len(indices) == 0:
        raise typer.BadParameter(f"Selection {keep!r} matched no atoms")

    stripped = traj.atom_slice(indices)
    stripped.save(str(output))
    stripped[0].save(str(topology_out))
    print(f"Kept {len(indices)} of {traj.n_atoms} atoms; "
          f"wrote {output} and {topology_out}")
