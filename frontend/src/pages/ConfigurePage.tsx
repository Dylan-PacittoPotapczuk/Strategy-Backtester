import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { runBacktest } from '../api'
import { FieldLabel, HelpTip } from '../components/HelpTip'
import { DEFINITIONS } from '../copy'
import type { BacktestRequest } from '../types'

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
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function update<K extends keyof typeof defaultForm>(key: K, value: (typeof defaultForm)[K]) {
    setForm((f) => ({ ...f, [key]: value }))
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
      const body: BacktestRequest = {
        symbols,
        start_date: form.start_date,
        end_date: form.end_date,
        initial_cash: Number(form.initial_cash),
        currency: 'USD',
        strategy: {
          type: 'buy_and_hold',
          symbols,
          params: {},
        },
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

  return (
    <section className="panel configure">
      <header className="panel-head">
        <h1>Set up your test</h1>
        <p>
          See how a simple buy-and-hold portfolio would have done, with risk limits that can cut
          position size or sell when losses get large.
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
            <div className="strategy-pill">Buy &amp; hold · equal weight · no rebalancing</div>
            <p className="hint">
              Buys at the start and holds unless a risk rule sells. Other strategies come later.
            </p>
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
            automatically in this phase.
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
        </div>
      </form>
    </section>
  )
}
