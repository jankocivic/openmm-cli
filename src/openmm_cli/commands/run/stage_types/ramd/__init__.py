"""Random Acceleration MD (RAMD) stage.

Pushes the ligand out of its binding site with a constant force on its center of
mass, re-randomizing the direction whenever it stalls, until the ligand-receptor
COM distance exceeds ``r_max`` or ``max_steps`` is reached. Ligand and receptor
are chosen by mdtraj selection strings; their centers of mass drive the force and
the exit criterion.

The simulation is built the standard way (the runner's default ``build``); this
stage just attaches the RAMD force to it via the ``RAMD`` engine (see
``engine.py``). The stage model lives in ``stage.py``.
"""

from .stage import RAMDStage

__all__ = ["RAMDStage"]
