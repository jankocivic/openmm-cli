"""Molecular dynamics stage: integrate the current state for ``steps``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from ..config import Quantity
from ..reporters import build_reporters
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
        for reporter in build_reporters(self.reporters, self.steps, runner.output_dir):
            sim.reporters.append(reporter)
        print(f"  Running {self.steps} steps")
        sim.step(self.steps)
