"""Pipeline stages: the framework and the stage-type definitions.

The framework (``StageBase``, ``register_stage``, ``get_stage_model``) lives
here; each module in this package defines one ``StageBase`` subclass decorated
with ``@register_stage``. Dropping a new module in this folder is all that is
required to add a stage type -- the discovery loop at the bottom imports every
module so its registration runs, and nothing else needs to change.

A stage subclass must:

  * subclass ``StageBase`` (which gives it the required ``name`` field),
  * declare a unique single-value ``type: Literal["..."]`` -- both the YAML
    ``type:`` value and the registry key,
  * implement ``run(self, runner)``.

Stage handlers are deliberately close to plain OpenMM: a stage reads/writes the
live ``runner.simulation`` directly. See ``STAGE_CONTRACT.md`` for what state
persists between stages.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING, get_args

from pydantic import BaseModel, ConfigDict

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
        """Execute the stage against the live simulation. Override this."""
        raise NotImplementedError


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
