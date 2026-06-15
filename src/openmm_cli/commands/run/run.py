"""``run`` command: drive an MD simulation from a YAML config.

The work is split across focused modules within this package:

  - :mod:`.config`     -- the configuration data models (the "what")
  - :mod:`.system`     -- build the OpenMM system/integrator/platform and the
                          fully-initialized starting simulation
  - :mod:`.restraints` -- restraint models + the `restrain` context manager
  - :mod:`.reporters`  -- trajectory/state/checkpoint/progress reporters
  - :mod:`.stage_types`-- the stage framework + one module per stage type
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
