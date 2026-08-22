import { request } from './client'
import type { Pulse, PulseAnomaly, PulseSnapshot, PulseTrend } from '../types/pulse'

export const getPlacePulse = (placeId: number) => request<Pulse>(`/places/${placeId}/pulse`)
// persist=false: used for bulk/overview browsing so scanning many places
// at once doesn't write a pulse_snapshot (or spend an LLM call on a
// narrative - see routers/pulse.py) for every single one of them.
export const getPlacePulseSummary = (placeId: number) =>
  request<Pulse>(`/places/${placeId}/pulse?persist=false`)
export const getPlaceHistory = (placeId: number, limit?: number) =>
  request<PulseSnapshot[]>(`/places/${placeId}/pulse/history${limit ? `?limit=${limit}` : ''}`)
export const getPlaceTrend = (placeId: number) =>
  request<PulseTrend>(`/places/${placeId}/pulse/trend`)
export const getPlaceAnomaly = (placeId: number) =>
  request<PulseAnomaly>(`/places/${placeId}/pulse/anomaly`)
