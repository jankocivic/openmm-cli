"""The RAMD stage model (see the package docstring for the method)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from openmm import unit

from ...selections import select_atoms
from ...units import Quantity
from .. import SimulationStage, register_stage
from .engine import RAMD

if TYPE_CHECKING:
    from ...runner import Runner


def _select(topology, selection: str) -> list[int]:
    return select_atoms(topology, selection, label="RAMD selection")


@register_stage
class RAMDStage(SimulationStage):
    type: Literal["ramd"]
    ligand: str                      # mdtraj selection; its COM is pushed
    receptor: str | None = None      # mdtraj selection; COM used for the exit distance
    magnitude: Quantity = 14 * unit.kilocalories_per_mole / unit.angstrom
    ramd_steps: int = 50             # MD steps between direction checks
    r_min: Quantity = 0.025 * unit.angstrom   # min COM advance per cycle, else reorient
    r_max: Quantity = 30 * unit.angstrom      # exit when ligand-receptor COM exceeds this
    max_steps: int = 1_000_000
    log_freq: int = 50

    def run(self, runner: "Runner") -> None:
        sim = runner.simulation
        ligand = _select(runner.topology, self.ligand)
        receptor = _select(runner.topology, self.receptor) if self.receptor else None

        self.add_reporters(runner, self.max_steps)

        # RAMD logs only to its file; the console shows the standard progress
        # reporter above (verbose=False keeps the engine off stdout).
        ramd = RAMD(
            sim,
            ligand=ligand,
            magnitude=self.magnitude,
            receptor=receptor,
            ramd_steps=self.ramd_steps,
            r_min=self.r_min,
            r_max=self.r_max,
            log_freq=self.log_freq,
            log_file=str(runner.output_dir / "ramd.log"),
            verbose=False,
        )
        ramd.run(max_steps=self.max_steps)
