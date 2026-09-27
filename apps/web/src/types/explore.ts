// Mirrors schemas/explore.py.
export type ChartType = 'line' | 'bar' | 'scatter' | 'heatmap' | 'map' | 'table'
export type Collapse = 'latest' | 'avg' | 'sum' | 'max' | 'min'
export type Grain = 'day' | 'month' | 'year'

export type Metric = {
  id: string
  label: string
  group: string
  unit: string
  grain: 'day' | 'month' | 'year' | 'static'
  aggregation: string
  description: string
  source: string
}

export type PlaceRef = {
  id: number
  name: string
  place_type: string
  country_code: string | null
  latitude: number | null
  longitude: number | null
}

export type Catalog = { metrics: Metric[]; places: PlaceRef[] }

export type QuerySpec = {
  metrics: string[]
  places: number[] | null
  place_type: 'destination' | 'country' | null
  grain: Grain
  start: string | null
  end: string | null
}

export type ChartSpec = {
  type: ChartType
  x: 'time' | 'place'
  collapse: Collapse
  color: 'place' | 'metric' | null
}

export type ViewSpec = { query: QuerySpec; chart: ChartSpec }

export type QueryRow = { metric: string; place_id: number; period: string | null; value: number }

export type QueryResult = {
  metrics: Metric[]
  places: PlaceRef[]
  rows: QueryRow[]
  truncated: boolean
  data_through: string | null
  notes: string[]
}

export type SavedView = {
  id: number
  title: string
  description: string | null
  spec: ViewSpec
  pinned: boolean
  position: number
  created_at: string
  updated_at: string
}

export type AskAnswer = { title: string; spec: ViewSpec; explanation: string }
