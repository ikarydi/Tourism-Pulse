import { request } from './client'
import type { Observatory, ObservatoryRanking } from '../types/observatory'

export const getPlaceObservatory = (placeId: number) =>
  request<Observatory>(`/places/${placeId}/observatory`)

// Official statistics change a few times a year; one ranking per five
// minutes serves the map, the observatory page and repeat visits.
const RANKING_TTL_MS = 5 * 60_000
let ranking: { at: number; rows: Promise<ObservatoryRanking[]> } | null = null

export function getObservatoryRanking(): Promise<ObservatoryRanking[]> {
  if (!ranking || Date.now() - ranking.at >= RANKING_TTL_MS) {
    const rows = request<ObservatoryRanking[]>('/observatory')
    ranking = { at: Date.now(), rows }
    // Do not keep a failed request around for five minutes.
    rows.catch(() => {
      if (ranking?.rows === rows) ranking = null
    })
  }
  return ranking.rows
}
