# Example: Fluorescent Protein from AMBER inputs

`openmm-cli` workflow starting from a pre-built AMBER topology (`fp.parm7`) and matching coordinates (`fp.pdb`). The system is already parametrised and solvated, so no preparation is needed — this example focuses on the simulation and analysis pipeline.

## What this example does

1. **Simulates** with `run config.yaml` through four stages:
   - **Minimize** energy.
   - **Heat** from 100 K to 300 K over 10 ps under NVT, with heavy-atom restraints (1000 kJ/mol/nm²) keeping the protein essentially fixed.
   - **Equilibrate** at 300 K and 1 atm for 20 ps under NPT, with looser CA-only restraints (100 kJ/mol/nm²) allowing side-chain relaxation.
   - **Production** at 300 K and 1 atm for 20 ps, no restraints; trajectory written every 1 ps.
2. **Analyzes** the production trajectory inline:
   - `rmsd` — Cα RMSD vs the starting structure (`rmsd.csv`).
   - `hbonds` — protein hydrogen bonds present in ≥50 % of frames, sorted by occupancy (`hbonds.csv`).

## Files

- `fp.parm7` — AMBER topology (input, must be provided)
- `fp.pdb` — matching coordinates (input, must be provided)
- `config.yaml` — simulation + analysis configuration
- `run.sh` — runs the pipeline
- `output/` — created by `run`, contains state XMLs per stage, the production trajectory, the analysis CSVs, and the state CSVs

## Running

```bash
bash run.sh
```

Or directly:

```bash
openmm-cli run config.yaml
```

## Runtime

The simulation is 50 ps total (~25 000 integration steps). On a modern CPU expect to finish within 1 hour; on a CUDA GPU it should finish in a couple of minutes. To run faster, set `platform.name: CUDA` in `config.yaml`.

## Notes

This example contrasts with the `253L/` example: there we start from a raw PDB and use `prepare clean` + `prepare solvate` followed by an OpenMM force field. Here the system is already prepared before (e.g. with AmberTools' `tleap`), so the runner uses the AMBER topology directly. The MD protocol and analysis stages are otherwise identical, which is the point — once the system is in place, the simulation workflow is the same regardless of how the topology was built.
