# Configuration reference

An `openmm-cli run` workflow is described by a single YAML file passed to `openmm-cli run config.yaml`. This page documents every element of that file and explains how information flows through a run.

The file has five top-level keys:

| Key | Required | Purpose |
| --- | --- | --- |
| `system` | yes | What to simulate — topology, coordinates, and (per format) force-field inputs. |
| `system_settings` | no | How forces are computed (the arguments to `createSystem`). |
| `defaults` | no | How the simulation is built — integrator, barostat, platform. |
| `output_dir` | no | Where outputs are written (default `output`). |
| `stages` | yes | The ordered list of steps to run. |

A minimal file needs only `system` and `stages`; everything else has defaults.

---

## `system`

Selects the input format from the **topology** file's extension and provides the files needed to build the OpenMM `System`. Fields common to every format:

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `topology` | path | — | The topology file. Its extension selects the format. |
| `coordinates` | path | none | Positions (and usually the box). Optional on restart, and for the PDB format (the topology *is* the coordinates). |
| `restart_from` | path | none | A saved state XML; supplies positions, velocities, and box. |
| `box` | block | none | Explicit unit cell, used only when no other source provides one. |

Each format then adds one field:

| Topology | Format | Adds |
| --- | --- | --- |
| `.parm7` / `.prmtop` | AMBER | — (the prmtop is self-contained) |
| `.pdb` / `.cif` | OpenMM force field | `forcefield` — list of force-field XMLs |
| `.top` | GROMACS | `include_dir` — directory of the force-field `.itp` files |
| `.psf` | CHARMM | `parameters` — list of `rtf`/`prm`/`str` files |

The `box` block is edge lengths plus optional angles (degrees, default 90):

```yaml
box:
  a: 6.0 nm
  b: 6.0 nm
  c: 6.0 nm
  # alpha, beta, gamma default to 90
```

### Coordinates and the box

`coordinates` may be any supported coordinate file — `.inpcrd`/`.rst7`, `.gro`, `.pdb`/`.cif`, or CHARMM `.crd` — independent of the topology format, as long as the atom ordering matches. The system is always built from the topology file; the coordinate file only supplies positions and, when it carries one, the periodic box.

The box used to build the system is resolved in order:

1. an explicit `box:` block (override);
2. the box found in the coordinate file (`inpcrd` / `gro` / PDB `CRYST1`);
3. the box carried in a `restart_from` (or previous-stage) state.

On restart the state's box is also reapplied to the context afterwards, so it is always the box the run actually continues with. AMBER additionally falls back to the box stored in the prmtop; GROMACS and CHARMM topology files carry no box, so they rely on the coordinate file, an explicit `box:`, or a restart. You only need an explicit `box:` when none of those provide one — e.g. a bare CHARMM `.crd` for a periodic system with no restart.

A few format examples:

```yaml
# AMBER: prmtop + coordinates (.inpcrd, .rst7, or .pdb)
system: { topology: protein.parm7, coordinates: protein.inpcrd }

# OpenMM force field: the PDB is the topology; coordinates default to it
system:
  topology: protein.pdb
  forcefield: [amber14-all.xml, amber14/tip3pfb.xml]

# GROMACS: top + gro, with the force-field include directory
system:
  topology: system.top
  coordinates: system.gro
  include_dir: /usr/local/gromacs/share/gromacs/top

# CHARMM: psf + coordinates + parameter set (box from the PDB's CRYST1)
system:
  topology: system.psf
  coordinates: system.pdb
  parameters: [charmm22.rtf, charmm22.prm]

# Restart: any format; coordinates optional (the state provides positions + box)
system: { topology: protein.parm7, restart_from: previous_run/production.xml }
```

!!! warning "GROMACS and CHARMM input is experimental"
    The AMBER and OpenMM force-field paths are the well-tested ones. GROMACS (`.top`) and CHARMM (`.psf`) input works in principle but has **not been thoroughly verified** — sanity-check energies and structures before trusting a run.

    Files produced by **CHARMM-GUI** for GROMACS/CHARMM have specifically given trouble (systems blowing apart on minimization). If you build a system with CHARMM-GUI, use the **AMBER-format files** it generates (`.parm7` + `.rst7`/`.inpcrd`) with the AMBER source — those have worked reliably in testing.

---

## `system_settings`

The arguments passed to `createSystem` — how non-bonded forces and constraints are computed. These apply to the whole run (the `System` is rebuilt identically for every stage).

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `nonbonded_method` | `NoCutoff`, `CutoffNonPeriodic`, `CutoffPeriodic`, `Ewald`, `PME`, `LJPME` | `PME` | The non-bonded method. `PME`/`Ewald`/`LJPME`/`CutoffPeriodic` are periodic and require a box. |
| `nonbonded_cutoff` | quantity | `1.0 nm` | Real-space cutoff (ignored for `NoCutoff`). |
| `constraints` | `HBonds`, `AllBonds`, `HAngles`, or null | `HBonds` | Which bonds/angles are constrained. |
| `rigid_water` | bool | `true` | Keep water rigid regardless of `constraints`. |
| `hydrogen_mass` | quantity | none | Hydrogen-mass repartitioning target (enables larger timesteps). |
| `ewald_error_tolerance` | float | `0.0005` | Error tolerance for `Ewald`/`PME`/`LJPME` (ignored otherwise). |
| `switch_distance` | quantity | none | Distance at which the LJ switching function turns on. None = no switching. Must be < `nonbonded_cutoff`. |
| `remove_cm_motion` | bool | `true` | Add a center-of-mass motion remover. |

---

## `defaults`

How each stage's simulation is constructed. A fresh `Simulation` is built for every simulation stage from this block; a stage may override any part of it with its own `defaults` block (see [per-stage overrides](#per-stage-defaults-overrides)).

| Field | Type | Default |
| --- | --- | --- |
| `integrator` | block | `LangevinMiddle`, 2 fs, 300 K |
| `barostat` | block or null | none (NVT/NVE) |
| `platform` | block | `CPU`, mixed precision |

### `integrator`

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `type` | `LangevinMiddle`, `Langevin`, `Verlet` | `LangevinMiddle` | Integrator. `Verlet` is NVE (no thermostat). |
| `timestep` | quantity | `2 fs` | Integration timestep. |
| `temperature` | quantity | `300 K` | Thermostat target (also the barostat's coupling temperature). |
| `friction` | quantity | `1.0 /ps` | Langevin collision frequency (ignored by `Verlet`). |

### `barostat`

Adding a `barostat` makes the ensemble NPT. It requires a thermostatted integrator (not `Verlet`) and a periodic `nonbonded_method`. All types share `frequency` (steps between volume-move attempts, default `25`). Pick a type:

```yaml
# Isotropic — scales the box uniformly (the usual choice)
barostat: { type: isotropic, pressure: 1 atm, frequency: 25 }

# Anisotropic — independent pressure per axis, optionally freezing axes
barostat:
  type: anisotropic
  pressure: [1 atm, 1 atm, 1 atm]
  scale_x: true
  scale_y: true
  scale_z: true

# Membrane — for bilayers, with a surface tension and XY/Z coupling modes
barostat:
  type: membrane
  pressure: 1 atm
  surface_tension: 0.0 bar*nm
  xy_mode: isotropic        # isotropic | anisotropic
  z_mode: free              # free | fixed | constant_volume
```

### `platform`

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `name` | `CUDA`, `OpenCL`, `CPU`, `Reference` | `CPU` | Compute platform. |
| `precision` | `single`, `mixed`, `double` | `mixed` | Used by `CUDA`/`OpenCL` only. |
| `device_index` | string | none | GPU selection, e.g. `"0"` or `"0,1"` (CUDA/OpenCL only). |

---

## `output_dir`

Directory for all outputs (default `output`). The runner creates it, writes a `resolved_config.yaml` (the full config with every default filled in, for reproducibility), and resolves each stage's reporter/analysis paths relative to it. Each simulation stage also saves its end state as `{stage_name}.xml` here.

**Resuming.** Re-running into an existing `output_dir` continues automatically: any simulation stage whose `{stage_name}.xml` is already present is skipped and its saved state carried forward, so an interrupted run picks up from the last completed stage. State files are written atomically, so a stage interrupted mid-write is treated as incomplete and re-run. The config is assumed unchanged between runs — if you change it, use a fresh `output_dir` (or delete the old outputs), since stale stages would otherwise be skipped.

---

## `stages`

An ordered list of steps. Every stage has a `name` (a label, also used for its saved `{name}.xml`) and a `type` that selects its behavior. See the [Stage types](stages.md) page for the fields of each type.

Stages fall into two groups:

- **Simulation stages** (`minimization`, `dynamics`, `heat`, `ramd`) advance a freshly-built simulation. They share three optional blocks — `defaults`, `restraints`, and `reporters` — described below.
- **Control / analysis stages** (`branch`, `analysis`) don't build a simulation; they steer the pipeline or post-process outputs.

### Per-stage `defaults` overrides

A simulation stage may carry a partial `defaults` block that overrides the run-wide `defaults` *for that stage only*. The merge rules:

- `integrator` and `platform` merge **field-wise** — only the keys you set change; the rest inherit. So "raise the temperature for this stage" is just `defaults: { integrator: { temperature: 310 K } }`.
- `barostat` is **whole-replaced** — give a full barostat block to change it, or `barostat: null` to switch it off (e.g. an NVT equilibration between NPT stages). Omitting it inherits the run-wide barostat.

### `restraints`

A list of restraint forces added to the stage's system at build time and discarded with it (restraints never carry between stages). Currently one type:

```yaml
restraints:
  - type: positional
    selection: "not water and not element H"   # mdtraj selection
    force_constant: 1000 kJ/mol/nm^2
```

A `positional` restraint harmonically tethers the selected atoms to their starting positions (the carried state's positions on a restart, otherwise the input coordinates).

### `reporters`

Output writers attached to a simulation stage. Three kinds, all optional, each taking a `file` (resolved under `output_dir`) and an `interval` in steps:

```yaml
reporters:
  trajectory: { file: prod.dcd, interval: 5000 }
  state:      { file: prod.csv, interval: 1000 }
  checkpoint: { file: prod.chk, interval: 50000 }
```

- **trajectory** — coordinates over time. Format inferred from the extension or set with `format:` (`dcd`, `xtc`, `pdb`, `pdbx`, `hdf5`/`h5`, `netcdf`/`nc`). Add `selection:` (an mdtraj selection) to store only some atoms — supported for `dcd`, `hdf5`/`h5`, `netcdf`/`nc` only. The mdtraj-backed formats (`dcd`, `hdf5`/`h5`, `netcdf`/`nc`) store coordinates in single precision, so a one-time `TypeCastPerformanceWarning` about casting `float64` → `float32` is expected and harmless; the simulation's own precision is unaffected.
- **state** — CSV of step, time, energies, temperature, volume, density, speed.
- **checkpoint** — binary checkpoint for restarting.

A console progress reporter is added automatically and needs no configuration.

---

## Flow of information

Understanding the order in which things happen clarifies which settings affect what.

**1. Parse and validate.** The YAML is loaded into a Pydantic `Config`. The `system` model is chosen from the topology extension; each stage is built into its registered type from its `type` tag. Unknown keys are rejected. Each simulation stage is then validated against its *resolved* settings (run `defaults` merged with the stage's override) — e.g. a barostat is rejected under a `Verlet` integrator or a non-periodic method.

**2. Set up the run.** The runner creates `output_dir`, writes `resolved_config.yaml`, and — if `system.restart_from` is given — deserializes it into an OpenMM `State`. That state is the starting point carried into the first stage.

**3. Run each stage in order.** For a **simulation stage**:

- Resolve `defaults` (run-wide merged with the stage's override).
- Build a *fresh* `Simulation`: the `System` from the `system` source (plus the resolved `barostat` and the stage's `restraints`), the integrator and platform from the resolved `defaults`.
- Seed the context — from the carried `State` (positions, velocities, box) if there is one, otherwise from the input files. The step counter and clock are reset to zero.
- Run the stage (`run` only advances `runner.simulation`).
- Capture the end `State` (positions + velocities + box) and save it as `{name}.xml`.

A **`branch`** stage instead re-runs all *following* stages `count` times, each starting from the current state, in `{name}_{i}` subdirectories. An **`analysis`** stage runs without building a simulation and leaves the carried state unchanged.

**4. What carries between stages.** Only the OpenMM `State` — positions, velocities, and box vectors — flows from one stage to the next. Forces do **not**: the system, barostat, and restraints are rebuilt fresh each stage from that stage's resolved config. So a restraint or barostat applied in one stage has no effect on the next unless that stage declares it too. This is what makes a workflow like *minimize → restrained heat → unrestrained NPT equilibration → production* behave exactly as written, with each stage's forces being precisely what its config specifies.
