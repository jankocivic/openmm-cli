# openmm-cli

A command-line interface for running standard molecular dynamics simulations with OpenMM.

`openmm-cli` provides a simple interface for common simulation tasks such as minimization, heating, equilibration, and production runs, with sensible defaults and minimal configuration.

> **Status: work in progress.** The tool currently supports AMBER topologies (`.parm7` / `.prmtop`) and OpenMM force field workflows (PDB topology + force field XMLs); other formats (GROMACS, CHARMM, ...) are planned.

---

## Features

- Run a full MD workflow from a single YAML config (minimize → heat → equilibrate → production)
- Supports restraints
- Restart from saved states
- Trajectory analysis and processing commands (RMSD, RMSF, distances, dihedrals, H-bonds, imaging, centering, stripping, format conversion)
- System preparation commands (PDB cleanup, solvation, ion placement)
- Built on [OpenMM](https://openmm.org) and [mdtraj](https://mdtraj.org)

---

## Installation

```bash
git clone https://github.com/jankocivic/openmm-cli.git
cd openmm-cli
uv sync
source .venv/bin/activate # Activate virtual environment, should be done every terminal session
```

Or with pip inside a virtual environment created with for example conda:

```bash
pip install -e .
```

Enable autocompletion of commands:

```bash
openmm-cli --install-completion # Applies only after restarting the terminal
```


Requires Python 3.10+ and a working OpenMM installation (CUDA recommended for production).

> **Platform note:** `openmm-cli` has so far only been tested on Linux via Windows WSL. It should work on macOS, but not verified.

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
    initialize_velocities: true
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

## Specifying the system
 
The `system` block supports a few input combinations:
 
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
 
**PDB topology + OpenMM force field** — no AMBER tooling required; the PDB carries the topology, and OpenMM's bundled force field XMLs parametrise it:
 
```yaml
system:
  topology: protein.pdb
  forcefield:
    - amber14-all.xml
    - amber14/tip3pfb.xml
```
 
**Restarting from a previous run** — load positions, velocities, and box vectors from a saved state. Works alongside any topology source above; `coordinates` becomes optional since the state XML provides positions:
 
```yaml
system:
  topology: protein.parm7
  restart_from: previous_run/production.xml
```
 
Set `initialize_velocities: false` on the first stage of a restart run, or the loaded velocities will be discarded.
 
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
    ├── solvate.py
    └── ...
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

`openmm-cli` is inspired by [**OMMProtocol**](https://github.com/insilichem/ommprotocol) (Rodríguez-Guerra et al.), which also drives OpenMM through a YAML config organized into stages. Differences from OMMProtocol: `openmm-cli` is built on a modern Python stack (Pydantic for config validation, Typer for the CLI), integrates preparation and trajectory analysis as commands, and is structured so new commands can be added by dropping a single file into the right folder — see [Adding a command](#adding-a-command) below.

---

## Acknowledgements

Built on [OpenMM](https://openmm.org) for the simulation engine, [mdtraj](https://mdtraj.org) for trajectory analysis, [PDBFixer](https://github.com/openmm/pdbfixer) for system preparation, [Pydantic](https://pydantic.dev) for config validation, and [Typer](https://typer.tiangolo.com) for the CLI.
