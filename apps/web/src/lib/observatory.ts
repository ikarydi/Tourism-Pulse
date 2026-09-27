import type { IndicatorReading } from '../types/observatory'

// Same bands as the backend's pressure level (observatory/pressure.py).
export function pressureBand(percentile: number): 'low' | 'moderate' | 'high' {
  if (percentile >= 70) return 'high'
  if (percentile >= 40) return 'moderate'
  return 'low'
}

const numberFormatter = new Intl.NumberFormat('en', { maximumFractionDigits: 0 })

export function formatIndicatorValue(reading: IndicatorReading, style: 'long' | 'short' = 'long'): string {
  const long = style === 'long'
  switch (reading.indicator) {
    case 'seasonality_peak_share':
      return `${(reading.value * 100).toFixed(1)}%${long ? " of the year's nights in its busiest month" : ' in peak month'}`
    case 'str_share':
      return `${(reading.value * 100).toFixed(1)}%${long ? ' of nights booked via online platforms' : ' via platforms'}`
    case 'tourism_intensity':
      return `${numberFormatter.format(reading.value)} nights${long ? ' per 1,000 residents' : ' / 1k residents'}`
    case 'tourism_density':
      return `${numberFormatter.format(reading.value)} nights${long ? ' per km²' : ' / km²'}`
    default:
      return `${numberFormatter.format(reading.value)} ${reading.unit}`
  }
}

export function ordinal(n: number): string {
  const rounded = Math.round(n)
  const lastTwo = rounded % 100
  const suffix =
    lastTwo >= 11 && lastTwo <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' }[rounded % 10] ?? 'th')
  return `${rounded}${suffix}`
}

export const OBSERVATORY_INDICATORS = [
  { key: 'tourism_intensity', short: 'Intensity' },
  { key: 'tourism_density', short: 'Density' },
  { key: 'seasonality_peak_share', short: 'Peak month' },
  { key: 'str_share', short: 'Rental share' },
] as const
