# Example: T4 Lysozyme L99A (PDB 253L)

End-to-end `openmm-cli` workflow starting from a raw PDB file: clean → solvate → simulate → analyze. T4 lysozyme L99A is a small (~162 residue) globular protein.

## What this example does

1. **Cleans** the structure with `prepare clean`: strips crystallographic waters and heteroatoms, fills in missing side-chain atoms, and adds hydrogens at pH 7.4 — output: `cleaned.pdb`.
2. **Solvates** with `prepare solvate`: adds a cubic TIP3P water box with 1 nm padding around the protein and brings the system to 0.15 M NaCl — output: `solvated.pdb`.
3. **Simulates** with `run config.yaml` through four stages:
   - **Minimize** energy.
   - **Heat** from 100 K to 300 K over 10 ps under NVT, with heavy-atom restraints (1000 kJ/mol/nm²) keeping the protein essentially fixed.
   - **Equilibrate** at 300 K and 1 atm for 20 ps under NPT, with looser CA-only restraints (100 kJ/mol/nm²) allowing side-chain relaxation.
   - **Production** at 300 K and 1 atm for 20 ps, no restraints; trajectory written every 1 ps.
4. **Analyzes** the production trajectory:
   - `rmsd` — Cα RMSD vs the starting structure (`rmsd.csv`).
   - `hbonds` — protein hydrogen bonds present in ≥50 % of frames, sorted by occupancy (`hbonds.csv`).

## Files

- `253L.pdb` — input structure 
- `config.yaml` — simulation + analysis configuration
- `run.sh` — runs the full pipeline
- `cleaned.pdb`, `solvated.pdb` — intermediate outputs from the prepare commands
- `output/` — created by `run`, contains state XMLs per stage, the production trajectory, the analysis CSVs, and the state CSVs

## Running

```bash
bash run.sh
```

Or step by step:

```bash
openmm-cli prepare clean 253L.pdb --out cleaned.pdb
openmm-cli prepare solvate cleaned.pdb --out solvated.pdb --padding 1.0
openmm-cli run config.yaml
```

## Runtime

The simulation is 50 ps total (~25 000 integration steps). On a modern CPU expect roughly within 1 hour; on a CUDA GPU it should finish in a couple of minutes. To run faster, set `platform.name: CUDA` in `config.yaml`.

## Notes

This example uses an OpenMM force field (Amber14 + TIP3P-FB) directly from the PDB — no AMBER tooling needed. The same workflow would also work with an AMBER `.parm7` topology by changing the `system` block accordingly; see the main README's "Specifying the system" section.

The simulation is deliberately short for a demonstration. For meaningful science you'd typically extend production to tens or hundreds of nanoseconds.
