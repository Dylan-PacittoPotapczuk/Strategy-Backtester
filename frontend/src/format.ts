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
