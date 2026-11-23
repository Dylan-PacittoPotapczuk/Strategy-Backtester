"""Strategy signal generators. Phase A: buy-and-hold only."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Optional

import pandas as pd

from app.models.schemas import StrategyConfig


@dataclass
class TargetWeight:
    symbol: str
    weight: float  # fraction of equity desired


@dataclass
class SignalBar:
    """Signals for a calendar date (emitted on bar close; filled next open)."""

    date: date
    targets: list[TargetWeight]
    is_entry: bool = False


class Strategy(ABC):
    @abstractmethod
    def generate_signals(
        self,
        ohlcv: dict[str, pd.DataFrame],
        trading_days: list[date],
    ) -> list[SignalBar]:
        ...


class BuyAndHoldStrategy(Strategy):
    """
    Allocate once on the first bar; hold thereafter (rebalance=never).
    Signal is emitted on day 0 close → filled at day 1 open (next-open fill).
    """

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        self.symbols = [s.upper() for s in config.symbols]
        weights = config.params.get("weights")
        if weights:
            self.weights = {k.upper(): float(v) for k, v in weights.items()}
        else:
            w = 1.0 / len(self.symbols)
            self.weights = {s: w for s in self.symbols}

    def generate_signals(
        self,
        ohlcv: dict[str, pd.DataFrame],
        trading_days: list[date],
    ) -> list[SignalBar]:
        if not trading_days:
            return []
        # Emit entry signal on first trading day (filled next open)
        targets = [TargetWeight(symbol=s, weight=self.weights[s]) for s in self.symbols]
        return [SignalBar(date=trading_days[0], targets=targets, is_entry=True)]


def build_strategy(config: StrategyConfig) -> Strategy:
    if config.type == "buy_and_hold":
        return BuyAndHoldStrategy(config)
    raise ValueError(f"Unsupported strategy type in Phase A: {config.type}")
