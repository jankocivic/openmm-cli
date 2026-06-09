"""Identify hydrogen bonds present in a trajectory (Baker-Hubbard criterion)."""

from pathlib import Path
from typing import Annotated

import mdtraj as md
import numpy as np
import typer


def command(
    trajectory: Annotated[Path, typer.Argument()],
    topology: Annotated[Path, typer.Option("--top")],
    output: Annotated[Path, typer.Option("--out")] = Path("hbonds.csv"),
    freq: Annotated[
        float,
        typer.Option(
            help="Minimum fraction of frames an H-bond must be present (0-1)."
        ),
    ] = 0.1,
    selection: Annotated[
        str | None,
        typer.Option(
            "--sel",
            help="Restrict to H-bonds where both donor and acceptor are in this selection.",
        ),
    ] = None,
) -> None:
    """List hydrogen bonds present in at least `freq` of frames, with their per-bond occupancy."""
    traj = md.load(str(trajectory), top=str(topology))
    hbonds = md.baker_hubbard(traj, freq=freq, periodic=True)

    if selection is not None:
        sel = set(int(i) for i in traj.topology.select(selection))
        if not sel:
            raise typer.BadParameter(f"Selection {selection!r} matched no atoms")
        hbonds = np.array([hb for hb in hbonds if hb[0] in sel or hb[2] in sel])

    if len(hbonds) == 0:
        print("No hydrogen bonds matched the criteria.")
        with open(output, "w") as f:
            f.write("donor,hydrogen,acceptor,frequency\n")
        return

    # Per-frame presence using the same criteria baker_hubbard applies:
    # H-A distance < 0.25 nm and D-H-A angle > 120 deg.
    ha_distances = md.compute_distances(traj, hbonds[:, [1, 2]], periodic=True)
    dha_angles = md.compute_angles(traj, hbonds, periodic=True)
    present = (ha_distances < 0.25) & (dha_angles > np.radians(120))
    frequencies = present.mean(axis=0)

    # Sort by frequency, highest first
    order = np.argsort(-frequencies)

    with open(output, "w") as f:
        f.write("donor,hydrogen,acceptor,frequency\n")
        for i in order:
            d, h, a = hbonds[i]
            f.write(
                f"{traj.topology.atom(int(d))},"
                f"{traj.topology.atom(int(h))},"
                f"{traj.topology.atom(int(a))},"
                f"{frequencies[i]:.4f}\n"
            )

    print(
        f"Found {len(hbonds)} hydrogen bonds (>= {freq * 100:.0f}% occupancy); wrote {output}"
    )
