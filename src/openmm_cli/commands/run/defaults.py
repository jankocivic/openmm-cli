"""Run-wide simulation-construction defaults and their merging.

The integrator / platform / barostat a stage builds its simulation from.
``Defaults`` bundles them; ``merge_defaults`` applies a stage's partial override
onto the run-wide defaults. (The system-build settings live with the sources --
see ``sources.SystemSettings``.)
"""

from __future__ import annotations

from typing import Literal

import openmm as mm
from openmm import unit
from pydantic import BaseModel

from .barostats import Barostat
from .base import _Base
from .units import Quantity


class PlatformConfig(_Base):
    name: Literal["CUDA", "OpenCL", "CPU", "Reference"] = "CPU"
    precision: Literal["single", "mixed", "double"] = "mixed"
    device_index: str | None = None  # e.g. "0" or "0,1"

    def build(self) -> tuple[mm.Platform, dict[str, str]]:
        """Return the platform and its property dict for ``Simulation``."""
        plat = mm.Platform.getPlatformByName(self.name)
        props: dict[str, str] = {}
        if self.name in ("CUDA", "OpenCL"):
            # CUDA and OpenCL both use the bare property names "Precision" and
            # "DeviceIndex" (not a platform-prefixed form).
            props["Precision"] = self.precision
            if self.device_index is not None:
                props["DeviceIndex"] = self.device_index
        return plat, props


# Integrator type -> factory from an IntegratorConfig.
_INTEGRATORS = {
    "LangevinMiddle": lambda c: mm.LangevinMiddleIntegrator(
        c.temperature, c.friction, c.timestep
    ),
    "Langevin": lambda c: mm.LangevinIntegrator(
        c.temperature, c.friction, c.timestep
    ),
    "Verlet": lambda c: mm.VerletIntegrator(c.timestep),
}


class IntegratorConfig(_Base):
    type: Literal["LangevinMiddle", "Langevin", "Verlet"] = "LangevinMiddle"
    timestep: Quantity = 2 * unit.femtoseconds
    temperature: Quantity = 300 * unit.kelvin
    friction: Quantity = 1.0 / unit.picoseconds

    def build(self) -> mm.Integrator:
        """Construct the integrator named by ``type``."""
        try:
            factory = _INTEGRATORS[self.type]
        except KeyError:
            raise ValueError(f"Unknown integrator type: {self.type}")
        return factory(self)


class Defaults(_Base):
    """Run-wide simulation-construction settings.

    Each stage builds a fresh simulation from these, and may override any of them
    with its own partial ``defaults`` block (see :func:`merge_defaults`).
    """

    integrator: IntegratorConfig = IntegratorConfig()
    barostat: Barostat | None = None
    platform: PlatformConfig = PlatformConfig()


def _set_fields(model: BaseModel) -> dict:
    """The fields the caller explicitly set on ``model`` (for partial merges)."""
    return {name: getattr(model, name) for name in model.model_fields_set}


def merge_defaults(base: Defaults, override: Defaults | None) -> Defaults:
    """Merge a stage's partial ``defaults`` override onto the run defaults.

    Integrator and platform merge field-wise (explicitly-set fields win, the rest
    inherit), so "change just the temperature/precision" works. The barostat is
    whole-replaced -- it is a discriminated union, so a cross-type field merge is
    meaningless; an explicit ``barostat: null`` turns it off for the stage, while
    omitting it inherits.
    """
    if override is None:
        return base
    update: dict = {}
    if "integrator" in override.model_fields_set:
        update["integrator"] = base.integrator.model_copy(
            update=_set_fields(override.integrator)
        )
    if "platform" in override.model_fields_set:
        update["platform"] = base.platform.model_copy(
            update=_set_fields(override.platform)
        )
    if "barostat" in override.model_fields_set:
        update["barostat"] = override.barostat
    return base.model_copy(update=update)
