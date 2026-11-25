import { useState } from 'react'
import {
  downloadBacktestCsv,
  downloadBacktestPdf,
  downloadCompareCsv,
  downloadComparePdf,
} from '../api'
import { HelpTip } from './HelpTip'
import { DEFINITIONS } from '../copy'
import type { BacktestResponse } from '../types'

type ResultsProps = {
  mode: 'results'
  runId: string
  mcId?: string | null
}

type CompareProps = {
  mode: 'compare'
  runs: BacktestResponse[]
}

type Props = ResultsProps | CompareProps

export function ExportButtons(props: Props) {
  const [busy, setBusy] = useState<'csv' | 'pdf' | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function onCsv() {
    setError(null)
    setBusy('csv')
    try {
      if (props.mode === 'results') {
        await downloadBacktestCsv(props.runId, props.mcId)
      } else {
        await downloadCompareCsv(props.runs)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  async function onPdf() {
    setError(null)
    setBusy('pdf')
    try {
      if (props.mode === 'results') {
        await downloadBacktestPdf(props.runId, props.mcId)
      } else {
        await downloadComparePdf(props.runs)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="export-bar">
      <div className="export-bar-head">
        <span className="label-row inline">
          <strong>Download risk report</strong>
          <HelpTip definition={DEFINITIONS.export_report} />
        </span>
        <p className="export-bar-lead">
          CSV = spreadsheet tables (metrics, equity, trades
          {props.mode === 'results' ? ', Monte Carlo if you ran it' : ''}). PDF = one-page summary.
        </p>
      </div>
      <div className="export-actions">
        <button
          type="button"
          className="btn-ghost"
          onClick={() => void onCsv()}
          disabled={busy !== null}
        >
          {busy === 'csv' ? 'Preparing CSV…' : 'Download CSV'}
          <HelpTip definition={DEFINITIONS.export_csv} />
        </button>
        <button
          type="button"
          className="btn-ghost"
          onClick={() => void onPdf()}
          disabled={busy !== null}
        >
          {busy === 'pdf' ? 'Preparing PDF…' : 'Download PDF'}
          <HelpTip definition={DEFINITIONS.export_pdf} />
        </button>
      </div>
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
    </div>
  )
}
