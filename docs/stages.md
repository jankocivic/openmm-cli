# Stage types

A workflow is an ordered list under `stages`. Every stage has a `name` and a `type`; the `type` selects one of the models below. This page documents each. For the shared `defaults` / `restraints` / `reporters` blocks and the run-wide settings, see the [Configuration reference](configuration.md).

## What every simulation stage provides

`minimization`, `dynamics`, `heat`, and `ramd` are *simulation stages*: the runner builds a fresh `Simulation` for each (from the resolved `defaults` plus the stage's `restraints`), seeds it from the state carried in from the previous stage, runs the stage, and saves the resulting state as `{name}.xml`. They all accept these optional blocks in addition to their own fields:

| Field | Purpose |
| --- | --- |
| `defaults` | Override the run-wide integrator/barostat/platform for this stage only (see [per-stage overrides](configuration.md#per-stage-defaults-overrides)). |
| `restraints` | Restraint forces added to this stage's system and discarded after it. |
| `reporters` | Trajectory / state / checkpoint output for this stage. |

`branch` and `analysis` are *control* stages: they don't build a simulation and don't take these blocks.

---

## `minimization`

Energy-minimizes the current coordinates. No dynamics are run.

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `max_iterations` | int | `0` | Maximum minimizer iterations; `0` means run until convergence. |
| `tolerance` | quantity | `10 kJ/mol/nm` | Convergence tolerance on the maximum force. |

```yaml
- name: minimize
  type: minimization
  max_iterations: 5000
```

Restraints declared on the stage are in effect during minimization.

---

## `dynamics`

Standard MD: integrate the system for a fixed number of steps. This is the workhorse stage for equilibration and production.

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `steps` | int | — | Number of integration steps. |
| `randomize_velocities` | quantity | none | If set, draw fresh velocities from a Boltzmann distribution at this temperature before running. |

```yaml
- name: production
  type: dynamics
  steps: 2500000
  randomize_velocities: 300 K
  reporters:
    trajectory: { file: prod.dcd, interval: 5000 }
    state:      { file: prod.csv, interval: 1000 }
```

The ensemble follows the resolved `defaults`: a thermostatted integrator gives NVT, adding a barostat gives NPT, `Verlet` gives NVE.

---

## `heat`

Linearly ramps the thermostat temperature from `start_temperature` to `temperature` over `steps`, in `n_chunks` equal segments. Useful for gently warming a freshly minimized system. Requires a thermostatted integrator (not `Verlet`).

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `steps` | int | — | Total integration steps over the ramp. |
| `start_temperature` | quantity | — | Temperature at the start of the ramp. |
| `temperature` | quantity | — | Target temperature at the end of the ramp. |
| `n_chunks` | int | `100` | Number of equal segments the ramp is split into. |

```yaml
- name: heat
  type: heat
  steps: 100000
  start_temperature: 50 K
  temperature: 300 K
  restraints:
    - type: positional
      selection: "not water and not element H"
      force_constant: 1000 kJ/mol/nm^2
```

---

## `ramd`

Random Acceleration Molecular Dynamics. A constant force of fixed `magnitude` is applied to the ligand's center of mass in a random direction, re-randomized whenever the ligand fails to advance, until it leaves the binding site — useful for probing ligand egress routes. Ligand and receptor are chosen by mdtraj selection strings.

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `ligand` | string | — | mdtraj selection; its center of mass is pushed. |
| `receptor` | string | none | mdtraj selection; its COM defines the exit distance. |
| `magnitude` | quantity | `14 kcal/mol/angstrom` | Force magnitude on the ligand COM. |
| `ramd_steps` | int | `50` | MD steps between stall checks. |
| `r_min` | quantity | `0.025 angstrom` | Minimum COM advance per check; below it, the direction is re-randomized. |
| `r_max` | quantity | `30 angstrom` | Stop once the ligand–receptor COM distance exceeds this. |
| `max_steps` | int | `1000000` | Hard cap on total steps. |
| `log_freq` | int | `50` | How often (in steps) to log progress to `ramd.log`. |

```yaml
- name: unbind
  type: ramd
  ligand: "resname LIG"
  receptor: "protein"
  magnitude: 14 kcal/mol/angstrom
  reporters:
    trajectory: { file: ramd.dcd, interval: 5000 }
```

Only `ligand` is required. The RAMD engine logs to `ramd.log` in the output directory; the console shows the standard progress reporter.

---

## `branch`

Forks the run into independent copies: every stage *after* the branch runs `count` times, each starting from the state at the branch point, in its own `{name}_{i}` subdirectory. The copies share positions, velocities, and box but evolve independently (each gets its own random seed) — a convenient way to launch replicas.

| Field | Type | Meaning |
| --- | --- | --- |
| `count` | int | Number of independent copies. |

```yaml
stages:
  - { name: equilibrate, type: dynamics, steps: 50000 }
  - { name: replica,     type: branch,   count: 4 }
  - { name: production,  type: dynamics, steps: 2500000 }   # runs in replica_0 .. replica_3
```

A branch consumes the stages that follow it (independent trajectories don't rejoin); nest branches to multiply.

---

## `analysis`

Runs one of the `trajectory` commands as a pipeline step, from within `output_dir`. Lets you compute observables on a just-produced trajectory as part of the run.

| Field | Type | Meaning |
| --- | --- | --- |
| `command` | string | Which `trajectory` subcommand to run, e.g. `rmsd`. |
| `args` | mapping | Arguments, with keys matching the command's CLI flag names. |

```yaml
- name: rmsd
  type: analysis
  command: rmsd
  args:
    trajectory: prod.dcd
    top: ../protein.parm7
    sel: "name CA"
    out: rmsd.csv
```

Keys under `args` mirror the CLI flags (`--sel` → `sel:`, `--top` → `top:`). The command runs with its working directory set to `output_dir`, so trajectory and output paths are relative to it; files outside it (the input topology) need a path back out, e.g. `top: ../protein.parm7`. Run `openmm-cli trajectory <command> --help` to see a command's options.

---

## Adding your own

Stage types are auto-discovered from `src/openmm_cli/commands/run/stage_types/`. Dropping in a module with a `@register_stage`-decorated class adds a new `type:`. See [Adding a stage type](index.md#adding-a-stage-type) on the home page for the template and the `build()` seam used by methods that construct the simulation differently (metadynamics, free-energy, etc.).
