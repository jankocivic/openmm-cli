"""Barostat config models and construction.

Each barostat type is a :class:`BarostatBase` subclass that carries its own
config *and* builds its OpenMM force via ``build(temperature)``. To add a type:
define a subclass with a unique ``type: Literal[...]`` and a ``build()``, and add
it to the :data:`Barostat` union below.
"""

from __future__ import annotations

from typing import Annotated, Literal

import openmm as mm
from openmm import Vec3, unit
from pydantic import BaseModel, ConfigDict, Field

from .config import Quantity


class BarostatBase(BaseModel):
    """Base class for every barostat type."""

    model_config = ConfigDict(extra="forbid")

    frequency: int = 25

    def build(self, temperature) -> mm.Force:
        """Build the OpenMM barostat force coupled at ``temperature``."""
        raise NotImplementedError


class IsotropicBarostat(BarostatBase):
    type: Literal["isotropic"]
    pressure: Quantity = 1 * unit.atmospheres

    def build(self, temperature) -> mm.Force:
        return mm.MonteCarloBarostat(self.pressure, temperature, self.frequency)


class AnisotropicBarostat(BarostatBase):
    type: Literal["anisotropic"]
    pressure: tuple[Quantity, Quantity, Quantity]
    scale_x: bool = True
    scale_y: bool = True
    scale_z: bool = True

    def build(self, temperature) -> mm.Force:
        px, py, pz = (p.value_in_unit(unit.bar) for p in self.pressure)
        pressure = unit.Quantity(Vec3(px, py, pz), unit.bar)
        return mm.MonteCarloAnisotropicBarostat(
            pressure,
            temperature,
            self.scale_x,
            self.scale_y,
            self.scale_z,
            self.frequency,
        )


class MembraneBarostat(BarostatBase):
    type: Literal["membrane"]
    pressure: Quantity = 1 * unit.atmospheres
    surface_tension: Quantity = 0.0 * unit.bar * unit.nanometer
    xy_mode: Literal["isotropic", "anisotropic"] = "isotropic"
    z_mode: Literal["free", "fixed", "constant_volume"] = "free"

    def build(self, temperature) -> mm.Force:
        xy = {
            "isotropic": mm.MonteCarloMembraneBarostat.XYIsotropic,
            "anisotropic": mm.MonteCarloMembraneBarostat.XYAnisotropic,
        }[self.xy_mode]
        z = {
            "free": mm.MonteCarloMembraneBarostat.ZFree,
            "fixed": mm.MonteCarloMembraneBarostat.ZFixed,
            "constant_volume": mm.MonteCarloMembraneBarostat.ConstantVolume,
        }[self.z_mode]
        return mm.MonteCarloMembraneBarostat(
            self.pressure, self.surface_tension, temperature, xy, z, self.frequency
        )


# Add new barostat types to this union.
Barostat = Annotated[
    IsotropicBarostat | AnisotropicBarostat | MembraneBarostat,
    Field(discriminator="type"),
]
