"""Random Acceleration MD (RAMD) stage.

Pushes the ligand out of its binding site with a constant force on its center of
mass, re-randomizing the direction whenever it stalls, until the ligand-receptor
COM distance exceeds ``r_max`` or ``max_steps`` is reached. Ligand and receptor
are chosen by mdtraj selection strings; their centers of mass drive the force and
the exit criterion.

The simulation is built the standard way (the runner's default `build`); this
stage just attaches the RAMD force to it via the `RAMD` engine (see `engine.py`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import mdtraj as md
from openmm import unit

from ...config import Quantity
from ...reporters import build_reporters
from .. import SimulationStage, register_stage
from .engine import RAMD

if TYPE_CHECKING:
    from ...runner import Runner


def _select(topology, selection: str) -> list[int]:
    indices = md.Topology.from_openmm(topology).select(selection)
    if len(indices) == 0:
        raise ValueError(f"RAMD selection {selection!r} matched no atoms")
    return [int(i) for i in indices]


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

        for reporter in build_reporters(self.reporters, self.max_steps, runner.output_dir):
            sim.reporters.append(reporter)

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
