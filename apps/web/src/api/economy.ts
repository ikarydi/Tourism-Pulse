import type { Economy } from '../types/economy'
import { request } from './client'

export const getPlaceEconomy = (placeId: number) => request<Economy>(`/places/${placeId}/economy`)
