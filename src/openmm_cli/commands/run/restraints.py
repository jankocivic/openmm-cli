"""Positional (and future) restraint forces.

Each restraint type is registered against the matching config model via
:func:`register_restraint`. To add a new restraint type, add a config model in
:mod:`.config` and register a force factory here -- no other code needs to
change.
"""

from __future__ import annotations

from typing import Callable

import mdtraj as md
import openmm as mm
from openmm import unit

from .config import PositionalRestraint

# A factory takes (restraint_config, openmm_topology, positions) -> Force.
RestraintFactory = Callable[[object, object, object], mm.Force]

_RESTRAINT_FACTORIES: dict[type, RestraintFactory] = {}


def register_restraint(config_type: type) -> Callable[[RestraintFactory], RestraintFactory]:
    """Register a force factory for a restraint config model."""

    def decorator(factory: RestraintFactory) -> RestraintFactory:
        _RESTRAINT_FACTORIES[config_type] = factory
        return factory

    return decorator


def _select_atoms(omm_topology, selection: str) -> list[int]:
    mdt_top = md.Topology.from_openmm(omm_topology)
    indices = mdt_top.select(selection)
    if len(indices) == 0:
        raise ValueError(f"Selection {selection!r} matched no atoms")
    return [int(i) for i in indices]


@register_restraint(PositionalRestraint)
def _make_positional_restraint_force(r: PositionalRestraint, omm_topology, positions):
    force = mm.CustomExternalForce("0.5*k*((x-x0)^2 + (y-y0)^2 + (z-z0)^2)")
    force.addGlobalParameter("k", r.force_constant)
    force.addPerParticleParameter("x0")
    force.addPerParticleParameter("y0")
    force.addPerParticleParameter("z0")

    for i in _select_atoms(omm_topology, r.selection):
        p = positions[i].value_in_unit(unit.nanometer)
        force.addParticle(i, [p[0], p[1], p[2]])
    return force


def _make_restraint_force(r, omm_topology, positions) -> mm.Force:
    factory = _RESTRAINT_FACTORIES.get(type(r))
    if factory is None:
        raise ValueError(f"Unsupported restraint type: {type(r).__name__}")
    return factory(r, omm_topology, positions)


def apply_restraints(
    simulation, system, omm_topology, restraints, prev_indices
) -> list[int]:
    """Replace the previously-added restraint forces with ``restraints``.

    Returns the force indices of the newly added restraints so the caller can
    remove them again before the next stage.
    """
    for idx in sorted(prev_indices, reverse=True):
        system.removeForce(idx)

    new_indices: list[int] = []
    if restraints:
        positions = simulation.context.getState(getPositions=True).getPositions()
        for r in restraints:
            force = _make_restraint_force(r, omm_topology, positions)
            new_indices.append(system.addForce(force))

    simulation.context.reinitialize(preserveState=True)
    return new_indices
