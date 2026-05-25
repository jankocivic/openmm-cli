# openmm-cli

A command-line interface for running standard molecular dynamics simulations with OpenMM.

`openmm-cli` provides a simple interface for common simulation tasks such as minimization, heating, equilibration, and production runs, with sensible defaults and minimal configuration.

> **Status: work in progress.** The current biggest limitation is that the MD runner accepts only AMBER `.parm7` topologies, with coordinates supplied as either an AMBER `.inpcrd` or a `.pdb` file. Support for other topology formats (GROMACS, CHARMM, OpenMM XML) is planned.

---

## Features

- Run a full MD workflow from a single YAML config (minimize → heat → equilibrate → production)
- Per-stage overrides for temperature, barostat, restraints, and reporters
- Restart from saved states
- Trajectory analysis and processing commands (RMSD, RMSF, distances, dihedrals, H-bonds, imaging, centering, stripping, format conversion)
- System preparation commands (PDB cleanup, solvation, ion placement)
- Built on [OpenMM](https://openmm.org) and [mdtraj](https://mdtraj.org)

---

## Installation

```bash
git clone https://github.com/<user>/openmm-cli.git
cd openmm-cli
uv sync
```

Or with pip:

```bash
pip install -e .
```

Requires Python 3.10+ and a working OpenMM installation (CUDA recommended for production).

> **Platform note:** `openmm-cli` has so far only been tested on Windows via WSL. In principle it should also work on Linux and macOS,  but neither has been verified.

---

## Quick Start

Write a `config.yaml`:

```yaml
system:
  topology: protein.parm7
  coordinates: protein.inpcrd

defaults:
  integrator:
    type: LangevinMiddle
    timestep: 4 fs
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

See `openmm-cli --help` and `openmm-cli trajectory --help` for the full command list.

---

## Related projects

`openmm-cli` is inspired by [**OMMProtocol**](https://github.com/insilichem/ommprotocol) (Rodríguez-Guerra et al.), which also drives OpenMM through a YAML config organized into stages. Differences from OMMProtocol: `openmm-cli` is built on a modern Python stack (Pydantic for config validation, Typer for the CLI), integrates preparation and trajectory analysis commands, and is structured so new commands can be added by dropping a single file into the right folder — see [Adding a command](#adding-a-command) below.

---

## Adding a command
 
Commands are auto-discovered from `src/openmm_cli/commands/`. The discovery rule is uniform at every level:
 
- A `.py` file in `commands/` becomes a **top-level command** (`openmm-cli <name>`).
- A folder in `commands/` whose `__init__.py` exposes a `command` function is **also a top-level command** — useful when the command needs supporting modules of its own (this is how `run/` works).
- A folder in `commands/` whose `__init__.py` does *not* expose `command` becomes a **subgroup**; each `.py` file inside becomes a subcommand (`openmm-cli <group> <name>`).
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
 
Example new trajectory command:
 
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

## Acknowledgements

Built on [OpenMM](https://openmm.org) for the simulation engine, [mdtraj](https://mdtraj.org) for trajectory analysis, [Pydantic](https://pydantic.dev) for config validation, and [Typer](https://typer.tiangolo.com) for the CLI.

---

## License

MIT
