"""Clean a PDB file: fix missing atoms, add hydrogens, optionally strip waters/heteroatoms."""

from pathlib import Path
from typing import Annotated

import typer


def command(
    pdb: Annotated[Path, typer.Argument(help="Input PDB file.")],
    output: Annotated[Path, typer.Option("--out", help="Output PDB file.")] = Path(
        "cleaned.pdb"
    ),
    ph: Annotated[
        float, typer.Option("--ph", help="pH used to assign protonation states.")
    ] = 7.4,
    keep_water: Annotated[
        bool,
        typer.Option(
            "--keep-water/--strip-water",
            help="Keep crystallographic water molecules (only applies when stripping heteroatoms).",
        ),
    ] = False,
    keep_heterogens: Annotated[
        bool,
        typer.Option(
            "--keep-hetero/--strip-hetero",
            help="Keep ligands, cofactors, and ions. Off by default for protein-only output.",
        ),
    ] = False,
    add_missing_residues: Annotated[
        bool,
        typer.Option(
            "--add-residues/--no-add-residues",
            help="Build in missing residues (gaps/loops). Off by default to avoid silent insertions.",
        ),
    ] = False,
    replace_nonstandard: Annotated[
        bool,
        typer.Option(
            "--replace-nonstandard/--keep-nonstandard",
            help="Replace nonstandard residues (e.g. MSE -> MET) with their standard equivalents.",
        ),
    ] = True,
) -> None:
    """Clean a PDB file with pdbfixer: fix structure, add hydrogens, optionally strip extras."""
    from openmm.app import PDBFile
    from pdbfixer import PDBFixer

    print(f"Loading {pdb}")
    fixer = PDBFixer(filename=str(pdb))

    # Missing residues
    if add_missing_residues:
        fixer.findMissingResidues()
    else:
        fixer.missingResidues = {}

    # Nonstandard residue replacement
    if replace_nonstandard:
        fixer.findNonstandardResidues()
        if fixer.nonstandardResidues:
            print(f"Replacing {len(fixer.nonstandardResidues)} nonstandard residue(s)")
        fixer.replaceNonstandardResidues()

    # Heteroatoms (ligands, ions, water)
    if not keep_heterogens:
        fixer.removeHeterogens(keepWater=keep_water)

    # Missing atoms (side chains, etc.)
    fixer.findMissingAtoms()
    if fixer.missingAtoms:
        print(f"Adding missing atoms in {len(fixer.missingAtoms)} residue(s)")
    fixer.addMissingAtoms()

    # Hydrogens
    fixer.addMissingHydrogens(pH=ph)

    with open(output, "w") as f:
        PDBFile.writeFile(fixer.topology, fixer.positions, f)

    n_atoms = sum(1 for _ in fixer.topology.atoms())
    n_residues = sum(1 for _ in fixer.topology.residues())
    print(f"Wrote {output} ({n_atoms} atoms, {n_residues} residues, pH {ph})")
