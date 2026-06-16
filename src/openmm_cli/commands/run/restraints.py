"""Restraint force definitions.

All restraint types live here. Each is a :class:`RestraintBase` subclass that
carries its own config *and* builds its OpenMM force via ``build()``. To add a
restraint type:

  1. define a ``RestraintBase`` subclass with a unique ``type: Literal[...]``
     and a ``build()`` method, and
  2. add it to the :data:`Restraint` union below.

Restraints are added to a stage's freshly-built system at construction time (see
``system.build_simulation``) and discarded with it, so there is no add/remove
bookkeeping here -- just the force factories.
"""

from __future__ import annotations

from typing import Literal

import mdtraj as md
import openmm as mm
from openmm import unit
from pydantic import BaseModel, ConfigDict

from .config import Quantity


class RestraintBase(BaseModel):
    """Base class for every restraint type."""

    # Reject unknown keys so typos in a restraint's YAML fail loudly.
    model_config = ConfigDict(extra="forbid")

    def build(self, topology, positions) -> mm.Force:
        """Build the OpenMM force for this restraint. Override this."""
        raise NotImplementedError


def _select_atoms(topology, selection: str) -> list[int]:
    indices = md.Topology.from_openmm(topology).select(selection)
    if len(indices) == 0:
        raise ValueError(f"Selection {selection!r} matched no atoms")
    return [int(i) for i in indices]


class PositionalRestraint(RestraintBase):
    type: Literal["positional"] = "positional"
    selection: str  # mdtraj-style, e.g. "not water and not element H"
    force_constant: Quantity

    def build(self, topology, positions) -> mm.Force:
        force = mm.CustomExternalForce("0.5*k*((x-x0)^2 + (y-y0)^2 + (z-z0)^2)")
        force.addGlobalParameter("k", self.force_constant)
        force.addPerParticleParameter("x0")
        force.addPerParticleParameter("y0")
        force.addPerParticleParameter("z0")
        for i in _select_atoms(topology, self.selection):
            p = positions[i].value_in_unit(unit.nanometer)
            force.addParticle(i, [p[0], p[1], p[2]])
        return force


# All restraint types. When adding a second, make this a discriminated union:
#   from typing import Annotated
#   from pydantic import Field
#   Restraint = Annotated[
#       PositionalRestraint | FlatBottomRestraint, Field(discriminator="type")
#   ]
Restraint = PositionalRestraint
