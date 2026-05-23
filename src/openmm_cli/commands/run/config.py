"""
Configuration models for the MD runner.

The single non-obvious bit is unit handling: YAML strings like "4 fs",
"1.0 nm", "1000 kJ/mol/nm^2" are parsed into openmm.unit.Quantity at
validation time. That way unit errors surface when the config is loaded,
not when OpenMM finally complains five function calls deep.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Literal, Optional, Union

from openmm import unit
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---- Unit parsing -----------------------------------------------------------

_UNIT_TOKENS = {
    # time
    "fs": unit.femtoseconds, "ps": unit.picoseconds, "ns": unit.nanoseconds,
    # length
    "nm": unit.nanometers, "A": unit.angstrom, "angstrom": unit.angstrom,
    # mass
    "amu": unit.amu, "dalton": unit.dalton,
    # temperature
    "K": unit.kelvin, "kelvin": unit.kelvin,
    # pressure
    "atm": unit.atmospheres, "bar": unit.bar,
    # inverse time (e.g. Langevin friction)
    "/ps": unit.picoseconds ** -1,
    # energy
    "kJ/mol": unit.kilojoules_per_mole,
    "kcal/mol": unit.kilocalories_per_mole,
    # force / force constants
    "kJ/mol/nm": unit.kilojoules_per_mole / unit.nanometer,
    "kJ/mol/nm^2": unit.kilojoules_per_mole / unit.nanometer ** 2,
    "kJ/mol/nm**2": unit.kilojoules_per_mole / unit.nanometer ** 2,
    "kcal/mol/A^2": unit.kilocalories_per_mole / unit.angstrom ** 2,
}

_QUANTITY_RE = re.compile(r"^([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+(.+)$")


def parse_quantity(value) -> unit.Quantity:
    """Convert 'NUMBER UNIT' strings into openmm.unit.Quantity."""
    if isinstance(value, unit.Quantity):
        return value
    if isinstance(value, (int, float)):
        raise ValueError(
            f"Bare number {value!r} given where a quantity with units is required "
            f"(e.g. '300 K', '1.0 nm')"
        )
    s = str(value).strip()
    m = _QUANTITY_RE.match(s)
    if not m:
        raise ValueError(
            f"Cannot parse quantity {value!r}; expected 'NUMBER UNIT' (e.g. '4 fs')"
        )
    number = float(m.group(1))
    unit_str = m.group(2).strip()
    if unit_str not in _UNIT_TOKENS:
        raise ValueError(
            f"Unknown unit {unit_str!r} in {value!r}. "
            f"Known units: {sorted(_UNIT_TOKENS)}"
        )
    return number * _UNIT_TOKENS[unit_str]


def _q(v):
    """Field validator helper."""
    return None if v is None else parse_quantity(v)


# ---- System ----------------------------------------------------------------

class SystemSources(BaseModel):
    """What we're simulating. Both AMBER files."""
    topology: Path
    coordinates: Path


class SystemSettings(BaseModel):
    """How forces are computed -- args to prmtop.createSystem()."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    nonbonded_method: Literal[
        "NoCutoff", "CutoffNonPeriodic", "CutoffPeriodic", "Ewald", "PME"
    ] = "PME"
    nonbonded_cutoff: unit.Quantity = "1.0 nm"
    constraints: Optional[Literal["HBonds", "AllBonds", "HAngles"]] = "HBonds"
    rigid_water: bool = True
    hydrogen_mass: Optional[unit.Quantity] = None

    _v = field_validator("nonbonded_cutoff", "hydrogen_mass", mode="before")(_q)


# ---- Platform --------------------------------------------------------------

class PlatformConfig(BaseModel):
    name: Literal["CUDA", "OpenCL", "CPU", "Reference"] = "CUDA"
    precision: Literal["single", "mixed", "double"] = "mixed"
    device_index: Optional[str] = None  # e.g. "0" or "0,1"


# ---- Integrator / barostat -------------------------------------------------

class IntegratorConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    type: Literal["LangevinMiddle", "Langevin", "Verlet"] = "LangevinMiddle"
    timestep: unit.Quantity = "2 fs"
    temperature: unit.Quantity = "300 K"
    friction: unit.Quantity = "1.0 /ps"

    _v = field_validator("timestep", "temperature", "friction", mode="before")(_q)


class BarostatConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    type: Literal["MonteCarloBarostat"] = "MonteCarloBarostat"
    pressure: unit.Quantity = "1 atm"
    frequency: int = 25

    _v = field_validator("pressure", mode="before")(_q)


class Defaults(BaseModel):
    """Settings applied to every dynamics stage unless overridden."""
    integrator: IntegratorConfig = IntegratorConfig()
    barostat: Optional[BarostatConfig] = None


# ---- Restraints ------------------------------------------------------------

class PositionalRestraint(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    type: Literal["positional"] = "positional"
    selection: str  # mdtraj-style, e.g. "not water and not element H"
    force_constant: unit.Quantity

    _v = field_validator("force_constant", mode="before")(_q)


# ---- Reporters -------------------------------------------------------------

class ReporterFile(BaseModel):
    file: Path
    interval: int


class Reporters(BaseModel):
    trajectory: Optional[ReporterFile] = None   # DCD
    state: Optional[ReporterFile] = None        # CSV state data
    checkpoint: Optional[ReporterFile] = None   # binary checkpoint


# ---- Stages ----------------------------------------------------------------

class MinimizationStage(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    type: Literal["minimization"]
    max_iterations: int = 0  # 0 = until convergence
    tolerance: unit.Quantity = "10 kJ/mol/nm"

    _v = field_validator("tolerance", mode="before")(_q)


class DynamicsStage(BaseModel):
    name: str
    type: Literal["dynamics"]
    steps: int

    # Per-stage overrides. None means "use default".
    integrator: Optional[IntegratorConfig] = None
    barostat: Optional[BarostatConfig] = None

    # Explicitly turn off the barostat for this stage (e.g. NVT after NPT default).
    disable_barostat: bool = False

    # Re-draw velocities from the Maxwell-Boltzmann distribution at stage start.
    # Set true for the first dynamics stage after minimization.
    initialize_velocities: bool = False

    restraints: list[PositionalRestraint] = []
    reporters: Reporters = Reporters()


Stage = Annotated[
    Union[MinimizationStage, DynamicsStage],
    Field(discriminator="type"),
]


# ---- Root ------------------------------------------------------------------

class Config(BaseModel):
    system: SystemSources
    system_settings: SystemSettings = SystemSettings()
    platform: PlatformConfig = PlatformConfig()
    defaults: Defaults = Defaults()
    output_dir: Path = Path("output")
    stages: list[Stage]


