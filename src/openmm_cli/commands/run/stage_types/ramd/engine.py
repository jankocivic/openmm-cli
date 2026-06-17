"""Random Acceleration Molecular Dynamics (RAMD) for OpenMM.

RAMD pushes a ligand out of its binding site with a constant-magnitude force
applied to the ligand's center of mass in a random direction. Whenever the
ligand fails to advance at least ``r_min`` during ``ramd_steps`` MD steps,
the direction is re-randomized. The run stops when the ligand-receptor COM
distance exceeds ``r_max`` (an exit event) or ``max_steps`` is reached.

Logging
-------
RAMD logs progress to the console by default. Pass ``log_file=`` to also write a
file, or ``verbose=False`` to stay silent and configure the "ramd" logger
yourself.

Example
-------
    sim = openmm.app.Simulation(topology, system, integrator, platform)
    sim.context.setPositions(pdb.positions)
    sim.minimizeEnergy()
    ramd = RAMD(sim, ligand=lig_indices, receptor=rec_indices,
                magnitude=14 * unit.kilocalorie_per_mole / unit.angstrom,
                log_file="ramd.log")
    exit_step = ramd.run()
"""

import logging

import numpy as np
import openmm
from openmm import unit

_FORCE_UNIT = unit.kilojoule_per_mole / unit.nanometer

log = logging.getLogger("ramd")


class RAMD:
    """Drive an existing ``openmm.app.Simulation`` with a RAMD force."""

    def __init__(self, simulation, ligand, magnitude, receptor=None,
                 ramd_steps=50, r_min=0.025 * unit.angstrom,
                 r_max=50 * unit.angstrom, log_freq=50, log_file=None,
                 verbose=True, seed=None):
        self.sim = simulation
        self.ligand = list(ligand)
        self.receptor = list(receptor) if receptor else None
        self.ramd_steps = ramd_steps
        self.r_min = r_min.value_in_unit(unit.nanometer)
        self.r_max = r_max.value_in_unit(unit.nanometer)
        self.magnitude = magnitude.value_in_unit(_FORCE_UNIT)
        self.log_freq = log_freq
        self.rng = np.random.default_rng(seed)
        self.direction = np.zeros(3)
        self._configure_logging(log_file, verbose)

        # Cache per-group atom indices and masses (constant for the run).
        self._lig_idx = np.array(self.ligand)
        self._lig_mass = self._masses(self.ligand)
        self._rec_idx = np.array(self.receptor) if self.receptor else None
        self._rec_mass = self._masses(self.receptor) if self.receptor else None

        # A uniform force (fx, fy, fz) on the ligand centroid; direction is set
        # at run time via global parameters, so no force re-indexing is needed.
        self.force = openmm.CustomCentroidBondForce(1, "-(fx*x1 + fy*y1 + fz*z1)")
        for name in ("fx", "fy", "fz"):
            self.force.addGlobalParameter(name, 0.0)
        self.force.addBond([self.force.addGroup(self.ligand)], [])
        self.sim.system.addForce(self.force)
        self.sim.context.reinitialize(preserveState=True)

    @staticmethod
    def _configure_logging(log_file, verbose):
        """Set up the "ramd" logger. Skipped if the caller manages it."""
        if not verbose and log_file is None:
            return  # caller configures the "ramd" logger themselves
        log.setLevel(logging.INFO)
        log.propagate = False
        for handler in list(log.handlers):
            log.removeHandler(handler)
        fmt = logging.Formatter("RAMD %(message)s")
        if verbose:
            console = logging.StreamHandler()
            console.setFormatter(fmt)
            log.addHandler(console)
        if log_file is not None:
            to_file = logging.FileHandler(log_file, mode="w")
            to_file.setFormatter(fmt)
            log.addHandler(to_file)

    def _positions(self):
        return self.sim.context.getState(
            getPositions=True).getPositions(asNumpy=True)

    def _masses(self, indices):
        """Mass-weights (in daltons) for ``indices``; computed once and cached."""
        return np.array(
            [self.sim.system.getParticleMass(i) / unit.dalton for i in indices]
        )

    @staticmethod
    def _com(positions, idx, masses):
        """Mass-weighted COM (nm) of ``idx`` from a positions Quantity."""
        coords = positions.value_in_unit(unit.nanometer)[idx]
        return np.average(coords, axis=0, weights=masses)

    def reorient(self):
        """Point the force in a fresh random direction at fixed magnitude."""
        self.direction = self.rng.normal(size=3)
        self.direction /= np.linalg.norm(self.direction)
        for name, value in zip(("fx", "fy", "fz"), self.magnitude * self.direction):
            self.sim.context.setParameter(name, value)

    def run(self, max_steps=100_000_000):
        """Run RAMD; return the step at which the ligand exited (or max_steps)."""
        log.info("start: magnitude=%.3f kJ/mol/nm ramd_steps=%d r_min=%.4f nm "
                 "r_max=%.3f nm ligand=%d atoms receptor=%s openmm=%s",
                 self.magnitude, self.ramd_steps, self.r_min, self.r_max,
                 len(self.ligand),
                 "%d atoms" % len(self.receptor) if self.receptor else "none",
                 openmm.version.full_version)
        self.reorient()
        log.info("step=0 initial direction=%s", np.array2string(self.direction, precision=3))
        previous = self._com(self._positions(), self._lig_idx, self._lig_mass)
        steps = 0
        while steps < max_steps:
            self.sim.step(self.ramd_steps)
            steps += self.ramd_steps
            positions = self._positions()
            ligand_com = self._com(positions, self._lig_idx, self._lig_mass)
            displacement = np.linalg.norm(ligand_com - previous)
            distance = None
            if self.receptor is not None:
                receptor_com = self._com(positions, self._rec_idx, self._rec_mass)
                distance = np.linalg.norm(ligand_com - receptor_com)
            if steps % self.log_freq == 0:
                log.info("step=%d displacement=%.4f nm distance=%s",
                         steps, displacement,
                         "%.4f nm" % distance if distance is not None else "n/a")
            if displacement < self.r_min:
                self.reorient()
                log.info("step=%d stalled (%.4f < %.4f nm): new direction=%s",
                         steps, displacement, self.r_min,
                         np.array2string(self.direction, precision=3))
            previous = ligand_com
            if distance is not None and distance > self.r_max:
                log.info("step=%d EXIT: ligand-receptor distance %.4f nm > %.4f nm",
                         steps, distance, self.r_max)
                return steps
        log.info("step=%d reached max_steps without an exit event", steps)
        return steps
