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
import { num, pct, usd, usdPrecise } from '../format'
import type { BacktestResponse } from '../types'

export function ResultsPage() {
  const { runId } = useParams<{ runId: string }>()
  const location = useLocation()
  const cached = (location.state as { result?: BacktestResponse } | null)?.result
  const [result, setResult] = useState<BacktestResponse | null>(
    cached && cached.id === runId ? cached : null,
  )
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!runId || (result && result.id === runId)) return
    let cancelled = false
    getBacktest(runId)
      .then((r) => {
        if (!cancelled) setResult(r)
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      })
    return () => {
      cancelled = true
    }
  }, [runId, result])

  if (error) {
    return (
      <section className="panel">
        <div className="error-banner">{error}</div>
        <Link to="/">← Configure another run</Link>
      </section>
    )
  }

  if (!result || !result.metrics) {
    return (
      <section className="panel">
        <p className="hint">Loading results…</p>
      </section>
    )
  }

  const m = result.metrics
  const equityData = result.equity_curve.map((p) => ({
    date: p.date,
    equity: Math.round(p.equity * 100) / 100,
    drawdown: Math.round(p.drawdown_pct * 10000) / 100,
  }))

  return (
    <section className="panel results">
      <header className="panel-head results-head">
        <div>
          <h1>Results</h1>
          <p>
            {result.request.strategy.type.replaceAll('_', ' ')} ·{' '}
            {result.request.symbols.join(', ')} · {result.request.start_date} →{' '}
            {result.request.end_date}
          </p>
        </div>
        <Link className="btn-ghost" to="/">
          New run
        </Link>
      </header>

      {result.dd_halted && (
        <div className="warn-banner">
          Drawdown halt active
          {result.dd_halt_date ? ` from ${result.dd_halt_date}` : ''}: new risk rejected; positions
          not auto-flattened.
        </div>
      )}

      <div className="metrics-strip">
        <Metric label="Total return" value={pct(m.total_return)} />
        <Metric label="CAGR" value={pct(m.cagr)} />
        <Metric label="Sharpe" value={num(m.sharpe)} />
        <Metric label="Max DD" value={pct(m.max_drawdown)} />
        <Metric label="Volatility" value={pct(m.volatility)} />
        <Metric label="Final equity" value={usd(m.final_equity)} />
        <Metric label="Trades" value={String(m.num_trades)} />
        <Metric label="Stops" value={String(m.num_stop_losses)} />
        <Metric label="DD events" value={String(m.num_dd_halts)} />
      </div>

      <div className="chart-block">
        <h2>Equity curve</h2>
        <div className="chart-frame">
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={equityData}>
              <defs>
                <linearGradient id="eqFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0f6e56" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#0f6e56" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(20,30,28,0.08)" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={40} />
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => `$${Math.round(v / 1000)}k`}
                width={56}
              />
              <Tooltip
                formatter={(value) => usdPrecise(Number(value))}
                labelFormatter={(l) => String(l)}
              />
              <Area
                type="monotone"
                dataKey="equity"
                stroke="#0f6e56"
                fill="url(#eqFill)"
                strokeWidth={2}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="chart-block">
        <h2>Drawdown</h2>
        <div className="chart-frame">
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={equityData}>
              <defs>
                <linearGradient id="ddFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#b42318" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#b42318" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(20,30,28,0.08)" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={40} />
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => `${v}%`}
                width={48}
                reversed
              />
              <Tooltip formatter={(value) => `${Number(value).toFixed(2)}%`} />
              <Area
                type="monotone"
                dataKey="drawdown"
                stroke="#b42318"
                fill="url(#ddFill)"
                strokeWidth={2}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="trades-block">
        <h2>Trades</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Price</th>
                <th>Reason</th>
                <th>PnL</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {result.trades.map((t) => (
                <tr key={t.id}>
                  <td>{t.ts}</td>
                  <td>{t.symbol}</td>
                  <td className={t.side}>{t.side}</td>
                  <td>{t.qty ? num(t.qty, 4) : '—'}</td>
                  <td>{t.price ? usdPrecise(t.price) : '—'}</td>
                  <td>
                    <span className={`reason reason-${t.reason}`}>{t.reason}</span>
                  </td>
                  <td>
                    {t.pnl != null
                      ? `${usdPrecise(t.pnl)}${t.pnl_pct != null ? ` (${pct(t.pnl_pct)})` : ''}`
                      : '—'}
                  </td>
                  <td className="note">{t.note ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span className="metric-label">{label}</span>
      <span className="metric-value">{value}</span>
    </div>
  )
}
