import type {
  BacktestRequest,
  BacktestResponse,
  CompareRequest,
  CompareResponse,
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
