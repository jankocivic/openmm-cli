"""Translate frames so a selection sits at the box center (or origin), optionally imaging molecules."""
from pathlib import Path
from typing import Annotated, Literal

import mdtraj as md
import typer


def command(
    trajectory: Annotated[Path, typer.Argument()],
    topology: Annotated[Path, typer.Option("--top")],
    output: Annotated[Path, typer.Option("--out")] = Path("centered.dcd"),
    selection: Annotated[str, typer.Option("--sel",
        help="Selection whose center of mass should be moved.")] = "protein",
    target: Annotated[Literal["box", "origin"], typer.Option("--target",
        help="Where to place the COM.")] = "box",
    image: Annotated[bool, typer.Option("--image/--no-image",
        help="Image molecules into the unit cell after centering.")] = True,
) -> None:
    """Translate each frame so the selection's COM sits at the target, then by default image molecules."""
    traj = md.load(str(trajectory), top=str(topology))

    idx = traj.topology.select(selection)
    if len(idx) == 0:
        raise typer.BadParameter(f"Selection {selection!r} matched no atoms")

    com = md.compute_center_of_mass(traj.atom_slice(idx))  # (n_frames, 3)

    if target == "box":
        if traj.unitcell_vectors is None:
            raise typer.BadParameter("No periodic box; use --target origin instead.")
        box_center = traj.unitcell_vectors.sum(axis=1) / 2.0
        shift = box_center - com
    else:
        shift = -com

    traj.xyz += shift[:, None, :]

    if image:
        if traj.unitcell_vectors is None:
            print("Warning: no periodic box; skipping imaging.")
        else:
            traj.image_molecules(inplace=True)

    traj.save(str(output))
    print(f"Centered {traj.n_frames} frames on '{selection}' at {target}"
          f"{' + imaged' if image and traj.unitcell_vectors is not None else ''}; wrote {output}")
