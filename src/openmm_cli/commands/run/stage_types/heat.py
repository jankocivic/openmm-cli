"""Heating stage: ramp the thermostat temperature from start to target."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from ..units import Quantity
from . import SimulationStage, register_stage

if TYPE_CHECKING:
    from ..defaults import Defaults
    from ..runner import Runner
    from ..sources import SystemSettings


def _ramp_temperature(simulation, start_T, end_T, steps, n_chunks=100):
    """Ramp the integrator temperature from ``start_T`` to ``end_T`` over ``steps``."""
    chunk = steps // n_chunks
    print(f"  Ramping temperature {start_T} -> {end_T} over {steps} steps")
    for i in range(n_chunks):
        simulation.integrator.setTemperature(
            start_T + (end_T - start_T) * (i + 1) / n_chunks
        )
        simulation.step(chunk)
    leftover = steps - chunk * n_chunks
    if leftover:
        simulation.step(leftover)


@register_stage
class HeatStage(SimulationStage):
    type: Literal["heat"]
    steps: int
    start_temperature: Quantity
    temperature: Quantity  # ramp target
    n_chunks: int = 100  # ramp granularity

    def validate_resolved(
        self, defaults: "Defaults", system_settings: "SystemSettings"
    ) -> None:
        super().validate_resolved(defaults, system_settings)
        if defaults.integrator.type == "Verlet":
            raise ValueError(
                f"Stage {self.name!r}: heating requires a thermostatted "
                "integrator, but the resolved integrator is Verlet (NVE)."
            )

    def run(self, runner: "Runner") -> None:
        sim = runner.simulation
        sim.integrator.setTemperature(self.start_temperature)
        self.add_reporters(runner, self.steps)
        _ramp_temperature(
            sim, self.start_temperature, self.temperature, self.steps, self.n_chunks
        )
