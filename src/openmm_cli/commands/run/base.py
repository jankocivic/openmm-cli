"""Shared Pydantic base for config models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    """Shared base: reject unknown keys so typos in YAML fail loudly."""

    model_config = ConfigDict(extra="forbid")
