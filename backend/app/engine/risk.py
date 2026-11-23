"""Risk guardrail engine: sizing, per-trade stop, portfolio DD halt."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.engine.portfolio import Portfolio, Position
from app.engine.strategy import TargetWeight
from app.models.schemas import CostConfig, GuardrailConfig, Trade, TradeReason, TradeSide


@dataclass
class OrderIntent:
    symbol: str
    side: TradeSide
    qty: float
    reason: TradeReason
    note: Optional[str] = None


class RiskEngine:
    def __init__(self, guardrails: GuardrailConfig, costs: CostConfig) -> None:
        self.g = guardrails
        self.costs = costs

    def apply_slippage(self, price: float, side: TradeSide) -> float:
        slip = self.costs.slippage_bps / 10_000.0
        if side == TradeSide.BUY:
            return price * (1 + slip)
        return price * (1 - slip)

    def size_entries(
        self,
        portfolio: Portfolio,
        targets: list[TargetWeight],
        fill_prices: dict[str, float],
        ts: date,
    ) -> tuple[list[OrderIntent], list[Trade]]:
        """
        Convert target weights into buy intents, capped by max_position_pct and cash.
        Does not place sells for underweights on initial B&H entry (cash → long only).
        Returns (orders, informational trades for rejections/resizes).
        """
        info_trades: list[Trade] = []
        orders: list[OrderIntent] = []

        if portfolio.dd_halted:
            for t in targets:
                if t.weight <= 0:
                    continue
                info_trades.append(
                    Trade(
                        symbol=t.symbol,
                        side=TradeSide.BUY,
                        qty=0,
                        price=fill_prices.get(t.symbol, 0),
                        ts=ts,
                        reason=TradeReason.REJECTED_DD,
                        note="New risk rejected: portfolio drawdown halt active",
                    )
                )
            return orders, info_trades

        equity = portfolio.equity(fill_prices)
        # Build desired notionals
        desired: list[tuple[str, float, float]] = []  # symbol, target_notional, price
        for t in targets:
            if t.weight <= 0:
                continue
            px = fill_prices.get(t.symbol)
            if px is None or px <= 0:
                continue
            # Already holding? B&H never rebalance — skip if position exists
            if t.symbol in portfolio.positions:
                continue
            raw_notional = t.weight * equity
            capped = min(raw_notional, self.g.max_position_pct * equity)
            if capped < raw_notional - 1e-9:
                info_trades.append(
                    Trade(
                        symbol=t.symbol,
                        side=TradeSide.BUY,
                        qty=0,
                        price=px,
                        ts=ts,
                        reason=TradeReason.SIZED_DOWN,
                        note=(
                            f"Target notional {raw_notional:.2f} capped to "
                            f"{capped:.2f} by max_position_pct={self.g.max_position_pct}"
                        ),
                    )
                )
            desired.append((t.symbol, capped, px))

        total_needed = sum(n for _, n, _ in desired)
        scale = 1.0
        if total_needed > portfolio.cash and total_needed > 0:
            scale = portfolio.cash / total_needed
            info_trades.append(
                Trade(
                    symbol="PORTFOLIO",
                    side=TradeSide.BUY,
                    qty=0,
                    price=0,
                    ts=ts,
                    reason=TradeReason.REJECTED_CASH,
                    note=f"Scaled all entries by {scale:.4f} due to insufficient cash",
                )
            )

        for sym, notional, px in desired:
            fill_px = self.apply_slippage(px, TradeSide.BUY)
            spend = notional * scale
            # Reserve commission
            spend_avail = max(0.0, spend - self.costs.commission_per_trade)
            qty = spend_avail / fill_px if fill_px > 0 else 0
            if qty <= 0:
                continue
            orders.append(
                OrderIntent(
                    symbol=sym,
                    side=TradeSide.BUY,
                    qty=qty,
                    reason=TradeReason.SIGNAL,
                )
            )

        return orders, info_trades

    def check_stops(
        self,
        portfolio: Portfolio,
        marks: dict[str, float],
        ts: date,
    ) -> list[OrderIntent]:
        """Force-sell positions that breached max_trade_loss_pct (mark-to-market)."""
        orders: list[OrderIntent] = []
        for sym, pos in list(portfolio.positions.items()):
            px = marks.get(sym)
            if px is None:
                continue
            pnl_pct = pos.pnl_pct(px)
            if pnl_pct <= -self.g.max_trade_loss_pct:
                orders.append(
                    OrderIntent(
                        symbol=sym,
                        side=TradeSide.SELL,
                        qty=pos.qty,
                        reason=TradeReason.STOP_LOSS,
                        note=f"pnl_pct={pnl_pct:.4f} <= -{self.g.max_trade_loss_pct}",
                    )
                )
        return orders

    def check_drawdown_halt(
        self,
        portfolio: Portfolio,
        marks: dict[str, float],
        ts: date,
    ) -> list[OrderIntent]:
        """
        If portfolio DD >= max_portfolio_drawdown_pct:
        - set dd_halted (no new risk)
        - optionally flatten if flatten_on_breach
        Phase A locked decision: halt new risk; do NOT auto-flatten by default.
        """
        dd = portfolio.drawdown_pct(marks)
        orders: list[OrderIntent] = []
        if dd >= self.g.max_portfolio_drawdown_pct and not portfolio.dd_halted:
            portfolio.dd_halted = True
            portfolio.dd_halt_date = ts
            if self.g.flatten_on_breach:
                for sym, pos in list(portfolio.positions.items()):
                    orders.append(
                        OrderIntent(
                            symbol=sym,
                            side=TradeSide.SELL,
                            qty=pos.qty,
                            reason=TradeReason.DRAWDOWN_HALT,
                            note=f"flatten_on_breach; dd={dd:.4f}",
                        )
                    )
        return orders

    def execute(
        self,
        portfolio: Portfolio,
        order: OrderIntent,
        fill_price_raw: float,
        ts: date,
    ) -> Trade:
        fill_px = self.apply_slippage(fill_price_raw, order.side)
        commission = self.costs.commission_per_trade

        if order.side == TradeSide.BUY:
            cost = order.qty * fill_px + commission
            if cost > portfolio.cash + 1e-6:
                # Scale to available cash
                spend = max(0.0, portfolio.cash - commission)
                qty = spend / fill_px if fill_px > 0 else 0
                order = OrderIntent(
                    symbol=order.symbol,
                    side=order.side,
                    qty=qty,
                    reason=order.reason,
                    note=(order.note or "") + " | cash-scaled at fill",
                )
                cost = order.qty * fill_px + commission
            portfolio.cash -= cost
            existing = portfolio.positions.get(order.symbol)
            if existing:
                # Average up (shouldn't happen for B&H never-rebalance, but safe)
                new_qty = existing.qty + order.qty
                avg = (
                    (existing.entry_price * existing.qty + fill_px * order.qty) / new_qty
                    if new_qty
                    else fill_px
                )
                existing.qty = new_qty
                existing.entry_price = avg
            else:
                portfolio.positions[order.symbol] = Position(
                    symbol=order.symbol,
                    qty=order.qty,
                    entry_price=fill_px,
                    entry_date=ts,
                )
            return Trade(
                symbol=order.symbol,
                side=TradeSide.BUY,
                qty=order.qty,
                price=fill_px,
                ts=ts,
                reason=order.reason,
                note=order.note,
            )

        # SELL
        pos = portfolio.positions.get(order.symbol)
        if not pos or pos.qty <= 0:
            return Trade(
                symbol=order.symbol,
                side=TradeSide.SELL,
                qty=0,
                price=fill_px,
                ts=ts,
                reason=order.reason,
                note="no position to sell",
            )
        qty = min(order.qty, pos.qty)
        proceeds = qty * fill_px - commission
        pnl = (fill_px - pos.entry_price) * qty - commission
        pnl_pct = (fill_px - pos.entry_price) / pos.entry_price if pos.entry_price else 0
        portfolio.cash += proceeds
        remaining = pos.qty - qty
        if remaining <= 1e-12:
            del portfolio.positions[order.symbol]
        else:
            pos.qty = remaining
        return Trade(
            symbol=order.symbol,
            side=TradeSide.SELL,
            qty=qty,
            price=fill_px,
            ts=ts,
            reason=order.reason,
            pnl=pnl,
            pnl_pct=pnl_pct,
            note=order.note,
        )
