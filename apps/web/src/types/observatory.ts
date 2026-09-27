// Mirrors schemas/observatory.py.
export type IndicatorReading = {
  indicator: 'tourism_intensity' | 'tourism_density' | 'seasonality_peak_share' | string
  label: string
  definition: string
  value: number
  unit: string
  year: number
  percentile: number
  rank: number
  peers: number
  source: string
  source_observation_id: number | null
}

export type Observatory = {
  place_id: number
  nuts_code: string | null
  region_name: string | null
  level_name: string | null
  indicators: IndicatorReading[]
  // Mean European percentile of the indicators, 0-100 (higher = more strain).
  score: number | null
  level: 'low' | 'moderate' | 'high' | null
  method: string | null
}
