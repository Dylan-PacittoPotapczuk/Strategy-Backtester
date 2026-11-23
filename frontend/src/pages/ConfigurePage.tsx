import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { runBacktest } from '../api'
import { FieldLabel, HelpTip } from '../components/HelpTip'
import { DEFINITIONS } from '../copy'
import {
  DEFAULT_MEAN_REVERSION,
  DEFAULT_MOMENTUM,
  STRATEGY_OPTIONS,
  meanReversionParamsPayload,
  momentumParamsPayload,
  type MeanReversionParams,
  type MomentumParams,
} from '../strategyMeta'
import type { BacktestRequest, StrategyType } from '../types'

const defaultForm = {
  symbols: 'SPY,QQQ',
  start_date: '2020-01-01',
  end_date: '2023-12-31',
  initial_cash: 100000,
  max_position_pct: 25,
  max_trade_loss_pct: 10,
  max_portfolio_drawdown_pct: 20,
  slippage_bps: 5,
  commission_per_trade: 0,
}

export function ConfigurePage() {
  const navigate = useNavigate()
  const [form, setForm] = useState(defaultForm)
  const [strategyType, setStrategyType] = useState<StrategyType>('buy_and_hold')
  const [momentum, setMomentum] = useState<MomentumParams>(DEFAULT_MOMENTUM)
  const [meanRev, setMeanRev] = useState<MeanReversionParams>(DEFAULT_MEAN_REVERSION)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function update<K extends keyof typeof defaultForm>(key: K, value: (typeof defaultForm)[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  function buildStrategyParams(symbols: string[]) {
    if (strategyType === 'momentum') {
      return {
        type: 'momentum' as const,
        symbols,
        params: momentumParamsPayload(momentum),
      }
    }
    if (strategyType === 'mean_reversion') {
      return {
        type: 'mean_reversion' as const,
        symbols,
        params: meanReversionParamsPayload(meanRev),
      }
    }
    return { type: 'buy_and_hold' as const, symbols, params: {} }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const symbols = form.symbols
        .split(/[,\s]+/)
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean)
      if (symbols.length === 0) {
        throw new Error('Enter at least one symbol (for example SPY or QQQ).')
      }
      if (form.start_date > form.end_date) {
        throw new Error('Start date must be on or before the end date.')
      }
      if (strategyType === 'momentum' && momentum.top_n > symbols.length) {
        throw new Error('Top N cannot be larger than the number of symbols.')
      }
      const body: BacktestRequest = {
        symbols,
        start_date: form.start_date,
        end_date: form.end_date,
        initial_cash: Number(form.initial_cash),
        currency: 'USD',
        strategy: buildStrategyParams(symbols),
        guardrails: {
          max_position_pct: Number(form.max_position_pct) / 100,
          max_trade_loss_pct: Number(form.max_trade_loss_pct) / 100,
          max_portfolio_drawdown_pct: Number(form.max_portfolio_drawdown_pct) / 100,
          sizing_mode: 'equal_weight',
          flatten_on_breach: false,
        },
        costs: {
          slippage_bps: Number(form.slippage_bps),
          commission_per_trade: Number(form.commission_per_trade),
        },
      }
      const result = await runBacktest(body)
      navigate(`/results/${result.id}`, { state: { result } })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  const selectedBlurb =
    STRATEGY_OPTIONS.find((o) => o.type === strategyType)?.blurb ?? DEFINITIONS.strategy

  return (
    <section className="panel configure">
      <header className="panel-head">
        <h1>Set up your test</h1>
        <p>
          Pick a strategy, set your stocks and dates, then apply risk limits that can cut size or
          sell when losses get large.
        </p>
      </header>

      <form className="config-form" onSubmit={onSubmit}>
        <fieldset className="config-section">
          <legend>1 · Setup</legend>
          <p className="section-lead">What to buy, when to test, and how much cash to start with.</p>
          <FieldLabel text="Stocks / ETFs" definition={DEFINITIONS.symbols}>
            <input
              value={form.symbols}
              onChange={(e) => update('symbols', e.target.value)}
              placeholder="SPY, QQQ, AAPL"
              required
              autoComplete="off"
            />
          </FieldLabel>
          <div className="row">
            <FieldLabel text="Start date" definition={DEFINITIONS.start_date}>
              <input
                type="date"
                value={form.start_date}
                onChange={(e) => update('start_date', e.target.value)}
                required
              />
            </FieldLabel>
            <FieldLabel text="End date" definition={DEFINITIONS.end_date}>
              <input
                type="date"
                value={form.end_date}
                onChange={(e) => update('end_date', e.target.value)}
                required
              />
            </FieldLabel>
            <FieldLabel text="Starting cash (USD)" definition={DEFINITIONS.initial_cash}>
              <input
                type="number"
                min={1}
                step={1}
                value={form.initial_cash}
                onChange={(e) => update('initial_cash', Number(e.target.value))}
                required
              />
            </FieldLabel>
          </div>

          <div className="strategy-block">
            <span className="label-row">
              <span className="label-text">Strategy</span>
              <HelpTip definition={DEFINITIONS.strategy} />
            </span>
            <div className="strategy-picker" role="radiogroup" aria-label="Strategy">
              {STRATEGY_OPTIONS.map((opt) => (
                <label
                  key={opt.type}
                  className={`strategy-option${strategyType === opt.type ? ' selected' : ''}`}
                >
                  <input
                    type="radio"
                    name="strategy"
                    value={opt.type}
                    checked={strategyType === opt.type}
                    onChange={() => setStrategyType(opt.type)}
                  />
                  <span className="strategy-option-label">
                    {opt.label}
                    <HelpTip
                      definition={
                        opt.type === 'buy_and_hold'
                          ? DEFINITIONS.strategy_buy_and_hold
                          : opt.type === 'momentum'
                            ? DEFINITIONS.strategy_momentum
                            : DEFINITIONS.strategy_mean_reversion
                      }
                    />
                  </span>
                </label>
              ))}
            </div>
            <p className="hint">{selectedBlurb}</p>

            {strategyType === 'momentum' && (
              <div className="strategy-params">
                <div className="row">
                  <FieldLabel text="Lookback (days)" definition={DEFINITIONS.lookback}>
                    <input
                      type="number"
                      min={1}
                      value={momentum.lookback}
                      onChange={(e) =>
                        setMomentum((p) => ({ ...p, lookback: Number(e.target.value) }))
                      }
                    />
                  </FieldLabel>
                  <FieldLabel text="Top N names" definition={DEFINITIONS.top_n}>
                    <input
                      type="number"
                      min={1}
                      value={momentum.top_n}
                      onChange={(e) =>
                        setMomentum((p) => ({ ...p, top_n: Number(e.target.value) }))
                      }
                    />
                  </FieldLabel>
                  <FieldLabel text="Rebalance every (days)" definition={DEFINITIONS.rebalance_days}>
                    <input
                      type="number"
                      min={1}
                      value={momentum.rebalance_days}
                      onChange={(e) =>
                        setMomentum((p) => ({ ...p, rebalance_days: Number(e.target.value) }))
                      }
                    />
                  </FieldLabel>
                </div>
                <div className="row">
                  <FieldLabel text="Skip recent days" definition={DEFINITIONS.skip_recent_days}>
                    <input
                      type="number"
                      min={0}
                      max={5}
                      value={momentum.skip_recent_days}
                      onChange={(e) =>
                        setMomentum((p) => ({ ...p, skip_recent_days: Number(e.target.value) }))
                      }
                    />
                  </FieldLabel>
                  <FieldLabel text="Weighting" definition={DEFINITIONS.weighting}>
                    <select
                      value={momentum.weighting}
                      onChange={(e) =>
                        setMomentum((p) => ({
                          ...p,
                          weighting: e.target.value as 'equal' | 'score',
                        }))
                      }
                    >
                      <option value="equal">Equal</option>
                      <option value="score">By score</option>
                    </select>
                  </FieldLabel>
                </div>
              </div>
            )}

            {strategyType === 'mean_reversion' && (
              <div className="strategy-params">
                <div className="row">
                  <FieldLabel text="Average window (days)" definition={DEFINITIONS.window}>
                    <input
                      type="number"
                      min={2}
                      value={meanRev.window}
                      onChange={(e) =>
                        setMeanRev((p) => ({ ...p, window: Number(e.target.value) }))
                      }
                    />
                  </FieldLabel>
                  <FieldLabel text="Entry z-score" definition={DEFINITIONS.entry_z}>
                    <input
                      type="number"
                      min={0.1}
                      step={0.1}
                      value={meanRev.entry_z}
                      onChange={(e) =>
                        setMeanRev((p) => ({ ...p, entry_z: Number(e.target.value) }))
                      }
                    />
                  </FieldLabel>
                  <FieldLabel text="Exit z-score" definition={DEFINITIONS.exit_z}>
                    <input
                      type="number"
                      min={0}
                      step={0.05}
                      value={meanRev.exit_z}
                      onChange={(e) =>
                        setMeanRev((p) => ({ ...p, exit_z: Number(e.target.value) }))
                      }
                    />
                  </FieldLabel>
                </div>
                <div className="row">
                  <FieldLabel text="Max positions" definition={DEFINITIONS.max_positions}>
                    <input
                      type="number"
                      min={1}
                      value={meanRev.max_positions}
                      onChange={(e) =>
                        setMeanRev((p) => ({ ...p, max_positions: Number(e.target.value) }))
                      }
                    />
                  </FieldLabel>
                  <FieldLabel text="Max hold days (optional)" definition={DEFINITIONS.max_hold_days}>
                    <input
                      type="number"
                      min={1}
                      placeholder="None"
                      value={meanRev.max_hold_days}
                      onChange={(e) =>
                        setMeanRev((p) => ({
                          ...p,
                          max_hold_days: e.target.value === '' ? '' : Number(e.target.value),
                        }))
                      }
                    />
                  </FieldLabel>
                </div>
              </div>
            )}
          </div>
        </fieldset>

        <fieldset className="config-section">
          <legend>2 · Risk limits</legend>
          <p className="section-lead">
            Guardrails that cap how much you put in one name and when losses force a sell or pause.
          </p>
          <div className="row">
            <FieldLabel text="Position size limit (%)" definition={DEFINITIONS.max_position_pct}>
              <input
                type="number"
                min={1}
                max={100}
                step={1}
                value={form.max_position_pct}
                onChange={(e) => update('max_position_pct', Number(e.target.value))}
              />
            </FieldLabel>
            <FieldLabel text="Per-trade loss limit (%)" definition={DEFINITIONS.max_trade_loss_pct}>
              <input
                type="number"
                min={1}
                max={100}
                step={1}
                value={form.max_trade_loss_pct}
                onChange={(e) => update('max_trade_loss_pct', Number(e.target.value))}
              />
            </FieldLabel>
            <FieldLabel
              text="Whole-portfolio drop limit (%)"
              definition={DEFINITIONS.max_portfolio_drawdown_pct}
            >
              <input
                type="number"
                min={1}
                max={100}
                step={1}
                value={form.max_portfolio_drawdown_pct}
                onChange={(e) => update('max_portfolio_drawdown_pct', Number(e.target.value))}
              />
            </FieldLabel>
          </div>
          <p className="hint">
            If the portfolio hits the drawdown limit, new buys stop. Open positions are not sold
            automatically.
          </p>
        </fieldset>

        <fieldset className="config-section">
          <legend>3 · Trading costs</legend>
          <p className="section-lead">
            Small costs applied on each fill so results are not unrealistically perfect.
          </p>
          <div className="row">
            <FieldLabel text="Slippage" definition={DEFINITIONS.slippage}>
              <input
                type="number"
                min={0}
                step={1}
                value={form.slippage_bps}
                onChange={(e) => update('slippage_bps', Number(e.target.value))}
                aria-describedby="slippage-unit"
              />
              <span id="slippage-unit" className="field-unit">
                in basis points (1 bp = 0.01%)
              </span>
            </FieldLabel>
            <FieldLabel text="Commission ($ per trade)" definition={DEFINITIONS.commission}>
              <input
                type="number"
                min={0}
                step={0.01}
                value={form.commission_per_trade}
                onChange={(e) => update('commission_per_trade', Number(e.target.value))}
              />
            </FieldLabel>
          </div>
          <p className="hint fill-hint">
            <span className="label-row inline">
              <span>Fills use the next day’s open</span>
              <HelpTip definition={DEFINITIONS.next_open_fill} />
            </span>
            <span className="hint-sep">·</span>
            <span>
              Default slippage is {form.slippage_bps} basis points (
              {(form.slippage_bps / 100).toFixed(2)}% of the trade price).
            </span>
          </p>
        </fieldset>

        {loading && (
          <div className="info-banner" role="status">
            Running your backtest… This usually takes a few seconds. Stay on this page.
          </div>
        )}

        {error && (
          <div className="error-banner" role="alert">
            <strong>Could not run the test.</strong> {error} Check your symbols and dates, then try
            again.
          </div>
        )}

        <div className="actions">
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Running…' : 'Run backtest'}
          </button>
          <Link className="btn-ghost" to="/compare">
            Compare strategies
          </Link>
        </div>
      </form>
    </section>
  )
}
