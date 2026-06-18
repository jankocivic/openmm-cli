"""System sources: build the OpenMM ``System`` + positions/box from input files.

One model per supported input format, sharing a common base (``topology``,
``coordinates``, ``restart_from``, ``box``) and differing only in the format's
extra field and its ``build``. The concrete model is chosen from the topology
file's extension (see ``SOURCE_BY_SUFFIX``), so configs need no ``type`` tag.

All formats follow the same shape: read the coordinate file (positions + box),
hand the box to the topology-file constructor, then ``createSystem``. The box used
at construction is resolved as: explicit ``box`` override -> coordinate-file box ->
the restart/previous-stage ``State``'s box (passed in as ``restart_box``). That
``State`` also reapplies positions/velocities/box to the context afterward (see
``system.build_simulation``), so on restart a box is available even with no
coordinates -- which is what lets GROMACS and CHARMM (whose topology files carry no
box) restart from topology + state alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from openmm import app, unit
from openmm.app.internal.unitcell import computePeriodicBoxVectors
from pydantic import model_validator

from .config import Quantity, SystemSettings, _Base


@dataclass
class BuiltSystem:
    """The OpenMM objects produced from a system source.

    ``positions`` and ``box_vectors`` may be ``None`` when a restart ``State`` is
    expected to supply them.
    """

    topology: app.Topology
    positions: object | None
    box_vectors: object | None
    system: object


# ---- Box + coordinate helpers ----------------------------------------------


class Box(_Base):
    """An explicit unit cell as edge lengths + angles (orthorhombic by default)."""

    a: Quantity
    b: Quantity
    c: Quantity
    alpha: float = 90.0  # degrees
    beta: float = 90.0
    gamma: float = 90.0

    def vectors(self):
        """The periodic box vectors (OpenMM's reduced form, in nanometers)."""
        return computePeriodicBoxVectors(
            self.a,
            self.b,
            self.c,
            self.alpha * unit.degrees,
            self.beta * unit.degrees,
            self.gamma * unit.degrees,
        )


def load_coordinates(path: Path):
    """Return ``(positions, box_vectors | None)`` for a coordinate file.

    Each branch knows that format's box accessor; the box is ``None`` for formats
    that carry none (a bare CHARMM ``.crd``).
    """
    suffix = path.suffix.lower()
    if suffix in (".inpcrd", ".rst7"):
        c = app.AmberInpcrdFile(str(path))
        return c.positions, c.boxVectors
    if suffix == ".gro":
        c = app.GromacsGroFile(str(path))
        return c.positions, c.getPeriodicBoxVectors()
    if suffix == ".pdb":
        c = app.PDBFile(str(path))
        return c.positions, c.topology.getPeriodicBoxVectors()
    if suffix in (".cif", ".pdbx"):
        c = app.PDBxFile(str(path))
        return c.positions, c.topology.getPeriodicBoxVectors()
    if suffix == ".crd":
        c = app.CharmmCrdFile(str(path))
        return c.positions, None
    raise ValueError(f"Unsupported coordinate format: {path.suffix!r}")


def _system_kwargs(s: SystemSettings) -> dict:
    """Shared keyword arguments for every ``createSystem`` call."""
    kw = {
        "nonbondedMethod": getattr(app, s.nonbonded_method),
        "rigidWater": s.rigid_water,
    }
    if s.nonbonded_method != "NoCutoff":
        kw["nonbondedCutoff"] = s.nonbonded_cutoff
    if s.constraints is not None:
        kw["constraints"] = getattr(app, s.constraints)
    if s.hydrogen_mass is not None:
        kw["hydrogenMass"] = s.hydrogen_mass
    return kw


def _is_periodic(s: SystemSettings) -> bool:
    return s.nonbonded_method not in ("NoCutoff", "CutoffNonPeriodic")


# ---- Sources ----------------------------------------------------------------


class SourceBase(_Base):
    """Common inputs for every system source.

    Subclasses add their one format-specific field and implement ``build``. The
    ``box`` field (if set) overrides any box found in the coordinate file.
    """

    topology: Path
    coordinates: Path | None = None
    restart_from: Path | None = None
    box: Box | None = None

    # Topology extensions this source claims (for suffix dispatch).
    suffixes: ClassVar[tuple[str, ...]] = ()
    # Whether positions must come from a file (PDB defaults them to the topology).
    requires_coordinates: ClassVar[bool] = True

    @model_validator(mode="after")
    def _need_positions(self):
        if (
            self.requires_coordinates
            and self.coordinates is None
            and self.restart_from is None
        ):
            raise ValueError(
                f"{type(self).__name__} needs `coordinates` or `restart_from`"
            )
        return self

    def _coords_and_box(self, restart_box=None):
        """Positions and the box to build with.

        Box precedence: explicit ``box`` override -> coordinate-file box ->
        ``restart_box`` (the box carried in a restart/previous-stage ``State``).
        The final box is reapplied to the context by ``setState`` regardless;
        this is just the box needed at construction.
        """
        positions, coord_box = (
            load_coordinates(self.coordinates)
            if self.coordinates is not None
            else (None, None)
        )
        if self.box is not None:
            box = self.box.vectors()
        elif coord_box is not None:
            box = coord_box
        else:
            box = restart_box
        return positions, box

    def build(self, settings: SystemSettings, restart_box=None) -> BuiltSystem:
        raise NotImplementedError


class AmberSource(SourceBase):
    """AMBER prmtop (+ inpcrd/rst7/pdb coordinates)."""

    suffixes: ClassVar[tuple[str, ...]] = (".parm7", ".prmtop")

    def build(self, settings: SystemSettings, restart_box=None) -> BuiltSystem:
        positions, box = self._coords_and_box(restart_box)
        # box may be None; AmberPrmtopFile then reads the box from the prmtop itself.
        prmtop = app.AmberPrmtopFile(str(self.topology), periodicBoxVectors=box)
        system = prmtop.createSystem(**_system_kwargs(settings))
        return BuiltSystem(prmtop.topology, positions, box, system)


class PdbSource(SourceBase):
    """OpenMM force field applied to a PDB/PDBx topology."""

    suffixes: ClassVar[tuple[str, ...]] = (".pdb", ".cif", ".pdbx")
    # the topology file is also the coordinate file, so coordinates are optional
    requires_coordinates: ClassVar[bool] = False
    forcefield: list[str]  # e.g. ["amber14-all.xml", "amber14/tip3pfb.xml"]

    def build(self, settings: SystemSettings, restart_box=None) -> BuiltSystem:
        is_pdbx = self.topology.suffix.lower() in (".cif", ".pdbx")
        pdb = (app.PDBxFile if is_pdbx else app.PDBFile)(str(self.topology))
        system = app.ForceField(*self.forcefield).createSystem(
            pdb.topology, **_system_kwargs(settings)
        )
        if self.coordinates is not None:
            positions, box = self._coords_and_box(restart_box)
        else:
            positions = pdb.positions
            if self.box is not None:
                box = self.box.vectors()
            else:
                box = pdb.topology.getPeriodicBoxVectors()  # CRYST1, may be None
                if box is None:
                    box = restart_box
        return BuiltSystem(pdb.topology, positions, box, system)


class GromacsSource(SourceBase):
    """GROMACS top (+ gro/pdb coordinates), referencing external force-field files."""

    suffixes: ClassVar[tuple[str, ...]] = (".top",)
    include_dir: Path  # GROMACS `share/gromacs/top` with the force-field include files

    def build(self, settings: SystemSettings, restart_box=None) -> BuiltSystem:
        positions, box = self._coords_and_box(restart_box)
        if box is None and _is_periodic(settings):
            raise ValueError(
                "GROMACS source with a periodic nonbonded method needs a box "
                "(from `coordinates`, an explicit `box`, or a restart state)"
            )
        top = app.GromacsTopFile(
            str(self.topology),
            periodicBoxVectors=box,
            includeDir=str(self.include_dir),
        )
        system = top.createSystem(**_system_kwargs(settings))
        return BuiltSystem(top.topology, positions, box, system)


class CharmmSource(SourceBase):
    """CHARMM psf (+ pdb/crd coordinates) with a parameter set.

    Parameters come from an explicit ``parameters`` list and/or a CHARMM-GUI
    ``toppar`` stream file. ``toppar`` must be the *OpenMM* ``toppar.str`` -- the
    one in CHARMM-GUI's generated ``openmm/`` folder that ``openmm_run.py -t``
    consumes, a plain list of file paths (one per line). It is **not** the
    ``toppar.str`` at the job root, which is a CHARMM script and will not parse.
    Paths in the manifest are resolved relative to the manifest file, and only
    ``rtf``/``prm``/``str`` entries are kept (so a listed ``.crd`` is skipped),
    matching CHARMM-GUI's ``read_params``.
    """

    suffixes: ClassVar[tuple[str, ...]] = (".psf",)
    parameters: list[Path] = []   # rtf/prm/str files for CharmmParameterSet
    toppar: Path | None = None    # CHARMM-GUI toppar stream file (a manifest of paths)

    @model_validator(mode="after")
    def _need_parameters(self):
        if not self.parameters and self.toppar is None:
            raise ValueError("CHARMM source needs `parameters` and/or `toppar`")
        return self

    def _parameter_files(self) -> list[str]:
        """Explicit ``parameters`` plus the files listed in a CHARMM-GUI ``toppar``."""
        files = [str(p) for p in self.parameters]
        if self.toppar is not None:
            base = self.toppar.parent
            for line in self.toppar.read_text().splitlines():
                entry = line.split("!", 1)[0].strip()  # drop CHARMM `!` comments
                if not entry:
                    continue
                if entry.rsplit(".", 1)[-1].lower() not in ("rtf", "prm", "str"):
                    continue  # skip non-parameter entries (e.g. .crd), like CHARMM-GUI
                files.append(str((base / entry).resolve()))
        return files

    def build(self, settings: SystemSettings, restart_box=None) -> BuiltSystem:
        positions, box = self._coords_and_box(restart_box)
        if box is None and _is_periodic(settings):
            raise ValueError(
                "CHARMM source with a periodic nonbonded method needs a box "
                "(from `coordinates`, an explicit `box`, or a restart state)"
            )
        # CharmmPsfFile takes the box at construction, just like AMBER/GROMACS.
        psf = app.CharmmPsfFile(str(self.topology), periodicBoxVectors=box)
        params = app.CharmmParameterSet(*self._parameter_files())
        system = psf.createSystem(params, **_system_kwargs(settings))
        return BuiltSystem(psf.topology, positions, box, system)


_SOURCES = (AmberSource, PdbSource, GromacsSource, CharmmSource)

# Topology extension -> source model, for suffix-based dispatch in `config.py`.
SOURCE_BY_SUFFIX: dict[str, type[SourceBase]] = {
    suffix: cls for cls in _SOURCES for suffix in cls.suffixes
}
