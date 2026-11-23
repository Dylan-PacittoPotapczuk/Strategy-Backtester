"""Position sizing: max_position_pct cap and cash scaling."""

from __future__ import annotations

from datetime import date

from app.data.adapter import FixtureDataAdapter
from app.engine.portfolio import Portfolio
from app.engine.risk import RiskEngine
from app.engine.runner import BacktestRunner
from app.engine.strategy import TargetWeight
from app.models.schemas import (
    BenchmarkConfig,
    BacktestRequest,
    CostConfig,
    GuardrailConfig,
    StrategyConfig,
    TradeReason,
    TradeSide,
)


def test_max_position_pct_caps_notional() -> None:
    risk = RiskEngine(
        GuardrailConfig(max_position_pct=0.10, max_trade_loss_pct=0.5, max_portfolio_drawdown_pct=0.5),
        CostConfig(slippage_bps=0.0),
    )
    portfolio = Portfolio(cash=100_000)
    targets = [TargetWeight(symbol="AAA", weight=0.50)]  # wants 50k, cap at 10k
    orders, info = risk.size_entries(
        portfolio, targets, fill_prices={"AAA": 100.0}, ts=date(2024, 1, 3)
    )
    assert any(t.reason == TradeReason.SIZED_DOWN for t in info)
    assert len(orders) == 1
    # 10% of 100k = 10k → 100 shares
    assert abs(orders[0].qty - 100.0) < 1e-6


def test_equal_weight_two_symbols_respects_cap(start: date) -> None:
    adapter = FixtureDataAdapter.from_synthetic(
        symbols=["AAA", "BBB"],
        start=start,
        n_days=15,
        start_price=100.0,
    )
    end = adapter.frames["AAA"].index[-1].date()
    req = BacktestRequest(
        symbols=["AAA", "BBB"],
        start_date=start,
        end_date=end,
        initial_cash=100_000,
        strategy=StrategyConfig(
            type="buy_and_hold",
            symbols=["AAA", "BBB"],
            params={},  # equal weight 50/50
        ),
        guardrails=GuardrailConfig(
            max_position_pct=0.30,  # 50% target → sized down to 30%
            max_trade_loss_pct=0.99,
            max_portfolio_drawdown_pct=0.99,
            sizing_mode="equal_weight",
        ),
        costs=CostConfig(slippage_bps=0.0),
            benchmark=BenchmarkConfig(enabled=False),
        )
    result = BacktestRunner(adapter).run(req)
    buys = [
        t
        for t in result["trades"]
        if t.side == TradeSide.BUY and t.reason == TradeReason.SIGNAL and t.qty > 0
    ]
    assert len(buys) == 2
    # Each notional ≈ 30% of initial cash
    for t in buys:
        notional = t.qty * t.price
        assert notional <= 100_000 * 0.30 + 1.0
    assert any(t.reason == TradeReason.SIZED_DOWN for t in result["trades"])


def test_insufficient_cash_scales_down() -> None:
    risk = RiskEngine(
        GuardrailConfig(max_position_pct=1.0, max_trade_loss_pct=0.5, max_portfolio_drawdown_pct=0.5),
        CostConfig(slippage_bps=0.0),
    )
    portfolio = Portfolio(cash=1_000)
    # Pretend equity is higher because of... actually equity=cash when flat
    # Target 100% of 1000 into one name at $100 → 10 shares, fine.
    # Two names at 100% weight each would need scale — use two 100%? weights sum handled upstream.
    targets = [
        TargetWeight(symbol="AAA", weight=0.6),
        TargetWeight(symbol="BBB", weight=0.6),  # total 1.2 of equity → cash constrained
    ]
    orders, info = risk.size_entries(
        portfolio,
        targets,
        fill_prices={"AAA": 100.0, "BBB": 100.0},
        ts=date(2024, 1, 3),
    )
    # max_position_pct=1.0 so each wants min(0.6*1000, 1000)=600 → total 1200 > cash 1000
    assert any(t.reason == TradeReason.REJECTED_CASH for t in info)
    total_spend = sum(o.qty * 100.0 for o in orders)
    assert total_spend <= 1_000 + 1e-6
