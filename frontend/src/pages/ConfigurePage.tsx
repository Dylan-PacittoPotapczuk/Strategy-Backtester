import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { runBacktest } from '../api'
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
        throw new Error('Enter at least one symbol')
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
        <h1>Configure run</h1>
        <p>
          Buy-and-hold equities/ETFs with position sizing, per-trade stop, and portfolio drawdown
          halt. Fills at next open; ~{form.slippage_bps} bps slippage.
        </p>
      </header>

      <form className="config-form" onSubmit={onSubmit}>
        <fieldset>
          <legend>Universe</legend>
          <label>
            Symbols
            <input
              value={form.symbols}
              onChange={(e) => update('symbols', e.target.value)}
              placeholder="SPY, QQQ, AAPL"
              required
            />
          </label>
          <div className="row">
            <label>
              Start
              <input
                type="date"
                value={form.start_date}
                onChange={(e) => update('start_date', e.target.value)}
                required
              />
            </label>
            <label>
              End
              <input
                type="date"
                value={form.end_date}
                onChange={(e) => update('end_date', e.target.value)}
                required
              />
            </label>
            <label>
              Initial cash (USD)
              <input
                type="number"
                min={1}
                step={1}
                value={form.initial_cash}
                onChange={(e) => update('initial_cash', Number(e.target.value))}
                required
              />
            </label>
          </div>
        </fieldset>

        <fieldset>
          <legend>Strategy</legend>
          <div className="strategy-pill">Buy &amp; hold · equal weight · never rebalance</div>
          <p className="hint">Momentum and mean reversion arrive in Phase B.</p>
        </fieldset>

        <fieldset>
          <legend>Risk guardrails</legend>
          <div className="row">
            <label>
              Max position %
              <input
                type="number"
                min={1}
                max={100}
                step={1}
                value={form.max_position_pct}
                onChange={(e) => update('max_position_pct', Number(e.target.value))}
              />
            </label>
            <label>
              Per-trade loss limit %
              <input
                type="number"
                min={1}
                max={100}
                step={1}
                value={form.max_trade_loss_pct}
                onChange={(e) => update('max_trade_loss_pct', Number(e.target.value))}
              />
            </label>
            <label>
              Portfolio DD limit %
              <input
                type="number"
                min={1}
                max={100}
                step={1}
                value={form.max_portfolio_drawdown_pct}
                onChange={(e) => update('max_portfolio_drawdown_pct', Number(e.target.value))}
              />
            </label>
          </div>
          <p className="hint">
            On DD breach, new risk is halted; open positions are not auto-flattened.
          </p>
        </fieldset>

        <fieldset>
          <legend>Costs</legend>
          <div className="row">
            <label>
              Slippage (bps)
              <input
                type="number"
                min={0}
                step={1}
                value={form.slippage_bps}
                onChange={(e) => update('slippage_bps', Number(e.target.value))}
              />
            </label>
            <label>
              Commission ($ / trade)
              <input
                type="number"
                min={0}
                step={0.01}
                value={form.commission_per_trade}
                onChange={(e) => update('commission_per_trade', Number(e.target.value))}
              />
            </label>
          </div>
        </fieldset>

        {error && <div className="error-banner" role="alert">{error}</div>}

        <div className="actions">
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Running…' : 'Run backtest'}
          </button>
        </div>
      </form>
    </section>
  )
}
