import type { BacktestRequest, BacktestResponse } from './types'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export async function runBacktest(body: BacktestRequest): Promise<BacktestResponse> {
  const res = await fetch(`${API_BASE}/api/backtests`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const err = await res.json()
      detail = err.detail ?? JSON.stringify(err)
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
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
