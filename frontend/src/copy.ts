import type { TradeReason } from './types'

/** One-sentence definitions for non-experts. Primary UI labels stay plain English. */
export const DEFINITIONS = {
  symbols:
    'Ticker symbols of the stocks or ETFs you want to test, separated by commas.',
  start_date: 'First day included in the historical test.',
  end_date: 'Last day included in the historical test.',
  initial_cash: 'How much play money the test starts with, in US dollars.',
  strategy:
    'The rules that decide what to own. Pick buy & hold, momentum, or mean reversion.',
  strategy_buy_and_hold:
    'Buy at the start and keep the positions unless a risk rule sells them.',
  strategy_momentum:
    'Rank names by recent performance and hold the top ones, refreshing on a schedule.',
  strategy_mean_reversion:
    'Buy when a name looks unusually cheap versus its recent average; sell as it normalizes (long only).',
  lookback:
    'How many past trading days are used to measure recent performance for ranking.',
  top_n: 'How many of the strongest recent performers the strategy will hold at once.',
  rebalance_days: 'How often (in trading days) the ranking is refreshed and holdings updated.',
  skip_recent_days:
    'Ignore this many most-recent days when scoring momentum, to reduce short-term whipsaws.',
  weighting:
    'Equal splits money evenly across picks; score puts more into the stronger recent winners.',
  window: 'How many past trading days form the average and typical range for the z-score.',
  entry_z:
    'Buy when price is this many standard deviations below its recent average (more = pickier).',
  exit_z:
    'Sell when price has climbed back to within this many standard deviations of the average.',
  max_hold_days: 'Optional cap on how many trading days a mean-reversion buy can stay open.',
  max_positions: 'Maximum number of mean-reversion names held at the same time.',
  compare_strategies:
    'Which rule sets to run side-by-side on the same stocks, dates, cash, and risk limits.',
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
  compare_equity:
    'Portfolio value over time for each selected strategy on the same setup, drawn together.',
  drawdown_chart:
    'How far the portfolio sat below its previous high — deeper means a larger temporary loss.',
  trades_table: 'Every buy, sell, and risk decision the engine recorded for this run.',
  compare_table:
    'Side-by-side headline numbers for each strategy: return, risk-adjusted return, worst drop, and risk-rule counts.',
  monte_carlo:
    'A set of made-up future paths built by reshuffling this backtest’s daily returns — not a forecast, just a range of plausible outcomes.',
  mc_simulation:
    'One simulated future path of portfolio value, built by randomly drawing from the backtest’s day-to-day returns.',
  mc_n_paths:
    'How many alternate futures to simulate. More paths smooth the bands; the default stays modest so the page stays quick.',
  mc_horizon:
    'How many trading days into the future each path is projected (about 252 trading days ≈ one year).',
  mc_seed:
    'A number that locks the random draws so the same settings produce the same chart again.',
  mc_block_bootstrap:
    'When on, returns are drawn in short streaks instead of one day at a time, which keeps mild day-to-day dependence from the backtest.',
  mc_block_size:
    'Length of each streak (in trading days) when block resampling is on — typically about one to four weeks.',
  mc_percentile_path:
    'At each future day, the band edges show where a given share of simulated paths sat (for example, 5% were below the bottom edge).',
  mc_percentile_bands:
    'Shaded ranges of simulated portfolio value over time: outer band ≈ middle 90% of paths, inner band ≈ middle 50%, line = typical (median) path.',
  mc_terminal_band:
    'Where ending portfolio value (or return) landed across all simulations — summarized as mean, spread, and low/mid/high percentiles.',
  mc_terminal_return:
    'Gain or loss from the Monte Carlo start value to the end of each simulated path, as a percent.',
  mc_prob_below_start:
    'Share of simulated paths that finished worth less than they started — a rough chance of a loss over the horizon.',
  mc_assumptions:
    'Forward paths reuse the backtest’s risk-constrained daily returns. Stops and drawdown halts are not re-run on each fake path; treat bands as “similar behavior continues,” not a full re-simulation of risk rules.',
  walk_forward:
    'Split the test into an earlier “in-sample” stretch and a later “out-of-sample” holdout so you can see whether results hold up after the period used for judgment.',
  walk_forward_enabled:
    'When on, metrics are reported separately for the early (in-sample) window and the later (out-of-sample) window. Rules stay the same — this does not auto-search parameters.',
  walk_forward_mode:
    'Percent uses a share of trading days for the early window; date uses a calendar cutover you pick.',
  train_pct:
    'Share of trading days treated as in-sample (early). The rest is the out-of-sample holdout.',
  split_date:
    'First calendar day of the out-of-sample window. Days before this are in-sample.',
  metrics_in_sample:
    'Performance measured only on the early (train) window of the backtest.',
  metrics_out_of_sample:
    'Performance measured only on the later (test) holdout window — the cleaner check against overfitting.',
  no_oos_warning:
    'You are viewing full-history results with no holdout. Tuning knobs on the whole period can look better than they will on unseen data.',
  benchmark:
    'A simple buy-and-hold reference (default SPY) plotted beside your strategy so you can see if the rules beat doing nothing fancy.',
  benchmark_enabled:
    'When on, the Results chart always overlays buy-and-hold of the benchmark symbol on the same dates and starting cash.',
  benchmark_symbol:
    'Ticker used for the buy-and-hold reference line (for example SPY or QQQ).',
  excess_return:
    'Strategy total return minus benchmark total return over the same window — positive means you beat the reference.',
  excess_cagr:
    'Strategy average yearly return minus the benchmark’s — how much extra annualized growth versus buy-and-hold.',
  excess_sharpe:
    'Strategy risk-adjusted return minus the benchmark’s — positive means better reward-for-risk than the reference.',
  benchmark_equity:
    'Dollar value over time of buying the benchmark once and holding it (same start cash as your test).',
  saved_runs:
    'Recent backtests stored on this machine (SQLite). Open one to revisit results; optionally give it a name.',
  run_name:
    'A short label you choose so this run is easy to find in the saved list.',
  presets:
    'Named snapshots of the Configure form (symbols, dates, strategy, risk, costs, walk-forward, benchmark). Load one to restore settings without retyping.',
  preset_name: 'What to call this saved setup so you can load it later.',
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

  text = text.replace(/Exited:\s*no longer in target set/gi, 'Sold because it left the target set')
  text = text.replace(/Trimmed toward target weight/gi, 'Sold some shares to move closer to the target weight')
  text = text.replace(/Added toward target weight/gi, 'Bought more to move closer to the target weight')

  text = text.replace(/\s*\|\s*cash-scaled at fill/gi, ' (also scaled at fill for available cash)')
  text = text.replace(/no position to sell/gi, 'No open position to sell')

  return text
}
