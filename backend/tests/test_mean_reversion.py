"""Mean reversion strategy: z-score entry/exit and no look-ahead."""

from __future__ import annotations

from datetime import date

import pandas as pd

from app.data.adapter import FixtureDataAdapter
from app.engine.runner import BacktestRunner
from app.engine.strategy import MeanReversionStrategy
from app.models.schemas import (
    BacktestRequest,
    CostConfig,
    GuardrailConfig,
    StrategyConfig,
    TradeSide,
)


def _dip_and_recover(start: date, n_days: int = 60) -> FixtureDataAdapter:
    """
    Price flat, then a sharp dip (oversold), then recovery toward the mean.
    Should trigger a long entry on the dip and exit on recovery.
    """
    rets = [0.0] * n_days
    # After window warms up (~20), crash for a few days then rebound
    for i in range(22, 26):
        rets[i] = -0.08
    for i in range(26, 35):
        rets[i] = 0.04
    return FixtureDataAdapter.from_synthetic(
        symbols=["MRV"],
        start=start,
        n_days=n_days,
        start_price=100.0,
        daily_returns={"MRV": rets},
    )


def test_mean_reversion_enters_on_oversold_z(start: date) -> None:
    adapter = _dip_and_recover(start)
    ohlcv = adapter.get_ohlcv(["MRV"], start, date(2024, 12, 31))
    days = sorted(ohlcv["MRV"].index.date.tolist())

    cfg = StrategyConfig(
        type="mean_reversion",
        symbols=["MRV"],
        params={
            "window": 20,
            "entry_z": 1.5,
            "exit_z": 0.25,
            "max_positions": 1,
        },
    )
    signals = MeanReversionStrategy(cfg).generate_signals(ohlcv, days)
    assert signals, "expected entry/exit signals around the dip"

    # First positive-weight signal should be an entry after the crash days
    entry = next(s for s in signals if any(t.weight > 0 for t in s.targets))
    assert entry.rebalance is True
    assert entry.date in days
    # Entry uses only closes through the signal day (window ends on signal day)
    i = days.index(entry.date)
    assert i + 1 >= 20
    window_days = days[i + 1 - 20 : i + 1]
    closes = [
        float(ohlcv["MRV"].loc[ohlcv["MRV"].index.date == d, "close"].iloc[0])
        for d in window_days
    ]
    mean = sum(closes) / len(closes)
    var = sum((c - mean) ** 2 for c in closes) / len(closes)
    z = (closes[-1] - mean) / (var**0.5)
    assert z <= -1.5


def test_mean_reversion_no_lookahead_on_fill(start: date) -> None:
    adapter = _dip_and_recover(start, n_days=55)
    ohlcv = adapter.get_ohlcv(["MRV"], start, date(2024, 12, 31))
    days = sorted(ohlcv["MRV"].index.date.tolist())
    cfg = StrategyConfig(
        type="mean_reversion",
        symbols=["MRV"],
        params={"window": 20, "entry_z": 1.5, "exit_z": 0.25, "max_positions": 1},
    )
    signals = MeanReversionStrategy(cfg).generate_signals(ohlcv, days)
    entry = next(s for s in signals if any(t.weight > 0 for t in s.targets))
    signal_i = days.index(entry.date)
    fill_day = days[signal_i + 1]

    # Stamp a distinctive open on the fill day
    df = adapter.frames["MRV"].copy()
    fill_ts = pd.Timestamp(fill_day)
    df.loc[fill_ts, "open"] = 77.7
    adapter.frames["MRV"] = df

    req = BacktestRequest(
        symbols=["MRV"],
        start_date=start,
        end_date=days[-1],
        initial_cash=50_000,
        strategy=cfg,
        guardrails=GuardrailConfig(
            max_position_pct=1.0,
            max_trade_loss_pct=0.99,
            max_portfolio_drawdown_pct=0.99,
        ),
        costs=CostConfig(slippage_bps=0.0, commission_per_trade=0.0),
    )
    result = BacktestRunner(adapter).run(req)
    buys = [
        t
        for t in result["trades"]
        if t.side == TradeSide.BUY and t.qty > 0 and t.symbol == "MRV"
    ]
    assert buys
    assert buys[0].ts == fill_day
    assert abs(buys[0].price - 77.7) < 1e-9
    assert buys[0].ts != entry.date


def test_mean_reversion_exits_when_z_recovers(start: date) -> None:
    adapter = _dip_and_recover(start, n_days=70)
    ohlcv = adapter.get_ohlcv(["MRV"], start, date(2024, 12, 31))
    days = sorted(ohlcv["MRV"].index.date.tolist())
    cfg = StrategyConfig(
        type="mean_reversion",
        symbols=["MRV"],
        params={"window": 20, "entry_z": 1.5, "exit_z": 0.25, "max_positions": 1},
    )
    signals = MeanReversionStrategy(cfg).generate_signals(ohlcv, days)
    # After an entry with weight>0, there should be a later all-zero (or exit) signal
    saw_entry = False
    saw_exit = False
    for s in signals:
        long_w = sum(t.weight for t in s.targets if t.weight > 0)
        if long_w > 0:
            saw_entry = True
        elif saw_entry and long_w == 0:
            saw_exit = True
            break
    assert saw_entry and saw_exit


def test_mean_reversion_max_hold_time_stop(start: date) -> None:
    # Grind lower so z stays negative (exit_z=0 never fires); time stop should exit.
    rets = [0.0] * 80
    for i in range(22, 80):
        rets[i] = -0.002
    adapter = FixtureDataAdapter.from_synthetic(
        symbols=["HOLD"],
        start=start,
        n_days=80,
        start_price=100.0,
        daily_returns={"HOLD": rets},
    )
    ohlcv = adapter.get_ohlcv(["HOLD"], start, date(2024, 12, 31))
    days = sorted(ohlcv["HOLD"].index.date.tolist())
    cfg = StrategyConfig(
        type="mean_reversion",
        symbols=["HOLD"],
        params={
            "window": 20,
            "entry_z": 1.0,
            "exit_z": 0.0,
            "max_hold_days": 5,
            "max_positions": 1,
        },
    )
    signals = MeanReversionStrategy(cfg).generate_signals(ohlcv, days)
    entry = next((s for s in signals if any(t.weight > 0 for t in s.targets)), None)
    assert entry is not None
    entry_i = days.index(entry.date)
    exit_sig = next(
        (
            s
            for s in signals
            if s.date > entry.date and all(t.weight == 0 for t in s.targets)
        ),
        None,
    )
    assert exit_sig is not None
    exit_i = days.index(exit_sig.date)
    assert exit_i - entry_i >= 5
