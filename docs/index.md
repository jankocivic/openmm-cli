# openmm-cli
[![docs](https://img.shields.io/badge/docs-online-blue)](https://jankocivic.github.io/openmm-cli/)

A command-line interface for running molecular dynamics simulations with OpenMM, without writing Python.

`openmm-cli` runs a full simulation workflow (minimization, heating, equilibration, production, and trajectory analysis) from one YAML file. Describe the simulation in the configuration file and the CLI does the rest. The field names are plain (`temperature: 300 K`, `nonbonded_method: PME`, `pressure: 1 atm`), which is easier to read than the short keywords used in other MD packages. The YAML file also serves as a record for future reproducibility.

> **Status: project in very early stage.** Report any bug as an issue.

---

## Features

- Run a full MD workflow from a single YAML config (minimize → heat → equilibrate → production)
- AMBER (`.parm7` / `.prmtop`), OpenMM force field (PDB/PDBx topology + force field XMLs), GROMACS (`.top` + `.gro`), and CHARMM (`.psf` + parameter set) inputs
- Supports restraints
- Restart from saved states
- Trajectory analysis and processing commands (RMSD, RMSF, distances, dihedrals, H-bonds, imaging, centering, stripping, format conversion)
- System preparation commands (PDB cleanup, solvation, ion placement)
- Optional web dashboard for browsing simulation outputs
- Built on [OpenMM](https://openmm.org) and [MDTraj](https://mdtraj.org)

---

## Installation

[`uv`](https://docs.astral.sh/uv/) is the recommended way to install `openmm-cli` (uv can be installed with `curl -LsSf https://astral.sh/uv/install.sh | sh` on Linux or macOS).

Then run:

```bash
git clone https://github.com/jankocivic/openmm-cli.git
cd openmm-cli
uv sync
source .venv/bin/activate # Activate virtual environment, should be done every terminal session
python -m openmm.testInstallation # Verify if OpenMM is installed properly
```

For the optional web dashboard:

```bash
uv sync --extra dashboard
```

Enable autocompletion of commands:

```bash
openmm-cli --install-completion # Applies only after restarting the terminal
```

### Install with conda

Create a conda environment and install with pip (add `[dashboard]` for the optional web dashboard):

```bash
git clone https://github.com/jankocivic/openmm-cli.git
cd openmm-cli
conda create -n openmm-cli python=3.12
conda activate openmm-cli
pip install .              # or: pip install ".[dashboard]"
python -m openmm.testInstallation # Verify if OpenMM is installed properly
```

### If OpenMM can't be installed from PyPI

If `uv` or `pip` can't find a working OpenMM (e.g. no compatible wheel, or the CUDA version doesn't match your GPU driver — check with `nvidia-smi`), install everything from conda-forge, pinning the CUDA version, and add the package with `--no-deps`:

```bash
git clone https://github.com/jankocivic/openmm-cli.git
cd openmm-cli
conda create -n openmm-cli -c conda-forge \
    python=3.12 openmm mdtraj pdbfixer numpy pydantic pyyaml typer matplotlib cuda-version=12.4
conda activate openmm-cli
python -m openmm.testInstallation # Verify if OpenMM is installed properly
pip install . --no-deps
```

For the dashboard on this path, also add `streamlit plotly pandas` to the conda env. `--no-deps` stops pip from re-resolving the dependencies and pulling mismatched copies from PyPI.

> **Note:** `openmm-cli` has so far only been tested on Linux. It should work on macOS, but not verified.

---

## Quick Start

See `openmm-cli --help`, `openmm-cli trajectory --help` and `openmm-cli prepare --help` for the full command list.

For running an MD simulation protocol write a `config.yaml`:

```yaml
system:
  topology: protein.parm7
  coordinates: protein.inpcrd

defaults:
  integrator:
    type: LangevinMiddle
    timestep: 2 fs
    temperature: 300 K
  barostat:
    type: isotropic
    pressure: 1 atm
    frequency: 25

output_dir: output

stages:
  - name: minimize
    type: minimization
    max_iterations: 5000

  - name: production
    type: dynamics
    steps: 2500000
    randomize_velocities: 300 K
    reporters:
      trajectory: { file: prod.dcd, interval: 5000 }
      state:      { file: prod.csv, interval: 1000 }

  - name: rmsd
    type: analysis
    command: rmsd
    args:
      trajectory: prod.dcd
      top: ../protein.parm7
      sel: "name CA"
      out: rmsd.csv
```

Run it:

```bash
openmm-cli run config.yaml
```

Analyze the resulting trajectory:

```bash
openmm-cli trajectory info     output/prod.dcd --top protein.parm7
openmm-cli trajectory rmsd     output/prod.dcd --top protein.parm7 --sel "name CA"
openmm-cli trajectory distance output/prod.dcd --top protein.parm7 \
    --a "resname LIG" --b "resid 42 and name CA"
```

---

## Configuration

A run is described by one YAML file. The [Quick Start](#quick-start) above is a complete example; for every available key, see the reference pages:

- **[Configuration reference](configuration.md)** — the `system` inputs, `system_settings`, `defaults` (integrator, barostat, platform), reporters, restraints, and how information flows through a run.
- **[Stage types](stages.md)** — the fields and behavior of each stage: `minimization`, `dynamics`, `heat`, `ramd`, `branch` (replicas), and `analysis`.

---

## Examples

The `examples/` directory contains complete, runnable workflows you can use as starting points:

- **`examples/253L/`** — T4 lysozyme L99A starting from a raw PDB. Demonstrates the full pipeline: `prepare clean` → `prepare solvate` → `run` with a multi-stage MD protocol (minimize → heat → equilibrate → production) and analysis (RMSD, H-bonds). Uses an OpenMM force field; no external programs necessary.
- **`examples/Amber_FP/`** — fluorescent protein starting from a pre-built AMBER topology (`parm7` + `pdb`). Same MD protocol as 253L, but skips the preparation stage since the system is already parametrised.

Each example has a `README.md` explaining the workflow, a `config.yaml`, and a `run.sh` that runs the full pipeline.

---

## Dashboard

`openmm-cli` includes an optional Streamlit dashboard for browsing simulation outputs. After installing the extra, launch it pointing at any directory containing CSV files:

```bash
openmm-cli dashboard                  # current directory
openmm-cli dashboard examples/253L/output
```

The dashboard reads every CSV in the directory and plots its numeric columns over time (energies, temperature, density, RMSD, etc.). Non-time-series files like H-bond inventories or RMSF results render as sortable tables.

---

## Adding a stage type

Stages are auto-discovered from `src/openmm_cli/commands/run/stage_types/` — drop a module there with a `@register_stage`-decorated `StageBase` subclass and nothing else needs to change.

Subclass `SimulationStage` for stages that drive the simulation: the runner builds a fresh simulation for each (run `defaults` + the stage's optional `defaults` override + its `restraints`) and saves the end state, so `run` only advances `runner.simulation`. Every `SimulationStage` already defines `name`, an optional `defaults` override, `restraints`, and `reporters` — so you only add the fields specific to your stage.

```python
# src/openmm_cli/commands/run/stage_types/my_stage.py
from typing import TYPE_CHECKING, Literal

from . import SimulationStage, register_stage

if TYPE_CHECKING:
    from ..runner import Runner


@register_stage
class MyStage(SimulationStage):
    type: Literal["my_stage"]   # unique YAML `type:` tag
    steps: int                  # add any config fields you need

    def run(self, runner: "Runner") -> None:
        runner.simulation.step(self.steps)
```

Then use it in a config: `- {name: relax, type: my_stage, steps: 1000}`. A stage that only post-processes outputs (no simulation) subclasses `StageBase` directly instead.

For methods that need to construct the simulation differently — e.g. metadynamics or free-energy setups that add forces before the context, or step via their own helper — override `build(self, cfg, defaults, state)`. By default it builds the standard simulation; override it to assemble a custom one (reusing `cfg.system.build` / `build_integrator` / `make_platform`).

---

## Adding a command

Commands are auto-discovered from `src/openmm_cli/commands/`. The discovery rule is uniform at every level:

- A `.py` file in `commands/` becomes a **top-level command** (`openmm-cli <name>`).
- A folder in `commands/` whose `__init__.py` exposes a `command` function is **also a top-level command** — useful when the command needs supporting modules of its own (this is how `run/` works).
- A folder in `commands/` whose `__init__.py` does *not* expose `command` becomes a **subgroup**; each `.py` file inside becomes a subcommand (`openmm-cli <group> <name>`).
- Files and folders starting with `_` are skipped.

Example of a new subcommand of the trajectory command:

```python
# src/openmm_cli/commands/trajectory/my_analysis.py
"""Short description of what the command does."""
from pathlib import Path
from typing import Annotated

import mdtraj as md
import typer


def command(
    trajectory: Annotated[Path, typer.Argument(help="Input trajectory.")],
    topology: Annotated[Path, typer.Option("--top")],
    selection: Annotated[str, typer.Option("--sel")] = "name CA",
    output: Annotated[Path, typer.Option("--out")] = Path("my_analysis.csv"),
) -> None:
    """One-line summary used as the command's --help description."""
    traj = md.load(str(trajectory), top=str(topology))
    # ... your logic here
```

No `cli.py` edits required. The new command appears as `openmm-cli trajectory my_analysis`. Name the function `command` (auto-discovery looks for this attribute), reuse flag names across commands (`--top`, `--out`, `--sel`, `--ref`), and add a docstring to each group's `__init__.py` (it becomes the group's `--help` text).

---

## Related projects

`openmm-cli` is inspired by [**OMMProtocol**](https://github.com/insilichem/ommprotocol), which also drives OpenMM through a YAML config organized into stages. Differences from OMMProtocol: `openmm-cli` is built on a modern Python stack (Pydantic for config validation, Typer for the CLI), integrates preparation and trajectory analysis as commands, and is structured so new commands can be added by dropping a single file into the right folder.

---

## Acknowledgements

Built on [OpenMM](https://openmm.org) for the simulation engine, [mdtraj](https://mdtraj.org) for trajectory analysis, [PDBFixer](https://github.com/openmm/pdbfixer) for system preparation, [Pydantic](https://pydantic.dev) for config validation, and [Typer](https://typer.tiangolo.com) for the CLI.
