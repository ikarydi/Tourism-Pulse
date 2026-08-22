import { useRef } from 'react'
import { EuropeMap } from '../features/map/EuropeMap'
import type { Place } from '../types/place'
import { DetailPage } from './DetailPage'
import './MapPage.css'

export function MapPage({
  places,
  selectedPlace,
  onSelectPlace,
}: {
  places: Place[]
  selectedPlace: Place | null
  onSelectPlace: (placeId: number) => void
}) {
  const detailRef = useRef<HTMLDivElement>(null)

  return (
    <div className="map-page">
      <EuropeMap
        places={places}
        onSelectPlace={onSelectPlace}
        onJumpToDetail={() => detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
      />
      <div ref={detailRef} className="map-page-detail">
        {selectedPlace ? (
          <DetailPage place={selectedPlace} />
        ) : (
          <div className="state-panel">
            <strong>No destination selected</strong>
            <span>Click a marker on the map to see its full intelligence readout.</span>
          </div>
        )}
      </div>
    </div>
  )
}
