/** Shared formatting for forecasts and attention figures. */

export function periodDate(period: string): Date {
  // Mid-month, so a month's point sits in the middle of its band.
  return new Date(`${period}-15T00:00:00Z`)
}

export function periodLabel(period: string, month: 'short' | 'long' = 'short'): string {
  return periodDate(period).toLocaleDateString('en', { month, year: 'numeric', timeZone: 'UTC' })
}

export function signedPercent(value: number | null | undefined, digits = 0): string {
  if (value == null || Number.isNaN(value)) return '—'
  const percent = value * 100
  const sign = percent > 0.05 ? '+' : percent < -0.05 ? '−' : ''
  return `${sign}${Math.abs(percent).toFixed(digits)}%`
}

export function plainPercent(value: number | null | undefined, digits = 0): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export function compactNights(value: number): string {
  return new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(value)
}

/** CSS class for a change: up, down or flat, for colour. */
export function changeTone(value: number | null | undefined, flat = 0.01): string {
  if (value == null) return 'flat'
  return value > flat ? 'up' : value < -flat ? 'down' : 'flat'
}
