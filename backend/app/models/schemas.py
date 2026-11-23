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
    type: Literal["buy_and_hold", "momentum", "mean_reversion"] = "buy_and_hold"
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
    def validate_params(self) -> StrategyConfig:
        if self.type == "buy_and_hold":
            weights = self.params.get("weights")
            if weights is not None:
                if set(weights.keys()) != set(self.symbols):
                    raise ValueError("weights keys must match symbols exactly")
                total = sum(float(w) for w in weights.values())
                if abs(total - 1.0) > 1e-6:
                    raise ValueError(f"weights must sum to 1.0, got {total}")
        elif self.type == "momentum":
            lookback = int(self.params.get("lookback", 63))
            top_n = int(self.params.get("top_n", 2))
            rebalance_days = int(self.params.get("rebalance_days", 21))
            skip_recent = int(self.params.get("skip_recent_days", 0))
            weighting = self.params.get("weighting", "equal")
            if lookback < 1:
                raise ValueError("lookback must be >= 1")
            if top_n < 1:
                raise ValueError("top_n must be >= 1")
            if rebalance_days < 1:
                raise ValueError("rebalance_days must be >= 1")
            if skip_recent < 0:
                raise ValueError("skip_recent_days must be >= 0")
            if weighting not in ("equal", "score"):
                raise ValueError("weighting must be 'equal' or 'score'")
        elif self.type == "mean_reversion":
            window = int(self.params.get("window", 20))
            entry_z = float(self.params.get("entry_z", 1.5))
            exit_z = float(self.params.get("exit_z", 0.25))
            max_positions = int(self.params.get("max_positions", max(1, len(self.symbols))))
            if window < 2:
                raise ValueError("window must be >= 2")
            if entry_z <= 0:
                raise ValueError("entry_z must be > 0")
            if exit_z < 0:
                raise ValueError("exit_z must be >= 0")
            if exit_z > entry_z:
                raise ValueError("exit_z should be <= entry_z")
            if max_positions < 1:
                raise ValueError("max_positions must be >= 1")
            if "max_hold_days" in self.params and self.params["max_hold_days"] is not None:
                if int(self.params["max_hold_days"]) < 1:
                    raise ValueError("max_hold_days must be >= 1")
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


class CompareRequest(BaseModel):
    """Same universe / period / guardrails; run one or more strategies side-by-side."""

    symbols: list[str] = Field(min_length=1)
    start_date: date
    end_date: date
    initial_cash: float = Field(default=100_000.0, gt=0)
    currency: Literal["USD"] = "USD"
    strategies: list[StrategyConfig] = Field(min_length=1)
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
    def validate_compare(self) -> CompareRequest:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        for strat in self.strategies:
            missing = set(strat.symbols) - set(self.symbols)
            if missing:
                raise ValueError(f"strategy symbols not in universe: {sorted(missing)}")
        return self


class CompareResponse(BaseModel):
    runs: list[BacktestResponse]


# --- Monte Carlo (Phase C) -------------------------------------------------


class MonteCarloRequest(BaseModel):
    """Parameters for a forward projection from a completed backtest's returns."""

    n_paths: int = Field(
        default=500,
        ge=10,
        le=2000,
        description="Number of simulated paths (capped for snappy UX)",
    )
    horizon_days: int = Field(
        default=252,
        ge=1,
        le=1260,
        description="Forward trading days to project",
    )
    seed: Optional[int] = Field(default=None, description="RNG seed for reproducibility")
    block_bootstrap: bool = Field(
        default=False,
        description="If true, resample contiguous blocks to keep mild autocorrelation",
    )
    block_size: int = Field(
        default=10,
        ge=1,
        le=63,
        description="Block length in trading days when block_bootstrap is true",
    )
    start_equity: Optional[float] = Field(
        default=None,
        gt=0,
        description="Override starting equity (default: backtest terminal equity)",
    )
    paths_sample_count: int = Field(
        default=0,
        ge=0,
        le=50,
        description="Optional thin sample of full equity paths for charting",
    )


class PercentileBand(BaseModel):
    day: int
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float


class TerminalReturnDist(BaseModel):
    mean: float
    std: float
    p5: float
    p50: float
    p95: float
    prob_below_start: float = Field(
        description="Share of paths ending below starting equity",
    )


class MonteCarloResult(BaseModel):
    percentile_bands: list[PercentileBand]
    terminal_return_dist: TerminalReturnDist
    paths_sample: Optional[list[list[float]]] = None
    start_equity: float
    n_paths: int
    horizon_days: int
    block_bootstrap: bool
    block_size: Optional[int] = None
    seed: Optional[int] = None
    assumptions: str


class MonteCarloResponse(BaseModel):
    id: UUID
    created_at: datetime
    backtest_run_id: UUID
    request: MonteCarloRequest
    result: MonteCarloResult
