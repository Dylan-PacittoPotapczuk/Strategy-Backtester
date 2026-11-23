"""Strategy signal generators: buy-and-hold, momentum, mean reversion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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
    # When True, risk engine sells/buys to match targets (exits weight=0 names).
    rebalance: bool = False


class Strategy(ABC):
    @abstractmethod
    def generate_signals(
        self,
        ohlcv: dict[str, pd.DataFrame],
        trading_days: list[date],
    ) -> list[SignalBar]:
        ...


def _close_series(ohlcv: dict[str, pd.DataFrame], symbol: str) -> pd.Series:
    df = ohlcv[symbol]
    closes = df["close"].copy()
    closes.index = pd.DatetimeIndex(closes.index).normalize()
    return closes


def _close_on(closes: pd.Series, day: date) -> Optional[float]:
    ts = pd.Timestamp(day)
    if ts in closes.index:
        return float(closes.loc[ts])
    mask = closes.index.date == day
    if mask.any():
        return float(closes.loc[mask].iloc[0])
    return None


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
        targets = [TargetWeight(symbol=s, weight=self.weights[s]) for s in self.symbols]
        return [SignalBar(date=trading_days[0], targets=targets, is_entry=True)]


class MomentumStrategy(Strategy):
    """
    Rank symbols by trailing return over `lookback` trading days (optionally
    skipping the most recent `skip_recent_days`). Long the top `top_n`.
    Rebalance every `rebalance_days`. All inputs use closes through the signal
    day only — no look-ahead.
    """

    def __init__(self, config: StrategyConfig) -> None:
        self.symbols = [s.upper() for s in config.symbols]
        p = config.params
        self.lookback = int(p.get("lookback", 63))
        self.top_n = int(p.get("top_n", 2))
        self.rebalance_days = int(p.get("rebalance_days", 21))
        self.skip_recent_days = int(p.get("skip_recent_days", 0))
        self.weighting = str(p.get("weighting", "equal"))
        if self.lookback < 1:
            raise ValueError("momentum lookback must be >= 1")
        if self.top_n < 1:
            raise ValueError("momentum top_n must be >= 1")
        if self.rebalance_days < 1:
            raise ValueError("momentum rebalance_days must be >= 1")
        if self.skip_recent_days < 0:
            raise ValueError("momentum skip_recent_days must be >= 0")
        if self.weighting not in ("equal", "score"):
            raise ValueError("momentum weighting must be 'equal' or 'score'")

    def generate_signals(
        self,
        ohlcv: dict[str, pd.DataFrame],
        trading_days: list[date],
    ) -> list[SignalBar]:
        if not trading_days:
            return []
        closes = {s: _close_series(ohlcv, s) for s in self.symbols if s in ohlcv}
        if not closes:
            return []

        signals: list[SignalBar] = []
        # Need lookback (+ optional skip) history before the first rebalance signal day
        next_rebalance_i = self.lookback + self.skip_recent_days

        for i, day in enumerate(trading_days):
            if i < next_rebalance_i:
                continue

            end_i = i - self.skip_recent_days
            start_i = end_i - self.lookback
            if start_i < 0 or end_i < 0 or end_i >= len(trading_days):
                next_rebalance_i = i + self.rebalance_days
                continue
            end_day = trading_days[end_i]
            start_day = trading_days[start_i]

            scores: list[tuple[str, float]] = []
            for sym, series in closes.items():
                px_end = _close_on(series, end_day)
                px_start = _close_on(series, start_day)
                if px_end is None or px_start is None or px_start <= 0:
                    continue
                scores.append((sym, (px_end / px_start) - 1.0))

            if scores:
                scores.sort(key=lambda x: x[1], reverse=True)
                chosen = scores[: min(self.top_n, len(scores))]
                targets = self._weights(chosen)
                held_syms = {t.symbol for t in targets}
                for sym in self.symbols:
                    if sym not in held_syms:
                        targets.append(TargetWeight(symbol=sym, weight=0.0))
                signals.append(
                    SignalBar(
                        date=day,
                        targets=targets,
                        is_entry=(len(signals) == 0),
                        rebalance=True,
                    )
                )

            next_rebalance_i = i + self.rebalance_days

        return signals

    def _weights(self, chosen: list[tuple[str, float]]) -> list[TargetWeight]:
        if not chosen:
            return []
        if self.weighting == "equal" or len(chosen) == 1:
            w = 1.0 / len(chosen)
            return [TargetWeight(symbol=s, weight=w) for s, _ in chosen]

        # Score-weight: use positive scores only; fall back to equal if none
        pos = [(s, max(score, 0.0)) for s, score in chosen]
        total = sum(sc for _, sc in pos)
        if total <= 0:
            w = 1.0 / len(chosen)
            return [TargetWeight(symbol=s, weight=w) for s, _ in chosen]
        return [TargetWeight(symbol=s, weight=sc / total) for s, sc in pos]


class MeanReversionStrategy(Strategy):
    """
    Long-only mean reversion on z-score of price vs rolling mean over `window`.
    Enter when z <= -entry_z; exit when z >= -exit_z (or time stop).
    Z-scores use closes through the signal day only — no look-ahead.
    """

    def __init__(self, config: StrategyConfig) -> None:
        self.symbols = [s.upper() for s in config.symbols]
        p = config.params
        self.window = int(p.get("window", 20))
        self.entry_z = float(p.get("entry_z", 1.5))
        self.exit_z = float(p.get("exit_z", 0.25))
        self.max_hold_days = p.get("max_hold_days")
        self.max_hold_days_int = int(self.max_hold_days) if self.max_hold_days is not None else None
        self.max_positions = int(p.get("max_positions", max(1, len(self.symbols))))
        if self.window < 2:
            raise ValueError("mean_reversion window must be >= 2")
        if self.entry_z <= 0:
            raise ValueError("mean_reversion entry_z must be > 0")
        if self.exit_z < 0:
            raise ValueError("mean_reversion exit_z must be >= 0")
        if self.exit_z > self.entry_z:
            raise ValueError("mean_reversion exit_z should be <= entry_z")
        if self.max_positions < 1:
            raise ValueError("mean_reversion max_positions must be >= 1")
        if self.max_hold_days_int is not None and self.max_hold_days_int < 1:
            raise ValueError("mean_reversion max_hold_days must be >= 1")

    def generate_signals(
        self,
        ohlcv: dict[str, pd.DataFrame],
        trading_days: list[date],
    ) -> list[SignalBar]:
        if not trading_days:
            return []
        closes = {s: _close_series(ohlcv, s) for s in self.symbols if s in ohlcv}
        if not closes:
            return []

        # held: symbol -> signal-day index when entered (strategy clock, not fill day)
        held: dict[str, int] = {}
        signals: list[SignalBar] = []
        prev_targets: Optional[tuple[tuple[str, float], ...]] = None

        for i, day in enumerate(trading_days):
            if i + 1 < self.window:
                continue

            zscores: dict[str, float] = {}
            for sym, series in closes.items():
                window_days = trading_days[i + 1 - self.window : i + 1]
                vals: list[float] = []
                ok = True
                for d in window_days:
                    px = _close_on(series, d)
                    if px is None:
                        ok = False
                        break
                    vals.append(px)
                if not ok or len(vals) < self.window:
                    continue
                mean = sum(vals) / len(vals)
                var = sum((v - mean) ** 2 for v in vals) / len(vals)
                std = var**0.5
                if std <= 1e-12:
                    continue
                zscores[sym] = (vals[-1] - mean) / std

            # Exits (no same-bar re-entry for names that just left)
            just_exited: set[str] = set()
            for sym in list(held.keys()):
                z = zscores.get(sym)
                hold_len = i - held[sym]
                timed_out = (
                    self.max_hold_days_int is not None and hold_len >= self.max_hold_days_int
                )
                mean_reverted = z is not None and z >= -self.exit_z
                if timed_out or mean_reverted or z is None:
                    del held[sym]
                    just_exited.add(sym)

            # Entries: most oversold first (skip names that exited this bar)
            candidates = [
                (sym, z)
                for sym, z in zscores.items()
                if sym not in held and sym not in just_exited and z <= -self.entry_z
            ]
            candidates.sort(key=lambda x: x[1])  # most negative first
            slots = self.max_positions - len(held)
            for sym, _z in candidates[: max(0, slots)]:
                held[sym] = i

            if not held:
                targets = [TargetWeight(symbol=s, weight=0.0) for s in self.symbols]
            else:
                w = 1.0 / len(held)
                targets = [TargetWeight(symbol=s, weight=w) for s in held]
                for s in self.symbols:
                    if s not in held:
                        targets.append(TargetWeight(symbol=s, weight=0.0))

            key = tuple(sorted((t.symbol, round(t.weight, 8)) for t in targets))
            if key == prev_targets:
                continue
            prev_targets = key
            signals.append(
                SignalBar(
                    date=day,
                    targets=targets,
                    is_entry=(len(signals) == 0),
                    rebalance=True,
                )
            )

        return signals


def build_strategy(config: StrategyConfig) -> Strategy:
    if config.type == "buy_and_hold":
        return BuyAndHoldStrategy(config)
    if config.type == "momentum":
        return MomentumStrategy(config)
    if config.type == "mean_reversion":
        return MeanReversionStrategy(config)
    raise ValueError(f"Unsupported strategy type: {config.type}")
