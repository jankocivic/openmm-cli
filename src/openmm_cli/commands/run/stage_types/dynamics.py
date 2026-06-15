"""Molecular dynamics stage (optionally a heating ramp).

Temperature, pressure and timestep are inherited from the running simulation
unless this stage overrides them -- see ``STAGE_CONTRACT.md``. ``defaults`` only
seeds those values when the simulation is first built.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import openmm as mm

from ..config import Quantity
from ..reporters import Reporters, build_reporters
from ..restraints import Restraint, restrain
from . import StageBase, register_stage

if TYPE_CHECKING:
    from ..runner import Runner


def _heat(simulation, start_T, end_T, steps, n_chunks=100):
    """Ramp the integrator temperature from ``start_T`` to ``end_T``."""
    chunk = steps // n_chunks
    print(f"  Heating from {start_T} to {end_T} over {steps} steps")
    for i in range(n_chunks):
        simulation.integrator.setTemperature(
            start_T + (end_T - start_T) * (i + 1) / n_chunks
        )
        simulation.step(chunk)
    leftover = steps - chunk * n_chunks
    if leftover:
        simulation.step(leftover)


@register_stage
class DynamicsStage(StageBase):
    type: Literal["dynamics"]
    steps: int
    start_temperature: Quantity | None = None

    # Per-stage overrides; left None they inherit the current running value.
    temperature: Quantity | None = None
    timestep: Quantity | None = None

    # Run NVT for this stage even if a barostat is configured in `defaults`.
    disable_barostat: bool = False

    # Re-draw velocities from Maxwell-Boltzmann at stage start (e.g. the first
    # dynamics stage after minimization).
    initialize_velocities: bool = False

    restraints: list[Restraint] = []
    reporters: Reporters = Reporters()

    def run(self, runner: "Runner") -> None:
        sim = runner.simulation
        system = runner.system
        integrator = sim.integrator
        has_thermostat = hasattr(integrator, "getTemperature")

        # Timestep inherits unless overridden.
        if self.timestep is not None:
            integrator.setStepSize(self.timestep)

        # Running temperature: stage override, else the current target, else the
        # construction default (when the integrator has no thermostat).
        if self.temperature is not None:
            end_T = self.temperature
        elif has_thermostat:
            end_T = integrator.getTemperature()
        else:
            end_T = runner.cfg.defaults.integrator.temperature

        start_T = self.start_temperature
        initial_T = start_T if start_T is not None else end_T
        if has_thermostat:
            integrator.setTemperature(initial_T)

        # Pressure coupling: the barostat (if any) was set up by the runner.
        # Keep its temperature in sync with this stage, or disable it for NVT.
        barostat = next(
            (f for f in system.getForces() if isinstance(f, mm.MonteCarloBarostat)),
            None,
        )
        if barostat is not None:
            b = runner.cfg.defaults.barostat
            barostat.setFrequency(0 if self.disable_barostat else b.frequency)
            barostat.setDefaultTemperature(end_T)
            sim.context.reinitialize(preserveState=True)

        if self.initialize_velocities:
            sim.context.setVelocitiesToTemperature(initial_T)

        for reporter in build_reporters(self.reporters, self.steps, runner.output_dir):
            sim.reporters.append(reporter)
        sim.currentStep = 0
        sim.context.setTime(0)

        with restrain(sim, system, runner.topology, self.restraints):
            if start_T is not None:
                _heat(sim, start_T, end_T, self.steps)
            else:
                print(f"  Running {self.steps} steps")
                sim.step(self.steps)

        state = sim.context.getState(
            getPositions=True, getVelocities=True, enforcePeriodicBox=True
        )
        with open(runner.output_dir / f"{self.name}.xml", "w") as f:
            f.write(mm.XmlSerializer.serialize(state))
