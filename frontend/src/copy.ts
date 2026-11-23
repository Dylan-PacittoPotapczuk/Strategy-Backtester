import type { TradeReason } from './types'

/** One-sentence definitions for non-experts. Primary UI labels stay plain English. */
export const DEFINITIONS = {
  symbols:
    'Ticker symbols of the stocks or ETFs you want to test, separated by commas.',
  start_date: 'First day included in the historical test.',
  end_date: 'Last day included in the historical test.',
  initial_cash: 'How much play money the test starts with, in US dollars.',
  strategy:
    'Buy-and-hold means buy at the start and keep the positions unless a risk rule sells them.',
  max_position_pct:
    'The largest share of your portfolio that can go into any single stock or ETF.',
  max_trade_loss_pct:
    'If one position loses this much from its buy price, the test sells it automatically.',
  max_portfolio_drawdown_pct:
    'If the whole portfolio falls this far from its peak, the test stops opening new buys.',
  slippage:
    'A small extra cost (entered in basis points) that mimics getting a slightly worse price than the quote — 5 means about 0.05%.',
  commission: 'A flat fee charged each time a buy or sell happens.',
  next_open_fill:
    'Trades are priced at the next day’s opening price, not the same-day close, to avoid peeking ahead.',
  total_return: 'Overall gain or loss from start to finish, as a percent of starting cash.',
  cagr: 'Average yearly return if gains and losses were smoothed across the full period.',
  sharpe:
    'Return compared with how bumpy the ride was — higher usually means better reward for the risk taken.',
  max_drawdown: 'The worst peak-to-trough drop in portfolio value during the test.',
  volatility: 'How much the portfolio’s day-to-day value tended to bounce around.',
  final_equity: 'What the portfolio was worth on the last day of the test.',
  num_trades: 'How many actual buys and sells were filled (not counting risk checks).',
  num_stop_losses: 'How many times a single-position loss limit forced a sell.',
  num_dd_halts: 'How many times the whole-portfolio drop limit stopped new buys.',
  equity_curve: 'Your portfolio’s dollar value from day to day across the test.',
  drawdown_chart:
    'How far the portfolio sat below its previous high — deeper means a larger temporary loss.',
  trades_table: 'Every buy, sell, and risk decision the engine recorded for this run.',
} as const

export type DefinitionKey = keyof typeof DEFINITIONS

export const REASON_LABELS: Record<TradeReason, string> = {
  signal: 'Strategy buy/sell',
  stop_loss: 'Loss limit sell',
  drawdown_halt: 'Portfolio drop halt',
  rebalance: 'Rebalance',
  sized_down: 'Size capped',
  rejected_dd: 'Blocked by drop limit',
  rejected_cash: 'Not enough cash',
  end_of_backtest: 'End of test',
}

export const REASON_DEFINITIONS: Record<TradeReason, string> = {
  signal: 'A normal buy or sell from the strategy rules.',
  stop_loss: 'Sold because this one position lost more than your per-trade loss limit.',
  drawdown_halt: 'Triggered because the whole portfolio fell too far from its peak.',
  rebalance: 'Adjusted holdings back toward the target mix.',
  sized_down: 'Buy size was reduced so it would not exceed the position size limit.',
  rejected_dd: 'New buy was blocked because the whole-portfolio drop limit was already hit.',
  rejected_cash: 'Order was cut back or skipped because there was not enough cash.',
  end_of_backtest: 'Positions closed or marked when the test period ended.',
}

export function reasonLabel(reason: TradeReason): string {
  return REASON_LABELS[reason] ?? reason.replaceAll('_', ' ')
}

export function reasonDefinition(reason: TradeReason): string {
  return REASON_DEFINITIONS[reason] ?? 'A recorded decision from the backtest engine.'
}

/** Turn engine note strings into short readable sentences when patterns match. */
export function humanizeNote(note: string | null | undefined): string {
  if (!note) return ''
  let text = note

  text = text.replace(
    /Target notional\s+([\d.]+)\s+capped to\s+([\d.]+)\s+by\s+max_position_pct=([\d.]+)/gi,
    (_m, target, capped, pct) => {
      const limitPct = (Number(pct) * 100).toFixed(0)
      return `Buy size cut from $${Number(target).toLocaleString('en-US', { maximumFractionDigits: 0 })} to $${Number(capped).toLocaleString('en-US', { maximumFractionDigits: 0 })} to stay within the ${limitPct}% position size limit`
    },
  )

  text = text.replace(
    /pnl_pct=(-?[\d.]+)\s*<=\s*-?([\d.]+)/gi,
    (_m, pnl, limit) => {
      const lossPct = (Math.abs(Number(pnl)) * 100).toFixed(1)
      const limitPct = (Number(limit) * 100).toFixed(0)
      return `Loss reached ${lossPct}%, which is past the ${limitPct}% per-trade loss limit`
    },
  )

  text = text.replace(
    /flatten_on_breach;\s*dd=(-?[\d.]+)/gi,
    (_m, dd) => {
      const ddPct = (Number(dd) * 100).toFixed(1)
      return `Portfolio was ${ddPct}% below its peak; positions flattened on breach`
    },
  )

  text = text.replace(
    /Scaled all entries by\s+([\d.]+)\s+due to insufficient cash/gi,
    (_m, scale) =>
      `All buys scaled to ${(Number(scale) * 100).toFixed(0)}% of target because cash ran short`,
  )

  text = text.replace(/New risk rejected:\s*portfolio drawdown halt active/gi, () => {
    return 'New buys blocked while the portfolio drawdown halt is active'
  })

  text = text.replace(/\s*\|\s*cash-scaled at fill/gi, ' (also scaled at fill for available cash)')
  text = text.replace(/no position to sell/gi, 'No open position to sell')

  return text
}
