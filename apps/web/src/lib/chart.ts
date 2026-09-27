import type { ChartSpec, ChartType, Collapse, Metric, PlaceRef, QueryResult, QueryRow, QuerySpec } from '../types/explore'

// Categorical palette from the design tokens, extended for many series.
export const SERIES_COLORS = [
  '#5fd3e8', '#f38a67', '#7bcf9e', '#e8c26a', '#a794f2', '#f0637f',
  '#8be7f5', '#c9a0dc', '#9ad0a8', '#f5b58f', '#6fa8dc', '#d6d68a',
]

export const CHART_TYPES: { type: ChartType; label: string; hint: string }[] = [
  { type: 'line', label: 'Line', hint: 'Trends over time' },
  { type: 'bar', label: 'Bar', hint: 'Compare places' },
  { type: 'scatter', label: 'Scatter', hint: 'Relationship between two metrics' },
  { type: 'heatmap', label: 'Heatmap', hint: 'Many places over time' },
  { type: 'map', label: 'Map', hint: 'Where values are high or low' },
  { type: 'table', label: 'Table', hint: 'Exact numbers' },
]

export const DEFAULT_QUERY: QuerySpec = {
  metrics: [],
  places: null,
  place_type: 'destination',
  grain: 'month',
  start: null,
  end: null,
}

export const DEFAULT_CHART: ChartSpec = { type: 'line', x: 'time', collapse: 'latest', color: null }

/** Chart types that make sense for the current metrics ("Show me"). */
export function availableTypes(metrics: Metric[]): ChartType[] {
  if (!metrics.length) return []
  const allStatic = metrics.every((metric) => metric.grain === 'static')
  const types: ChartType[] = []
  if (!allStatic) types.push('line', 'heatmap')
  types.push('bar')
  if (metrics.length >= 2) types.push('scatter')
  types.push('map', 'table')
  return CHART_TYPES.map((item) => item.type).filter((type) => types.includes(type))
}

/** Per-place value: counts (articles, events, videos) add up over the
 * period; everything else is read at its latest value. */
export function defaultCollapse(metrics: Metric[]): Collapse {
  return metrics.some((metric) => metric.id.startsWith('count.')) ? 'sum' : 'latest'
}

/** The chart we'd draw for these metrics and places if the user hasn't chosen. */
export function recommendChart(metrics: Metric[], placeCount: number): ChartSpec {
  const allStatic = metrics.every((metric) => metric.grain === 'static')
  const annualOnly = metrics.every((metric) => metric.grain === 'year' || metric.grain === 'static')
  const collapse = defaultCollapse(metrics)
  if (!metrics.length) return DEFAULT_CHART
  if (metrics.length >= 2 && (placeCount > 8 || allStatic)) {
    return { type: 'scatter', x: 'place', collapse, color: null }
  }
  if (allStatic || (annualOnly && placeCount > 8)) {
    return { type: 'bar', x: 'place', collapse, color: null }
  }
  if (placeCount > 8) return { type: 'heatmap', x: 'time', collapse, color: null }
  return { type: 'line', x: 'time', collapse, color: metrics.length > 1 ? 'metric' : 'place' }
}

export function xForType(type: ChartType): 'time' | 'place' {
  return type === 'line' || type === 'heatmap' ? 'time' : 'place'
}

/** One value per (metric, place): the time series folded by `collapse`. */
export function collapseRows(rows: QueryRow[], collapse: Collapse): Map<string, Map<number, number>> {
  const series = new Map<string, Map<number, QueryRow[]>>()
  for (const row of rows) {
    const byPlace = series.get(row.metric) ?? new Map<number, QueryRow[]>()
    const list = byPlace.get(row.place_id) ?? []
    list.push(row)
    byPlace.set(row.place_id, list)
    series.set(row.metric, byPlace)
  }
  const out = new Map<string, Map<number, number>>()
  for (const [metric, byPlace] of series) {
    const folded = new Map<number, number>()
    for (const [placeId, list] of byPlace) {
      const values = list.map((row) => row.value)
      let value: number
      if (collapse === 'latest') {
        const sorted = [...list].sort((a, b) => (a.period ?? '').localeCompare(b.period ?? ''))
        value = sorted[sorted.length - 1].value
      } else if (collapse === 'sum') value = values.reduce((a, b) => a + b, 0)
      else if (collapse === 'max') value = Math.max(...values)
      else if (collapse === 'min') value = Math.min(...values)
      else value = values.reduce((a, b) => a + b, 0) / values.length
      folded.set(placeId, value)
    }
    out.set(metric, folded)
  }
  return out
}

export function pearson(xs: number[], ys: number[]): number | null {
  const n = xs.length
  if (n < 3) return null
  const mx = xs.reduce((a, b) => a + b, 0) / n
  const my = ys.reduce((a, b) => a + b, 0) / n
  let sxy = 0
  let sxx = 0
  let syy = 0
  for (let i = 0; i < n; i++) {
    sxy += (xs[i] - mx) * (ys[i] - my)
    sxx += (xs[i] - mx) ** 2
    syy += (ys[i] - my) ** 2
  }
  return sxx && syy ? sxy / Math.sqrt(sxx * syy) : null
}

const compact = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 })
const whole = new Intl.NumberFormat('en', { maximumFractionDigits: 0 })
const plain = new Intl.NumberFormat('en', { maximumFractionDigits: 2 })

export function formatValue(metric: Metric | undefined, value: number): string {
  if (metric?.unit.startsWith('share')) return `${(value * 100).toFixed(1)}%`
  const magnitude = Math.abs(value)
  if (magnitude >= 10_000) return compact.format(value)
  // Decimals on "6,929.36 nights" are false precision.
  if (magnitude >= 100) return whole.format(value)
  return plain.format(value)
}

// Metric groups in reading order: our own scores first, raw feeds last.
export const GROUP_ORDER = [
  'Tourism Pulse',
  'Pressure observatory',
  'Official statistics',
  'Supply',
  'Media & events',
  'Live signals',
]

/** Log scale when positive values span two or more orders of magnitude. */
export function wantsLog(values: number[]): boolean {
  if (values.length < 3 || values.some((value) => value <= 0)) return false
  return Math.max(...values) / Math.min(...values) >= 100
}

export function axisLabel(metric: Metric): string {
  if (metric.unit.startsWith('share')) return `${metric.label} (%)`
  // "score (0-100)" -> "Pulse score (0-100)", not "Pulse score (score (0-100))".
  const unit = metric.unit.replace(/^score\s*/, '').replace(/^\((.*)\)$/, '$1')
  return `${metric.label} (${unit})`
}

export function placeName(places: PlaceRef[], id: number): string {
  return places.find((place) => place.id === id)?.name ?? `Place ${id}`
}

export function metricById(result: QueryResult, id: string): Metric | undefined {
  return result.metrics.find((metric) => metric.id === id)
}

const periodFormat = new Intl.DateTimeFormat('en', { month: 'short', year: 'numeric' })

export function formatPeriod(period: string | null, grain: string): string {
  if (!period) return 'Current'
  const date = new Date(`${period}T00:00:00`)
  if (grain === 'year') return String(date.getFullYear())
  if (grain === 'day') return period
  return periodFormat.format(date)
}
