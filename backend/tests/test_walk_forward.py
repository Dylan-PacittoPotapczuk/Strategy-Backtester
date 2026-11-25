"""Walk-forward / out-of-sample split correctness."""

from __future__ import annotations

from datetime import date

import pytest

from app.data.adapter import FixtureDataAdapter
from app.engine.runner import BacktestRunner
from app.engine.walk_forward import (
    build_walk_forward_result,
    resolve_split_date,
    split_daily_returns,
    split_equity_curve,
)
from app.models.schemas import (
    BacktestRequest,
    BenchmarkConfig,
    EquityPoint,
    GuardrailConfig,
    StrategyConfig,
    WalkForwardConfig,
)


def _days(n: int = 20, start: date = date(2024, 1, 2)) -> list[date]:
    import pandas as pd

    return [ts.date() for ts in pd.bdate_range(start=start, periods=n)]


def test_resolve_split_percent_70():
    days = _days(10)
    cfg = WalkForwardConfig(enabled=True, mode="percent", train_pct=0.7)
    split = resolve_split_date(days, cfg)
    # floor(10 * 0.7) = 7 → index 7 is 8th day (0-based)
    assert split == days[7]
    is_n = sum(1 for d in days if d < split)
    oos_n = sum(1 for d in days if d >= split)
    assert is_n == 7
    assert oos_n == 3


def test_resolve_split_date_mode():
    days = _days(10)
    cfg = WalkForwardConfig(
        enabled=True, mode="date", split_date=days[5]
    )
    assert resolve_split_date(days, cfg) == days[5]


def test_resolve_split_date_rejects_empty_segments():
    days = _days(10)
    with pytest.raises(ValueError, match="empty in-sample"):
        resolve_split_date(
            days,
            WalkForwardConfig(enabled=True, mode="date", split_date=days[0]),
        )
    with pytest.raises(ValueError, match="empty out-of-sample"):
        resolve_split_date(
            days,
            WalkForwardConfig(enabled=True, mode="date", split_date=days[-1]),
        )


def test_split_equity_and_returns_align():
    days = _days(8)
    curve = [
        EquityPoint(date=d, equity=100_000 + i * 100, cash=0, drawdown_pct=0)
        for i, d in enumerate(days)
    ]
    rets = [0.01] * len(days)
    split = days[5]
    is_c, oos_c = split_equity_curve(curve, split)
    is_r, oos_r = split_daily_returns(curve, rets, split)
    assert [p.date for p in is_c] == days[:5]
    assert [p.date for p in oos_c] == days[5:]
    assert len(is_r) == 5
    assert len(oos_r) == 3


def test_build_walk_forward_metrics_segments():
    days = _days(20)
    # Rising then flat-ish
    curve = []
    eq = 100_000.0
    rets = []
    for i, d in enumerate(days):
        r = 0.002 if i < 10 else -0.001
        eq *= 1 + r
        rets.append(r)
        curve.append(EquityPoint(date=d, equity=eq, cash=0, drawdown_pct=0))

    wf = build_walk_forward_result(
        WalkForwardConfig(enabled=True, mode="percent", train_pct=0.5),
        days,
        curve,
        [],
        rets,
        100_000.0,
    )
    assert wf.enabled
    assert wf.metrics_in_sample is not None
    assert wf.metrics_out_of_sample is not None
    assert wf.train_trading_days + wf.test_trading_days == 20
    assert wf.metrics_in_sample.total_return > 0
    assert wf.metrics_out_of_sample.total_return < 0
    assert wf.split_date == days[10]


def test_runner_walk_forward_end_to_end():
    start = date(2024, 1, 2)
    adapter = FixtureDataAdapter.from_synthetic(
        ["SPY", "QQQ"], start=start, n_days=40, start_price=100.0
    )
    req = BacktestRequest(
        symbols=["SPY", "QQQ"],
        start_date=start,
        end_date=date(2024, 3, 1),
        initial_cash=100_000,
        strategy=StrategyConfig(type="buy_and_hold", symbols=["SPY", "QQQ"], params={}),
        guardrails=GuardrailConfig(max_position_pct=0.5),
        walk_forward=WalkForwardConfig(enabled=True, mode="percent", train_pct=0.6),
        benchmark=BenchmarkConfig(enabled=False),
    )
    result = BacktestRunner(adapter).run(req)
    assert result["walk_forward"] is not None
    wf = result["walk_forward"]
    assert wf.metrics_in_sample is not None
    assert wf.metrics_out_of_sample is not None
    assert wf.train_trading_days > 0
    assert wf.test_trading_days > 0
    assert result["no_oos_warning"] is None


def test_runner_warns_without_oos():
    start = date(2024, 1, 2)
    adapter = FixtureDataAdapter.from_synthetic(
        ["SPY"], start=start, n_days=30, start_price=100.0
    )
    req = BacktestRequest(
        symbols=["SPY"],
        start_date=start,
        end_date=date(2024, 2, 15),
        initial_cash=50_000,
        strategy=StrategyConfig(type="buy_and_hold", symbols=["SPY"], params={}),
        walk_forward=WalkForwardConfig(enabled=False),
        benchmark=BenchmarkConfig(enabled=False),
    )
    result = BacktestRunner(adapter).run(req)
    assert result["walk_forward"] is None
    assert result["no_oos_warning"]
    assert "out-of-sample" in result["no_oos_warning"].lower()
