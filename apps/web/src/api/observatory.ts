import { request } from './client'
import type { Observatory } from '../types/observatory'

export const getPlaceObservatory = (placeId: number) =>
  request<Observatory>(`/places/${placeId}/observatory`)
