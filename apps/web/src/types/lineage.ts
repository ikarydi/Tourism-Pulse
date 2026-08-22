export type LineageSourceObservation = {
  id: number
  dataset: string
  retrieved_at: string
  source_url: string | null
  checksum: string
  schema_version: string | null
}

export type LineageSource = {
  id: number
  name: string
  category: string
  reliability: string
}

export type LineageQualityResult = {
  check_name: string
  passed: boolean
  severity: string
  detail: string | null
  checked_at: string
}

export type SignalLineage = {
  signal_id: number
  place_id: number
  signal_type: string
  value: string
  unit: string | null
  source: string
  observed_at: string
  source_observation: LineageSourceObservation | null
  source_detail: LineageSource | null
  quality_results: LineageQualityResult[]
}

export type EventLineage = {
  event_id: number
  place_id: number
  name: string
  event_type: string
  source: string | null
  start_at: string
  source_observation: LineageSourceObservation | null
  source_detail: LineageSource | null
  quality_results: LineageQualityResult[]
}
