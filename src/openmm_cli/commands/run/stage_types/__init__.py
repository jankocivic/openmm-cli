"""Pipeline stages: the framework (in ``_framework``) and the stage definitions.

Importing this package registers every stage type: it re-exports the framework,
then imports each stage module so its ``@register_stage`` runs.
"""

from ._framework import (
    SimulationStage,
    StageBase,
    discover_stages,
    get_stage_model,
    register_stage,
)

__all__ = ["StageBase", "SimulationStage", "register_stage", "get_stage_model"]

discover_stages(__name__, __path__)
