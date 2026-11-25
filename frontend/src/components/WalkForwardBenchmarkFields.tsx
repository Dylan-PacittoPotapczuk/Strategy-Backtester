import { FieldLabel, HelpTip } from './HelpTip'
import { DEFINITIONS } from '../copy'

export type WalkForwardForm = {
  enabled: boolean
  mode: 'percent' | 'date'
  train_pct: number
  split_date: string
}

export type BenchmarkForm = {
  enabled: boolean
  symbol: string
}

export const DEFAULT_WALK_FORWARD: WalkForwardForm = {
  enabled: false,
  mode: 'percent',
  train_pct: 70,
  split_date: '2022-01-01',
}

export const DEFAULT_BENCHMARK: BenchmarkForm = {
  enabled: true,
  symbol: 'SPY',
}

export function WalkForwardBenchmarkFields({
  walkForward,
  setWalkForward,
  benchmark,
  setBenchmark,
}: {
  walkForward: WalkForwardForm
  setWalkForward: (updater: (w: WalkForwardForm) => WalkForwardForm) => void
  benchmark: BenchmarkForm
  setBenchmark: (updater: (b: BenchmarkForm) => BenchmarkForm) => void
}) {
  return (
    <>
      <fieldset className="config-section">
        <legend>Walk-forward / out-of-sample</legend>
        <p className="section-lead">
          <span className="label-row inline">
            <span>Optional holdout so you can check results after the early window</span>
            <HelpTip definition={DEFINITIONS.walk_forward} />
          </span>
        </p>
        <label className="check-row">
          <input
            type="checkbox"
            checked={walkForward.enabled}
            onChange={(e) =>
              setWalkForward((w) => ({ ...w, enabled: e.target.checked }))
            }
          />
          <span className="label-row inline">
            <span>Split into in-sample and out-of-sample</span>
            <HelpTip definition={DEFINITIONS.walk_forward_enabled} />
          </span>
        </label>
        {walkForward.enabled && (
          <div className="row">
            <FieldLabel text="Split mode" definition={DEFINITIONS.walk_forward_mode}>
              <select
                value={walkForward.mode}
                onChange={(e) =>
                  setWalkForward((w) => ({
                    ...w,
                    mode: e.target.value as 'percent' | 'date',
                  }))
                }
              >
                <option value="percent">By percent of days</option>
                <option value="date">By calendar date</option>
              </select>
            </FieldLabel>
            {walkForward.mode === 'percent' ? (
              <FieldLabel text="In-sample share (%)" definition={DEFINITIONS.train_pct}>
                <input
                  type="number"
                  min={10}
                  max={90}
                  step={5}
                  value={walkForward.train_pct}
                  onChange={(e) =>
                    setWalkForward((w) => ({
                      ...w,
                      train_pct: Number(e.target.value),
                    }))
                  }
                />
              </FieldLabel>
            ) : (
              <FieldLabel text="Out-of-sample start date" definition={DEFINITIONS.split_date}>
                <input
                  type="date"
                  value={walkForward.split_date}
                  onChange={(e) =>
                    setWalkForward((w) => ({ ...w, split_date: e.target.value }))
                  }
                />
              </FieldLabel>
            )}
          </div>
        )}
        {!walkForward.enabled && (
          <p className="hint warn-hint">
            Tuning parameters on the full history without a holdout can overfit. Enable a
            walk-forward split when you are comparing settings.
          </p>
        )}
      </fieldset>

      <fieldset className="config-section">
        <legend>Benchmark</legend>
        <p className="section-lead">
          <span className="label-row inline">
            <span>Buy-and-hold reference line vs your strategy</span>
            <HelpTip definition={DEFINITIONS.benchmark} />
          </span>
        </p>
        <label className="check-row">
          <input
            type="checkbox"
            checked={benchmark.enabled}
            onChange={(e) =>
              setBenchmark((b) => ({ ...b, enabled: e.target.checked }))
            }
          />
          <span className="label-row inline">
            <span>Plot benchmark buy-and-hold</span>
            <HelpTip definition={DEFINITIONS.benchmark_enabled} />
          </span>
        </label>
        {benchmark.enabled && (
          <FieldLabel text="Benchmark symbol" definition={DEFINITIONS.benchmark_symbol}>
            <input
              value={benchmark.symbol}
              onChange={(e) =>
                setBenchmark((b) => ({ ...b, symbol: e.target.value.toUpperCase() }))
              }
              placeholder="SPY"
              autoComplete="off"
            />
          </FieldLabel>
        )}
      </fieldset>
    </>
  )
}

export function toWalkForwardPayload(w: WalkForwardForm) {
  return {
    enabled: w.enabled,
    mode: w.mode,
    train_pct: Number(w.train_pct) / 100,
    split_date: w.mode === 'date' ? w.split_date : null,
  }
}

export function toBenchmarkPayload(b: BenchmarkForm) {
  return {
    enabled: b.enabled,
    symbol: (b.symbol || 'SPY').trim().toUpperCase(),
  }
}
