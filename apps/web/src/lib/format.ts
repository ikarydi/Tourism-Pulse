export type ScoreStatus = 'Weak' | 'Moderate' | 'Strong'

export function scoreStatus(score: number): ScoreStatus {
  if (score < 40) return 'Weak'
  if (score < 70) return 'Moderate'
  return 'Strong'
}

export function statusBadgeClass(score: number): string {
  const status = scoreStatus(score)
  if (status === 'Strong') return 'badge-good'
  if (status === 'Moderate') return 'badge-warn'
  return 'badge-bad'
}

const dateTimeFormatter = new Intl.DateTimeFormat('en', {
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})

const dateFormatter = new Intl.DateTimeFormat('en', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
})

const monthYearFormatter = new Intl.DateTimeFormat('en', {
  month: 'short',
  year: 'numeric',
})

export function formatDateTime(value: string): string {
  return dateTimeFormatter.format(new Date(value))
}

export function formatDate(value: string): string {
  return dateFormatter.format(new Date(value))
}

export function formatMonthYear(value: string): string {
  return monthYearFormatter.format(new Date(value))
}

export function formatChange(change: number): string {
  if (change === 0) return '0.0'
  const sign = change > 0 ? '+' : ''
  return `${sign}${change.toFixed(1)}`
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat('en').format(Math.round(value))
}

export function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat('en', { notation: 'compact' }).format(value)
}
