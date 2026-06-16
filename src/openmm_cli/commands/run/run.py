"""``run`` command: drive an MD simulation from a YAML config.

The work is split across focused modules within this package:

  - :mod:`.config`     -- the configuration data models + per-stage `defaults` merge
  - :mod:`.system`     -- build a fresh per-stage simulation (system/integrator/
                          platform + barostat + restraints), seeded from a State
  - :mod:`.barostats`  -- barostat config models + force construction
  - :mod:`.restraints` -- restraint config models + force construction
  - :mod:`.reporters`  -- trajectory/state/checkpoint/progress reporters
  - :mod:`.stage_types`-- the stage framework + one module per stage type
  - :mod:`.runner`     -- drives the stages, rebuilding the simulation per stage
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml

from .config import Config
from .runner import Runner


def command(
    config: Annotated[
        Path, typer.Argument(..., help="Path to yaml configuration file.")
    ],
) -> None:
    """Run an MD simulation from a YAML config file."""
    with open(config) as f:
        raw = yaml.safe_load(f)
    cfg = Config.model_validate(raw)
    Runner(cfg).run()
