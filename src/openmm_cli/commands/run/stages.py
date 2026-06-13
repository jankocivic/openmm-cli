"""Stage handlers and the stage dispatch registry.

Each pipeline stage type is handled by a function registered with
:func:`register_stage`. To add a new stage type, add a config model in
:mod:`.config` and register a handler here; the runner loop dispatches on the
stage's type and needs no changes.

Handlers receive the active :class:`~.runner.Runner` (for shared simulation
state) and the stage config.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from .analysis import run_analysis
from .barostat import configure_barostat
from .config import AnalysisStage, DynamicsStage, MinimizationStage
from .reporters import build_reporters
from .state import save_state

if TYPE_CHECKING:
    from .runner import Runner

StageHandler = Callable[["Runner", object], None]

_STAGE_HANDLERS: dict[type, StageHandler] = {}


def register_stage(stage_type: type) -> Callable[[StageHandler], StageHandler]:
    """Register a handler for a stage config model."""

    def decorator(handler: StageHandler) -> StageHandler:
        _STAGE_HANDLERS[stage_type] = handler
        return handler

    return decorator


def get_stage_handler(stage_type: type) -> StageHandler:
    handler = _STAGE_HANDLERS.get(stage_type)
    if handler is None:
        raise ValueError(f"No handler registered for stage type: {stage_type.__name__}")
    return handler


@register_stage(MinimizationStage)
def run_minimization(runner: "Runner", stage: MinimizationStage) -> None:
    runner.apply_stage_restraints(stage.restraints)
    print(f"  Minimizing (max {stage.max_iterations or 'unlimited'} iterations)")
    runner.simulation.minimizeEnergy(
        maxIterations=stage.max_iterations,
        tolerance=stage.tolerance,
    )
    save_state(runner.simulation, runner.output_dir / f"{stage.name}.xml")


def _heat(simulation, start_T, end_T, steps: int, n_chunks: int = 100) -> None:
    """Ramp the integrator temperature from ``start_T`` to ``end_T`` over ``steps``."""
    chunk = steps // n_chunks
    print(f"  Heating from {start_T} to {end_T} over {steps} steps")
    for i in range(n_chunks):
        T = start_T + (end_T - start_T) * (i + 1) / n_chunks
        simulation.integrator.setTemperature(T)
        simulation.step(chunk)
    leftover = steps - chunk * n_chunks
    if leftover:
        simulation.step(leftover)


@register_stage(DynamicsStage)
def run_dynamics(runner: "Runner", stage: DynamicsStage) -> None:
    simulation = runner.simulation
    defaults = runner.cfg.defaults.integrator

    # Per-stage temperature/timestep overrides fall back to the defaults. The
    # timestep is (re)applied every stage so an override in one stage does not
    # leak into the next; the integrator type and friction are never changed.
    end_T = stage.temperature if stage.temperature is not None else defaults.temperature
    timestep = stage.timestep if stage.timestep is not None else defaults.timestep
    start_T = stage.start_temperature  # None unless this is a heating ramp
    initial_T = start_T if start_T is not None else end_T

    simulation.integrator.setStepSize(timestep)
    if hasattr(simulation.integrator, "setTemperature"):
        simulation.integrator.setTemperature(initial_T)

    configure_barostat(simulation, runner.system, runner.cfg, stage, end_T)
    runner.apply_stage_restraints(stage.restraints)

    if stage.initialize_velocities:
        simulation.context.setVelocitiesToTemperature(initial_T)

    simulation.reporters.clear()
    for reporter in build_reporters(stage.reporters, stage.steps, runner.output_dir):
        simulation.reporters.append(reporter)
    simulation.currentStep = 0
    simulation.context.setTime(0)

    if start_T is not None:
        _heat(simulation, start_T, end_T, stage.steps)
    else:
        print(f"  Running {stage.steps} steps")
        simulation.step(stage.steps)

    save_state(simulation, runner.output_dir / f"{stage.name}.xml")


@register_stage(AnalysisStage)
def run_analysis_stage(runner: "Runner", stage: AnalysisStage) -> None:
    run_analysis(stage, runner.output_dir)
