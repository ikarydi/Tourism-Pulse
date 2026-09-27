import { request } from './client'
import type { Pulse, PulseAnomaly, PulseSnapshot, PulseTrend } from '../types/pulse'

export const getPlacePulse = (placeId: number) => request<Pulse>(`/places/${placeId}/pulse`)
// persist=false: used for bulk/overview browsing so scanning many places
// at once doesn't write a pulse_snapshot (or spend an LLM call on a
// narrative - see routers/pulse.py) for every single one of them.
//
// Summaries are shared for a minute: the map and the destinations table ask
// for the same ~90 places, and switching between them (or React's dev-mode
// double effects) should not recompute every Pulse.
const SUMMARY_TTL_MS = 60_000
const summaries = new Map<number, { at: number; pulse: Promise<Pulse> }>()

export function getPlacePulseSummary(placeId: number): Promise<Pulse> {
  const cached = summaries.get(placeId)
  if (cached && Date.now() - cached.at < SUMMARY_TTL_MS) return cached.pulse
  const pulse = request<Pulse>(`/places/${placeId}/pulse?persist=false`)
  // A failure (no Pulse for this place) is cached too, then retried after the TTL.
  summaries.set(placeId, { at: Date.now(), pulse })
  return pulse
}
export const getPlaceHistory = (placeId: number, limit?: number) =>
  request<PulseSnapshot[]>(`/places/${placeId}/pulse/history${limit ? `?limit=${limit}` : ''}`)
export const getPlaceTrend = (placeId: number) =>
  request<PulseTrend>(`/places/${placeId}/pulse/trend`)
export const getPlaceAnomaly = (placeId: number) =>
  request<PulseAnomaly>(`/places/${placeId}/pulse/anomaly`)
