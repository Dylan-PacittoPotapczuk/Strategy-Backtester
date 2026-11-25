import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getBacktest, renameBacktest } from '../api'
import { ExportButtons } from '../components/ExportButtons'
import { HeadingWithHelp, HelpTip } from '../components/HelpTip'
import { MonteCarloSection } from '../components/MonteCarloSection'
import {
  DEFINITIONS,
  humanizeNote,
  reasonDefinition,
  reasonLabel,
} from '../copy'
import { formatDate, formatDateShort, num, pct, usd, usdPrecise } from '../format'
import { strategyLabel } from '../strategyMeta'
import type { BacktestResponse, Metrics, TradeReason } from '../types'

export function ResultsPage() {
  const { runId } = useParams<{ runId: string }>()
  const location = useLocation()
  const cached = (location.state as { result?: BacktestResponse } | null)?.result
  const [result, setResult] = useState<BacktestResponse | null>(
    cached && cached.id === runId ? cached : null,
  )
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(!cached || cached.id !== runId)
  const [nameDraft, setNameDraft] = useState('')
  const [renaming, setRenaming] = useState(false)
  const [mcId, setMcId] = useState<string | null>(null)

  useEffect(() => {
    if (!runId || (result && result.id === runId)) {
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    getBacktest(runId)
      .then((r) => {
        if (!cancelled) {
          setResult(r)
          setNameDraft(r.name || '')
          setLoading(false)
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e))
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [runId, result])

  useEffect(() => {
    if (result) setNameDraft(result.name || '')
  }, [result])

  const equityData = useMemo(() => {
    if (!result) return []
    const byDate = new Map<string, Record<string, number | string>>()
    for (const p of result.equity_curve) {
      byDate.set(p.date, {
        date: p.date,
        strategy: Math.round(p.equity * 100) / 100,
        drawdown: Math.round(p.drawdown_pct * 10000) / 100,
      })
    }
    if (result.benchmark?.equity_curve) {
      for (const p of result.benchmark.equity_curve) {
        const row = byDate.get(p.date) ?? { date: p.date }
        row.benchmark = Math.round(p.equity * 100) / 100
        byDate.set(p.date, row)
      }
    }
    return Array.from(byDate.values()).sort((a, b) =>
      String(a.date).localeCompare(String(b.date)),
    )
  }, [result])

  if (error) {
    return (
      <section className="panel">
        <header className="panel-head">
          <h1>Results unavailable</h1>
          <p>We could not load this backtest. It may have expired or the id is wrong.</p>
        </header>
        <div className="error-banner" role="alert">
          {error}
        </div>
        <p className="state-next">
          <Link className="btn-primary" to="/">
            Set up a new test
          </Link>
        </p>
      </section>
    )
  }

  if (loading || !result || !result.metrics) {
    return (
      <section className="panel">
        <header className="panel-head">
          <h1>Loading results</h1>
          <p>Fetching the equity curve, risk metrics, and trade list…</p>
        </header>
        <div className="info-banner" role="status">
          Almost there. If this hangs, go back and run the test again.
        </div>
        <p className="state-next">
          <Link className="btn-ghost" to="/">
            ← Back to setup
          </Link>
        </p>
      </section>
    )
  }

  const m = result.metrics
  const filledTrades = result.trades.filter((t) => t.qty > 0)
  const riskEvents = result.trades.filter((t) => t.qty === 0)
  const wf = result.walk_forward
  const bench = result.benchmark

  async function saveName() {
    if (!result || !nameDraft.trim()) return
    setRenaming(true)
    try {
      const updated = await renameBacktest(result.id, nameDraft.trim())
      setResult(updated)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRenaming(false)
    }
  }

  return (
    <section className="panel results">
      <header className="panel-head results-head">
        <div>
          <h1>Results</h1>
          <p>
            {strategyLabel(result.request.strategy.type)} · {result.request.symbols.join(', ')} ·{' '}
            {formatDate(result.request.start_date)} → {formatDate(result.request.end_date)}
          </p>
          <div className="run-name-edit">
            <FieldNameInput
              value={nameDraft}
              onChange={setNameDraft}
              onSave={saveName}
              saving={renaming}
            />
          </div>
        </div>
        <div className="head-actions">
          <Link className="btn-ghost" to="/runs">
            Saved runs
          </Link>
          <Link className="btn-ghost" to="/">
            New test
          </Link>
        </div>
      </header>

      <ExportButtons mode="results" runId={result.id} mcId={mcId} />

      {result.dd_halted && (
        <div className="warn-banner">
          Portfolio drawdown limit was hit
          {result.dd_halt_date ? ` on ${formatDate(result.dd_halt_date)}` : ''}. New buys were
          blocked after that; open positions were not sold automatically.
        </div>
      )}

      {result.no_oos_warning && (
        <div className="warn-banner" role="status">
          <span className="label-row inline">
            <strong>No out-of-sample holdout.</strong>
            <HelpTip definition={DEFINITIONS.no_oos_warning} />
          </span>{' '}
          {result.no_oos_warning}
        </div>
      )}

      <section className="results-section summary-section" aria-labelledby="summary-heading">
        <h2 id="summary-heading" className="section-title">
          Results summary
        </h2>
        <p className="section-lead">
          The headline numbers. Open “?” for a plain-English definition of each metric.
        </p>

        <div className="metrics-hero">
          <Metric
            label="Total return"
            value={pct(m.total_return)}
            definition={DEFINITIONS.total_return}
            emphasize
            tone={m.total_return >= 0 ? 'up' : 'down'}
          />
          <Metric
            label="Ending value"
            value={usd(m.final_equity)}
            definition={DEFINITIONS.final_equity}
            emphasize
          />
          <Metric
            label="Worst drop"
            value={pct(m.max_drawdown)}
            definition={DEFINITIONS.max_drawdown}
            emphasize
            tone="down"
          />
        </div>

        <div className="metrics-secondary">
          <Metric label="Avg yearly return" value={pct(m.cagr)} definition={DEFINITIONS.cagr} />
          <Metric
            label="Risk-adjusted return"
            value={num(m.sharpe)}
            definition={DEFINITIONS.sharpe}
          />
          <Metric
            label="Day-to-day swings"
            value={pct(m.volatility)}
            definition={DEFINITIONS.volatility}
          />
          <Metric
            label="Filled trades"
            value={String(m.num_trades)}
            definition={DEFINITIONS.num_trades}
          />
          <Metric
            label="Loss-limit sells"
            value={String(m.num_stop_losses)}
            definition={DEFINITIONS.num_stop_losses}
          />
          <Metric
            label="Drop-limit pauses"
            value={String(m.num_dd_halts)}
            definition={DEFINITIONS.num_dd_halts}
          />
        </div>
      </section>

      {wf?.enabled && wf.metrics_in_sample && wf.metrics_out_of_sample && (
        <section className="results-section" aria-labelledby="wf-heading">
          <HeadingWithHelp
            as="h2"
            text="In-sample vs out-of-sample"
            definition={DEFINITIONS.walk_forward}
            className="section-title"
          />
          <p className="chart-caption" id="wf-heading">
            Split on {wf.split_date ? formatDate(wf.split_date) : '—'} ·{' '}
            {wf.train_trading_days} in-sample days · {wf.test_trading_days} out-of-sample days
            {wf.train_pct_used != null
              ? ` · ~${Math.round(wf.train_pct_used * 100)}% in-sample`
              : ''}
            . Same rules throughout — not an automatic parameter search.
          </p>
          <div className="wf-grid">
            <div className="wf-card">
              <h3>
                <span className="label-row inline">
                  In-sample
                  <HelpTip definition={DEFINITIONS.metrics_in_sample} />
                </span>
              </h3>
              <SegmentMetrics m={wf.metrics_in_sample} />
            </div>
            <div className="wf-card wf-card-oos">
              <h3>
                <span className="label-row inline">
                  Out-of-sample
                  <HelpTip definition={DEFINITIONS.metrics_out_of_sample} />
                </span>
              </h3>
              <SegmentMetrics m={wf.metrics_out_of_sample} />
            </div>
          </div>
        </section>
      )}

      {bench?.enabled && bench.metrics && (
        <section className="results-section" aria-labelledby="bench-heading">
          <HeadingWithHelp
            as="h2"
            text={`Versus ${bench.symbol} buy-and-hold`}
            definition={DEFINITIONS.benchmark}
            className="section-title"
          />
          <p className="chart-caption" id="bench-heading">
            Same start cash and dates. Excess metrics = strategy minus benchmark.
          </p>
          <div className="metrics-secondary">
            <Metric
              label={`${bench.symbol} total return`}
              value={pct(bench.metrics.total_return)}
              definition={DEFINITIONS.total_return}
            />
            <Metric
              label="Excess return"
              value={pct(bench.excess_return ?? 0)}
              definition={DEFINITIONS.excess_return}
              tone={(bench.excess_return ?? 0) >= 0 ? 'up' : 'down'}
            />
            <Metric
              label="Excess yearly return"
              value={pct(bench.excess_cagr ?? 0)}
              definition={DEFINITIONS.excess_cagr}
            />
            <Metric
              label="Excess risk-adjusted"
              value={num(bench.excess_sharpe ?? 0)}
              definition={DEFINITIONS.excess_sharpe}
            />
          </div>
        </section>
      )}

      <section className="results-section chart-block" aria-labelledby="equity-heading">
        <HeadingWithHelp
          as="h2"
          text="Portfolio value over time"
          definition={DEFINITIONS.equity_curve}
          className="section-title"
        />
        <p className="chart-caption" id="equity-heading">
          Dollar value of the portfolio each day
          {bench?.enabled ? `, with ${bench.symbol} buy-and-hold overlaid` : ''}.
          {wf?.enabled && wf.split_date
            ? ` Vertical note: out-of-sample starts ${formatDate(wf.split_date)}.`
            : ''}
        </p>
        <div className="chart-frame chart-frame-primary">
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={equityData} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
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
                label={{
                  value: 'Portfolio ($)',
                  angle: -90,
                  position: 'insideLeft',
                  offset: 10,
                  style: { fontSize: 11, fill: '#5a6b63' },
                }}
              />
              <Tooltip
                formatter={(value, name) => [
                  usdPrecise(Number(value)),
                  name === 'benchmark'
                    ? `${bench?.symbol ?? 'Benchmark'} buy & hold`
                    : 'Strategy',
                ]}
                labelFormatter={(l) => formatDate(String(l))}
              />
              <Legend
                formatter={(value) =>
                  value === 'benchmark'
                    ? `${bench?.symbol ?? 'Benchmark'} buy & hold`
                    : 'Strategy'
                }
              />
              {wf?.enabled && wf.split_date && (
                <ReferenceLine
                  x={wf.split_date}
                  stroke="#9a3412"
                  strokeDasharray="4 4"
                  label={{
                    value: 'OOS →',
                    position: 'insideTopRight',
                    fill: '#9a3412',
                    fontSize: 11,
                  }}
                />
              )}
              <Line
                type="monotone"
                dataKey="strategy"
                name="strategy"
                stroke="#0f6e56"
                strokeWidth={2}
                dot={false}
                connectNulls
              />
              {bench?.enabled && (
                <Line
                  type="monotone"
                  dataKey="benchmark"
                  name="benchmark"
                  stroke="#6b7280"
                  strokeWidth={2}
                  strokeDasharray="6 4"
                  dot={false}
                  connectNulls
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="results-section chart-block" aria-labelledby="dd-heading">
        <HeadingWithHelp
          as="h2"
          text="Drawdown from peak"
          definition={DEFINITIONS.drawdown_chart}
          className="section-title"
        />
        <p className="chart-caption" id="dd-heading">
          How far below the previous high the portfolio sat. Deeper = a larger temporary loss from
          the peak.
        </p>
        <div className="chart-frame">
          <ResponsiveContainer width="100%" height={190}>
            <LineChart data={equityData} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
              <CartesianGrid stroke="rgba(20,30,28,0.08)" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: '#5a6b63' }}
                minTickGap={48}
                tickFormatter={formatDateShort}
              />
              <YAxis
                tick={{ fontSize: 11, fill: '#5a6b63' }}
                tickFormatter={(v) => `${v}%`}
                width={48}
                reversed
              />
              <Tooltip
                formatter={(value) => [`${Number(value).toFixed(2)}%`, 'Below peak']}
                labelFormatter={(l) => formatDate(String(l))}
              />
              <Line
                type="monotone"
                dataKey="drawdown"
                name="Below peak"
                stroke="#b42318"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <MonteCarloSection
        backtestId={result.id}
        defaultStartEquity={m.final_equity}
        onResult={(mc) => setMcId(mc?.id ?? null)}
      />

      <section className="results-section trades-block" aria-labelledby="trades-heading">
        <HeadingWithHelp
          as="h2"
          text="Trades & risk decisions"
          definition={DEFINITIONS.trades_table}
          className="section-title"
        />
        <p className="chart-caption" id="trades-heading">
          Filled buys and sells first. Risk checks (size caps, blocks) are listed afterward when
          they did not create a fill.
        </p>

        {filledTrades.length === 0 ? (
          <div className="empty-banner">
            No filled trades in this run. Try a wider date range or looser risk limits, then run
            again from setup.
          </div>
        ) : (
          <TradeTable trades={filledTrades} />
        )}

        {riskEvents.length > 0 && (
          <details className="risk-events">
            <summary>
              {riskEvents.length} risk check{riskEvents.length === 1 ? '' : 's'} without a fill
            </summary>
            <p className="hint">
              These rows explain sizing or blocks. They are not buys or sells in the market.
            </p>
            <TradeTable trades={riskEvents} />
          </details>
        )}
      </section>
    </section>
  )
}

function FieldNameInput({
  value,
  onChange,
  onSave,
  saving,
}: {
  value: string
  onChange: (v: string) => void
  onSave: () => void
  saving: boolean
}) {
  return (
    <span className="inline-rename">
      <span className="label-row inline">
        <span className="muted-label">Name</span>
        <HelpTip definition={DEFINITIONS.run_name} />
      </span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Untitled run"
        aria-label="Run name"
      />
      <button type="button" className="btn-ghost btn-small" onClick={onSave} disabled={saving}>
        {saving ? 'Saving…' : 'Save name'}
      </button>
    </span>
  )
}

function SegmentMetrics({ m }: { m: Metrics }) {
  return (
    <div className="metrics-secondary compact">
      <Metric label="Total return" value={pct(m.total_return)} definition={DEFINITIONS.total_return} />
      <Metric label="Risk-adjusted" value={num(m.sharpe)} definition={DEFINITIONS.sharpe} />
      <Metric label="Worst drop" value={pct(m.max_drawdown)} definition={DEFINITIONS.max_drawdown} />
      <Metric label="Filled trades" value={String(m.num_trades)} definition={DEFINITIONS.num_trades} />
    </div>
  )
}

function Metric({
  label,
  value,
  definition,
  emphasize,
  tone,
}: {
  label: string
  value: string
  definition: string
  emphasize?: boolean
  tone?: 'up' | 'down'
}) {
  return (
    <div className={`metric${emphasize ? ' metric-emphasize' : ''}${tone ? ` metric-${tone}` : ''}`}>
      <span className="metric-label">
        <span>{label}</span>
        <HelpTip definition={definition} />
      </span>
      <span className="metric-value">{value}</span>
    </div>
  )
}

function TradeTable({ trades }: { trades: BacktestResponse['trades'] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Symbol</th>
            <th>Side</th>
            <th>Shares</th>
            <th>Price</th>
            <th>Why</th>
            <th>Profit / loss</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <tr key={t.id}>
              <td>{formatDate(t.ts)}</td>
              <td>{t.symbol}</td>
              <td className={t.side}>{t.side === 'buy' ? 'Buy' : 'Sell'}</td>
              <td>{t.qty ? num(t.qty, 4) : '—'}</td>
              <td>{t.price ? usdPrecise(t.price) : '—'}</td>
              <td>
                <ReasonBadge reason={t.reason} />
              </td>
              <td>
                {t.pnl != null
                  ? `${usdPrecise(t.pnl)}${t.pnl_pct != null ? ` (${pct(t.pnl_pct)})` : ''}`
                  : '—'}
              </td>
              <td className="note">{humanizeNote(t.note)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ReasonBadge({ reason }: { reason: TradeReason }) {
  return (
    <span className={`reason reason-${reason}`}>
      <span>{reasonLabel(reason)}</span>
      <HelpTip definition={reasonDefinition(reason)} />
    </span>
  )
}
