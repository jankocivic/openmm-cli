"""Reporter config models and construction for a dynamics stage.

Owns both the config models (what the user requests in YAML) and the code that
turns them into OpenMM reporters.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from mdtraj.reporters import DCDReporter as MDTrajDCDReporter
from mdtraj.reporters import HDF5Reporter, NetCDFReporter
from openmm import app

from .config import _Base


class TrajectoryReporter(_Base):
    file: Path
    interval: int
    format: (
        Literal["dcd", "xtc", "pdb", "pdbx", "hdf5", "h5", "netcdf", "nc"] | None
    ) = None
    # If None, format is inferred from the file extension.


class ReporterFile(_Base):
    file: Path
    interval: int


class Reporters(_Base):
    trajectory: TrajectoryReporter | None = None  # DCD/XTC/PDB/HDF5/NetCDF
    state: ReporterFile | None = None  # CSV state data
    checkpoint: ReporterFile | None = None  # binary checkpoint


# Trajectory file format -> reporter class.
_TRAJECTORY_REPORTERS = {
    "dcd": MDTrajDCDReporter,
    "xtc": app.XTCReporter,
    "pdb": app.PDBReporter,
    "pdbx": app.PDBxReporter,
    "hdf5": HDF5Reporter,
    "h5": HDF5Reporter,
    "netcdf": NetCDFReporter,
    "nc": NetCDFReporter,
}


def _make_trajectory_reporter(cfg, output_dir: Path):
    """Build the reporter for the requested trajectory format."""
    path = output_dir / cfg.file
    fmt = (cfg.format or path.suffix.lstrip(".")).lower()
    try:
        reporter_cls = _TRAJECTORY_REPORTERS[fmt]
    except KeyError:
        raise ValueError(
            f"Unknown trajectory format {fmt!r} for file {cfg.file}. "
            f"Supported: {', '.join(sorted(_TRAJECTORY_REPORTERS))}."
        )
    return reporter_cls(str(path), cfg.interval)


def _make_state_reporter(cfg, output_dir: Path):
    return app.StateDataReporter(
        str(output_dir / cfg.file),
        cfg.interval,
        step=True,
        time=True,
        potentialEnergy=True,
        kineticEnergy=True,
        totalEnergy=True,
        temperature=True,
        volume=True,
        density=True,
        speed=True,
    )


def _make_progress_reporter(stage_steps: int):
    """Console progress reporter, printed roughly 20 times per stage."""
    return app.StateDataReporter(
        sys.stdout,
        max(1, stage_steps // 20),
        step=True,
        progress=True,
        totalSteps=stage_steps,
        temperature=True,
        speed=True,
        remainingTime=True,
    )


def build_reporters(reporters_cfg: Reporters, stage_steps: int, output_dir: Path) -> list:
    """Build the reporters for a stage (file outputs + console progress)."""
    out = []
    if reporters_cfg.trajectory:
        out.append(_make_trajectory_reporter(reporters_cfg.trajectory, output_dir))
    if reporters_cfg.state:
        out.append(_make_state_reporter(reporters_cfg.state, output_dir))
    if reporters_cfg.checkpoint:
        out.append(
            app.CheckpointReporter(
                str(output_dir / reporters_cfg.checkpoint.file),
                reporters_cfg.checkpoint.interval,
            )
        )
    out.append(_make_progress_reporter(stage_steps))
    return out
