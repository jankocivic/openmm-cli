#!/usr/bin/env bash
# Run the simulation + analysis described in config.yaml.
# Expects fp.parm7 and fp.pdb already present in this directory.
openmm-cli run config.yaml
