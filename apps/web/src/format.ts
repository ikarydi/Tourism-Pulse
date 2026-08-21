export const dimensions = [
  { key: 'demand', label: 'Demand', tone: 'coral' },
  { key: 'capacity', label: 'Capacity', tone: 'cyan' },
  { key: 'events', label: 'Events', tone: 'amber' },
  { key: 'environment', label: 'Environment', tone: 'green' },
] as const

export function scoreStatus(score: number) {
  if (score < 40) return 'Weak'
  if (score < 70) return 'Moderate'
  return 'Strong'
}

export function formatDateTime(value: string) {
  return new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(new Date(value))
}

export function formatObservationDate(value: string) {
  return new Intl.DateTimeFormat('en', { month: 'short', year: 'numeric' }).format(new Date(value))
}

export function formatChange(change: number) {
  if (change === 0) return '0.0'
  return `${change > 0 ? '+' : ''}${change.toFixed(1)}`
}
