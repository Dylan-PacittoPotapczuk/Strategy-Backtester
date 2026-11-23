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
