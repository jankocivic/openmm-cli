"""Extract a subset of frames (start:stop:stride) from a trajectory."""

from pathlib import Path
from typing import Annotated

import mdtraj as md
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
    traj = md.load(str(trajectory), top=str(topology))
    sliced = traj[start:stop:stride]
    sliced.save(str(output))
    print(f"Extracted {sliced.n_frames} of {traj.n_frames} frames; wrote {output}")
