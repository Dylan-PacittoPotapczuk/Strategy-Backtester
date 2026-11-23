export function pct(value: number, digits = 2): string {
  return `${(value * 100).toFixed(digits)}%`
}

export function usd(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}

export function usdPrecise(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(value)
}

export function num(value: number, digits = 2): string {
  return value.toFixed(digits)
}

/** Format ISO date (YYYY-MM-DD) for display, e.g. Jan 3, 2020. */
export function formatDate(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T12:00:00Z`)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

/** Shorter axis tick: Jan ’20 */
export function formatDateShort(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T12:00:00Z`)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-US', {
    month: 'short',
    year: '2-digit',
    timeZone: 'UTC',
  })
}
