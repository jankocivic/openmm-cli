"""Extract a subset of frames (start:stop:stride) from a trajectory."""

from pathlib import Path
from typing import Annotated

import typer


def command(
    trajectory: Annotated[Path, typer.Argument()],
    topology: Annotated[Path, typer.Option("--top")],
    output: Annotated[Path, typer.Option("--out")] = Path("extracted.dcd"),
    start: Annotated[int, typer.Option(help="First frame (0-indexed).")] = 0,
    stop: Annotated[
        int | None, typer.Option(help="Stop frame (exclusive). Default: end.")
    ] = None,
    stride: Annotated[int, typer.Option(help="Take every Nth frame.")] = 1,
) -> None:
    """Extract a frame range [start:stop:stride] from a trajectory."""
    import mdtraj as md
    import parmed

    traj = md.load(str(trajectory), top=str(topology))

    # Undo MDTraj's PDB-standard renaming (WAT->HOH, Na+->NA, HIE->HIS, ...)
    ref = parmed.load_file(str(topology))
    for res, ref_res in zip(traj.topology.residues, ref.residues, strict=True):
        res.name = ref_res.name
        for atom, ref_atom in zip(res.atoms, ref_res.atoms, strict=True):
            atom.name = ref_atom.name

    sliced = traj[start:stop:stride]
    sliced.save(str(output))
    print(f"Extracted {sliced.n_frames} of {traj.n_frames} frames; wrote {output}")
