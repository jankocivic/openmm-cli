"""Add a water box and counterions to a structure using pdbfixer."""

from pathlib import Path
from typing import Annotated, Literal

import typer


def command(
    pdb: Annotated[
        Path, typer.Argument(help="Input PDB file (typically already cleaned).")
    ],
    output: Annotated[
        Path, typer.Option("--out", help="Output solvated PDB file.")
    ] = Path("solvated.pdb"),
    padding: Annotated[
        float,
        typer.Option(
            "--padding", help="Minimum distance (nm) from solute to box edge."
        ),
    ] = 1.0,
    box_shape: Annotated[
        Literal["cube", "dodecahedron", "octahedron"],
        typer.Option("--box-shape", help="Shape of the periodic box."),
    ] = "cube",
    ionic_strength: Annotated[
        float,
        typer.Option(
            "--ionic-strength", help="Ionic strength in mol/L (physiological ~0.15)."
        ),
    ] = 0.15,
    positive_ion: Annotated[
        str,
        typer.Option("--positive-ion", help="Cation species (Na+, K+, Li+, Rb+, Cs+)."),
    ] = "Na+",
    negative_ion: Annotated[
        str, typer.Option("--negative-ion", help="Anion species (Cl-, Br-, F-, I-).")
    ] = "Cl-",
) -> None:
    """Add a water box and counterions to bring the system to the target ionic strength."""
    from openmm import unit
    from openmm.app import PDBFile
    from pdbfixer import PDBFixer

    print(f"Loading {pdb}")
    fixer = PDBFixer(filename=str(pdb))

    n_before = sum(1 for _ in fixer.topology.atoms())

    fixer.addSolvent(
        padding=padding * unit.nanometer,
        boxShape=box_shape,
        positiveIon=positive_ion,
        negativeIon=negative_ion,
        ionicStrength=ionic_strength * unit.molar,
    )

    n_after = sum(1 for _ in fixer.topology.atoms())
    n_waters = sum(1 for r in fixer.topology.residues() if r.name == "HOH")
    pos = positive_ion.rstrip("+").upper()   
    neg = negative_ion.rstrip("-").upper()    
    n_pos = sum(1 for r in fixer.topology.residues() if r.name.upper() == pos)
    n_neg = sum(1 for r in fixer.topology.residues() if r.name.upper() == neg)

    with open(output, "w") as f:
        PDBFile.writeFile(fixer.topology, fixer.positions, f)

    print(
        f"Added {n_waters} waters, {n_pos} {positive_ion}, {n_neg} {negative_ion} "
        f"({n_after - n_before} atoms total); wrote {output}"
    )
