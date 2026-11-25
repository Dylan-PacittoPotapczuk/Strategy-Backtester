import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listRunSummaries, renameBacktest } from '../api'
import { HelpTip } from '../components/HelpTip'
import { DEFINITIONS } from '../copy'
import { formatDate, pct } from '../format'
import { strategyLabel } from '../strategyMeta'
import type { RunSummary, StrategyType } from '../types'

export function SavedRunsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [nameDraft, setNameDraft] = useState('')

  function refresh() {
    setLoading(true)
    listRunSummaries(40)
      .then(setRuns)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    refresh()
  }, [])

  async function saveName(id: string) {
    const cleaned = nameDraft.trim()
    if (!cleaned) return
    try {
      await renameBacktest(id, cleaned)
      setRenamingId(null)
      refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <section className="panel">
      <header className="panel-head">
        <div>
          <h1 className="heading-with-help">
            <span>Saved runs</span>
            <HelpTip definition={DEFINITIONS.saved_runs} />
          </h1>
          <p>Reopen recent backtests stored locally. No account required.</p>
        </div>
        <Link className="btn-ghost" to="/">
          New test
        </Link>
      </header>

      {loading && (
        <div className="info-banner" role="status">
          Loading recent runs…
        </div>
      )}
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {!loading && runs.length === 0 && (
        <div className="empty-banner">
          No saved runs yet. Run a backtest from Configure — it will appear here.
        </div>
      )}

      {runs.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>When</th>
                <th>Strategy</th>
                <th>Universe</th>
                <th>Period</th>
                <th>Return</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td>
                    {renamingId === r.id ? (
                      <span className="inline-rename">
                        <input
                          value={nameDraft}
                          onChange={(e) => setNameDraft(e.target.value)}
                          aria-label="Run name"
                        />
                        <button type="button" className="btn-primary btn-small" onClick={() => saveName(r.id)}>
                          Save
                        </button>
                        <button
                          type="button"
                          className="btn-ghost btn-small"
                          onClick={() => setRenamingId(null)}
                        >
                          Cancel
                        </button>
                      </span>
                    ) : (
                      <span className="run-name-cell">
                        <span>{r.name || 'Untitled run'}</span>
                        <button
                          type="button"
                          className="linkish"
                          onClick={() => {
                            setRenamingId(r.id)
                            setNameDraft(r.name || '')
                          }}
                        >
                          Rename
                        </button>
                      </span>
                    )}
                  </td>
                  <td>{formatDate(r.created_at.slice(0, 10))}</td>
                  <td>{strategyLabel(r.strategy_type as StrategyType)}</td>
                  <td>{r.symbols.join(', ')}</td>
                  <td>
                    {formatDate(r.start_date)} → {formatDate(r.end_date)}
                    {r.walk_forward_enabled ? ' · OOS' : ''}
                    {r.benchmark_symbol ? ` · vs ${r.benchmark_symbol}` : ''}
                  </td>
                  <td>
                    {r.total_return != null ? (
                      <span className={r.total_return >= 0 ? 'buy' : 'sell'}>
                        {pct(r.total_return)}
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td>
                    <Link to={`/results/${r.id}`}>Open</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
