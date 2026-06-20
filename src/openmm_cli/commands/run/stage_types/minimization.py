"""Energy minimization stage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from openmm import unit

from ..units import Quantity
from . import SimulationStage, register_stage

if TYPE_CHECKING:
    from ..runner import Runner


@register_stage
class MinimizationStage(SimulationStage):
    type: Literal["minimization"]
    max_iterations: int = 0  # 0 = until convergence
    tolerance: Quantity = 10 * unit.kilojoules_per_mole / unit.nanometer

    def run(self, runner: "Runner") -> None:
        # Restraints (if any) are already on the system, added when the runner
        # built this stage's simulation.
        print(f"  Minimizing (max {self.max_iterations or 'unlimited'} iterations)")
        runner.simulation.minimizeEnergy(
            maxIterations=self.max_iterations, tolerance=self.tolerance
        )
