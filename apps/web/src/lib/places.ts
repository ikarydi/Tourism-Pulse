import type { Place } from '../types/place'

export const PLACE_TYPE_LABELS: Record<string, { one: string; many: string }> = {
  destination: { one: 'Destination', many: 'Destinations' },
  city: { one: 'City', many: 'EU cities' },
  region: { one: 'NUTS 2 region', many: 'Regions (NUTS 2)' },
  area: { one: 'NUTS 3 area', many: 'Areas (NUTS 3)' },
  country: { one: 'Country', many: 'Countries' },
}

/** Curated places have live signals and a Pulse; the rest official statistics only. */
export function isCurated(place: Pick<Place, 'place_type'>): boolean {
  return place.place_type === 'destination' || place.place_type === 'country'
}

export function placeTypeLabel(placeType: string): string {
  return PLACE_TYPE_LABELS[placeType]?.one ?? placeType
}

export function placeSubtitle(place: Pick<Place, 'place_type' | 'country_code'>): string {
  const label = placeTypeLabel(place.place_type)
  return place.place_type === 'country' || !place.country_code ? label : `${label} · ${place.country_code}`
}
