const API_BASE = '/api'

export type Place = {
  id: number
  name: string
  country_code?: string
  place_type?: string
  destination_id?: number
  latitude?: number | null
  longitude?: number | null
}

type Destination = {
  id: number
  name: string
  country_code: string
}

export type Pulse = {
  place_id: number
  pulse: number
  dimensions: Record<'demand' | 'capacity' | 'events' | 'environment', number>
  confidence: { score: number; coverage: number }
  trend: { change: number; direction: string }
  interpretation: { headline: string; strengths: string[]; weaknesses: string[]; data_quality: string }
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
  confidence_score: number
  confidence_coverage: number
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

export type Signal = {
  id: number
  place_id: number
  signal_type: string
  value: number
  unit: string | null
  observed_at: string
  source: string
  source_url: string | null
}

export type Event = {
  id: number
  place_id: number
  name: string
  event_type: string
  description: string | null
  start_at: string
  end_at: string | null
  source_url: string | null
  source: string | null
  external_id: string | null
}

export type Attraction = {
  id: number
  place_id: number
  name: string
  category: string
  description: string | null
  latitude: number | null
  longitude: number | null
  source: string | null
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = await response.json() as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // Keep the status-based message when the server does not return JSON.
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export async function getPlaces() {
  try {
    return await request<Place[]>('/places')
  } catch {
    const destinations = await request<Destination[]>('/destinations')
    const placesByDestination = await Promise.all(
      destinations.map(async (destination) => {
        const places = await request<Place[]>(`/destinations/${destination.id}/places`)
        return places.map((place) => ({ ...place, country_code: destination.country_code }))
      }),
    )
    return placesByDestination.flat()
  }
}
export const getPlacePulse = (placeId: number) => request<Pulse>(`/places/${placeId}/pulse`)
// persist=false: used for bulk/overview browsing so scanning many places at
// once doesn't write a pulse_snapshot row for every single one of them.
export const getPlacePulseSummary = (placeId: number) => request<Pulse>(`/places/${placeId}/pulse?persist=false`)
export const getPlaceHistory = (placeId: number) => request<PulseSnapshot[]>(`/places/${placeId}/pulse/history`)
export const getPlaceTrend = (placeId: number) => request<PulseTrend>(`/places/${placeId}/pulse/trend`)
export const getPlaceAnomaly = (placeId: number) => request<PulseAnomaly>(`/places/${placeId}/pulse/anomaly`)
export const getPlaceSignals = (placeId: number) => request<Signal[]>(`/places/${placeId}/signals`)
export const getPlaceEvents = (placeId: number) => request<Event[]>(`/places/${placeId}/events`)
export const getPlaceAttractions = (placeId: number) => request<Attraction[]>(`/places/${placeId}/attractions`)
