import { request } from './client'
import type { EventLineage, SignalLineage } from '../types/lineage'

export const getSignalLineage = (placeId: number, signalId: number) =>
  request<SignalLineage>(`/places/${placeId}/signals/${signalId}/lineage`)

export const getEventLineage = (placeId: number, eventId: number) =>
  request<EventLineage>(`/places/${placeId}/events/${eventId}/lineage`)
