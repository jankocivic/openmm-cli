"""Serialization of simulation state to/from disk."""

from __future__ import annotations

from pathlib import Path

import openmm as mm


def save_state(simulation, path: Path) -> None:
    """Write the full simulation state (positions, velocities, box) as XML."""
    state = simulation.context.getState(
        getPositions=True,
        getVelocities=True,
        getEnergy=True,
        enforcePeriodicBox=True,
    )
    with open(path, "w") as f:
        f.write(mm.XmlSerializer.serialize(state))


def load_state(simulation, path: Path) -> None:
    """Restore a simulation state previously written by :func:`save_state`."""
    with open(path) as f:
        state = mm.XmlSerializer.deserialize(f.read())
    simulation.context.setState(state)
