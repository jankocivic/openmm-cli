"""Construction of the OpenMM system, integrator and platform from config.

These helpers turn the static configuration (see :mod:`.config`) into the live
OpenMM objects needed to build a ``Simulation``. They are deliberately free of
any simulation-driving logic so they can be reused and tested in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass

import openmm as mm
from openmm import app

from .config import Config, IntegratorConfig


@dataclass
class BuiltSystem:
    """The OpenMM objects produced from the configured system sources.

    ``positions`` and ``box_vectors`` may be ``None`` when a restart file is
    expected to supply them.
    """

    topology: app.Topology
    positions: object | None
    box_vectors: object | None
    system: mm.System


def _create_system_kwargs(cfg: Config) -> dict:
    """Shared keyword arguments for ``createSystem``."""
    ss = cfg.system_settings
    kwargs = {
        "nonbondedMethod": getattr(app, ss.nonbonded_method),
        "rigidWater": ss.rigid_water,
    }
    if ss.nonbonded_method != "NoCutoff":
        kwargs["nonbondedCutoff"] = ss.nonbonded_cutoff
    if ss.constraints is not None:
        kwargs["constraints"] = getattr(app, ss.constraints)
    if ss.hydrogen_mass is not None:
        kwargs["hydrogenMass"] = ss.hydrogen_mass
    return kwargs


def _build_amber_system(cfg: Config, kwargs: dict) -> BuiltSystem:
    prmtop = app.AmberPrmtopFile(str(cfg.system.topology))
    system = prmtop.createSystem(**kwargs)

    if cfg.system.coordinates is None:
        # A restart file will provide positions and box vectors.
        return BuiltSystem(prmtop.topology, None, None, system)

    if cfg.system.coordinates.suffix.lower() == ".pdb":
        coords = app.PDBFile(str(cfg.system.coordinates))
    else:
        coords = app.AmberInpcrdFile(str(cfg.system.coordinates))
    box = (
        getattr(coords, "boxVectors", None)
        or coords.topology.getPeriodicBoxVectors()
    )
    return BuiltSystem(prmtop.topology, coords.positions, box, system)


def _build_pdb_system(cfg: Config, kwargs: dict) -> BuiltSystem:
    pdb = app.PDBFile(str(cfg.system.topology))
    forcefield = app.ForceField(*cfg.system.forcefield)
    system = forcefield.createSystem(pdb.topology, **kwargs)
    return BuiltSystem(
        pdb.topology,
        pdb.positions,
        pdb.topology.getPeriodicBoxVectors(),
        system,
    )


def build_system(cfg: Config) -> BuiltSystem:
    """Build the OpenMM system from the configured topology/coordinates."""
    kwargs = _create_system_kwargs(cfg)
    suffix = cfg.system.topology.suffix.lower()
    if suffix in (".parm7", ".prmtop"):
        return _build_amber_system(cfg, kwargs)
    return _build_pdb_system(cfg, kwargs)


_INTEGRATORS = {
    "LangevinMiddle": lambda c: mm.LangevinMiddleIntegrator(
        c.temperature, c.friction, c.timestep
    ),
    "Langevin": lambda c: mm.LangevinIntegrator(
        c.temperature, c.friction, c.timestep
    ),
    "Verlet": lambda c: mm.VerletIntegrator(c.timestep),
}


def build_integrator(cfg: IntegratorConfig) -> mm.Integrator:
    """Construct the integrator named by ``cfg.type``."""
    try:
        factory = _INTEGRATORS[cfg.type]
    except KeyError:
        raise ValueError(f"Unknown integrator type: {cfg.type}")
    return factory(cfg)


def build_platform(cfg: Config) -> tuple[mm.Platform, dict[str, str]]:
    """Return the platform and its property dict for ``Simulation``."""
    platform = mm.Platform.getPlatformByName(cfg.platform.name)
    props: dict[str, str] = {}
    if cfg.platform.name in ("CUDA", "OpenCL"):
        props[f"{cfg.platform.name}Precision"] = cfg.platform.precision
        if cfg.platform.device_index is not None:
            props[f"{cfg.platform.name}DeviceIndex"] = cfg.platform.device_index
    return platform, props
