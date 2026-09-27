// Keep in sync with schemas/pulse.py's DIMENSION_WEIGHTS-derived shape.
export type DimensionKey = 'demand' | 'capacity' | 'events' | 'environment' | 'risk' | 'economic'

export type PulseDimensions = Record<DimensionKey, number>

export type EvidenceSignal = {
  id: number
  signal_type: string
  source: string
  value: number
  unit: string | null
  observed_at: string
}

export type EvidenceArticle = {
  title: string
  url: string
  source: string
  published_at: string | null
}

export type EvidenceVideo = {
  title: string
  video_id: string
  channel: string | null
  published_at: string | null
}

export type EvidenceEvent = {
  id: number
  name: string
  event_type: string
  start_at: string
}

export type DimensionEvidence = {
  dimension: string
  value: number
  contributing_signals: EvidenceSignal[]
  related_articles: EvidenceArticle[]
  related_videos: EvidenceVideo[]
  related_events: EvidenceEvent[]
}

export type Pulse = {
  place_id: number
  pulse: number
  dimensions: PulseDimensions
  confidence: { score: number; coverage: number }
  // Tourism-pressure index, 0-100 (higher = more strain on residents).
  // Reported beside the Pulse, never part of it; null without pressure data.
  pressure: number | null
  trend: { change: number; direction: string }
  interpretation: {
    headline: string
    strengths: string[]
    weaknesses: string[]
    data_quality: string
  }
  // Both only present on a persist=true (real, non-bulk) calculation -
  // see routers/pulse.py.
  evidence: Partial<Record<DimensionKey, DimensionEvidence>> | null
  narrative: string | null
}

export type PulseSnapshot = {
  id: number
  place_id: number
  calculated_at: string
  pulse: number
  demand: number
  capacity: number
  events: number
  environment: number
  risk: number
  economic: number
  pressure: number | null
  confidence_score: number
  confidence_coverage: number
  narrative: string | null
}

export type PulseTrend = {
  place_id: number
  current_pulse: number
  change_24h: number | null
  change_7d: number | null
  direction: string
  momentum: string
  drivers: { positive: string[]; negative: string[] }
}

export type PulseAnomaly = {
  place_id: number
  detected: boolean
  severity: string
  change: number | null
  message: string
  drivers: string[]
}
