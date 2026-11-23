"""Pydantic schemas for the backtest API and engine."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class TradeSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TradeReason(str, Enum):
    SIGNAL = "signal"
    STOP_LOSS = "stop_loss"
    DRAWDOWN_HALT = "drawdown_halt"
    REBALANCE = "rebalance"
    SIZED_DOWN = "sized_down"
    REJECTED_DD = "rejected_dd"
    REJECTED_CASH = "rejected_cash"
    END_OF_BACKTEST = "end_of_backtest"


class BacktestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class CostConfig(BaseModel):
    slippage_bps: float = Field(default=5.0, ge=0, description="Slippage in basis points")
    commission_per_trade: float = Field(default=0.0, ge=0, description="Flat $ commission")


class GuardrailConfig(BaseModel):
    max_position_pct: float = Field(
        default=0.25,
        gt=0,
        le=1.0,
        description="Max notional per name as fraction of equity",
    )
    max_trade_loss_pct: float = Field(
        default=0.10,
        gt=0,
        le=1.0,
        description="Force-exit when position loss from entry reaches this fraction",
    )
    max_portfolio_drawdown_pct: float = Field(
        default=0.20,
        gt=0,
        le=1.0,
        description="Halt new risk when portfolio DD from peak reaches this fraction",
    )
    sizing_mode: Literal["fixed_pct", "equal_weight"] = "equal_weight"
    flatten_on_breach: bool = Field(
        default=False,
        description="If true, flatten all positions on DD breach; Phase A default is halt-only",
    )


class StrategyConfig(BaseModel):
    type: Literal["buy_and_hold"] = "buy_and_hold"
    params: dict[str, Any] = Field(default_factory=dict)
    symbols: list[str] = Field(min_length=1)

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, v: list[str]) -> list[str]:
        out = [s.strip().upper() for s in v if s.strip()]
        if not out:
            raise ValueError("At least one symbol required")
        return out

    @model_validator(mode="after")
    def validate_weights(self) -> StrategyConfig:
        weights = self.params.get("weights")
        if weights is not None:
            if set(weights.keys()) != set(self.symbols):
                raise ValueError("weights keys must match symbols exactly")
            total = sum(float(w) for w in weights.values())
            if abs(total - 1.0) > 1e-6:
                raise ValueError(f"weights must sum to 1.0, got {total}")
        return self


class BacktestRequest(BaseModel):
    symbols: list[str] = Field(min_length=1)
    start_date: date
    end_date: date
    initial_cash: float = Field(default=100_000.0, gt=0)
    currency: Literal["USD"] = "USD"
    strategy: StrategyConfig
    guardrails: GuardrailConfig = Field(default_factory=GuardrailConfig)
    costs: CostConfig = Field(default_factory=CostConfig)

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, v: list[str]) -> list[str]:
        out = [s.strip().upper() for s in v if s.strip()]
        if not out:
            raise ValueError("At least one symbol required")
        return out

    @model_validator(mode="after")
    def validate_dates_and_symbols(self) -> BacktestRequest:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        # Strategy symbols should align with universe; if strategy omits, inherit
        if set(self.strategy.symbols) != set(self.symbols):
            # Allow strategy to use a subset; require all strategy symbols in universe
            missing = set(self.strategy.symbols) - set(self.symbols)
            if missing:
                raise ValueError(f"strategy symbols not in universe: {sorted(missing)}")
        return self


class Trade(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    side: TradeSide
    qty: float
    price: float
    ts: date
    reason: TradeReason
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    note: Optional[str] = None


class EquityPoint(BaseModel):
    date: date
    equity: float
    cash: float
    drawdown_pct: float


class Metrics(BaseModel):
    total_return: float
    cagr: float
    volatility: float
    sharpe: float
    max_drawdown: float
    win_rate: Optional[float] = None
    num_trades: int
    num_stop_losses: int
    num_dd_halts: int
    final_equity: float
    initial_cash: float
    trading_days: int


class BacktestResponse(BaseModel):
    id: UUID
    created_at: datetime
    status: BacktestStatus
    request: BacktestRequest
    equity_curve: list[EquityPoint] = Field(default_factory=list)
    trades: list[Trade] = Field(default_factory=list)
    metrics: Optional[Metrics] = None
    daily_returns: list[float] = Field(default_factory=list)
    error: Optional[str] = None
    dd_halted: bool = False
    dd_halt_date: Optional[date] = None
