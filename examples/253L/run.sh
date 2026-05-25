#!/usr/bin/env bash
# Full pipeline: clean -> solvate -> simulate -> analyze.
# 1. Clean the PDB: strip crystallographic water and heteroatoms,
#    add missing side-chain atoms, add hydrogens at pH 7.4.
openmm-cli prepare clean 253L.pdb --out cleaned.pdb

# 2. Solvate in a cubic water box with 0.15 M NaCl, 1 nm padding.
openmm-cli prepare solvate cleaned.pdb --out solvated.pdb --padding 1.0

# 3. Run the simulation + inline analysis described in config.yaml.
openmm-cli run config.yaml
