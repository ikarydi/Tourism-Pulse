import type { DimensionKey } from '../types/pulse'

export type DimensionMeta = {
  key: DimensionKey
  label: string
  short: string
  color: string
  description: string
}

// Order matters: this is display order everywhere (dimension grid,
// radar chart axes, legends) - roughly "what a destination has" (demand,
// capacity, events) before "what surrounds it" (environment, risk,
// economic).
export const DIMENSIONS: DimensionMeta[] = [
  {
    key: 'demand',
    label: 'Demand',
    short: 'DMD',
    color: 'var(--dim-demand)',
    description: 'Visitor volume - nights, arrivals, search & media attention.',
  },
  {
    key: 'capacity',
    label: 'Capacity',
    short: 'CAP',
    color: 'var(--dim-capacity)',
    description: 'Accommodation supply and visitor pressure relative to residents.',
  },
  {
    key: 'events',
    label: 'Events',
    short: 'EVT',
    color: 'var(--dim-events)',
    description: 'Upcoming events and event-related coverage.',
  },
  {
    key: 'environment',
    label: 'Environment',
    short: 'ENV',
    color: 'var(--dim-environment)',
    description: 'Weather comfort and air quality.',
  },
  {
    key: 'risk',
    label: 'Risk',
    short: 'RSK',
    color: 'var(--dim-risk)',
    description: 'Active disaster alerts and hazard-related coverage.',
  },
  {
    key: 'economic',
    label: 'Economic',
    short: 'ECO',
    color: 'var(--dim-economic)',
    description: 'Tourism-sector turnover growth and economic coverage.',
  },
]

export const DIMENSION_BY_KEY: Record<DimensionKey, DimensionMeta> = Object.fromEntries(
  DIMENSIONS.map((dimension) => [dimension.key, dimension]),
) as Record<DimensionKey, DimensionMeta>
