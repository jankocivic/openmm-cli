"""Root configuration model for the MD runner.

Ties together the system source, run-wide ``defaults``, and the ordered
``stages`` into the top-level :class:`Config`. The building blocks live in
sibling modules -- units in ``units``, the shared base in ``base``, the
construction settings in ``settings``, system sources in ``sources``, and the
stage models in ``stage_types`` -- so this module sits at the top of the import
graph and pulls them all together.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import SerializeAsAny, field_validator, model_validator

from .base import _Base
from .defaults import Defaults, merge_defaults
from .sources import SOURCE_BY_SUFFIX, SourceBase, SystemSettings
from .stage_types import SimulationStage, StageBase, get_stage_model


class Config(_Base):
    # `SerializeAsAny` so the resolved-config dump keeps each concrete source's
    # and stage's own fields rather than only those declared on the base.
    system: SerializeAsAny[SourceBase]
    system_settings: SystemSettings = SystemSettings()
    defaults: Defaults = Defaults()
    output_dir: Path = Path("output")
    stages: list[SerializeAsAny[StageBase]]

    @field_validator("system", mode="before")
    @classmethod
    def _dispatch_source(cls, raw):
        """Pick the system-source model from the topology file's extension."""
        if isinstance(raw, SourceBase):
            return raw
        if not isinstance(raw, dict) or "topology" not in raw:
            raise ValueError("`system` must be a mapping with a `topology` field")
        suffix = Path(str(raw["topology"])).suffix.lower()
        model = SOURCE_BY_SUFFIX.get(suffix)
        if model is None:
            known = ", ".join(sorted(SOURCE_BY_SUFFIX))
            raise ValueError(
                f"Unsupported topology format {suffix!r}. Known: {known}"
            )
        return model.model_validate(raw)

    @field_validator("stages", mode="before")
    @classmethod
    def _dispatch_stages(cls, raw):
        """Build each entry into its registered stage model by its `type` tag."""
        if not isinstance(raw, list):
            raise ValueError("`stages` must be a list")
        built = []
        for i, item in enumerate(raw):
            if isinstance(item, StageBase):
                built.append(item)
            elif isinstance(item, dict):
                tag = item.get("type")
                if tag is None:
                    raise ValueError(f"stages[{i}] is missing a `type` field")
                built.append(get_stage_model(tag).model_validate(item))
            else:
                raise ValueError(
                    f"stages[{i}] must be a mapping with a `type` field"
                )
        return built

    @model_validator(mode="after")
    def _validate_stages(self):
        """Validate each simulation stage against its *resolved* settings.

        Each stage builds a fresh simulation, so coherence is checked per stage on
        the merged config (run defaults + the stage's override). The rules
        themselves live on the stage classes via ``validate_resolved`` so a new
        stage type carries its own validation -- see ``stage_types``.
        """
        for stage in self.stages:
            if isinstance(stage, SimulationStage):
                eff = merge_defaults(self.defaults, stage.defaults)
                stage.validate_resolved(eff, self.system_settings)
        return self
