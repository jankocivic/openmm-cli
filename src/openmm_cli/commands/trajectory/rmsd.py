"""Compute RMSD vs a reference structure over time."""

from pathlib import Path
from typing import Annotated

import typer


def command(
    trajectory: Annotated[Path, typer.Argument()],
    topology: Annotated[Path, typer.Option("--top")],
    output: Annotated[Path, typer.Option("--out")] = Path("rmsd.csv"),
    reference: Annotated[
        Path | None,
        typer.Option("--ref", help="Reference structure (default: first frame)."),
    ] = None,
    selection: Annotated[
        str, typer.Option("--sel", help="Atoms the RMSD is computed over.")
    ] = "name CA",
    fit_selection: Annotated[
        str | None,
        typer.Option(
            "--fit-sel",
            help="Atoms to align on (default: same as --sel). Use this for e.g. "
            "ligand RMSD after superposing on the protein.",
        ),
    ] = None,
    no_fit: Annotated[
        bool,
        typer.Option("--no-fit", help="Skip alignment; use coordinates as they are."),
    ] = False,
) -> None:
    """RMSD (nm) of each frame versus a reference."""
    import mdtraj as md
    import numpy as np

    if no_fit and fit_selection is not None:
        raise typer.BadParameter("--no-fit and --fit-sel are mutually exclusive")

    traj = md.load(str(trajectory), top=str(topology))
    ref = md.load(str(reference), top=str(topology)) if reference else traj[0]

    def select(expr: str) -> np.ndarray:
        idx = traj.topology.select(expr)
        if len(idx) == 0:
            raise typer.BadParameter(f"Selection {expr!r} matched no atoms")
        return idx

    atom_indices = select(selection)

    if not no_fit and fit_selection is None:
        # align and measure on the same atoms: mdtraj's fast path
        rmsd = md.rmsd(traj, ref, atom_indices=atom_indices)
    else:
        if not no_fit:
            traj.superpose(ref, atom_indices=select(fit_selection))
        diff = traj.xyz[:, atom_indices] - ref.xyz[0, atom_indices]
        rmsd = np.sqrt((diff**2).sum(axis=2).mean(axis=1))

    with open(output, "w") as f:
        f.write("frame,rmsd_nm\n")
        for i, r in enumerate(rmsd):
            f.write(f"{i},{r}\n")
    print(f"Wrote {output} ({traj.n_frames} frames)")
