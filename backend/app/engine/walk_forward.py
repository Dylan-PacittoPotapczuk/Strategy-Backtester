"""Walk-forward / out-of-sample split helpers."""

from __future__ import annotations

from datetime import date
from typing import Optional

from app.engine.metrics import compute_metrics
from app.models.schemas import (
    EquityPoint,
    Metrics,
    Trade,
    WalkForwardConfig,
    WalkForwardResult,
)


def resolve_split_date(
    trading_days: list[date],
    config: WalkForwardConfig,
) -> date:
    """
    Pick the first out-of-sample trading day.

    Percent mode: train uses the first floor(n * train_pct) days;
    the split date is the first day of the test segment.
    Date mode: first trading day on or after split_date (must leave
    at least one day in each segment).
    """
    if len(trading_days) < 4:
        raise ValueError("Walk-forward needs at least 4 trading days")

    if config.mode == "percent":
        n_train = int(len(trading_days) * config.train_pct)
        n_train = max(1, min(n_train, len(trading_days) - 1))
        return trading_days[n_train]

    if config.split_date is None:
        raise ValueError("split_date is required when walk-forward mode is 'date'")

    for idx, d in enumerate(trading_days):
        if d >= config.split_date:
            if idx == 0:
                raise ValueError("split_date leaves an empty in-sample window")
            if idx >= len(trading_days) - 1:
                raise ValueError("split_date leaves an empty out-of-sample window")
            return d

    raise ValueError(
        f"split_date {config.split_date} is after the last trading day "
        f"{trading_days[-1]}"
    )


def split_equity_curve(
    equity_curve: list[EquityPoint],
    split_date: date,
) -> tuple[list[EquityPoint], list[EquityPoint]]:
    """Split curve into in-sample (date < split) and out-of-sample (date >= split)."""
    is_curve = [p for p in equity_curve if p.date < split_date]
    oos_curve = [p for p in equity_curve if p.date >= split_date]
    return is_curve, oos_curve


def split_trades(
    trades: list[Trade],
    split_date: date,
) -> tuple[list[Trade], list[Trade]]:
    is_trades = [t for t in trades if t.ts < split_date]
    oos_trades = [t for t in trades if t.ts >= split_date]
    return is_trades, oos_trades


def split_daily_returns(
    equity_curve: list[EquityPoint],
    daily_returns: list[float],
    split_date: date,
) -> tuple[list[float], list[float]]:
    """Align daily_returns with equity_curve dates (same length)."""
    if len(daily_returns) != len(equity_curve):
        # Runner appends one return per equity point; tolerate mismatch by date mask
        is_rets: list[float] = []
        oos_rets: list[float] = []
        for i, p in enumerate(equity_curve):
            r = daily_returns[i] if i < len(daily_returns) else 0.0
            if p.date < split_date:
                is_rets.append(r)
            else:
                oos_rets.append(r)
        return is_rets, oos_rets

    is_rets = []
    oos_rets = []
    for p, r in zip(equity_curve, daily_returns):
        if p.date < split_date:
            is_rets.append(r)
        else:
            oos_rets.append(r)
    return is_rets, oos_rets


def _metrics_for_segment(
    curve: list[EquityPoint],
    trades: list[Trade],
    daily_returns: list[float],
    initial_cash: float,
) -> Optional[Metrics]:
    if not curve:
        return None
    return compute_metrics(curve, trades, initial_cash, daily_returns)


def build_walk_forward_result(
    config: WalkForwardConfig,
    trading_days: list[date],
    equity_curve: list[EquityPoint],
    trades: list[Trade],
    daily_returns: list[float],
    initial_cash: float,
) -> WalkForwardResult:
    """Resolve split and compute in-sample vs out-of-sample metrics."""
    split = resolve_split_date(trading_days, config)
    is_curve, oos_curve = split_equity_curve(equity_curve, split)
    is_trades, oos_trades = split_trades(trades, split)
    is_rets, oos_rets = split_daily_returns(equity_curve, daily_returns, split)

    if not is_curve or not oos_curve:
        raise ValueError("Walk-forward split produced an empty in-sample or out-of-sample segment")

    # OOS initial = equity at end of IS (or start of OOS mark)
    oos_initial = is_curve[-1].equity

    # Rebuild OOS drawdowns relative to OOS peak for fair segment metrics
    oos_curve_norm = _rebase_drawdowns(oos_curve)
    is_curve_norm = _rebase_drawdowns(is_curve)

    metrics_is = _metrics_for_segment(is_curve_norm, is_trades, is_rets, initial_cash)
    metrics_oos = _metrics_for_segment(oos_curve_norm, oos_trades, oos_rets, oos_initial)

    train_days = len(is_curve)
    test_days = len(oos_curve)
    train_pct_used = train_days / max(train_days + test_days, 1)

    return WalkForwardResult(
        enabled=True,
        mode=config.mode,
        split_date=split,
        train_pct_used=train_pct_used,
        train_trading_days=train_days,
        test_trading_days=test_days,
        metrics_in_sample=metrics_is,
        metrics_out_of_sample=metrics_oos,
        warning=None,
    )


def _rebase_drawdowns(curve: list[EquityPoint]) -> list[EquityPoint]:
    """Recompute drawdown_pct from peak within this segment only."""
    if not curve:
        return []
    peak = curve[0].equity
    out: list[EquityPoint] = []
    for p in curve:
        peak = max(peak, p.equity)
        dd = (peak - p.equity) / peak if peak > 0 else 0.0
        out.append(
            EquityPoint(date=p.date, equity=p.equity, cash=p.cash, drawdown_pct=dd)
        )
    return out


def no_oos_warning() -> str:
    return (
        "No out-of-sample holdout is enabled. Tuning parameters on the full history "
        "can overfit — enable walk-forward to compare in-sample vs out-of-sample results."
    )
