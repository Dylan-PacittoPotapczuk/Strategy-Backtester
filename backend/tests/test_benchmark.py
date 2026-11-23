"""Benchmark buy-and-hold series alignment and excess metrics."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app.data.adapter import FixtureDataAdapter
from app.engine.benchmark import (
    build_buy_and_hold_equity,
    compute_benchmark_result,
    daily_returns_from_curve,
)
from app.engine.runner import BacktestRunner
from app.models.schemas import (
    BacktestRequest,
    BenchmarkConfig,
    GuardrailConfig,
    Metrics,
    StrategyConfig,
)


def test_buy_and_hold_equity_length_and_start():
    dates = pd.bdate_range(start="2024-01-02", periods=5)
    closes = pd.Series([100.0, 110.0, 105.0, 120.0, 130.0], index=dates)
    days = [d.date() for d in dates]
    curve = build_buy_and_hold_equity(closes, days, initial_cash=10_000.0)
    assert len(curve) == 5
    assert curve[0].date == days[0]
    assert abs(curve[0].equity - 10_000.0) < 1e-6
    # 100 → 130 = +30%
    assert abs(curve[-1].equity - 13_000.0) < 1e-6
    assert all(p.date == d for p, d in zip(curve, days))


def test_benchmark_dates_align_with_strategy_calendar():
    start = date(2024, 1, 2)
    # Divergent returns so strategy ≠ benchmark
    adapter = FixtureDataAdapter.from_synthetic(
        ["QQQ", "SPY"],
        start=start,
        n_days=30,
        start_price=100.0,
        daily_returns={
            "QQQ": [0.01] * 30,
            "SPY": [0.001] * 30,
        },
    )
    req = BacktestRequest(
        symbols=["QQQ"],
        start_date=start,
        end_date=date(2024, 2, 15),
        initial_cash=100_000,
        strategy=StrategyConfig(type="buy_and_hold", symbols=["QQQ"], params={}),
        guardrails=GuardrailConfig(max_position_pct=1.0),
        benchmark=BenchmarkConfig(enabled=True, symbol="SPY"),
    )
    result = BacktestRunner(adapter).run(req)
    assert result["benchmark"] is not None
    bench = result["benchmark"]
    strat_dates = [p.date for p in result["equity_curve"]]
    bench_dates = [p.date for p in bench.equity_curve]
    assert strat_dates == bench_dates
    assert bench.symbol == "SPY"
    assert bench.metrics is not None
    assert bench.excess_return is not None
    # QQQ grows faster → positive excess
    assert bench.excess_return > 0


def test_compute_benchmark_result_excess():
    start = date(2024, 1, 2)
    dates = pd.bdate_range(start=start, periods=10)
    spy = pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": [100 + i for i in range(10)],
            "volume": 1e6,
        },
        index=dates,
    )
    days = [d.date() for d in dates]
    strategy_metrics = Metrics(
        total_return=0.20,
        cagr=0.20,
        volatility=0.1,
        sharpe=1.0,
        max_drawdown=0.05,
        win_rate=None,
        num_trades=0,
        num_stop_losses=0,
        num_dd_halts=0,
        final_equity=120_000,
        initial_cash=100_000,
        trading_days=10,
    )
    br = compute_benchmark_result(
        "SPY",
        {"SPY": spy},
        days,
        100_000.0,
        strategy_metrics,
        BenchmarkConfig(enabled=True, symbol="SPY"),
    )
    assert br.metrics is not None
    assert abs(br.excess_return - (0.20 - br.metrics.total_return)) < 1e-9
    assert [p.date for p in br.equity_curve] == days


def test_benchmark_missing_symbol_raises():
    dates = pd.bdate_range(start="2024-01-02", periods=5)
    df = pd.DataFrame(
        {"open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}, index=dates
    )
    days = [d.date() for d in dates]
    dummy = Metrics(
        total_return=0,
        cagr=0,
        volatility=0,
        sharpe=0,
        max_drawdown=0,
        num_trades=0,
        num_stop_losses=0,
        num_dd_halts=0,
        final_equity=1,
        initial_cash=1,
        trading_days=5,
    )
    with pytest.raises(ValueError, match="missing"):
        compute_benchmark_result(
            "SPY",
            {"QQQ": df},
            days,
            1.0,
            dummy,
            BenchmarkConfig(symbol="SPY"),
        )


def test_daily_returns_from_curve():
    dates = pd.bdate_range(start="2024-01-02", periods=3)
    from app.models.schemas import EquityPoint

    days = [d.date() for d in dates]
    curve = [
        EquityPoint(date=days[0], equity=100, cash=0, drawdown_pct=0),
        EquityPoint(date=days[1], equity=110, cash=0, drawdown_pct=0),
        EquityPoint(date=days[2], equity=99, cash=0, drawdown_pct=0),
    ]
    rets = daily_returns_from_curve(curve, 100)
    assert abs(rets[0] - 0.0) < 1e-12  # first mark vs initial same
    assert abs(rets[1] - 0.1) < 1e-12
    assert abs(rets[2] - (99 / 110 - 1)) < 1e-12
