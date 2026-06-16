"""Branch stage: fork the run into ``count`` independent copies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from . import StageBase, register_stage

if TYPE_CHECKING:
    from ..runner import Runner


@register_stage
class BranchStage(StageBase):
    type: Literal["branch"]
    count: int

    def run(self, runner: "Runner") -> None:  # pragma: no cover - never called
        raise RuntimeError("branch stages are handled by the runner, not run()")
