import type { FeatureCollection } from 'geojson'
import { request } from '../../api/client'

export type RegionMeasure =
  | 'score'
  | 'tourism_intensity'
  | 'tourism_density'
  | 'seasonality_peak_share'
  | 'str_share'

export const REGION_MEASURES: { key: RegionMeasure; label: string }[] = [
  { key: 'score', label: 'Tourism pressure' },
  { key: 'tourism_intensity', label: 'Tourism intensity' },
  { key: 'tourism_density', label: 'Tourism density' },
  { key: 'seasonality_peak_share', label: 'Peak-month concentration' },
  { key: 'str_share', label: 'Short-term rental share' },
]

// Sequential, low -> high percentile; readable under the white markers.
export const REGION_RAMP = ['#1d3b53', '#2d6478', '#4b9384', '#c9b35a', '#e3834f', '#df4f60']

const shapes = new Map<number, Promise<FeatureCollection | null>>()

export function loadShapes(level: 2 | 3): Promise<FeatureCollection | null> {
  if (!shapes.has(level)) {
    shapes.set(
      level,
      request<FeatureCollection>(`/regions/geojson?level=${level}`).catch(() => null),
    )
  }
  return shapes.get(level) as Promise<FeatureCollection | null>
}
