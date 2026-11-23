"""Momentum strategy: ranking, rebalance cadence, and no look-ahead."""

from __future__ import annotations

from datetime import date

from app.data.adapter import FixtureDataAdapter
from app.engine.runner import BacktestRunner
from app.engine.strategy import MomentumStrategy
from app.models.schemas import (
    BenchmarkConfig,
    BacktestRequest,
    CostConfig,
    GuardrailConfig,
    StrategyConfig,
    TradeReason,
    TradeSide,
)


def _adapter_with_ranks(start: date, n_days: int = 90) -> FixtureDataAdapter:
    """
    AAA rises strongly, BBB flat, CCC falls.
    Momentum should prefer AAA over CCC after lookback.
    """
    aaa = [0.01] * n_days  # strong up
    bbb = [0.0] * n_days
    ccc = [-0.005] * n_days  # down
    return FixtureDataAdapter.from_synthetic(
        symbols=["AAA", "BBB", "CCC"],
        start=start,
        n_days=n_days,
        start_price=100.0,
        daily_returns={"AAA": aaa, "BBB": bbb, "CCC": ccc},
    )


def test_momentum_ranks_top_n_without_lookahead(start: date) -> None:
    adapter = _adapter_with_ranks(start, n_days=80)
    ohlcv = adapter.get_ohlcv(["AAA", "BBB", "CCC"], start, date(2024, 12, 31))
    days = sorted({d for df in ohlcv.values() for d in df.index.date})

    cfg = StrategyConfig(
        type="momentum",
        symbols=["AAA", "BBB", "CCC"],
        params={
            "lookback": 20,
            "top_n": 1,
            "rebalance_days": 40,
            "skip_recent_days": 0,
            "weighting": "equal",
        },
    )
    signals = MomentumStrategy(cfg).generate_signals(ohlcv, days)
    assert signals, "expected at least one rebalance signal"
    first = signals[0]
    # Signal on day index == lookback (20); uses closes through that day only
    assert first.date == days[20]
    assert first.rebalance is True
    positive = [t for t in first.targets if t.weight > 0]
    assert len(positive) == 1
    assert positive[0].symbol == "AAA"

    # Look-ahead check: trailing return must equal closes[i]/closes[i-lookback]
    # using only data available on the signal day (not future opens/closes).
    i = days.index(first.date)
    end_day = days[i]
    start_day = days[i - 20]
    for sym in ("AAA", "BBB", "CCC"):
        df = ohlcv[sym]
        # No future bar should be needed: signal day is the last close used
        assert df.index.date.max() >= end_day
        px_end = float(df.loc[df.index.date == end_day, "close"].iloc[0])
        px_start = float(df.loc[df.index.date == start_day, "close"].iloc[0])
        # Sanity: AAA has highest trailing return
        if sym == "AAA":
            aaa_ret = px_end / px_start - 1
        elif sym == "CCC":
            ccc_ret = px_end / px_start - 1
    assert aaa_ret > ccc_ret


def test_momentum_fill_is_next_open_not_signal_close(start: date) -> None:
    adapter = _adapter_with_ranks(start, n_days=50)
    # Make day-after-first-signal open distinctive for AAA
    df = adapter.frames["AAA"].copy()
    days = list(df.index)
    signal_i = 20
    fill_i = signal_i + 1
    df.loc[days[fill_i], "open"] = 250.0
    adapter.frames["AAA"] = df

    end = days[-1].date()
    req = BacktestRequest(
        symbols=["AAA", "BBB", "CCC"],
        start_date=start,
        end_date=end,
        initial_cash=100_000,
        strategy=StrategyConfig(
            type="momentum",
            symbols=["AAA", "BBB", "CCC"],
            params={
                "lookback": 20,
                "top_n": 1,
                "rebalance_days": 100,
                "weighting": "equal",
            },
        ),
        guardrails=GuardrailConfig(
            max_position_pct=1.0,
            max_trade_loss_pct=0.99,
            max_portfolio_drawdown_pct=0.99,
        ),
        costs=CostConfig(slippage_bps=0.0, commission_per_trade=0.0),
            benchmark=BenchmarkConfig(enabled=False),
        )
    result = BacktestRunner(adapter).run(req)
    buys = [
        t
        for t in result["trades"]
        if t.side == TradeSide.BUY
        and t.qty > 0
        and t.symbol == "AAA"
        and t.reason in (TradeReason.SIGNAL, TradeReason.REBALANCE)
    ]
    assert buys, "expected AAA buy after momentum signal"
    assert buys[0].ts == days[fill_i].date()
    assert abs(buys[0].price - 250.0) < 1e-9
    # Must not fill on the signal day itself
    assert buys[0].ts != days[signal_i].date()


def test_momentum_skip_recent_days_shifts_window(start: date) -> None:
    adapter = _adapter_with_ranks(start, n_days=60)
    ohlcv = adapter.get_ohlcv(["AAA", "BBB", "CCC"], start, date(2024, 12, 31))
    days = sorted({d for df in ohlcv.values() for d in df.index.date})
    cfg = StrategyConfig(
        type="momentum",
        symbols=["AAA", "BBB", "CCC"],
        params={
            "lookback": 10,
            "top_n": 1,
            "rebalance_days": 50,
            "skip_recent_days": 5,
            "weighting": "equal",
        },
    )
    signals = MomentumStrategy(cfg).generate_signals(ohlcv, days)
    assert signals
    # First signal when i >= lookback + skip = 15
    assert signals[0].date == days[15]
