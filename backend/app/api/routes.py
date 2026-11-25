"""Backtest, compare, Monte Carlo, presets, and saved-run HTTP routes."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.data.adapter import get_default_adapter
from app.db import RunStore
from app.engine.monte_carlo import run_monte_carlo
from app.engine.runner import BacktestRunner
from app.export import (
    build_backtest_csv_zip,
    build_backtest_pdf,
    build_compare_csv_zip,
    build_compare_pdf,
)
from app.models.schemas import (
    BacktestRequest,
    BacktestResponse,
    BacktestStatus,
    CompareExportRequest,
    CompareRequest,
    CompareResponse,
    ConfigPreset,
    ConfigPresetCreate,
    ConfigPresetUpdate,
    MonteCarloRequest,
    MonteCarloResponse,
    RunNameUpdate,
    RunSummary,
)

router = APIRouter(prefix="/api")
store = RunStore()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _execute_backtest(request: BacktestRequest) -> BacktestResponse:
    if not request.strategy.symbols:
        request.strategy.symbols = request.symbols
    if set(request.strategy.symbols) - set(request.symbols):
        raise HTTPException(400, "strategy symbols must be subset of universe")

    run = store.create(request)
    run.status = BacktestStatus.RUNNING
    store.update(run)

    try:
        runner = BacktestRunner(get_default_adapter())
        result = runner.run(request)
        run.equity_curve = result["equity_curve"]
        run.trades = result["trades"]
        run.metrics = result["metrics"]
        run.daily_returns = result["daily_returns"]
        run.dd_halted = result["dd_halted"]
        run.dd_halt_date = result["dd_halt_date"]
        run.walk_forward = result.get("walk_forward")
        run.benchmark = result.get("benchmark")
        run.no_oos_warning = result.get("no_oos_warning")
        run.status = BacktestStatus.DONE
    except Exception as exc:  # noqa: BLE001 — surface as failed run
        run.status = BacktestStatus.FAILED
        run.error = str(exc)
        store.update(run)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    store.update(run)
    return run


@router.post("/backtests", response_model=BacktestResponse)
def create_backtest(request: BacktestRequest) -> BacktestResponse:
    return _execute_backtest(request)


@router.post("/compare", response_model=CompareResponse)
def compare_strategies(request: CompareRequest) -> CompareResponse:
    """Run selected strategies on the same universe/period/guardrails."""
    runs: list[BacktestResponse] = []
    for strat in request.strategies:
        symbols = strat.symbols or request.symbols
        bt = BacktestRequest(
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_cash=request.initial_cash,
            currency=request.currency,
            strategy=strat.model_copy(update={"symbols": symbols}),
            guardrails=request.guardrails,
            costs=request.costs,
            walk_forward=request.walk_forward,
            benchmark=request.benchmark,
        )
        runs.append(_execute_backtest(bt))
    return CompareResponse(runs=runs)


@router.get("/backtests/{run_id}", response_model=BacktestResponse)
def get_backtest(run_id: UUID) -> BacktestResponse:
    run = store.get(run_id)
    if not run:
        raise HTTPException(404, "Backtest run not found")
    return run


@router.get("/backtests", response_model=list[BacktestResponse])
def list_backtests(limit: int = 20) -> list[BacktestResponse]:
    return store.list_recent(limit=min(limit, 100))


@router.get("/runs", response_model=list[RunSummary])
def list_run_summaries(limit: int = 30) -> list[RunSummary]:
    """Recent saved runs (name + timestamp + headline fields)."""
    return store.list_summaries(limit=min(limit, 100))


@router.patch("/backtests/{run_id}/name", response_model=BacktestResponse)
def rename_backtest(run_id: UUID, body: RunNameUpdate) -> BacktestResponse:
    run = store.rename(run_id, body.name)
    if not run:
        raise HTTPException(404, "Backtest run not found")
    return run


@router.post(
    "/backtests/{run_id}/monte-carlo",
    response_model=MonteCarloResponse,
)
def create_monte_carlo(run_id: UUID, request: MonteCarloRequest) -> MonteCarloResponse:
    """Bootstrap (or block-bootstrap) forward paths from a completed backtest."""
    run = store.get(run_id)
    if not run:
        raise HTTPException(404, "Backtest run not found")
    if run.status != BacktestStatus.DONE:
        raise HTTPException(400, "Backtest must be completed before running Monte Carlo")
    if not run.daily_returns:
        raise HTTPException(400, "Backtest has no daily returns to sample from")

    if request.start_equity is not None:
        start_equity = request.start_equity
    elif run.metrics is not None:
        start_equity = run.metrics.final_equity
    else:
        start_equity = run.request.initial_cash

    try:
        result = run_monte_carlo(run.daily_returns, request, start_equity=start_equity)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return store.create_monte_carlo(run_id, request, result)


@router.get("/monte-carlo/{mc_id}", response_model=MonteCarloResponse)
def get_monte_carlo(mc_id: UUID) -> MonteCarloResponse:
    mc = store.get_monte_carlo(mc_id)
    if not mc:
        raise HTTPException(404, "Monte Carlo run not found")
    return mc


@router.get(
    "/backtests/{run_id}/monte-carlo",
    response_model=list[MonteCarloResponse],
)
def list_monte_carlo(run_id: UUID, limit: int = 10) -> list[MonteCarloResponse]:
    run = store.get(run_id)
    if not run:
        raise HTTPException(404, "Backtest run not found")
    return store.list_monte_carlo_for_backtest(run_id, limit=min(limit, 50))


# --- Config presets ---------------------------------------------------------


@router.get("/presets", response_model=list[ConfigPreset])
def list_presets(limit: int = 50) -> list[ConfigPreset]:
    return store.list_presets(limit=min(limit, 100))


@router.post("/presets", response_model=ConfigPreset)
def create_preset(body: ConfigPresetCreate) -> ConfigPreset:
    return store.create_preset(body.name, body.config)


@router.get("/presets/{preset_id}", response_model=ConfigPreset)
def get_preset(preset_id: UUID) -> ConfigPreset:
    preset = store.get_preset(preset_id)
    if not preset:
        raise HTTPException(404, "Preset not found")
    return preset


@router.patch("/presets/{preset_id}", response_model=ConfigPreset)
def update_preset(preset_id: UUID, body: ConfigPresetUpdate) -> ConfigPreset:
    preset = store.update_preset(preset_id, name=body.name, config=body.config)
    if not preset:
        raise HTTPException(404, "Preset not found")
    return preset


@router.delete("/presets/{preset_id}")
def delete_preset(preset_id: UUID) -> dict:
    if not store.delete_preset(preset_id):
        raise HTTPException(404, "Preset not found")
    return {"ok": True}


# --- Risk report export -----------------------------------------------------


def _latest_monte_carlo(run_id: UUID) -> Optional[MonteCarloResponse]:
    mcs = store.list_monte_carlo_for_backtest(run_id, limit=1)
    return mcs[0] if mcs else None


def _resolve_monte_carlo(
    run_id: UUID,
    mc_id: Optional[UUID],
) -> Optional[MonteCarloResponse]:
    if mc_id is not None:
        mc = store.get_monte_carlo(mc_id)
        if not mc:
            raise HTTPException(404, "Monte Carlo run not found")
        if mc.backtest_run_id != run_id:
            raise HTTPException(400, "Monte Carlo run does not belong to this backtest")
        return mc
    return _latest_monte_carlo(run_id)


@router.get("/backtests/{run_id}/export.csv")
def export_backtest_csv(
    run_id: UUID,
    mc_id: Optional[UUID] = Query(
        default=None,
        description="Optional Monte Carlo run to include; defaults to latest if any",
    ),
) -> Response:
    """Download ZIP of CSV files: metrics, equity, trades, and MC summary when present."""
    run = store.get(run_id)
    if not run:
        raise HTTPException(404, "Backtest run not found")
    if run.status != BacktestStatus.DONE:
        raise HTTPException(400, "Backtest must be completed before export")
    mc = _resolve_monte_carlo(run_id, mc_id)
    payload = build_backtest_csv_zip(run, monte_carlo=mc)
    filename = f"backtest-{run_id}-export.zip"
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/backtests/{run_id}/export.pdf")
def export_backtest_pdf(
    run_id: UUID,
    mc_id: Optional[UUID] = Query(
        default=None,
        description="Optional Monte Carlo run to include; defaults to latest if any",
    ),
) -> Response:
    """Download a simple PDF summary of key metrics, equity sketch, and assumptions."""
    run = store.get(run_id)
    if not run:
        raise HTTPException(404, "Backtest run not found")
    if run.status != BacktestStatus.DONE:
        raise HTTPException(400, "Backtest must be completed before export")
    mc = _resolve_monte_carlo(run_id, mc_id)
    payload = build_backtest_pdf(run, monte_carlo=mc)
    filename = f"backtest-{run_id}-report.pdf"
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/compare/export.csv")
def export_compare_csv(body: CompareExportRequest) -> Response:
    """ZIP of side-by-side metrics plus per-strategy equity/trades CSVs."""
    if not body.runs:
        raise HTTPException(400, "No runs to export")
    for run in body.runs:
        if run.status != BacktestStatus.DONE:
            raise HTTPException(400, f"Run {run.id} is not completed")
    payload = build_compare_csv_zip(body.runs)
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="compare-export.zip"'},
    )


@router.post("/compare/export.pdf")
def export_compare_pdf(body: CompareExportRequest) -> Response:
    """PDF table of compare metrics plus shared assumptions."""
    if not body.runs:
        raise HTTPException(400, "No runs to export")
    for run in body.runs:
        if run.status != BacktestStatus.DONE:
            raise HTTPException(400, f"Run {run.id} is not completed")
    payload = build_compare_pdf(body.runs)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="compare-report.pdf"'},
    )
