import { EuropeMap } from '../features/map/EuropeMap'
import type { Place } from '../types/place'

export function MapPage({
  places,
  onSelectPlace,
  onOpenPlace,
}: {
  places: Place[]
  onSelectPlace: (placeId: number) => void
  onOpenPlace: (placeId: number) => void
}) {
  return (
    <div className="map-page">
      <EuropeMap places={places} onSelectPlace={onSelectPlace} onOpenPlace={onOpenPlace} />
    </div>
  )
}
