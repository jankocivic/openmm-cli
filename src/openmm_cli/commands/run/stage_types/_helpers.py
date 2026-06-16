"""Helpers shared by more than one stage type.

Not a stage type itself -- the leading underscore keeps the discovery loop in
``__init__`` from importing it as one. Single-consumer helpers belong in their
own stage module, not here.
"""

from __future__ import annotations

from ..barostats import find_barostat


def configure_barostat(simulation, system, cfg, disable: bool) -> None:
    """Enable/disable the run's barostat for a stage and sync its temperature.

    No-op if no barostat is configured. The barostat's temperature is taken from
    the integrator's current target -- which is always available, because the
    config forbids a barostat without a thermostatted integrator.
    """
    barostat = find_barostat(system)
    if barostat is None:
        return
    barostat.setFrequency(0 if disable else cfg.defaults.barostat.frequency)
    barostat.setDefaultTemperature(simulation.integrator.getTemperature())
    simulation.context.reinitialize(preserveState=True)
