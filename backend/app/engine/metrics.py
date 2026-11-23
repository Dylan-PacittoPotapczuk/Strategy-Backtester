"""Performance metrics from equity curve and trades."""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from app.models.schemas import EquityPoint, Metrics, Trade, TradeReason, TradeSide


def compute_metrics(
    equity_curve: list[EquityPoint],
    trades: list[Trade],
    initial_cash: float,
    daily_returns: list[float],
) -> Metrics:
    if not equity_curve:
        return Metrics(
            total_return=0.0,
            cagr=0.0,
            volatility=0.0,
            sharpe=0.0,
            max_drawdown=0.0,
            win_rate=None,
            num_trades=0,
            num_stop_losses=0,
            num_dd_halts=0,
            final_equity=initial_cash,
            initial_cash=initial_cash,
            trading_days=0,
        )

    final = equity_curve[-1].equity
    total_return = (final - initial_cash) / initial_cash if initial_cash else 0.0
    n = len(equity_curve)
    years = max(n / 252.0, 1e-9)
    cagr = (final / initial_cash) ** (1 / years) - 1 if initial_cash > 0 and final > 0 else 0.0

    rets = np.array(daily_returns, dtype=float) if daily_returns else np.array([0.0])
    vol = float(np.std(rets, ddof=1) * math.sqrt(252)) if len(rets) > 1 else 0.0
    mean_r = float(np.mean(rets)) if len(rets) else 0.0
    sharpe = (mean_r * 252) / vol if vol > 1e-12 else 0.0

    max_dd = max((p.drawdown_pct for p in equity_curve), default=0.0)

    closed = [t for t in trades if t.side == TradeSide.SELL and t.pnl is not None]
    wins = [t for t in closed if (t.pnl or 0) > 0]
    win_rate: Optional[float] = (len(wins) / len(closed)) if closed else None

    num_stops = sum(1 for t in trades if t.reason == TradeReason.STOP_LOSS)
    num_dd = sum(
        1
        for t in trades
        if t.reason in (TradeReason.DRAWDOWN_HALT, TradeReason.REJECTED_DD)
    )
    # Count real fills only for num_trades
    real_trades = [
        t
        for t in trades
        if t.qty > 0
        and t.reason
        in (
            TradeReason.SIGNAL,
            TradeReason.STOP_LOSS,
            TradeReason.DRAWDOWN_HALT,
            TradeReason.REBALANCE,
            TradeReason.END_OF_BACKTEST,
        )
    ]

    return Metrics(
        total_return=total_return,
        cagr=cagr,
        volatility=vol,
        sharpe=sharpe,
        max_drawdown=max_dd,
        win_rate=win_rate,
        num_trades=len(real_trades),
        num_stop_losses=num_stops,
        num_dd_halts=num_dd,
        final_equity=final,
        initial_cash=initial_cash,
        trading_days=n,
    )
