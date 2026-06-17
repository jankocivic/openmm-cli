"""Pipeline stages: the framework and the stage-type definitions."""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING, ClassVar, get_args

from pydantic import BaseModel, ConfigDict

from ..config import Defaults
from ..reporters import Reporters
from ..restraints import Restraint

if TYPE_CHECKING:
    from ..runner import Runner

_REGISTRY: dict[str, type["StageBase"]] = {}


class StageBase(BaseModel):
    """Base class for every pipeline stage."""

    # Reject unknown keys so typos in a stage's YAML fail loudly.
    model_config = ConfigDict(extra="forbid")

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

    # Stages that drive temperature (e.g. heating) set this so the config can
    # reject them under a non-thermostatted (Verlet) integrator.
    requires_thermostat: ClassVar[bool] = False

    def build(self, cfg, defaults, state):
        """Construct this stage's simulation, seeded from the carried ``state``.

        The default builds the standard simulation -- system + ``defaults.barostat``
        + this stage's ``restraints``, with the integrator/platform from the
        resolved ``defaults``. Override this for methods that assemble the
        simulation differently (e.g. metadynamics or alchemical free energy, which
        add forces before the context and may step via their own helper object);
        compose ``cfg.system.build`` / ``build_integrator`` / ``make_platform``
        as needed.
        """
        # Local import avoids a config <-> system import cycle at module load.
        from ..system import build_simulation

        return build_simulation(cfg, defaults, self.restraints, state)


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
