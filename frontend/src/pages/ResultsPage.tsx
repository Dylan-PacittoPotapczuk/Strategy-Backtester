import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getBacktest } from '../api'
import { HeadingWithHelp, HelpTip } from '../components/HelpTip'
import {
  DEFINITIONS,
  humanizeNote,
  reasonDefinition,
  reasonLabel,
} from '../copy'
import { formatDate, formatDateShort, num, pct, usd, usdPrecise } from '../format'
import type { BacktestResponse, TradeReason } from '../types'

export function ResultsPage() {
  const { runId } = useParams<{ runId: string }>()
  const location = useLocation()
  const cached = (location.state as { result?: BacktestResponse } | null)?.result
  const [result, setResult] = useState<BacktestResponse | null>(
    cached && cached.id === runId ? cached : null,
  )
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(!cached || cached.id !== runId)

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
  const equityData = result.equity_curve.map((p) => ({
    date: p.date,
    equity: Math.round(p.equity * 100) / 100,
    drawdown: Math.round(p.drawdown_pct * 10000) / 100,
  }))

  const filledTrades = result.trades.filter((t) => t.qty > 0)
  const riskEvents = result.trades.filter((t) => t.qty === 0)

  return (
    <section className="panel results">
      <header className="panel-head results-head">
        <div>
          <h1>Results</h1>
          <p>
            Buy &amp; hold · {result.request.symbols.join(', ')} ·{' '}
            {formatDate(result.request.start_date)} → {formatDate(result.request.end_date)}
          </p>
        </div>
        <Link className="btn-ghost" to="/">
          New test
        </Link>
      </header>

      {result.dd_halted && (
        <div className="warn-banner">
          Portfolio drawdown limit was hit
          {result.dd_halt_date ? ` on ${formatDate(result.dd_halt_date)}` : ''}. New buys were
          blocked after that; open positions were not sold automatically.
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

      <section className="results-section chart-block" aria-labelledby="equity-heading">
        <HeadingWithHelp
          as="h2"
          text="Portfolio value over time"
          definition={DEFINITIONS.equity_curve}
          className="section-title"
        />
        <p className="chart-caption" id="equity-heading">
          Dollar value of the portfolio each day. A flat line usually means the test is holding cash
          after exits.
        </p>
        <div className="chart-frame chart-frame-primary">
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={equityData} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
              <defs>
                <linearGradient id="eqFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0f6e56" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#0f6e56" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(20,30,28,0.08)" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: '#5a6b63' }}
                minTickGap={48}
                tickFormatter={formatDateShort}
              />
              <YAxis
                tick={{ fontSize: 11, fill: '#5a6b63' }}
                tickFormatter={(v) => `$${Math.round(v / 1000)}k`}
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
                formatter={(value) => [usdPrecise(Number(value)), 'Portfolio value']}
                labelFormatter={(l) => formatDate(String(l))}
              />
              <Area
                type="monotone"
                dataKey="equity"
                name="Portfolio value"
                stroke="#0f6e56"
                fill="url(#eqFill)"
                strokeWidth={2}
                dot={false}
              />
            </AreaChart>
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
            <AreaChart data={equityData} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
              <defs>
                <linearGradient id="ddFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#b42318" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#b42318" stopOpacity={0} />
                </linearGradient>
              </defs>
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
                label={{
                  value: 'Below peak',
                  angle: -90,
                  position: 'insideLeft',
                  offset: 8,
                  style: { fontSize: 11, fill: '#5a6b63' },
                }}
              />
              <Tooltip
                formatter={(value) => [`${Number(value).toFixed(2)}%`, 'Below peak']}
                labelFormatter={(l) => formatDate(String(l))}
              />
              <Area
                type="monotone"
                dataKey="drawdown"
                name="Below peak"
                stroke="#b42318"
                fill="url(#ddFill)"
                strokeWidth={2}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

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
