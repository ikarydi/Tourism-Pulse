export type Destination = {
  id: number
  country_code: string
  name: string
}

// "destination" = hand-curated places with live signals and a Pulse;
// "city" / "region" (NUTS 2) / "area" (NUTS 3) are generated from
// official EU geography and carry official statistics only.
export type PlaceType = 'country' | 'destination' | 'city' | 'region' | 'area'

// One row of GET /places.
export type Place = {
  id: number
  name: string
  place_type: PlaceType | string
  destination_id: number
  latitude: number | null
  longitude: number | null
  country_code?: string | null
  nuts_code?: string | null
  nuts3_code?: string | null
  urau_code?: string | null
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
