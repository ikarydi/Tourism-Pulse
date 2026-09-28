import type { Attention, AttentionSummary } from '../types/attention'
import { request } from './client'

export const getPlaceAttention = (placeId: number) => request<Attention>(`/places/${placeId}/attention`)
export const getAttention = () => request<AttentionSummary[]>('/attention')
