import { request } from './client'
import type { Attraction, Destination, Place, TourismEvent } from '../types/place'

// There's no flat GET /places - only GET /destinations/{id}/places -
// so this walks every destination and stitches each place's
// country_code from its parent (see types/place.ts's note on
// Place.country_code).
export async function getPlaces(): Promise<Place[]> {
  const destinations = await request<Destination[]>('/destinations')
  const placesByDestination = await Promise.all(
    destinations.map(async (destination) => {
      const places = await request<Place[]>(`/destinations/${destination.id}/places`)
      return places.map((place) => ({ ...place, country_code: destination.country_code }))
    }),
  )
  return placesByDestination.flat()
}

export const getPlace = (placeId: number) => request<Place>(`/places/${placeId}`)
export const getPlaceAttractions = (placeId: number) =>
  request<Attraction[]>(`/places/${placeId}/attractions`)
export const getPlaceEvents = (placeId: number) =>
  request<TourismEvent[]>(`/places/${placeId}/events`)
