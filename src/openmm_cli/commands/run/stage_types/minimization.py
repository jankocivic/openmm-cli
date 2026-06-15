"""Energy minimization stage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import openmm as mm
from openmm import unit

from ..config import Quantity
from ..restraints import Restraint, restrain
from . import StageBase, register_stage

if TYPE_CHECKING:
    from ..runner import Runner


@register_stage
class MinimizationStage(StageBase):
    type: Literal["minimization"]
    max_iterations: int = 0  # 0 = until convergence
    tolerance: Quantity = 10 * unit.kilojoules_per_mole / unit.nanometer
    restraints: list[Restraint] = []

    def run(self, runner: "Runner") -> None:
        sim = runner.simulation
        print(f"  Minimizing (max {self.max_iterations or 'unlimited'} iterations)")
        with restrain(sim, runner.system, runner.topology, self.restraints):
            sim.minimizeEnergy(
                maxIterations=self.max_iterations, tolerance=self.tolerance
            )

        state = sim.context.getState(
            getPositions=True, getVelocities=True, enforcePeriodicBox=True
        )
        with open(runner.output_dir / f"{self.name}.xml", "w") as f:
            f.write(mm.XmlSerializer.serialize(state))
