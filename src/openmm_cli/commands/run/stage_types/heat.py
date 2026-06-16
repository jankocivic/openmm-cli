"""Heating stage: ramp the thermostat temperature from start to target."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import openmm as mm

from ..config import Quantity
from ..reporters import Reporters, build_reporters
from ..restraints import Restraint, restrain
from . import StageBase, register_stage
from ._helpers import configure_barostat

if TYPE_CHECKING:
    from ..runner import Runner


def _ramp_temperature(simulation, start_T, end_T, steps, n_chunks=100):
    """Ramp the integrator temperature from ``start_T`` to ``end_T`` over ``steps``."""
    chunk = steps // n_chunks
    print(f"  Heating from {start_T} to {end_T} over {steps} steps")
    simulation.context.setVelocitiesToTemperature(start_T)
    for i in range(n_chunks):
        simulation.integrator.setTemperature(
            start_T + (end_T - start_T) * (i + 1) / n_chunks
        )
        simulation.step(chunk)
    leftover = steps - chunk * n_chunks
    if leftover:
        simulation.step(leftover)


@register_stage
class HeatStage(StageBase):
    type: Literal["heat"]
    steps: int
    start_temperature: Quantity
    temperature: Quantity  # target
    timestep: Quantity | None = None
    disable_barostat: bool = False
    n_chunks: int = 100  # ramp granularity
    restraints: list[Restraint] = []
    reporters: Reporters = Reporters()

    def run(self, runner: "Runner") -> None:
        sim = runner.simulation
        integrator = sim.integrator

        if self.timestep is not None:
            integrator.setStepSize(self.timestep)
        # Safe: config forbids a `temperature` (which heat always sets) under Verlet.
        integrator.setTemperature(self.start_temperature)

        configure_barostat(sim, runner.system, runner.cfg, self.disable_barostat)

        for reporter in build_reporters(self.reporters, self.steps, runner.output_dir):
            sim.reporters.append(reporter)

        with restrain(sim, runner.system, runner.topology, self.restraints):
            _ramp_temperature(
                sim, self.start_temperature, self.temperature, self.steps, self.n_chunks
            )

        state = sim.context.getState(getPositions=True, getVelocities=True)
        with open(runner.output_dir / f"{self.name}.xml", "w") as f:
            f.write(mm.XmlSerializer.serialize(state))
