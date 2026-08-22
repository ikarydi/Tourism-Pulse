export type Destination = {
  id: number
  country_code: string
  name: string
}

export type Place = {
  id: number
  name: string
  place_type: string
  destination_id: number
  latitude: number | null
  longitude: number | null
  // Not part of the API response - stitched on client-side from the
  // parent Destination when places are loaded (see api/places.ts), so
  // every other module can treat a Place as self-contained.
  country_code?: string
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

export type TourismEvent = {
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
