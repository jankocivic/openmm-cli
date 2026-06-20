"""Reporter config models and the OpenMM reporters they build.

Each reporter model (trajectory / state / checkpoint) carries its own ``build``,
matching the source/barostat/restraint models. ``build_reporters`` orchestrates
them for a stage and adds the always-on console progress reporter.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from mdtraj.reporters import DCDReporter as MDTrajDCDReporter
from mdtraj.reporters import HDF5Reporter, NetCDFReporter
from openmm import app

from .base import _Base
from .selections import select_atoms

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

# Formats whose (mdtraj-backed) reporters accept an ``atomSubset`` argument.
_SELECTION_FORMATS = {"dcd", "hdf5", "h5", "netcdf", "nc"}


class TrajectoryReporter(_Base):
    file: Path
    interval: int
    format: (
        Literal["dcd", "xtc", "pdb", "pdbx", "hdf5", "h5", "netcdf", "nc"] | None
    ) = None
    # If None, format is inferred from the file extension.
    selection: str | None = None
    # mdtraj selection string (e.g. "protein"); writes only those atoms. Only
    # the mdtraj-backed formats below support this.

    def build(self, output_dir: Path, topology):
        """Build the reporter for the requested trajectory format."""
        path = output_dir / self.file
        fmt = (self.format or path.suffix.lstrip(".")).lower()
        try:
            reporter_cls = _TRAJECTORY_REPORTERS[fmt]
        except KeyError:
            raise ValueError(
                f"Unknown trajectory format {fmt!r} for file {self.file}. "
                f"Supported: {', '.join(sorted(_TRAJECTORY_REPORTERS))}."
            )
        if self.selection is None:
            return reporter_cls(str(path), self.interval)
        if fmt not in _SELECTION_FORMATS:
            raise ValueError(
                f"Trajectory format {fmt!r} does not support atom selection. "
                f"Use one of: {', '.join(sorted(_SELECTION_FORMATS))}."
            )
        atoms = select_atoms(topology, self.selection, label="Trajectory selection")
        return reporter_cls(str(path), self.interval, atomSubset=atoms)


class StateReporter(_Base):
    """CSV of step / time / energies / temperature / volume / density / speed."""

    file: Path
    interval: int

    def build(self, output_dir: Path):
        return app.StateDataReporter(
            str(output_dir / self.file),
            self.interval,
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


class CheckpointReporter(_Base):
    """Binary checkpoint for restarting."""

    file: Path
    interval: int

    def build(self, output_dir: Path):
        return app.CheckpointReporter(str(output_dir / self.file), self.interval)


class Reporters(_Base):
    trajectory: TrajectoryReporter | None = None  # DCD/XTC/PDB/HDF5/NetCDF
    state: StateReporter | None = None  # CSV state data
    checkpoint: CheckpointReporter | None = None  # binary checkpoint


def _make_progress_reporter(stage_steps: int):
    """Console progress reporter, printed roughly 20 times per stage.

    Always added by ``build_reporters`` and not user-configurable, so it stays a
    plain helper rather than a config model.
    """
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


def build_reporters(
    reporters_cfg: Reporters, stage_steps: int, output_dir: Path, topology
) -> list:
    """Build a stage's reporters (configured file outputs + console progress)."""
    out = []
    if reporters_cfg.trajectory:
        out.append(reporters_cfg.trajectory.build(output_dir, topology))
    if reporters_cfg.state:
        out.append(reporters_cfg.state.build(output_dir))
    if reporters_cfg.checkpoint:
        out.append(reporters_cfg.checkpoint.build(output_dir))
    out.append(_make_progress_reporter(stage_steps))
    return out
