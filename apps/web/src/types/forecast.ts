// Mirrors schemas/forecast.py.
export type ForecastPoint = {
  period: string
  horizon: number
  point: number
  low_80: number
  high_80: number
  low_95: number
  high_95: number
  last_year: number | null
}

export type Outlook = {
  months: number
  forecast: number
  last_year: number
  change: number
  low_80: number
  high_80: number
}

export type Accuracy = {
  scored: number
  mape: number | null
  coverage_80: number | null
  by_horizon: { horizon: number; mape: number; scored: number }[]
}

export type Validation = {
  study: string
  mape: number
  seasonal_naive_mape: number
  countries_better_than_last_year: number
  countries_attention_helps: number
  countries: number
  coverage_80: number
}

export type PlaceForecast = {
  place_id: number
  signal_type: string
  unit: string
  model: string
  validated: boolean
  method: string
  validation: Validation | null
  issued_at: string
  origin: string
  history: { period: string; value: number }[]
  points: ForecastPoint[]
  outlook: Outlook[]
  backtest: Accuracy | null
  track_record: Accuracy | null
}

export type ForecastSummary = {
  place_id: number
  name: string
  place_type: string
  country_code: string | null
  origin: string
  model: string
  validated: boolean
  next_3_change: number | null
  next_12_change: number | null
  next_12_nights: number | null
  backtest_mape: number | null
  live_scored: number
  live_mape: number | null
}
