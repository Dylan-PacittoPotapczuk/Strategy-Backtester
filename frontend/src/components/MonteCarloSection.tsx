import { useState, type FormEvent } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { runMonteCarlo } from '../api'
import { FieldLabel, HeadingWithHelp, HelpTip } from './HelpTip'
import { DEFINITIONS } from '../copy'
import { num, pct, usd, usdPrecise } from '../format'
import type { MonteCarloResponse } from '../types'

type Props = {
  backtestId: string
  defaultStartEquity: number
  onResult?: (mc: MonteCarloResponse | null) => void
}

const DEFAULTS = {
  n_paths: 500,
  horizon_days: 252,
  seed: 42,
  block_bootstrap: false,
  block_size: 10,
}

export function MonteCarloSection({ backtestId, defaultStartEquity, onResult }: Props) {
  const [nPaths, setNPaths] = useState(DEFAULTS.n_paths)
  const [horizon, setHorizon] = useState(DEFAULTS.horizon_days)
  const [seed, setSeed] = useState(DEFAULTS.seed)
  const [blockBootstrap, setBlockBootstrap] = useState(DEFAULTS.block_bootstrap)
  const [blockSize, setBlockSize] = useState(DEFAULTS.block_size)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mc, setMc] = useState<MonteCarloResponse | null>(null)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result = await runMonteCarlo(backtestId, {
        n_paths: nPaths,
        horizon_days: horizon,
        seed,
        block_bootstrap: blockBootstrap,
        block_size: blockBootstrap ? blockSize : undefined,
      })
      setMc(result)
      onResult?.(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  const bandData =
    mc?.result.percentile_bands.map((b) => ({
      day: b.day,
      p5: Math.round(b.p5 * 100) / 100,
      p25: Math.round(b.p25 * 100) / 100,
      p50: Math.round(b.p50 * 100) / 100,
      p75: Math.round(b.p75 * 100) / 100,
      p95: Math.round(b.p95 * 100) / 100,
      // Recharts stacked areas for bands: outer = p95-p5, inner = p75-p25
      bandOuterBase: Math.round(b.p5 * 100) / 100,
      bandOuterSpan: Math.round((b.p95 - b.p5) * 100) / 100,
      bandInnerBase: Math.round(b.p25 * 100) / 100,
      bandInnerSpan: Math.round((b.p75 - b.p25) * 100) / 100,
    })) ?? []

  const term = mc?.result.terminal_return_dist

  return (
    <section className="results-section mc-block" aria-labelledby="mc-heading">
      <HeadingWithHelp
        as="h2"
        text="Forward projection (Monte Carlo)"
        definition={DEFINITIONS.monte_carlo}
        className="section-title"
      />
      <p className="chart-caption" id="mc-heading">
        Resample this backtest’s daily returns into many possible futures. Starting value defaults
        to the ending portfolio ({usd(defaultStartEquity)}).
      </p>

      <form className="mc-form" onSubmit={onSubmit}>
        <div className="form-grid mc-form-grid">
          <FieldLabel text="Simulated paths" definition={DEFINITIONS.mc_n_paths}>
            <input
              type="number"
              min={10}
              max={2000}
              step={10}
              value={nPaths}
              onChange={(e) => setNPaths(Number(e.target.value))}
            />
          </FieldLabel>
          <FieldLabel text="Horizon (trading days)" definition={DEFINITIONS.mc_horizon}>
            <input
              type="number"
              min={1}
              max={1260}
              step={1}
              value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))}
            />
          </FieldLabel>
          <FieldLabel text="Random seed" definition={DEFINITIONS.mc_seed}>
            <input
              type="number"
              step={1}
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value))}
            />
          </FieldLabel>
          <FieldLabel text="Block size (days)" definition={DEFINITIONS.mc_block_size}>
            <input
              type="number"
              min={1}
              max={63}
              step={1}
              value={blockSize}
              disabled={!blockBootstrap}
              onChange={(e) => setBlockSize(Number(e.target.value))}
            />
          </FieldLabel>
        </div>

        <label className="check-row mc-check">
          <input
            type="checkbox"
            checked={blockBootstrap}
            onChange={(e) => setBlockBootstrap(e.target.checked)}
          />
          <span>
            Use block resampling
            <HelpTip definition={DEFINITIONS.mc_block_bootstrap} />
          </span>
        </label>

        <div className="mc-actions">
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Running projection…' : mc ? 'Re-run projection' : 'Run forward projection'}
          </button>
          <span className="hint">
            Default {DEFAULTS.n_paths} paths (max 2,000) keeps the UI snappy.
          </span>
        </div>
      </form>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      <aside className="mc-assumptions" aria-label="Monte Carlo assumptions">
        <HeadingWithHelp
          as="h3"
          text="Important assumption"
          definition={DEFINITIONS.mc_assumptions}
          className="mc-assumptions-title"
        />
        <p>
          Forward paths reuse this backtest’s daily returns <em>after</em> costs and guardrails.
          Path-dependent risk rules (per-trade stops, portfolio drawdown halts) are{' '}
          <strong>not re-applied</strong> on each synthetic path. Treat the bands as “similar
          risk-constrained behavior continues,” not a full re-simulation of every stop and halt.
        </p>
      </aside>

      {mc && term && (
        <>
          <div className="metrics-secondary mc-terminal-metrics">
            <Metric
              label="Typical ending return"
              value={pct(term.p50)}
              definition={DEFINITIONS.mc_terminal_return}
              tone={term.p50 >= 0 ? 'up' : 'down'}
            />
            <Metric
              label="Low ending return (5%)"
              value={pct(term.p5)}
              definition={DEFINITIONS.mc_terminal_band}
              tone="down"
            />
            <Metric
              label="High ending return (95%)"
              value={pct(term.p95)}
              definition={DEFINITIONS.mc_terminal_band}
              tone="up"
            />
            <Metric
              label="Average ending return"
              value={pct(term.mean)}
              definition={DEFINITIONS.mc_terminal_return}
            />
            <Metric
              label="Spread of endings"
              value={pct(term.std)}
              definition={DEFINITIONS.mc_terminal_band}
            />
            <Metric
              label="Chance of a loss"
              value={pct(term.prob_below_start)}
              definition={DEFINITIONS.mc_prob_below_start}
              tone="down"
            />
          </div>

          <HeadingWithHelp
            as="h3"
            text="Percentile value bands"
            definition={DEFINITIONS.mc_percentile_bands}
            className="section-title mc-subhead"
          />
          <p className="chart-caption">
            Outer shade ≈ middle 90% of paths (5th–95th). Inner shade ≈ middle 50% (25th–75th). Line
            = median path.{' '}
            <HelpTip definition={DEFINITIONS.mc_percentile_path} label="What is a percentile path?" />{' '}
            <HelpTip definition={DEFINITIONS.mc_simulation} label="What is a simulation?" />
          </p>

          <div className="chart-frame chart-frame-primary">
            <ResponsiveContainer width="100%" height={320}>
              <ComposedChart data={bandData} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
                <defs>
                  <linearGradient id="mcOuter" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#1d4f91" stopOpacity={0.22} />
                    <stop offset="100%" stopColor="#1d4f91" stopOpacity={0.08} />
                  </linearGradient>
                  <linearGradient id="mcInner" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#0f6e56" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#0f6e56" stopOpacity={0.12} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(20,30,28,0.08)" vertical={false} />
                <XAxis
                  dataKey="day"
                  tick={{ fontSize: 11, fill: '#5a6b63' }}
                  minTickGap={40}
                  label={{
                    value: 'Forward trading day',
                    position: 'insideBottom',
                    offset: -2,
                    style: { fontSize: 11, fill: '#5a6b63' },
                  }}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: '#5a6b63' }}
                  tickFormatter={(v) => `$${Math.round(Number(v) / 1000)}k`}
                  width={56}
                  domain={['auto', 'auto']}
                  label={{
                    value: 'Portfolio ($)',
                    angle: -90,
                    position: 'insideLeft',
                    offset: 10,
                    style: { fontSize: 11, fill: '#5a6b63' },
                  }}
                />
                <Tooltip content={<McTooltip startEquity={mc.result.start_equity} />} />
                {/* Nested bands via stacked transparent base + span */}
                <Area
                  type="monotone"
                  dataKey="bandOuterBase"
                  stackId="outer"
                  stroke="none"
                  fill="transparent"
                  legendType="none"
                  isAnimationActive={false}
                  tooltipType="none"
                />
                <Area
                  type="monotone"
                  dataKey="bandOuterSpan"
                  name="5–95% of paths"
                  stackId="outer"
                  stroke="none"
                  fill="url(#mcOuter)"
                  isAnimationActive={false}
                />
                <Area
                  type="monotone"
                  dataKey="bandInnerBase"
                  stackId="inner"
                  stroke="none"
                  fill="transparent"
                  legendType="none"
                  isAnimationActive={false}
                  tooltipType="none"
                />
                <Area
                  type="monotone"
                  dataKey="bandInnerSpan"
                  name="25–75% of paths"
                  stackId="inner"
                  stroke="none"
                  fill="url(#mcInner)"
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="p95"
                  name="95th"
                  stroke="#1d4f91"
                  strokeWidth={1}
                  strokeOpacity={0.45}
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="p5"
                  name="5th"
                  stroke="#1d4f91"
                  strokeWidth={1}
                  strokeOpacity={0.45}
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="p50"
                  name="Median (50th)"
                  stroke="#0f6e56"
                  strokeWidth={2.25}
                  dot={false}
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <p className="mc-meta hint">
            {mc.result.n_paths.toLocaleString()} paths · {mc.result.horizon_days} days · seed{' '}
            {mc.result.seed ?? 'none'}
            {mc.result.block_bootstrap
              ? ` · block size ${mc.result.block_size}`
              : ' · day-by-day bootstrap'}{' '}
            · start {usd(mc.result.start_equity)}
          </p>
        </>
      )}
    </section>
  )
}

function Metric({
  label,
  value,
  definition,
  tone,
}: {
  label: string
  value: string
  definition: string
  tone?: 'up' | 'down'
}) {
  return (
    <div className={`metric${tone ? ` metric-${tone}` : ''}`}>
      <span className="metric-label">
        <span>{label}</span>
        <HelpTip definition={definition} />
      </span>
      <span className="metric-value">{value}</span>
    </div>
  )
}

function McTooltip({
  active,
  payload,
  label,
  startEquity,
}: {
  active?: boolean
  payload?: Array<{ payload: Record<string, number> }>
  label?: string | number
  startEquity: number
}) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  return (
    <div className="mc-tooltip">
      <div className="mc-tooltip-day">Day {label}</div>
      <div>95th: {usdPrecise(row.p95)}</div>
      <div>75th: {usdPrecise(row.p75)}</div>
      <div>Median: {usdPrecise(row.p50)}</div>
      <div>25th: {usdPrecise(row.p25)}</div>
      <div>5th: {usdPrecise(row.p5)}</div>
      <div className="mc-tooltip-ret">
        Median vs start: {pct(row.p50 / startEquity - 1)} ({num(row.p50 / startEquity, 3)}×)
      </div>
    </div>
  )
}
