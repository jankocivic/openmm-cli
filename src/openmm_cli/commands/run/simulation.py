"""Assembly of a stage's default OpenMM ``Simulation`` from the run config.

The pieces build themselves: the ``System`` (topology, positions, box) comes from
the configured system source (``sources.py``), and the integrator/platform from
the resolved ``defaults`` models (``defaults.py``). This module wires them
together -- adding the run-wide barostat, then seeding the context. Stage-specific
forces (restraints, biases) are layered on by the stage, on top of this default.
"""

from __future__ import annotations

from openmm import app

from .defaults import Defaults
from .sources import SourceBase, SystemSettings


def build_simulation(
    source: SourceBase,
    system_settings: SystemSettings,
    defaults: Defaults,
    state=None,
) -> app.Simulation:
    """Build the default ``Simulation`` for a stage from the run-wide config.

    Assembles the system (plus the run-wide ``defaults.barostat``), the integrator
    and platform from the resolved ``defaults``, then seeds the context from
    ``state`` (the previous stage's positions / velocities / box) or, for the
    first stage, from the input files. Stage-specific forces (e.g. restraints) are
    added by the stage afterward. Free of side effects apart from reading the
    input files.
    """
    # A restart/previous-stage state carries the box, so the source can build with
    # it when no coordinates or explicit box is given (it's reapplied below anyway).
    restart_box = state.getPeriodicBoxVectors() if state is not None else None
    built = source.build(system_settings, restart_box=restart_box)
    if defaults.barostat is not None:
        built.system.addForce(
            defaults.barostat.build(defaults.integrator.temperature)
        )

    integrator = defaults.integrator.build()
    platform, props = defaults.platform.build()
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
