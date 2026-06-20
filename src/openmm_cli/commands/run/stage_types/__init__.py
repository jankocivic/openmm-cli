"""Pipeline stages: the framework and the stage-type definitions."""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING, get_args

from ..base import _Base
from ..defaults import Defaults
from ..reporters import Reporters
from ..restraints import Restraint

if TYPE_CHECKING:
    from ..runner import Runner
    from ..sources import SystemSettings

_REGISTRY: dict[str, type["StageBase"]] = {}


class StageBase(_Base):
    """Base class for every pipeline stage."""

    name: str
    # Subclasses pin `type`, e.g. `type: Literal["dynamics"]`.

    def run(self, runner: "Runner") -> None:
        """Execute the stage. Override this."""
        raise NotImplementedError


class SimulationStage(StageBase):
    """Base for stages that advance a freshly-built simulation.

    The runner builds the simulation for these stages -- resolving ``defaults``
    over the run defaults and adding ``restraints`` -- then captures and saves the
    resulting state. The stage's ``run`` only advances the simulation.
    """

    defaults: Defaults | None = None     # per-stage override of the run defaults
    restraints: list[Restraint] = []
    reporters: Reporters = Reporters()

    def validate_resolved(
        self, defaults: Defaults, system_settings: "SystemSettings"
    ) -> None:
        """Validate this stage against its *resolved* settings.

        ``defaults`` is the run defaults merged with this stage's override, and
        ``system_settings`` the run-wide force settings. Called once per stage by
        ``Config``. The base enforces the rules common to every simulation stage
        (a barostat needs a thermostatted, periodic system); override and call
        ``super().validate_resolved(...)`` to add stage-specific rules.
        """
        if defaults.barostat is None:
            return
        if defaults.integrator.type == "Verlet":
            raise ValueError(
                f"Stage {self.name!r}: a barostat needs a thermostatted "
                "integrator (NPT needs a target temperature)."
            )
        periodic = system_settings.nonbonded_method not in (
            "NoCutoff",
            "CutoffNonPeriodic",
        )
        if not periodic:
            raise ValueError(
                f"Stage {self.name!r}: a barostat needs a periodic nonbonded "
                f"method (got {system_settings.nonbonded_method!r})."
            )

    def build(self, cfg, defaults, state):
        """Construct this stage's simulation, seeded from the carried ``state``.

        Builds the default simulation from the run-wide config (system + the
        run-wide ``defaults.barostat``, integrator/platform from the resolved
        ``defaults``), then adds this stage's ``restraints`` on top. Override this
        for methods that assemble the simulation differently (e.g. metadynamics or
        alchemical free energy); compose ``build_simulation`` and add forces as
        needed.
        """
        # Local import avoids an import cycle at module load.
        from ..simulation import build_simulation

        sim = build_simulation(cfg.system, cfg.system_settings, defaults, state)
        if self.restraints:
            anchor = sim.context.getState(getPositions=True).getPositions()
            for restraint in self.restraints:
                sim.system.addForce(restraint.build(sim.topology, anchor))
            sim.context.reinitialize(preserveState=True)
        return sim


def _tag_of(cls: type[StageBase]) -> str:
    """Read the single ``Literal`` value of a stage class's ``type`` field."""
    field = cls.model_fields.get("type")
    if field is None:
        raise TypeError(f"{cls.__name__} must declare a `type: Literal[...]` field")
    tags = get_args(field.annotation)
    if len(tags) != 1 or not isinstance(tags[0], str):
        raise TypeError(
            f"{cls.__name__}.type must be a single-value Literal, e.g. Literal['x']"
        )
    return tags[0]


def register_stage(cls: type[StageBase]) -> type[StageBase]:
    """Register a stage class under its ``type`` tag (use as a decorator)."""
    tag = _tag_of(cls)
    existing = _REGISTRY.get(tag)
    if existing is not None and existing is not cls:
        raise ValueError(
            f"Stage type {tag!r} already registered by {existing.__name__}"
        )
    _REGISTRY[tag] = cls
    return cls


def get_stage_model(tag: str) -> type[StageBase]:
    """Return the stage class registered for ``tag``."""
    try:
        return _REGISTRY[tag]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise ValueError(
            f"Unknown stage type {tag!r}. Registered: {known}"
        ) from None


# Import every stage module so its `@register_stage` runs. Kept at the bottom so
# the framework above is defined before the stage modules import it.
for _info in pkgutil.iter_modules(__path__):
    if not _info.name.startswith("_"):
        importlib.import_module(f"{__name__}.{_info.name}")
