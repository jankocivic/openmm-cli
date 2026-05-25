"""Run an MD simulation from a YAML config."""
from __future__ import annotations

import sys
from typing import Annotated
from pathlib import Path
import typer

import mdtraj as md
import openmm as mm
import yaml
from openmm import app, unit

from .config import (
    BarostatConfig,
    Config,
    DynamicsStage,
    AnalysisStage,
    IntegratorConfig,
    MinimizationStage,
    PositionalRestraint,
)


# ---- Construction helpers --------------------------------------------------

def build_system(cfg: Config):
    """Returns (topology, positions, box_vectors, system)."""
    top_path = cfg.system.topology
    suffix = top_path.suffix.lower()
    ss = cfg.system_settings

    # Shared createSystem kwargs
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

    if suffix in (".parm7", ".prmtop"):
        prmtop = app.AmberPrmtopFile(str(top_path))
        system = prmtop.createSystem(**kwargs)
        if cfg.system.coordinates is not None:
            if cfg.system.coordinates.suffix.lower() == ".pdb":
                coords = app.PDBFile(str(cfg.system.coordinates))
            else:
                coords = app.AmberInpcrdFile(str(cfg.system.coordinates))
            positions = coords.positions
            box = getattr(coords, "boxVectors", None) or coords.topology.getPeriodicBoxVectors()
        else:
            positions, box = None, None  # restart will provide them
        return prmtop.topology, positions, box, system

    else:  # .pdb
        pdb = app.PDBFile(str(top_path))
        forcefield = app.ForceField(*cfg.system.forcefield)
        system = forcefield.createSystem(pdb.topology, **kwargs)
        return pdb.topology, pdb.positions, pdb.topology.getPeriodicBoxVectors(), system


def build_integrator(cfg: IntegratorConfig) -> mm.Integrator:
    if cfg.type == "LangevinMiddle":
        return mm.LangevinMiddleIntegrator(cfg.temperature, cfg.friction, cfg.timestep)
    if cfg.type == "Langevin":
        return mm.LangevinIntegrator(cfg.temperature, cfg.friction, cfg.timestep)
    if cfg.type == "Verlet":
        return mm.VerletIntegrator(cfg.timestep)
    raise ValueError(f"Unknown integrator type: {cfg.type}")


def build_platform(cfg: Config):
    platform = mm.Platform.getPlatformByName(cfg.platform.name)
    props: dict[str, str] = {}
    if cfg.platform.name in ("CUDA", "OpenCL"):
        props[f"{cfg.platform.name}Precision"] = cfg.platform.precision
        if cfg.platform.device_index is not None:
            props[f"{cfg.platform.name}DeviceIndex"] = cfg.platform.device_index
    return platform, props


# ---- Restraints ------------------------------------------------------------

def _select_atoms(omm_topology, selection: str):
    mdt_top = md.Topology.from_openmm(omm_topology)
    indices = mdt_top.select(selection)
    if len(indices) == 0:
        raise ValueError(f"Selection {selection!r} matched no atoms")
    return [int(i) for i in indices]


def _make_positional_restraint_force(r: PositionalRestraint, omm_topology, positions):
    force = mm.CustomExternalForce("0.5*k*((x-x0)^2 + (y-y0)^2 + (z-z0)^2)")
    force.addGlobalParameter("k", r.force_constant)
    force.addPerParticleParameter("x0")
    force.addPerParticleParameter("y0")
    force.addPerParticleParameter("z0")

    for i in _select_atoms(omm_topology, r.selection):
        p = positions[i].value_in_unit(unit.nanometer)
        force.addParticle(i, [p[0], p[1], p[2]])
    return force


def apply_restraints(simulation, system, omm_topology, restraints, prev_indices):
    for idx in sorted(prev_indices, reverse=True):
        system.removeForce(idx)

    new_indices: list[int] = []
    if restraints:
        state = simulation.context.getState(getPositions=True)
        positions = state.getPositions()
        for r in restraints:
            if r.type == "positional":
                f = _make_positional_restraint_force(r, omm_topology, positions)
                new_indices.append(system.addForce(f))

    simulation.context.reinitialize(preserveState=True)
    return new_indices


# ---- Barostat handling -----------------------------------------------------

def _find_barostat(system):
    for i, f in enumerate(system.getForces()):
        if isinstance(f, mm.MonteCarloBarostat):
            return i, f
    return None, None


def configure_barostat(simulation, system, cfg: Config, stage: DynamicsStage):
    idx, barostat = _find_barostat(system)
    if barostat is None:
        return

    default_b = cfg.defaults.barostat
    stage_b: BarostatConfig | None = stage.barostat or default_b

    if stage.disable_barostat:
        barostat.setFrequency(0)
    elif stage_b is not None:
        barostat.setFrequency(stage_b.frequency)
        barostat.setDefaultPressure(stage_b.pressure)
        T = (stage.integrator.temperature if stage.integrator
             else cfg.defaults.integrator.temperature)
        barostat.setDefaultTemperature(T)

    simulation.context.reinitialize(preserveState=True)


# ---- Reporters -------------------------------------------------------------

_TRAJECTORY_REPORTERS = {
    "dcd": app.DCDReporter,
    "xtc": app.XTCReporter,
    "pdb": app.PDBReporter,
    "pdbx": app.PDBxReporter,
}


def _make_trajectory_reporter(cfg, output_dir: Path):
    """Build the right reporter for the requested trajectory format."""
    path = output_dir / cfg.file
    fmt = (cfg.format or path.suffix.lstrip(".")).lower()

    if fmt in _TRAJECTORY_REPORTERS:
        return _TRAJECTORY_REPORTERS[fmt](str(path), cfg.interval)
    if fmt in ("h5", "hdf5"):
        from mdtraj.reporters import HDF5Reporter
        return HDF5Reporter(str(path), cfg.interval)
    if fmt in ("nc", "netcdf"):
        from mdtraj.reporters import NetCDFReporter
        return NetCDFReporter(str(path), cfg.interval)
    raise ValueError(
        f"Unknown trajectory format {fmt!r} for file {cfg.file}. "
        f"Supported: dcd, xtc, pdb, pdbx, hdf5/h5, netcdf/nc."
    )


def build_reporters(reporters_cfg, stage_steps: int, output_dir: Path):
    out = []
    if reporters_cfg.trajectory:
        out.append(_make_trajectory_reporter(reporters_cfg.trajectory, output_dir))
    if reporters_cfg.state:
        path = output_dir / reporters_cfg.state.file
        out.append(app.StateDataReporter(
            str(path), reporters_cfg.state.interval,
            step=True, time=True,
            potentialEnergy=True, kineticEnergy=True, totalEnergy=True,
            temperature=True, volume=True, density=True, speed=True,
        ))
    if reporters_cfg.checkpoint:
        path = output_dir / reporters_cfg.checkpoint.file
        out.append(app.CheckpointReporter(str(path), reporters_cfg.checkpoint.interval))
    out.append(app.StateDataReporter(
        sys.stdout, max(1, stage_steps // 20),
        step=True, progress=True, totalSteps=stage_steps,
        temperature=True, speed=True, remainingTime=True,
    ))
    return out


# ---- State I/O -------------------------------------------------------------

def save_state(simulation, path: Path):
    state = simulation.context.getState(
        getPositions=True, getVelocities=True, getEnergy=True,
        enforcePeriodicBox=True,
    )
    with open(path, "w") as f:
        f.write(mm.XmlSerializer.serialize(state))


# ---- Analysis helper -------------------------------------------------------

def _cli_args_to_kwargs(func, args: dict) -> dict:
    """Translate YAML keys (matching --flag names) to Python parameter names."""
    from typing import get_type_hints

    cli_to_py = {}
    hints = get_type_hints(func, include_extras=True)
    for py_name, hint in hints.items():
        cli_name = py_name
        for meta in getattr(hint, "__metadata__", ()):
            # Typer stores positional flag args in `default` until command-building time
            decls = list(getattr(meta, "param_decls", None) or [])
            default = getattr(meta, "default", None)
            if isinstance(default, str) and default.startswith("-"):
                decls.insert(0, default)

            for decl in decls:
                if decl and decl.startswith("--"):
                    cli_name = decl.lstrip("-")
                    break
        cli_to_py[cli_name] = py_name
    return {cli_to_py.get(k, k): v for k, v in args.items()}


# ---- Stage drivers ---------------------------------------------------------

def run_minimization(simulation, system, topology, stage, prev_restraint_indices, output_dir):
    new_restraint_indices = apply_restraints(
        simulation, system, topology, stage.restraints, prev_restraint_indices
    )
    print(f"  Minimizing (max {stage.max_iterations or 'unlimited'} iterations)")
    simulation.minimizeEnergy(
        maxIterations=stage.max_iterations,
        tolerance=stage.tolerance,
    )
    save_state(simulation, output_dir / f"{stage.name}.xml")
    return new_restraint_indices


def run_dynamics(simulation, system, topology, cfg, stage, prev_restraint_indices, output_dir):
    end_T = (stage.integrator.temperature if stage.integrator
             else cfg.defaults.integrator.temperature)
    start_T = stage.start_temperature  # None if not heating
    initial_T = start_T if start_T is not None else end_T

    if hasattr(simulation.integrator, "setTemperature"):
        simulation.integrator.setTemperature(initial_T)

    configure_barostat(simulation, system, cfg, stage)
    new_restraint_indices = apply_restraints(
        simulation, system, topology, stage.restraints, prev_restraint_indices
    )

    if stage.initialize_velocities:
        simulation.context.setVelocitiesToTemperature(initial_T)

    simulation.reporters.clear()
    for r in build_reporters(stage.reporters, stage.steps, output_dir):
        simulation.reporters.append(r)
    simulation.currentStep = 0

    if start_T is not None:
        # Heating ramp: 100 chunks, temperature stepped between each
        n_chunks = 100
        chunk = stage.steps // n_chunks
        print(f"  Heating from {start_T} to {end_T} over {stage.steps} steps")
        for i in range(n_chunks):
            T = start_T + (end_T - start_T) * (i + 1) / n_chunks
            simulation.integrator.setTemperature(T)
            simulation.step(chunk)
        leftover = stage.steps - chunk * n_chunks
        if leftover:
            simulation.step(leftover)
    else:
        print(f"  Running {stage.steps} steps")
        simulation.step(stage.steps)

    save_state(simulation, output_dir / f"{stage.name}.xml")
    return new_restraint_indices


def run_analysis(stage: AnalysisStage, output_dir: Path):
    import importlib, os
    module = importlib.import_module(f"openmm_cli.commands.trajectory.{stage.command}")
    kwargs = _cli_args_to_kwargs(module.command, stage.args)
    cwd = os.getcwd()
    try:
        os.chdir(output_dir)
        module.command(**kwargs)
    finally:
        os.chdir(cwd)


# ---- Typer command ---------------------------------------------------------

def command(config: Annotated[Path, typer.Argument(..., help="Path to yaml configuration file.")]) -> None:
    """Run an MD simulation from a YAML config file."""
    with open(config) as f:
        raw = yaml.safe_load(f)
    cfg = Config.model_validate(raw)

    output_dir = cfg.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if cfg.system.restart_from is not None:
        print(f"Loading coordinates from {cfg.system.restart_from}")
    elif cfg.system.coordinates is not None:
        print(f"Loading coordinates from {cfg.system.coordinates}")
    else:
        print(f"Loading coordinates from {cfg.system.topology}")

    topology, positions, box_vectors, system = build_system(cfg)
    print(f"System: {system.getNumParticles()} particles, "
          f"{system.getNumConstraints()} constraints")

    if cfg.defaults.barostat is not None:
        b = cfg.defaults.barostat
        system.addForce(mm.MonteCarloBarostat(
            b.pressure, cfg.defaults.integrator.temperature, b.frequency,
        ))

    integrator = build_integrator(cfg.defaults.integrator)
    platform, plat_props = build_platform(cfg)
    simulation = app.Simulation(topology, system, integrator, platform, plat_props)
    if positions is not None:
        simulation.context.setPositions(positions)
    if box_vectors is not None:
        simulation.context.setPeriodicBoxVectors(*box_vectors)

    if cfg.system.restart_from is not None:
        with open(cfg.system.restart_from) as f:
            state = mm.XmlSerializer.deserialize(f.read())
        simulation.context.setState(state)

    print(f"Platform: {simulation.context.getPlatform().getName()} "
          f"({cfg.platform.precision} precision)")

    restraint_indices: list[int] = []
    for stage in cfg.stages:
        print(f"\n=== Stage: {stage.name} ({stage.type}) ===")
        if isinstance(stage, MinimizationStage):
            restraint_indices = run_minimization(
                simulation, system, topology, stage, restraint_indices, output_dir,
            )
        elif isinstance(stage, DynamicsStage):
            restraint_indices = run_dynamics(
                simulation, system, topology, cfg, stage,
                restraint_indices, output_dir,
            )
        elif isinstance(stage, AnalysisStage):
            run_analysis(stage, output_dir)

    print("\nAll stages complete.")
