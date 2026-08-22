import { request } from './client'
import type { PlaceDemographics } from '../types/demographics'

export const getPlaceDemographics = (placeId: number) =>
  request<PlaceDemographics[]>(`/places/${placeId}/demographics`)
