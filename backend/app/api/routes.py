"""Backtest HTTP routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.data.adapter import get_default_adapter
from app.db import RunStore
from app.engine.runner import BacktestRunner
from app.models.schemas import (
    BacktestRequest,
    BacktestResponse,
    BacktestStatus,
)

router = APIRouter(prefix="/api")
store = RunStore()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/backtests", response_model=BacktestResponse)
def create_backtest(request: BacktestRequest) -> BacktestResponse:
    # Ensure strategy symbols default to universe if caller only set top-level symbols
    if not request.strategy.symbols:
        request.strategy.symbols = request.symbols
    # Align strategy symbols with request if user only filled symbols once
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


@router.get("/backtests/{run_id}", response_model=BacktestResponse)
def get_backtest(run_id: UUID) -> BacktestResponse:
    run = store.get(run_id)
    if not run:
        raise HTTPException(404, "Backtest run not found")
    return run


@router.get("/backtests", response_model=list[BacktestResponse])
def list_backtests(limit: int = 20) -> list[BacktestResponse]:
    return store.list_recent(limit=min(limit, 100))
