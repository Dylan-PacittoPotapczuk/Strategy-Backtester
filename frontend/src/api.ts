import type {
  BacktestRequest,
  BacktestResponse,
  CompareRequest,
  CompareResponse,
  ConfigPreset,
  MonteCarloRequest,
  MonteCarloResponse,
  RunSummary,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

async function readError(res: Response): Promise<string> {
  let detail = res.statusText
  try {
    const err = await res.json()
    detail = err.detail ?? JSON.stringify(err)
  } catch {
    /* ignore */
  }
  return typeof detail === 'string' ? detail : JSON.stringify(detail)
}

export async function runBacktest(body: BacktestRequest): Promise<BacktestResponse> {
  const res = await fetch(`${API_BASE}/api/backtests`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    throw new Error(await readError(res))
  }
  return res.json()
}

export async function runCompare(body: CompareRequest): Promise<CompareResponse> {
  const res = await fetch(`${API_BASE}/api/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    throw new Error(await readError(res))
  }
  return res.json()
}

export async function getBacktest(id: string): Promise<BacktestResponse> {
  const res = await fetch(`${API_BASE}/api/backtests/${id}`)
  if (!res.ok) {
    throw new Error(`Failed to load backtest ${id}`)
  }
  return res.json()
}

export async function listRunSummaries(limit = 30): Promise<RunSummary[]> {
  const res = await fetch(`${API_BASE}/api/runs?limit=${limit}`)
  if (!res.ok) {
    throw new Error(await readError(res))
  }
  return res.json()
}

export async function renameBacktest(id: string, name: string): Promise<BacktestResponse> {
  const res = await fetch(`${API_BASE}/api/backtests/${id}/name`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  if (!res.ok) {
    throw new Error(await readError(res))
  }
  return res.json()
}

export async function listPresets(): Promise<ConfigPreset[]> {
  const res = await fetch(`${API_BASE}/api/presets`)
  if (!res.ok) {
    throw new Error(await readError(res))
  }
  return res.json()
}

export async function createPreset(
  name: string,
  config: Record<string, unknown>,
): Promise<ConfigPreset> {
  const res = await fetch(`${API_BASE}/api/presets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, config }),
  })
  if (!res.ok) {
    throw new Error(await readError(res))
  }
  return res.json()
}

export async function deletePreset(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/presets/${id}`, { method: 'DELETE' })
  if (!res.ok) {
    throw new Error(await readError(res))
  }
}

export async function runMonteCarlo(
  backtestId: string,
  body: MonteCarloRequest = {},
): Promise<MonteCarloResponse> {
  const res = await fetch(`${API_BASE}/api/backtests/${backtestId}/monte-carlo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    throw new Error(await readError(res))
  }
  return res.json()
}

function withMcQuery(path: string, mcId?: string | null): string {
  if (!mcId) return path
  const q = new URLSearchParams({ mc_id: mcId })
  return `${path}?${q.toString()}`
}

export function exportCsvUrl(runId: string, mcId?: string | null): string {
  return `${API_BASE}${withMcQuery(`/api/backtests/${runId}/export.csv`, mcId)}`
}

export function exportPdfUrl(runId: string, mcId?: string | null): string {
  return `${API_BASE}${withMcQuery(`/api/backtests/${runId}/export.pdf`, mcId)}`
}

async function saveBlobResponse(res: Response, fallbackName: string): Promise<void> {
  if (!res.ok) {
    throw new Error(await readError(res))
  }
  const blob = await res.blob()
  const cd = res.headers.get('Content-Disposition') || ''
  const match = /filename="([^"]+)"/.exec(cd)
  const filename = match?.[1] ?? fallbackName
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export async function downloadBacktestCsv(runId: string, mcId?: string | null): Promise<void> {
  const res = await fetch(exportCsvUrl(runId, mcId))
  await saveBlobResponse(res, `backtest-${runId}-export.zip`)
}

export async function downloadBacktestPdf(runId: string, mcId?: string | null): Promise<void> {
  const res = await fetch(exportPdfUrl(runId, mcId))
  await saveBlobResponse(res, `backtest-${runId}-report.pdf`)
}

export async function downloadCompareCsv(runs: BacktestResponse[]): Promise<void> {
  const res = await fetch(`${API_BASE}/api/compare/export.csv`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ runs }),
  })
  await saveBlobResponse(res, 'compare-export.zip')
}

export async function downloadComparePdf(runs: BacktestResponse[]): Promise<void> {
  const res = await fetch(`${API_BASE}/api/compare/export.pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ runs }),
  })
  await saveBlobResponse(res, 'compare-report.pdf')
}
