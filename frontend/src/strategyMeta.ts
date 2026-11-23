import type { StrategyType } from './types'

export const STRATEGY_OPTIONS: {
  type: StrategyType
  label: string
  short: string
  blurb: string
}[] = [
  {
    type: 'buy_and_hold',
    label: 'Buy & hold',
    short: 'Buy & hold',
    blurb: 'Buy at the start and keep the mix unless a risk rule sells.',
  },
  {
    type: 'momentum',
    label: 'Momentum',
    short: 'Momentum',
    blurb: 'Own the recent winners in your list and refresh that ranking on a schedule.',
  },
  {
    type: 'mean_reversion',
    label: 'Mean reversion',
    short: 'Mean reversion',
    blurb: 'Buy names that look unusually cheap vs their recent average; sell as they normalize.',
  },
]

export function strategyLabel(type: StrategyType): string {
  return STRATEGY_OPTIONS.find((o) => o.type === type)?.label ?? type
}

export type MomentumParams = {
  lookback: number
  top_n: number
  rebalance_days: number
  skip_recent_days: number
  weighting: 'equal' | 'score'
}

export type MeanReversionParams = {
  window: number
  entry_z: number
  exit_z: number
  max_hold_days: number | ''
  max_positions: number
}

export const DEFAULT_MOMENTUM: MomentumParams = {
  lookback: 63,
  top_n: 2,
  rebalance_days: 21,
  skip_recent_days: 0,
  weighting: 'equal',
}

export const DEFAULT_MEAN_REVERSION: MeanReversionParams = {
  window: 20,
  entry_z: 1.5,
  exit_z: 0.25,
  max_hold_days: '',
  max_positions: 3,
}

export function momentumParamsPayload(p: MomentumParams): Record<string, unknown> {
  return {
    lookback: Number(p.lookback),
    top_n: Number(p.top_n),
    rebalance_days: Number(p.rebalance_days),
    skip_recent_days: Number(p.skip_recent_days),
    weighting: p.weighting,
  }
}

export function meanReversionParamsPayload(p: MeanReversionParams): Record<string, unknown> {
  const out: Record<string, unknown> = {
    window: Number(p.window),
    entry_z: Number(p.entry_z),
    exit_z: Number(p.exit_z),
    max_positions: Number(p.max_positions),
  }
  if (p.max_hold_days !== '' && p.max_hold_days != null) {
    out.max_hold_days = Number(p.max_hold_days)
  }
  return out
}
