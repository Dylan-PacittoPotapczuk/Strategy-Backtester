"""Backtest and Monte Carlo HTTP routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.data.adapter import get_default_adapter
from app.db import RunStore
from app.engine.monte_carlo import run_monte_carlo
from app.engine.runner import BacktestRunner
from app.models.schemas import (
    BacktestRequest,
    BacktestResponse,
    BacktestStatus,
    CompareRequest,
    CompareResponse,
    MonteCarloRequest,
    MonteCarloResponse,
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
