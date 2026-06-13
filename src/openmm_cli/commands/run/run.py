"""``run`` command: drive an MD simulation from a YAML config.

This module is intentionally thin. The work is split across focused modules
within this package:

  - :mod:`.config`     -- the configuration data models (the "what")
  - :mod:`.system`     -- build the OpenMM system, integrator and platform
  - :mod:`.restraints` -- positional (and future) restraint forces
  - :mod:`.barostat`   -- barostat creation and per-stage configuration
  - :mod:`.reporters`  -- trajectory/state/checkpoint/progress reporters
  - :mod:`.state`      -- save/load serialized simulation state
  - :mod:`.analysis`   -- run trajectory analysis commands as stages
  - :mod:`.stages`     -- stage handlers + the stage dispatch registry
  - :mod:`.runner`     -- the Runner that wires it together and drives stages
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
