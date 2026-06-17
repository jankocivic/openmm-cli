"""Atom-selection helpers shared across stages and reporters.

A single place to turn an mdtraj-style selection string (e.g. ``"protein"`` or
``"not water and not element H"``) into a list of atom indices against an OpenMM
topology, so restraints, RAMD, and trajectory reporters resolve selections the
same way and emit consistent errors.
"""

from __future__ import annotations

import mdtraj as md


def select_atoms(topology, selection: str, label: str = "Selection") -> list[int]:
    """Resolve an mdtraj selection string to atom indices.

    Raises ``ValueError`` if the selection matches no atoms. ``label`` prefixes
    that error so callers can say e.g. "RAMD selection ... matched no atoms".
    """
    indices = md.Topology.from_openmm(topology).select(selection)
    if len(indices) == 0:
        raise ValueError(f"{label} {selection!r} matched no atoms")
    return [int(i) for i in indices]
