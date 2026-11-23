"""Portfolio state for the backtest engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Position:
    symbol: str
    qty: float
    entry_price: float
    entry_date: date

    def market_value(self, price: float) -> float:
        return self.qty * price

    def pnl_pct(self, price: float) -> float:
        if self.entry_price <= 0:
            return 0.0
        return (price - self.entry_price) / self.entry_price

    def unrealized_pnl(self, price: float) -> float:
        return (price - self.entry_price) * self.qty


@dataclass
class Portfolio:
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    peak_equity: float = 0.0
    dd_halted: bool = False
    dd_halt_date: Optional[date] = None

    def __post_init__(self) -> None:
        if self.peak_equity <= 0:
            self.peak_equity = self.cash

    def equity(self, marks: dict[str, float]) -> float:
        total = self.cash
        for sym, pos in self.positions.items():
            px = marks.get(sym)
            if px is not None:
                total += pos.market_value(px)
        return total

    def drawdown_pct(self, marks: dict[str, float]) -> float:
        eq = self.equity(marks)
        if eq > self.peak_equity:
            self.peak_equity = eq
        if self.peak_equity <= 0:
            return 0.0
        return max(0.0, (self.peak_equity - eq) / self.peak_equity)

    def update_peak(self, marks: dict[str, float]) -> float:
        eq = self.equity(marks)
        if eq > self.peak_equity:
            self.peak_equity = eq
        return eq
