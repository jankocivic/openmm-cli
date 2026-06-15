"""
Configuration models for the MD runner.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Literal

from openmm import unit
from pydantic import (
    BaseModel,
    ConfigDict,
    PlainSerializer,
    PlainValidator,
    SerializeAsAny,
    field_validator,
    model_validator,
)

# ---- Unit parsing -----------------------------------------------------------

_UNIT_TOKENS = {
    # time
    "fs": unit.femtoseconds,
    "ps": unit.picoseconds,
    "ns": unit.nanoseconds,
    # length
    "nm": unit.nanometers,
    "A": unit.angstrom,
    "angstrom": unit.angstrom,
    # mass
    "amu": unit.amu,
    "dalton": unit.dalton,
    # temperature
    "K": unit.kelvin,
    "kelvin": unit.kelvin,
    # pressure
    "atm": unit.atmospheres,
    "bar": unit.bar,
    # inverse time (e.g. Langevin friction)
    "/ps": unit.picoseconds**-1,
    # energy
    "kJ/mol": unit.kilojoules_per_mole,
    "kcal/mol": unit.kilocalories_per_mole,
    # force / force constants
    "kJ/mol/nm": unit.kilojoules_per_mole / unit.nanometer,
    "kJ/mol/nm^2": unit.kilojoules_per_mole / unit.nanometer**2,
    "kJ/mol/nm**2": unit.kilojoules_per_mole / unit.nanometer**2,
    "kcal/mol/A^2": unit.kilocalories_per_mole / unit.angstrom**2,
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


# Reverse of `_UNIT_TOKENS`, keyed by the unit's string form. The first token
# for each unit wins, so short symbols ("K", "A", "kJ/mol/nm^2") are preferred
# over their aliases.
_UNIT_TO_TOKEN: dict[str, str] = {}
for _token, _u in _UNIT_TOKENS.items():
    _UNIT_TO_TOKEN.setdefault(str(_u), _token)


def serialize_quantity(value: unit.Quantity) -> str:
    """Render a Quantity as a `parse_quantity`-readable 'NUMBER UNIT' string.

    Uses the canonical `_UNIT_TOKENS` spelling so a dumped config round-trips
    back through `parse_quantity`. Falls back to OpenMM's own representation for
    any unit not in the table (which would not re-parse, but should not occur
    for configured fields).
    """
    token = _UNIT_TO_TOKEN.get(str(value.unit))
    if token is None:
        return str(value)
    return f"{value.value_in_unit(value.unit)} {token}"


# A physical quantity field for Pydantic
Quantity = Annotated[
    unit.Quantity,
    PlainValidator(parse_quantity),
    PlainSerializer(serialize_quantity, return_type=str),
]


class _Base(BaseModel):
    """Shared base: reject unknown keys so typos in YAML fail loudly."""

    model_config = ConfigDict(extra="forbid")


# ---- System ----------------------------------------------------------------


class SystemSources(_Base):
    """What we're simulating.

    Supported combinations:
      - AMBER topology (.parm7/.prmtop) + coordinates (.inpcrd or .pdb), or restart_from
      - OpenMM PDB topology (.pdb) + forcefield XML list
    """

    topology: Path
    coordinates: Path | None = None
    restart_from: Path | None = None
    forcefield: list[str] | None = (
        None  # e.g. ["amber14-all.xml", "amber14/tip3pfb.xml"]
    )

    @model_validator(mode="after")
    def _validate_inputs(self):
        suffix = self.topology.suffix.lower()
        if suffix in (".parm7", ".prmtop"):
            if self.coordinates is None and self.restart_from is None:
                raise ValueError(
                    "AMBER topology requires `coordinates` or `restart_from`"
                )
        elif suffix == ".pdb":
            if self.forcefield is None:
                raise ValueError("PDB topology requires a `forcefield` list")
        else:
            raise ValueError(f"Unsupported topology format: {suffix}")
        return self


class SystemSettings(_Base):
    """How forces are computed -- args to prmtop.createSystem()."""

    nonbonded_method: Literal[
        "NoCutoff", "CutoffNonPeriodic", "CutoffPeriodic", "Ewald", "PME"
    ] = "PME"
    nonbonded_cutoff: Quantity = 1.0 * unit.nanometers
    constraints: Literal["HBonds", "AllBonds", "HAngles"] | None = "HBonds"
    rigid_water: bool = True
    hydrogen_mass: Quantity | None = None


# ---- Platform --------------------------------------------------------------


class PlatformConfig(_Base):
    name: Literal["CUDA", "OpenCL", "CPU", "Reference"] = "CPU"
    precision: Literal["single", "mixed", "double"] = "mixed"
    device_index: str | None = None  # e.g. "0" or "0,1"


# ---- Integrator / barostat -------------------------------------------------


class IntegratorConfig(_Base):
    type: Literal["LangevinMiddle", "Langevin", "Verlet"] = "LangevinMiddle"
    timestep: Quantity = 2 * unit.femtoseconds
    temperature: Quantity = 300 * unit.kelvin
    friction: Quantity = 1.0 / unit.picoseconds


class BarostatConfig(_Base):
    type: Literal["MonteCarloBarostat"] = "MonteCarloBarostat"
    pressure: Quantity = 1 * unit.atmospheres
    frequency: int = 25


class Defaults(_Base):
    """Settings applied to every dynamics stage unless overridden."""

    integrator: IntegratorConfig = IntegratorConfig()
    barostat: BarostatConfig | None = None


# ---- Stages ----------------------------------------------------------------

# The stage framework and the stage models both live in the `stage_types`
# package. Importing it here exposes `StageBase` (the field type) and triggers
# discovery, so every stage type is registered before a Config is validated.
# Placed after the shared models above, which the stage modules import.
from .stage_types import StageBase, get_stage_model  # noqa: E402


# ---- Root ------------------------------------------------------------------


class Config(_Base):
    system: SystemSources
    system_settings: SystemSettings = SystemSettings()
    platform: PlatformConfig = PlatformConfig()
    defaults: Defaults = Defaults()
    output_dir: Path = Path("output")
    # `SerializeAsAny` so the resolved-config dump keeps each concrete stage's
    # own fields rather than only those declared on StageBase.
    stages: list[SerializeAsAny[StageBase]]

    @field_validator("stages", mode="before")
    @classmethod
    def _dispatch_stages(cls, raw):
        """Build each entry into its registered stage model by its `type` tag."""
        if not isinstance(raw, list):
            raise ValueError("`stages` must be a list")
        built = []
        for i, item in enumerate(raw):
            if isinstance(item, StageBase):
                built.append(item)
            elif isinstance(item, dict):
                tag = item.get("type")
                if tag is None:
                    raise ValueError(f"stages[{i}] is missing a `type` field")
                built.append(get_stage_model(tag).model_validate(item))
            else:
                raise ValueError(
                    f"stages[{i}] must be a mapping with a `type` field"
                )
        return built
