"""Per-trade loss limit forces exit with stop_loss reason."""

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


def test_stop_loss_triggers_on_adverse_move(start: date) -> None:
    # Flat then large drop after entry
    # Day0 signal, day1 fill near 100, then price crashes >10%
    rets = [0.0, 0.0, -0.15, 0.0, 0.0, 0.0, 0.0, 0.0]
    adapter = FixtureDataAdapter.from_synthetic(
        symbols=["AAA"],
        start=start,
        n_days=len(rets),
        start_price=100.0,
        daily_returns={"AAA": rets},
    )
    # Keep opens ~ prior close for predictable fills
    df = adapter.frames["AAA"]
    for i in range(1, len(df)):
        df.iloc[i, df.columns.get_loc("open")] = float(df.iloc[i - 1]["close"])

    end = df.index[-1].date()
    req = BacktestRequest(
        symbols=["AAA"],
        start_date=start,
        end_date=end,
        initial_cash=10_000,
        strategy=StrategyConfig(type="buy_and_hold", symbols=["AAA"]),
        guardrails=GuardrailConfig(
            max_position_pct=1.0,
            max_trade_loss_pct=0.10,  # 10% stop
            max_portfolio_drawdown_pct=0.99,  # don't trip DD first
        ),
        costs=CostConfig(slippage_bps=0.0),
            benchmark=BenchmarkConfig(enabled=False),
        )
    result = BacktestRunner(adapter).run(req)
    stops = [t for t in result["trades"] if t.reason == TradeReason.STOP_LOSS and t.qty > 0]
    assert len(stops) == 1
    assert stops[0].side == TradeSide.SELL
    assert result["metrics"].num_stop_losses >= 1
    # Position should be flat after stop
    final_cash = result["equity_curve"][-1].cash
    final_eq = result["equity_curve"][-1].equity
    assert abs(final_cash - final_eq) < 1e-6
