"""Barostat creation and per-stage (re)configuration."""

from __future__ import annotations

import openmm as mm

from .config import Config, DynamicsStage


def add_default_barostat(system, cfg: Config) -> None:
    """Add the default Monte Carlo barostat to the system, if configured."""
    b = cfg.defaults.barostat
    if b is None:
        return
    system.addForce(
        mm.MonteCarloBarostat(b.pressure, cfg.defaults.integrator.temperature, b.frequency)
    )


def _find_barostat(system):
    for i, force in enumerate(system.getForces()):
        if isinstance(force, mm.MonteCarloBarostat):
            return i, force
    return None, None


def configure_barostat(
    simulation, system, cfg: Config, stage: DynamicsStage, temperature
) -> None:
    """Enable or disable the configured barostat for a dynamics stage.

    Pressure and frequency come from ``defaults`` (a barostat only exists in the
    system if ``defaults.barostat`` was set); ``temperature`` is the stage's
    resolved running temperature so pressure coupling matches it. Re-applying the
    settings each stage also re-enables the barostat after a stage disabled it.
    """
    _, barostat = _find_barostat(system)
    if barostat is None:
        return

    if stage.disable_barostat:
        barostat.setFrequency(0)
    else:
        b = cfg.defaults.barostat
        barostat.setFrequency(b.frequency)
        barostat.setDefaultPressure(b.pressure)
        barostat.setDefaultTemperature(temperature)

    simulation.context.reinitialize(preserveState=True)
