import { request } from './client'
import type { Attraction, Place, TourismEvent } from '../types/place'

// Every place in one request: curated destinations, countries, and the
// EU regions, areas and cities generated from official geography.
export const getPlaces = () => request<Place[]>('/places')

export const getPlace = (placeId: number) => request<Place>(`/places/${placeId}`)
export const getPlaceAttractions = (placeId: number) =>
  request<Attraction[]>(`/places/${placeId}/attractions`)
export const getPlaceEvents = (placeId: number) =>
  request<TourismEvent[]>(`/places/${placeId}/events`)
