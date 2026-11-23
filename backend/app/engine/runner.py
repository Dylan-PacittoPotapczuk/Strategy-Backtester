"""Backtest runner: signal → next-open fill → risk checks → equity curve."""

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from app.data.adapter import DataAdapter
from app.engine.metrics import compute_metrics
from app.engine.portfolio import Portfolio
from app.engine.risk import OrderIntent, RiskEngine
from app.engine.strategy import SignalBar, build_strategy
from app.models.schemas import (
    BacktestRequest,
    EquityPoint,
    Trade,
    TradeReason,
    TradeSide,
)


class BacktestRunner:
    """
    Execution model (locked):
    - Signals generated on bar close
    - Fills at next trading day's open (+ slippage)
    - Long-only, USD
    - DD breach: halt new risk (no auto-flatten unless configured)
    """

    def __init__(self, data: DataAdapter) -> None:
        self.data = data

    def run(self, request: BacktestRequest) -> dict:
        ohlcv = self.data.get_ohlcv(
            symbols=list(set(request.symbols) | set(request.strategy.symbols)),
            start=request.start_date,
            end=request.end_date,
        )
        trading_days = self._common_trading_days(ohlcv)
        if len(trading_days) < 2:
            raise ValueError("Need at least 2 trading days for next-open fills")

        strategy = build_strategy(request.strategy)
        signals = strategy.generate_signals(ohlcv, trading_days)
        signal_map: dict[date, SignalBar] = {s.date: s for s in signals}

        risk = RiskEngine(request.guardrails, request.costs)
        portfolio = Portfolio(cash=request.initial_cash)
        pending: Optional[SignalBar] = None  # fill next open

        trades: list[Trade] = []
        equity_curve: list[EquityPoint] = []
        daily_returns: list[float] = []
        prev_equity = request.initial_cash

        for i, day in enumerate(trading_days):
            opens = self._prices(ohlcv, day, "open")
            closes = self._prices(ohlcv, day, "close")

            # --- 1) Fill pending signals at today's open ---
            if pending is not None:
                if pending.rebalance:
                    orders, info = risk.rebalance_to_targets(
                        portfolio, pending.targets, opens, day
                    )
                else:
                    orders, info = risk.size_entries(
                        portfolio, pending.targets, opens, day
                    )
                trades.extend(info)
                for order in orders:
                    px = opens.get(order.symbol)
                    if px is None:
                        continue
                    trades.append(risk.execute(portfolio, order, px, day))
                pending = None

            # --- 2) Intraday / EOD risk: stops then DD halt (use close marks) ---
            stop_orders = risk.check_stops(portfolio, closes, day)
            for order in stop_orders:
                # Stop fills at close (conservative same-bar exit after breach)
                px = closes.get(order.symbol)
                if px is None:
                    continue
                trades.append(risk.execute(portfolio, order, px, day))

            dd_orders = risk.check_drawdown_halt(portfolio, closes, day)
            for order in dd_orders:
                px = closes.get(order.symbol)
                if px is None:
                    continue
                trades.append(risk.execute(portfolio, order, px, day))

            # Record informational DD halt event once
            if (
                portfolio.dd_halted
                and portfolio.dd_halt_date == day
                and not any(
                    t.reason == TradeReason.DRAWDOWN_HALT and t.ts == day for t in trades
                )
                and not request.guardrails.flatten_on_breach
            ):
                trades.append(
                    Trade(
                        symbol="PORTFOLIO",
                        side=TradeSide.SELL,
                        qty=0,
                        price=0,
                        ts=day,
                        reason=TradeReason.DRAWDOWN_HALT,
                        note=(
                            f"New risk halted; DD "
                            f"{portfolio.drawdown_pct(closes):.2%} >= "
                            f"{request.guardrails.max_portfolio_drawdown_pct:.2%}"
                        ),
                    )
                )

            # --- 3) Mark equity at close ---
            eq = portfolio.update_peak(closes)
            dd = (
                (portfolio.peak_equity - eq) / portfolio.peak_equity
                if portfolio.peak_equity > 0
                else 0.0
            )
            equity_curve.append(
                EquityPoint(
                    date=day,
                    equity=eq,
                    cash=portfolio.cash,
                    drawdown_pct=dd,
                )
            )
            if prev_equity > 0:
                daily_returns.append((eq - prev_equity) / prev_equity)
            else:
                daily_returns.append(0.0)
            prev_equity = eq

            # --- 4) Generate signal on close → pending for next open ---
            if day in signal_map:
                # Only queue if there is a next day to fill
                if i < len(trading_days) - 1:
                    pending = signal_map[day]

        metrics = compute_metrics(
            equity_curve, trades, request.initial_cash, daily_returns
        )

        return {
            "equity_curve": equity_curve,
            "trades": trades,
            "metrics": metrics,
            "daily_returns": daily_returns,
            "dd_halted": portfolio.dd_halted,
            "dd_halt_date": portfolio.dd_halt_date,
        }

    @staticmethod
    def _common_trading_days(ohlcv: dict[str, pd.DataFrame]) -> list[date]:
        common: Optional[set] = None
        for df in ohlcv.values():
            days = set(df.index.date)
            common = days if common is None else common & days
        if not common:
            return []
        return sorted(common)

    @staticmethod
    def _prices(
        ohlcv: dict[str, pd.DataFrame], day: date, field: str
    ) -> dict[str, float]:
        out: dict[str, float] = {}
        ts = pd.Timestamp(day)
        for sym, df in ohlcv.items():
            if ts in df.index:
                out[sym] = float(df.loc[ts, field])
            else:
                # try date match
                mask = df.index.date == day
                if mask.any():
                    out[sym] = float(df.loc[mask, field].iloc[0])
        return out
