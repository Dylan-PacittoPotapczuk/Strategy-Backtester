import { useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { runCompare } from '../api'
import { FieldLabel, HeadingWithHelp, HelpTip } from '../components/HelpTip'
import { DEFINITIONS } from '../copy'
import { formatDate, formatDateShort, num, pct, usd } from '../format'
import {
  DEFAULT_MEAN_REVERSION,
  DEFAULT_MOMENTUM,
  STRATEGY_OPTIONS,
  meanReversionParamsPayload,
  momentumParamsPayload,
  strategyLabel,
  type MeanReversionParams,
  type MomentumParams,
} from '../strategyMeta'
import type { BacktestResponse, CompareRequest, StrategyType } from '../types'

const COLORS: Record<StrategyType, string> = {
  buy_and_hold: '#0f6e56',
  momentum: '#1d4f91',
  mean_reversion: '#9a3412',
}

const defaultForm = {
  symbols: 'SPY,QQQ,IWM',
  start_date: '2020-01-01',
  end_date: '2023-12-31',
  initial_cash: 100000,
  max_position_pct: 25,
  max_trade_loss_pct: 10,
  max_portfolio_drawdown_pct: 20,
  slippage_bps: 5,
  commission_per_trade: 0,
}

export function ComparePage() {
  const [form, setForm] = useState(defaultForm)
  const [selected, setSelected] = useState<Record<StrategyType, boolean>>({
    buy_and_hold: true,
    momentum: true,
    mean_reversion: true,
  })
  const [momentum, setMomentum] = useState<MomentumParams>(DEFAULT_MOMENTUM)
  const [meanRev, setMeanRev] = useState<MeanReversionParams>(DEFAULT_MEAN_REVERSION)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [runs, setRuns] = useState<BacktestResponse[] | null>(null)

  function update<K extends keyof typeof defaultForm>(key: K, value: (typeof defaultForm)[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  function toggle(type: StrategyType) {
    setSelected((s) => ({ ...s, [type]: !s[type] }))
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    setRuns(null)
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
      const types = (Object.keys(selected) as StrategyType[]).filter((t) => selected[t])
      if (types.length === 0) {
        throw new Error('Select at least one strategy to compare.')
      }
      if (selected.momentum && momentum.top_n > symbols.length) {
        throw new Error('Momentum Top N cannot be larger than the number of symbols.')
      }

      const strategies = types.map((type) => {
        if (type === 'momentum') {
          return {
            type,
            symbols,
            params: momentumParamsPayload(momentum),
          }
        }
        if (type === 'mean_reversion') {
          return {
            type,
            symbols,
            params: meanReversionParamsPayload(meanRev),
          }
        }
        return { type, symbols, params: {} }
      })

      const body: CompareRequest = {
        symbols,
        start_date: form.start_date,
        end_date: form.end_date,
        initial_cash: Number(form.initial_cash),
        currency: 'USD',
        strategies,
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
      const result = await runCompare(body)
      setRuns(result.runs)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  const chartData = useMemo(() => {
    if (!runs || runs.length === 0) return []
    const byDate = new Map<string, Record<string, number | string>>()
    for (const run of runs) {
      const key = run.request.strategy.type
      for (const pt of run.equity_curve) {
        const row = byDate.get(pt.date) ?? { date: pt.date }
        row[key] = Math.round(pt.equity * 100) / 100
        byDate.set(pt.date, row)
      }
    }
    return Array.from(byDate.values()).sort((a, b) =>
      String(a.date).localeCompare(String(b.date)),
    )
  }, [runs])

  return (
    <section className="panel compare">
      <header className="panel-head">
        <h1>Compare strategies</h1>
        <p>
          Same stocks, dates, cash, and risk limits — run the strategies you select and overlay
          their portfolio values.
        </p>
      </header>

      <form className="config-form" onSubmit={onSubmit}>
        <fieldset className="config-section">
          <legend>Shared setup</legend>
          <p className="section-lead">
            Universe, period, cash, and costs apply to every strategy in this comparison.
          </p>
          <FieldLabel text="Stocks / ETFs" definition={DEFINITIONS.symbols}>
            <input
              value={form.symbols}
              onChange={(e) => update('symbols', e.target.value)}
              placeholder="SPY, QQQ, IWM"
              required
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
                value={form.initial_cash}
                onChange={(e) => update('initial_cash', Number(e.target.value))}
                required
              />
            </FieldLabel>
          </div>
          <div className="row">
            <FieldLabel text="Position size limit (%)" definition={DEFINITIONS.max_position_pct}>
              <input
                type="number"
                min={1}
                max={100}
                value={form.max_position_pct}
                onChange={(e) => update('max_position_pct', Number(e.target.value))}
              />
            </FieldLabel>
            <FieldLabel text="Per-trade loss limit (%)" definition={DEFINITIONS.max_trade_loss_pct}>
              <input
                type="number"
                min={1}
                max={100}
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
                value={form.max_portfolio_drawdown_pct}
                onChange={(e) => update('max_portfolio_drawdown_pct', Number(e.target.value))}
              />
            </FieldLabel>
          </div>
          <div className="row">
            <FieldLabel text="Slippage" definition={DEFINITIONS.slippage}>
              <input
                type="number"
                min={0}
                value={form.slippage_bps}
                onChange={(e) => update('slippage_bps', Number(e.target.value))}
              />
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
        </fieldset>

        <fieldset className="config-section">
          <legend>Strategies to compare</legend>
          <p className="section-lead">
            <span className="label-row inline">
              <span>Choose one or more rule sets</span>
              <HelpTip definition={DEFINITIONS.compare_strategies} />
            </span>
          </p>
          <div className="strategy-picker compare-picker">
            {STRATEGY_OPTIONS.map((opt) => (
              <label
                key={opt.type}
                className={`strategy-option${selected[opt.type] ? ' selected' : ''}`}
              >
                <input
                  type="checkbox"
                  checked={selected[opt.type]}
                  onChange={() => toggle(opt.type)}
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

          {selected.momentum && (
            <div className="strategy-params">
              <h3 className="params-title">Momentum settings</h3>
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

          {selected.mean_reversion && (
            <div className="strategy-params">
              <h3 className="params-title">Mean reversion settings</h3>
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
        </fieldset>

        {loading && (
          <div className="info-banner" role="status">
            Running comparison… Each strategy uses the same market data and risk limits.
          </div>
        )}
        {error && (
          <div className="error-banner" role="alert">
            <strong>Could not compare.</strong> {error}
          </div>
        )}

        <div className="actions">
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Comparing…' : 'Run comparison'}
          </button>
          <Link className="btn-ghost" to="/">
            ← Single backtest
          </Link>
        </div>
      </form>

      {runs && runs.length > 0 && (
        <div className="compare-results">
          <section className="results-section chart-block" aria-labelledby="compare-equity">
            <HeadingWithHelp
              as="h2"
              text="Portfolio value over time"
              definition={DEFINITIONS.compare_equity}
              className="section-title"
            />
            <p className="chart-caption" id="compare-equity">
              Overlay of each selected strategy on the shared setup. Colors match the table below.
            </p>
            <div className="chart-frame chart-frame-primary">
              <ResponsiveContainer width="100%" height={340}>
                <LineChart data={chartData} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
                  <CartesianGrid stroke="rgba(20,30,28,0.08)" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11, fill: '#5a6b63' }}
                    minTickGap={48}
                    tickFormatter={formatDateShort}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: '#5a6b63' }}
                    tickFormatter={(v) => `$${Math.round(Number(v) / 1000)}k`}
                    width={56}
                  />
                  <Tooltip
                    formatter={(value, name) => [
                      usd(Number(value)),
                      strategyLabel(String(name) as StrategyType),
                    ]}
                    labelFormatter={(l) => formatDate(String(l))}
                  />
                  <Legend formatter={(value) => strategyLabel(value as StrategyType)} />
                  {runs.map((run) => {
                    const type = run.request.strategy.type
                    return (
                      <Line
                        key={run.id}
                        type="monotone"
                        dataKey={type}
                        name={type}
                        stroke={COLORS[type]}
                        strokeWidth={2}
                        dot={false}
                        connectNulls
                      />
                    )
                  })}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="results-section" aria-labelledby="compare-metrics">
            <HeadingWithHelp
              as="h2"
              text="Side-by-side metrics"
              definition={DEFINITIONS.compare_table}
              className="section-title"
            />
            <p className="chart-caption" id="compare-metrics">
              Return, risk-adjusted return, worst drop, and how often risk rules fired.
            </p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Strategy</th>
                    <th>
                      <span className="th-with-help">
                        Total return
                        <HelpTip definition={DEFINITIONS.total_return} />
                      </span>
                    </th>
                    <th>
                      <span className="th-with-help">
                        Risk-adjusted
                        <HelpTip definition={DEFINITIONS.sharpe} />
                      </span>
                    </th>
                    <th>
                      <span className="th-with-help">
                        Worst drop
                        <HelpTip definition={DEFINITIONS.max_drawdown} />
                      </span>
                    </th>
                    <th>
                      <span className="th-with-help">
                        Loss-limit sells
                        <HelpTip definition={DEFINITIONS.num_stop_losses} />
                      </span>
                    </th>
                    <th>
                      <span className="th-with-help">
                        Drop-limit pauses
                        <HelpTip definition={DEFINITIONS.num_dd_halts} />
                      </span>
                    </th>
                    <th>Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => {
                    const m = run.metrics
                    const type = run.request.strategy.type
                    if (!m) return null
                    return (
                      <tr key={run.id}>
                        <td>
                          <span
                            className="swatch"
                            style={{ background: COLORS[type] }}
                            aria-hidden
                          />
                          {strategyLabel(type)}
                        </td>
                        <td className={m.total_return >= 0 ? 'buy' : 'sell'}>
                          {pct(m.total_return)}
                        </td>
                        <td>{num(m.sharpe)}</td>
                        <td className="sell">{pct(m.max_drawdown)}</td>
                        <td>{m.num_stop_losses}</td>
                        <td>{m.num_dd_halts}</td>
                        <td>
                          <Link to={`/results/${run.id}`} state={{ result: run }}>
                            View run
                          </Link>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <p className="hint">
              Comparing many parameter choices on the same history can overfit — treat this as
              exploration, not a guarantee of future results. Open <strong>View run</strong> on any
              row to see full results and run a Monte Carlo forward projection from that
              strategy’s returns.
            </p>
          </section>
        </div>
      )}
    </section>
  )
}
