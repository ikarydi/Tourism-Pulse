import type { ForecastSummary, PlaceForecast } from '../types/forecast'
import { request } from './client'

export const getPlaceForecast = (placeId: number) => request<PlaceForecast>(`/places/${placeId}/forecast`)
export const getForecasts = () => request<ForecastSummary[]>('/forecasts')
