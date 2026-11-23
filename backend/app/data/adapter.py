"""Market data adapters: Yahoo EOD + fixture cache behind a common interface."""

from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "cache"
CACHE_DB = CACHE_DIR / "ohlcv.sqlite"

YAHOO_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class DataAdapter(ABC):
    """Interface for OHLCV market data."""

    @abstractmethod
    def get_ohlcv(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> dict[str, pd.DataFrame]:
        """
        Return {symbol: DataFrame} with columns:
        open, high, low, close, volume; DatetimeIndex (UTC-naive dates).
        Adjusted prices preferred.
        """


def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [c.lower().replace(" ", "_") for c in out.columns]
    if "adj_close" in out.columns and "close" in out.columns:
        factor = out["adj_close"] / out["close"].replace(0, pd.NA)
        for col in ("open", "high", "low", "close"):
            if col in out.columns:
                out[col] = out[col] * factor
    keep = [c for c in ("open", "high", "low", "close", "volume") if c in out.columns]
    out = out[keep].dropna(subset=["open", "close"])
    out.index = pd.to_datetime(out.index).tz_localize(None).normalize()
    out = out.sort_index()
    return out


def _fetch_yahoo_chart(symbol: str, start: date, end: date) -> pd.DataFrame:
    """
    Free Yahoo Finance chart API (no API key).
    Prefer this over the yfinance package which is often blocked/rate-limited
    in headless environments without a browser User-Agent.
    """
    period1 = int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    # Yahoo end is exclusive; pad one day
    period2 = int(
        datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp()
    )
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {
        "period1": period1,
        "period2": period2,
        "interval": "1d",
        "events": "div,splits",
        "includeAdjustedClose": "true",
    }
    resp = requests.get(url, params=params, headers={"User-Agent": YAHOO_UA}, timeout=30)
    if resp.status_code != 200:
        raise ValueError(f"Yahoo chart HTTP {resp.status_code} for {symbol}")
    payload = resp.json()
    result = (payload.get("chart") or {}).get("result")
    if not result:
        err = (payload.get("chart") or {}).get("error")
        raise ValueError(f"No market data for {symbol}: {err or 'empty result'}")
    block = result[0]
    ts = block.get("timestamp") or []
    quote = (block.get("indicators") or {}).get("quote") or [{}]
    adj = (block.get("indicators") or {}).get("adjclose") or [{}]
    q0 = quote[0] if quote else {}
    a0 = adj[0] if adj else {}
    if not ts:
        raise ValueError(f"No market data for {symbol} between {start} and {end}")

    idx = pd.to_datetime(ts, unit="s").tz_localize(None).normalize()
    df = pd.DataFrame(
        {
            "open": q0.get("open"),
            "high": q0.get("high"),
            "low": q0.get("low"),
            "close": q0.get("close"),
            "volume": q0.get("volume"),
            "adj_close": a0.get("adjclose") or q0.get("close"),
        },
        index=idx,
    )
    return _normalize_frame(df)


class SqliteOhlcvCache:
    def __init__(self, db_path: Path = CACHE_DB) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ohlcv (
                    symbol TEXT NOT NULL,
                    dt TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    PRIMARY KEY (symbol, dt)
                )
                """
            )

    def get(self, symbol: str, start: date, end: date) -> Optional[pd.DataFrame]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT dt, open, high, low, close, volume
                FROM ohlcv
                WHERE symbol = ? AND dt >= ? AND dt <= ?
                ORDER BY dt
                """,
                (symbol.upper(), start.isoformat(), end.isoformat()),
            ).fetchall()
        if not rows:
            return None
        df = pd.DataFrame(rows, columns=["dt", "open", "high", "low", "close", "volume"])
        df["dt"] = pd.to_datetime(df["dt"])
        return df.set_index("dt")

    def put(self, symbol: str, df: pd.DataFrame) -> None:
        if df.empty:
            return
        rows = []
        for ts, row in df.iterrows():
            dt = pd.Timestamp(ts).date().isoformat()
            rows.append(
                (
                    symbol.upper(),
                    dt,
                    float(row["open"]),
                    float(row["high"]),
                    float(row["low"]),
                    float(row["close"]),
                    float(row.get("volume", 0) or 0),
                )
            )
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO ohlcv (symbol, dt, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )


class YFinanceDataAdapter(DataAdapter):
    """
    Free EOD equities/ETFs via Yahoo chart API (same free source as yfinance).
    Results are cached in SQLite.
    """

    def __init__(self, cache: Optional[SqliteOhlcvCache] = None) -> None:
        self.cache = cache or SqliteOhlcvCache()

    def get_ohlcv(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> dict[str, pd.DataFrame]:
        result: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            cached = self.cache.get(symbol, start, end)
            if cached is not None and not cached.empty:
                first = cached.index.min().date()
                last = cached.index.max().date()
                if first <= start + timedelta(days=7) and last >= end - timedelta(days=7):
                    result[symbol.upper()] = cached.loc[
                        (cached.index.date >= start) & (cached.index.date <= end)
                    ]
                    continue

            frame = _fetch_yahoo_chart(symbol, start, end)
            self.cache.put(symbol, frame)
            masked = frame.loc[(frame.index.date >= start) & (frame.index.date <= end)]
            if masked.empty:
                raise ValueError(f"No market data for {symbol} between {start} and {end}")
            result[symbol.upper()] = masked

        return result


class FixtureDataAdapter(DataAdapter):
    """Deterministic OHLCV for unit tests — no network."""

    def __init__(self, frames: Optional[dict[str, pd.DataFrame]] = None) -> None:
        self.frames = frames or {}

    @classmethod
    def from_synthetic(
        cls,
        symbols: list[str],
        start: date,
        n_days: int = 60,
        start_price: float = 100.0,
        daily_returns: Optional[dict[str, list[float]]] = None,
    ) -> FixtureDataAdapter:
        dates = pd.bdate_range(start=start, periods=n_days)
        frames: dict[str, pd.DataFrame] = {}
        for i, sym in enumerate(symbols):
            rets = None
            if daily_returns and sym.upper() in daily_returns:
                rets = daily_returns[sym.upper()]
            prices = []
            px = start_price * (1 + 0.01 * i)
            for d_i, _ in enumerate(dates):
                if rets is not None and d_i < len(rets):
                    px = px * (1 + rets[d_i])
                else:
                    px = px * 1.001
                prices.append(px)
            closes = pd.Series(prices, index=dates)
            df = pd.DataFrame(
                {
                    "open": closes.shift(1).fillna(closes.iloc[0]),
                    "high": closes * 1.005,
                    "low": closes * 0.995,
                    "close": closes,
                    "volume": 1_000_000,
                }
            )
            df.iloc[0, df.columns.get_loc("open")] = closes.iloc[0]
            frames[sym.upper()] = df
        return cls(frames)

    def get_ohlcv(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> dict[str, pd.DataFrame]:
        out: dict[str, pd.DataFrame] = {}
        for s in symbols:
            key = s.upper()
            if key not in self.frames:
                raise ValueError(f"Fixture missing symbol {key}")
            df = self.frames[key]
            masked = df.loc[(df.index.date >= start) & (df.index.date <= end)]
            if masked.empty:
                raise ValueError(f"Fixture empty for {key} in range")
            out[key] = masked.copy()
        return out


def get_default_adapter() -> DataAdapter:
    return YFinanceDataAdapter()
