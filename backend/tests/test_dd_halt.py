"""Portfolio drawdown halt: reject new risk; do not auto-flatten by default."""

from __future__ import annotations

from datetime import date

from app.data.adapter import FixtureDataAdapter
from app.engine.portfolio import Portfolio
from app.engine.risk import RiskEngine
from app.engine.runner import BacktestRunner
from app.engine.strategy import TargetWeight
from app.models.schemas import (
    BacktestRequest,
    CostConfig,
    GuardrailConfig,
    StrategyConfig,
    TradeReason,
    TradeSide,
)


def test_dd_halt_rejects_new_entries_without_flattening() -> None:
    risk = RiskEngine(
        GuardrailConfig(
            max_position_pct=1.0,
            max_trade_loss_pct=0.99,
            max_portfolio_drawdown_pct=0.10,
            flatten_on_breach=False,
        ),
        CostConfig(slippage_bps=0.0),
    )
    portfolio = Portfolio(cash=50_000, peak_equity=100_000)
    # Equity at 50k cash only → DD = 50%
    orders = risk.check_drawdown_halt(portfolio, marks={}, ts=date(2024, 2, 1))
    assert portfolio.dd_halted is True
    assert orders == []  # no auto-flatten

    entry_orders, info = risk.size_entries(
        portfolio,
        [TargetWeight(symbol="ZZZ", weight=1.0)],
        fill_prices={"ZZZ": 10.0},
        ts=date(2024, 2, 2),
    )
    assert entry_orders == []
    assert any(t.reason == TradeReason.REJECTED_DD for t in info)


def test_dd_halt_in_backtest_keeps_positions(start: date) -> None:
    # Rally then crash > 15% from peak to trip 10% DD halt; stop very loose
    rets = [0.05, 0.05, 0.05, -0.20, -0.05, 0.0, 0.0, 0.0, 0.0, 0.0]
    adapter = FixtureDataAdapter.from_synthetic(
        symbols=["AAA"],
        start=start,
        n_days=len(rets),
        start_price=100.0,
        daily_returns={"AAA": rets},
    )
    df = adapter.frames["AAA"]
    for i in range(1, len(df)):
        df.iloc[i, df.columns.get_loc("open")] = float(df.iloc[i - 1]["close"])

    end = df.index[-1].date()
    req = BacktestRequest(
        symbols=["AAA"],
        start_date=start,
        end_date=end,
        initial_cash=100_000,
        strategy=StrategyConfig(type="buy_and_hold", symbols=["AAA"]),
        guardrails=GuardrailConfig(
            max_position_pct=1.0,
            max_trade_loss_pct=0.90,  # don't stop out first
            max_portfolio_drawdown_pct=0.10,
            flatten_on_breach=False,
        ),
        costs=CostConfig(slippage_bps=0.0),
    )
    result = BacktestRunner(adapter).run(req)
    assert result["dd_halted"] is True
    assert result["dd_halt_date"] is not None
    halt_events = [t for t in result["trades"] if t.reason == TradeReason.DRAWDOWN_HALT]
    assert len(halt_events) >= 1
    # No flatten sells from DD halt
    flatten_sells = [
        t
        for t in result["trades"]
        if t.reason == TradeReason.DRAWDOWN_HALT and t.side == TradeSide.SELL and t.qty > 0
    ]
    assert flatten_sells == []
    # Position still held: equity != cash at end (unless price recovered weirdly)
    # After crash we still hold shares
    assert result["equity_curve"][-1].cash < result["equity_curve"][-1].equity


def test_flatten_on_breach_optional(start: date) -> None:
    rets = [0.10, 0.10, -0.25, 0.0, 0.0, 0.0]
    adapter = FixtureDataAdapter.from_synthetic(
        symbols=["AAA"],
        start=start,
        n_days=len(rets),
        start_price=100.0,
        daily_returns={"AAA": rets},
    )
    df = adapter.frames["AAA"]
    for i in range(1, len(df)):
        df.iloc[i, df.columns.get_loc("open")] = float(df.iloc[i - 1]["close"])
    end = df.index[-1].date()
    req = BacktestRequest(
        symbols=["AAA"],
        start_date=start,
        end_date=end,
        initial_cash=50_000,
        strategy=StrategyConfig(type="buy_and_hold", symbols=["AAA"]),
        guardrails=GuardrailConfig(
            max_position_pct=1.0,
            max_trade_loss_pct=0.90,
            max_portfolio_drawdown_pct=0.10,
            flatten_on_breach=True,
        ),
        costs=CostConfig(slippage_bps=0.0),
    )
    result = BacktestRunner(adapter).run(req)
    assert result["dd_halted"] is True
    sells = [
        t
        for t in result["trades"]
        if t.reason == TradeReason.DRAWDOWN_HALT and t.qty > 0
    ]
    assert len(sells) >= 1
