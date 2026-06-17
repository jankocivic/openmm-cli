"""Construction of the OpenMM integrator, platform and simulation from config.

The ``System`` itself (topology, positions, box) is produced by the configured
system source -- see ``sources.py``. This module assembles the integrator and
platform from the resolved defaults and seeds the simulation context.
"""

from __future__ import annotations

import openmm as mm
from openmm import app

from .config import Config, Defaults, IntegratorConfig, PlatformConfig


_INTEGRATORS = {
    "LangevinMiddle": lambda c: mm.LangevinMiddleIntegrator(
        c.temperature, c.friction, c.timestep
    ),
    "Langevin": lambda c: mm.LangevinIntegrator(
        c.temperature, c.friction, c.timestep
    ),
    "Verlet": lambda c: mm.VerletIntegrator(c.timestep),
}


def build_integrator(cfg: IntegratorConfig) -> mm.Integrator:
    """Construct the integrator named by ``cfg.type``."""
    try:
        factory = _INTEGRATORS[cfg.type]
    except KeyError:
        raise ValueError(f"Unknown integrator type: {cfg.type}")
    return factory(cfg)


def make_platform(platform: PlatformConfig) -> tuple[mm.Platform, dict[str, str]]:
    """Return the platform and its property dict for ``Simulation``."""
    plat = mm.Platform.getPlatformByName(platform.name)
    props: dict[str, str] = {}
    if platform.name in ("CUDA", "OpenCL"):
        # CUDA and OpenCL both use the bare property names "Precision" and
        # "DeviceIndex" (not a platform-prefixed form).
        props["Precision"] = platform.precision
        if platform.device_index is not None:
            props["DeviceIndex"] = platform.device_index
    return plat, props


def build_simulation(
    cfg: Config, defaults: Defaults, restraints, state=None
) -> app.Simulation:
    """Build a fresh ``Simulation`` for one stage.

    Assembles the system (plus ``defaults.barostat`` and this stage's
    ``restraints``), the integrator and platform from the resolved ``defaults``,
    then seeds the context from ``state`` (the previous stage's positions /
    velocities / box) or, for the first stage, from the input files. Free of side
    effects apart from reading the input files.
    """
    # A restart/previous-stage state carries the box, so the source can build with
    # it when no coordinates or explicit box is given (it's reapplied below anyway).
    restart_box = state.getPeriodicBoxVectors() if state is not None else None
    built = cfg.system.build(cfg.system_settings, restart_box=restart_box)
    if defaults.barostat is not None:
        built.system.addForce(
            defaults.barostat.build(defaults.integrator.temperature)
        )
    anchor = state.getPositions() if state is not None else built.positions
    for restraint in restraints:
        built.system.addForce(restraint.build(built.topology, anchor))

    integrator = build_integrator(defaults.integrator)
    platform, props = make_platform(defaults.platform)
    simulation = app.Simulation(
        built.topology, built.system, integrator, platform, props
    )

    if state is not None:
        simulation.context.setState(state)
    else:
        if built.positions is not None:
            simulation.context.setPositions(built.positions)
        if built.box_vectors is not None:
            simulation.context.setPeriodicBoxVectors(*built.box_vectors)
    return simulation
