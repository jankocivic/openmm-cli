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

Enable autocompletion of commands:

```bash
openmm-cli --install-completion # Applies only after restarting the terminal
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

## Specifying the system
 
The input format is chosen from the **topology** file's extension. Each format reads the topology shown plus its companion field(s):

| Topology | Format | Companion field(s) |
| --- | --- | --- |
| `.parm7` / `.prmtop` | AMBER | `coordinates` |
| `.pdb` / `.cif` | OpenMM force field | `forcefield` (the topology file also supplies coordinates) |
| `.top` | GROMACS | `coordinates`, `include_dir` |
| `.psf` | CHARMM | `coordinates`, `parameters` |

Examples:
 
**AMBER topology + AMBER coordinates**:
 
```yaml
system:
  topology: protein.parm7
  coordinates: protein.inpcrd
```
 
**AMBER topology + PDB coordinates**:
 
```yaml
system:
  topology: protein.parm7
  coordinates: protein.pdb
```
 
**PDB topology + OpenMM force fields**:
 
```yaml
system:
  topology: protein.pdb
  forcefield:
    - amber14-all.xml
    - amber14/tip3pfb.xml
```
 
**GROMACS topology + force field files**:

```yaml
system:
  topology: system.top
  coordinates: system.gro
  include_dir: /usr/local/gromacs/share/gromacs/top   # directory holding the force-field include files
```

**CHARMM topology + parameter set** — the box is read from the PDB's `CRYST1` record:

```yaml
system:
  topology: system.psf
  coordinates: system.pdb
  parameters:
    - top_all36_prot.rtf
    - par_all36_prot.prm
    - toppar_water_ions.str
```

### Coordinates and the periodic box

`coordinates` may be any supported coordinate file — `.inpcrd`/`.rst7`, `.gro`, `.pdb`/`.cif`, or CHARMM `.crd` — independent of the topology format, as long as the atom ordering matches. The system is always built from the topology file; the coordinate file only supplies the positions and, when it carries one, the periodic box.

The box used to build the system is resolved in this order:

1. an explicit `box:` block (override);
2. the box found in the coordinate file (`inpcrd` / `gro` / PDB `CRYST1`);
3. the box carried in a `restart_from` (or previous-stage) state.

On restart the saved state's box is also reapplied to the context afterwards, so it is always the box the run actually continues with. (AMBER additionally falls back to the box stored in the prmtop, and `restart_box` covers GROMACS and CHARMM, whose topology files carry no box.)

You only need to give a `box:` explicitly when none of those provide one — e.g. a bare CHARMM `.crd` for a periodic system with no restart. Lengths take units; the angles are degrees and default to 90 (orthorhombic):

```yaml
system:
  topology: system.psf
  coordinates: system.crd
  parameters:
    - par_all36_prot.prm
  box:
    a: 6.0 nm
    b: 6.0 nm
    c: 6.0 nm
```

**Restarting from a previous run** — load positions, velocities, and box vectors from a saved state. Works with any topology format above; `coordinates` becomes optional since the state supplies positions, velocities, and the box:
 
```yaml
system:
  topology: protein.parm7
  restart_from: previous_run/production.xml
```
 
---

## Analysis stages

A stage with `type: analysis` runs one of the `trajectory` commands, using the same arguments and options that command accepts on the CLI:

```yaml
- name: rmsd
  type: analysis
  command: rmsd                # which trajectory command to run
  args:
    trajectory: prod.dcd
    top: ../protein.parm7
    sel: "name CA"
    out: rmsd.csv
```

Keys under `args` mirror the command's CLI flag names — `--sel` becomes `sel:`, `--top` becomes `top:`, `--a` becomes `a:`, and so on. Whatever you'd type on the CLI works here too; running `openmm-cli trajectory <command> --help` shows the available options for any analysis command.

The analysis command runs with its working directory set to `output_dir`, so trajectory paths and output paths are resolved relative to it. Files outside `output_dir` (typically the input topology) need a relative path back out, which is why `top: ../protein.parm7` in the example.

Analysis stages can be interleaved with dynamics stages, but a common pattern is one or more at the end of the workflow to compute standard observables on the production trajectory.

---

## Branching

A `branch` stage forks the run into independent copies: every stage *after* it runs `count` times, each starting from the state at the branch point, in its own `{name}_{i}` subdirectory. The copies share positions, velocities, and box vectors but evolve independently (each gets its own random seed) — a convenient way to launch replicas.

```yaml
stages:
  - { name: equilibrate, type: dynamics, steps: 50000 }
  - { name: replica,     type: branch,   count: 4 }
  - { name: production,  type: dynamics, steps: 2500000 }   # runs in replica_0 .. replica_3
```

A branch consumes the stages that follow it (independent trajectories don't rejoin onto a single state); nest branches to multiply.

---

## Adding a stage type

Stages are auto-discovered from `src/openmm_cli/commands/run/stage_types/` — drop a module there with a `@register_stage`-decorated `StageBase` subclass and nothing else needs to change.

Subclass `SimulationStage` for stages that drive the simulation: the runner builds a fresh simulation for each (run `defaults` + the stage's optional `defaults` override + its `restraints`) and saves the end state, so `run` only advances `runner.simulation`.

Every `SimulationStage` already defines `name` (the stage label, also the saved `{name}.xml`), an optional `defaults` block to override the run-wide integrator/barostat/platform for this stage, `restraints`, and `reporters` — so you only add the fields specific to your stage.

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

For methods that need to construct the simulation differently — e.g. metadynamics or free-energy setups that add forces before the context, or step via their own helper — override `build(self, cfg, defaults, state)`. By default it builds the standard simulation; override it to assemble a custom one (reusing `system.build_system` / `build_integrator` / `make_platform`).

---

## Adding a command

Commands are auto-discovered from `src/openmm_cli/commands/`. The discovery rule is uniform at every level:

- A `.py` file in `commands/` becomes a **top-level command** (`openmm-cli <name>`).
- A folder in `commands/` whose `__init__.py` exposes a `command` function is **also a top-level command** — useful when the command needs supporting modules of its own (this is how `run/` works).
- A folder in `commands/` whose `__init__.py` does *not* expose `command` becomes a **subgroup**; each `.py` file inside becomes a subcommand (`openmm-cli <group> <name>`).
- Files and folders starting with `_` are skipped.

Current layout:

```
src/openmm_cli/commands/
├── run/                  # `openmm-cli run`
│   ├── __init__.py       # exposes `command`
│   ├── run.py
│   └── config.py
├── prepare/              # `openmm-cli prepare ...`
│   ├── __init__.py
│   ├── clean.py
│   ├── solvate.py
│   └── ...
└── trajectory/           # `openmm-cli trajectory ...`
    ├── __init__.py
    ├── rmsd.py
    ├── distance.py
    └── ...
```

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

No `cli.py` edits required. The new command appears as `openmm-cli trajectory my_analysis`.

Conventions worth following:

- **Name the function `command`.** Auto-discovery looks for this exact attribute.
- **Reuse flag names across commands** (`--top`, `--out`, `--sel`, `--ref`) so users don't have to relearn them.
- **Add a docstring to each group's `__init__.py`**; it becomes the `--help` text for the group.

---

## Related projects

`openmm-cli` is inspired by [**OMMProtocol**](https://github.com/insilichem/ommprotocol), which also drives OpenMM through a YAML config organized into stages. Differences from OMMProtocol: `openmm-cli` is built on a modern Python stack (Pydantic for config validation, Typer for the CLI), integrates preparation and trajectory analysis as commands, and is structured so new commands can be added by dropping a single file into the right folder — see [Adding a command](#adding-a-command).

---

## Acknowledgements

Built on [OpenMM](https://openmm.org) for the simulation engine, [mdtraj](https://mdtraj.org) for trajectory analysis, [PDBFixer](https://github.com/openmm/pdbfixer) for system preparation, [Pydantic](https://pydantic.dev) for config validation, and [Typer](https://typer.tiangolo.com) for the CLI.
