import { request } from './client'

export type Signal = {
  id: number
  place_id: number
  signal_type: string
  value: number
  unit: string | null
  observed_at: string
  source: string
  source_url: string | null
}

// The wire shape's `value` is a Pydantic Decimal, which FastAPI serializes
// as a JSON string (not a number) to preserve precision - see
// schemas/signal.py. Coerced to a real number once, right here, so every
// consumer of `Signal` can rely on `value: number` and use it directly
// (.toFixed, arithmetic, comparisons) without redoing this at every call
// site.
type RawSignal = Omit<Signal, 'value'> & { value: number | string }

export async function getPlaceSignals(placeId: number): Promise<Signal[]> {
  const raw = await request<RawSignal[]>(`/places/${placeId}/signals`)
  return raw.map((signal) => ({ ...signal, value: Number(signal.value) }))
}
