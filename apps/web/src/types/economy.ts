// Mirrors schemas/economy.py. Growth, price and turnover figures are
// percents (4.5 = +4.5%), not fractions; survey figures are balances.
export type FlightPoint = { period: string; arrivals: number | null; growth: number | null }

export type Flights = {
  latest_period: string
  arrivals: number
  growth: number | null
  growth_3m: number | null
  airports: { icao: string; arrivals: number }[]
  series: FlightPoint[]
}

export type Survey = {
  latest_period: string
  confidence: number | null
  demand_past: number | null
  demand_expected: number | null
  demand_expected_year_ago: number | null
  employment_expected: number | null
  prices_expected: number | null
  travel_trade_demand_expected: number | null
  series: { period: string; demand_expected: number | null; demand_past: number | null }[]
  stale: boolean
}

export type Prices = {
  latest_period: string
  accommodation: number | null
  restaurants: number | null
  air_fares: number | null
  all_items: number | null
  series: { period: string; accommodation: number | null; all_items: number | null }[]
}

export type Turnover = { latest_period: string; accommodation: number | null; food_service: number | null }

export type OriginShare = { key: string; name: string; nights: number; share: number; previous_share: number | null }

export type Origins = {
  year: number
  total_nights: number
  domestic_share: number | null
  foreign_nights: number
  top: OriginShare[]
}

export type Economy = {
  place_id: number
  place_name: string
  national_place_id: number | null
  national_place_name: string | null
  flights: Flights | null
  survey: Survey | null
  prices: Prices | null
  turnover: Turnover | null
  origins: Origins | null
  highlights: string[]
}
