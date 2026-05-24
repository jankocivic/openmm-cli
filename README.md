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

## Acknowledgements

Built on [OpenMM](https://openmm.org) for the simulation engine, [mdtraj](https://mdtraj.org) for trajectory analysis, [Pydantic](https://pydantic.dev) for config validation, and [Typer](https://typer.tiangolo.com) for the CLI.

---

## License

MIT
