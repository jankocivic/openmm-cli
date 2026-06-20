"""Molecular dynamics stage: integrate the current state for ``steps``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from ..units import Quantity
from . import SimulationStage, register_stage

if TYPE_CHECKING:
    from ..runner import Runner


@register_stage
class DynamicsStage(SimulationStage):
    type: Literal["dynamics"]
    steps: int
    randomize_velocities: Quantity | None = None

    def run(self, runner: "Runner") -> None:
        sim = runner.simulation
        if self.randomize_velocities is not None:
            sim.context.setVelocitiesToTemperature(self.randomize_velocities)
        self.add_reporters(runner, self.steps)
        print(f"  Running {self.steps} steps")
        sim.step(self.steps)
