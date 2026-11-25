"""Fill convention: signal on day N close → fill at day N+1 open."""

from __future__ import annotations

from datetime import date

from app.data.adapter import FixtureDataAdapter
from app.engine.runner import BacktestRunner
from app.models.schemas import (
    BenchmarkConfig,
    BacktestRequest,
    CostConfig,
    GuardrailConfig,
    StrategyConfig,
    TradeReason,
    TradeSide,
)


def test_buy_and_hold_fills_next_open_not_same_day(start: date) -> None:
    # Craft opens/closes so we can assert fill price == day-2 open
    # Day 0 close signal → day 1 open fill
    adapter = FixtureDataAdapter.from_synthetic(
        symbols=["AAA"],
        start=start,
        n_days=10,
        start_price=100.0,
        daily_returns={"AAA": [0.0] * 10},
    )
    # Override opens so day-1 open is distinctive
    df = adapter.frames["AAA"].copy()
    dates = list(df.index)
    df.loc[dates[0], "close"] = 100.0
    df.loc[dates[1], "open"] = 111.0  # expected fill
    df.loc[dates[1], "close"] = 112.0
    adapter.frames["AAA"] = df

    req = BacktestRequest(
        symbols=["AAA"],
        start_date=start,
        end_date=dates[-1].date(),
        initial_cash=10_000,
        strategy=StrategyConfig(type="buy_and_hold", symbols=["AAA"], params={}),
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
        if t.side == TradeSide.BUY and t.reason == TradeReason.SIGNAL and t.qty > 0
    ]
    assert len(buys) == 1
    assert buys[0].ts == dates[1].date()
    assert abs(buys[0].price - 111.0) < 1e-9
    # Must NOT fill on signal day
    assert buys[0].ts != dates[0].date()


def test_signal_on_last_day_has_no_fill(start: date) -> None:
    """If somehow only one day existed we error; with 2 days B&H fills day 2."""
    adapter = FixtureDataAdapter.from_synthetic(
        symbols=["BBB"], start=start, n_days=2, start_price=50.0
    )
    end = adapter.frames["BBB"].index[-1].date()
    req = BacktestRequest(
        symbols=["BBB"],
        start_date=start,
        end_date=end,
        initial_cash=5_000,
        strategy=StrategyConfig(type="buy_and_hold", symbols=["BBB"]),
        guardrails=GuardrailConfig(
            max_position_pct=1.0,
            max_trade_loss_pct=0.99,
            max_portfolio_drawdown_pct=0.99,
        ),
        costs=CostConfig(slippage_bps=0.0),
            benchmark=BenchmarkConfig(enabled=False),
        )
    result = BacktestRunner(adapter).run(req)
    buys = [t for t in result["trades"] if t.side == TradeSide.BUY and t.qty > 0]
    assert len(buys) == 1
    assert buys[0].ts == end
