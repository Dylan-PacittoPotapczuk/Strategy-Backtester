"""Buy-and-hold benchmark equity series aligned to a strategy backtest."""

from __future__ import annotations

from datetime import date

import pandas as pd

from app.engine.metrics import compute_metrics
from app.models.schemas import (
    BenchmarkConfig,
    BenchmarkResult,
    EquityPoint,
    Metrics,
)


def build_buy_and_hold_equity(
    closes: pd.Series,
    trading_days: list[date],
    initial_cash: float,
) -> list[EquityPoint]:
    """
    Fully invested buy-and-hold on one series (close marks).

    Shares are bought notionally at the first day's close; equity each day
    is shares * close. Cash stays 0 after entry (fully invested).
    """
    if closes.empty or not trading_days:
        raise ValueError("Benchmark needs price history and trading days")

    # Align closes to trading_days
    prices: list[float] = []
    for d in trading_days:
        ts = pd.Timestamp(d)
        if ts in closes.index:
            prices.append(float(closes.loc[ts]))
        else:
            mask = closes.index.date == d
            if not mask.any():
                raise ValueError(f"Missing benchmark close on {d}")
            prices.append(float(closes.loc[mask].iloc[0]))

    first = prices[0]
    if first <= 0:
        raise ValueError("Benchmark first price must be positive")
    shares = initial_cash / first

    curve: list[EquityPoint] = []
    peak = initial_cash
    for d, px in zip(trading_days, prices):
        eq = shares * px
        peak = max(peak, eq)
        dd = (peak - eq) / peak if peak > 0 else 0.0
        curve.append(EquityPoint(date=d, equity=eq, cash=0.0, drawdown_pct=dd))
    return curve


def daily_returns_from_curve(curve: list[EquityPoint], initial_cash: float) -> list[float]:
    rets: list[float] = []
    prev = initial_cash
    for p in curve:
        rets.append((p.equity - prev) / prev if prev > 0 else 0.0)
        prev = p.equity
    return rets


def compute_benchmark_result(
    symbol: str,
    ohlcv: dict[str, pd.DataFrame],
    trading_days: list[date],
    initial_cash: float,
    strategy_metrics: Metrics,
    config: BenchmarkConfig,
) -> BenchmarkResult:
    """Build benchmark equity on the strategy's trading calendar and vs-metrics."""
    key = symbol.upper()
    if key not in ohlcv:
        raise ValueError(f"Benchmark symbol {key} missing from market data")

    df = ohlcv[key]
    closes = df["close"]
    # Restrict to strategy trading days that exist for the benchmark
    available = set(df.index.date)
    aligned_days = [d for d in trading_days if d in available]
    if len(aligned_days) < 2:
        raise ValueError(
            f"Benchmark {key} does not overlap the strategy trading calendar"
        )
    if len(aligned_days) != len(trading_days):
        # Prefer strict alignment: require every strategy day present
        missing = [d for d in trading_days if d not in available]
        raise ValueError(
            f"Benchmark {key} missing {len(missing)} day(s) on the strategy calendar "
            f"(first missing: {missing[0]})"
        )

    curve = build_buy_and_hold_equity(closes, trading_days, initial_cash)
    rets = daily_returns_from_curve(curve, initial_cash)
    metrics = compute_metrics(curve, [], initial_cash, rets)

    excess_return = strategy_metrics.total_return - metrics.total_return
    excess_cagr = strategy_metrics.cagr - metrics.cagr
    excess_sharpe = strategy_metrics.sharpe - metrics.sharpe

    return BenchmarkResult(
        enabled=config.enabled,
        symbol=key,
        equity_curve=curve,
        metrics=metrics,
        excess_return=excess_return,
        excess_cagr=excess_cagr,
        excess_sharpe=excess_sharpe,
    )
