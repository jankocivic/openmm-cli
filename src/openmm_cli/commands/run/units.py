"""Physical-quantity parsing for config models.

Bridges YAML text and ``openmm.unit.Quantity``: configs are written as
``"NUMBER UNIT"`` strings (e.g. ``"300 K"``, ``"2 fs"``), which :data:`Quantity`
parses into real OpenMM quantities and serializes back into the same readable
form so a dumped config round-trips. The runtime values are genuine
``openmm.unit.Quantity`` objects; only the text<->object bridge lives here.
"""

from __future__ import annotations

import re
from typing import Annotated

from openmm import unit
from pydantic import PlainSerializer, PlainValidator

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
    # surface tension (pressure * length, e.g. membrane barostat)
    "bar*nm": unit.bar * unit.nanometer,
    # inverse time (e.g. Langevin friction)
    "/ps": unit.picoseconds**-1,
    # energy
    "kJ/mol": unit.kilojoules_per_mole,
    "kcal/mol": unit.kilocalories_per_mole,
    # force / force constants
    "kJ/mol/nm": unit.kilojoules_per_mole / unit.nanometer,
    "kcal/mol/A": unit.kilocalories_per_mole / unit.angstrom,
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
