import { request } from './client'
import type { Observatory, ObservatoryRanking } from '../types/observatory'

export const getPlaceObservatory = (placeId: number) =>
  request<Observatory>(`/places/${placeId}/observatory`)

export const getObservatoryRanking = () => request<ObservatoryRanking[]>('/observatory')
