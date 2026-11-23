export type TradeSide = 'buy' | 'sell'

export type TradeReason =
  | 'signal'
  | 'stop_loss'
  | 'drawdown_halt'
  | 'rebalance'
  | 'sized_down'
  | 'rejected_dd'
  | 'rejected_cash'
  | 'end_of_backtest'

export type StrategyType = 'buy_and_hold' | 'momentum' | 'mean_reversion'

export interface CostConfig {
  slippage_bps: number
  commission_per_trade: number
}

export interface GuardrailConfig {
  max_position_pct: number
  max_trade_loss_pct: number
  max_portfolio_drawdown_pct: number
  sizing_mode: 'fixed_pct' | 'equal_weight'
  flatten_on_breach: boolean
}

export interface StrategyConfig {
  type: StrategyType
  params: Record<string, unknown>
  symbols: string[]
}

export interface BacktestRequest {
  symbols: string[]
  start_date: string
  end_date: string
  initial_cash: number
  currency: 'USD'
  strategy: StrategyConfig
  guardrails: GuardrailConfig
  costs: CostConfig
}

export interface CompareRequest {
  symbols: string[]
  start_date: string
  end_date: string
  initial_cash: number
  currency: 'USD'
  strategies: StrategyConfig[]
  guardrails: GuardrailConfig
  costs: CostConfig
}

export interface Trade {
  id: string
  symbol: string
  side: TradeSide
  qty: number
  price: number
  ts: string
  reason: TradeReason
  pnl?: number | null
  pnl_pct?: number | null
  note?: string | null
}

export interface EquityPoint {
  date: string
  equity: number
  cash: number
  drawdown_pct: number
}

export interface Metrics {
  total_return: number
  cagr: number
  volatility: number
  sharpe: number
  max_drawdown: number
  win_rate?: number | null
  num_trades: number
  num_stop_losses: number
  num_dd_halts: number
  final_equity: number
  initial_cash: number
  trading_days: number
}

export interface BacktestResponse {
  id: string
  created_at: string
  status: 'pending' | 'running' | 'done' | 'failed'
  request: BacktestRequest
  equity_curve: EquityPoint[]
  trades: Trade[]
  metrics?: Metrics | null
  daily_returns: number[]
  error?: string | null
  dd_halted: boolean
  dd_halt_date?: string | null
}

export interface CompareResponse {
  runs: BacktestResponse[]
}

export interface MonteCarloRequest {
  n_paths?: number
  horizon_days?: number
  seed?: number | null
  block_bootstrap?: boolean
  block_size?: number
  start_equity?: number | null
  paths_sample_count?: number
}

export interface PercentileBand {
  day: number
  p5: number
  p25: number
  p50: number
  p75: number
  p95: number
}

export interface TerminalReturnDist {
  mean: number
  std: number
  p5: number
  p50: number
  p95: number
  prob_below_start: number
}

export interface MonteCarloResult {
  percentile_bands: PercentileBand[]
  terminal_return_dist: TerminalReturnDist
  paths_sample?: number[][] | null
  start_equity: number
  n_paths: number
  horizon_days: number
  block_bootstrap: boolean
  block_size?: number | null
  seed?: number | null
  assumptions: string
}

export interface MonteCarloResponse {
  id: string
  created_at: string
  backtest_run_id: string
  request: MonteCarloRequest
  result: MonteCarloResult
}
