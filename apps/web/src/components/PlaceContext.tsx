import { useMemo, useState } from 'react'
import { placeTypeLabel } from '../lib/places'
import type { Place } from '../types/place'
import './PlaceContext.css'

const LINK_LIMIT = 14

function PlaceLinks({
  title,
  items,
  onSelectPlace,
}: {
  title: string
  items: Place[]
  onSelectPlace: (placeId: number) => void
}) {
  const [showAll, setShowAll] = useState(false)
  if (!items.length) return null
  const shown = showAll ? items : items.slice(0, LINK_LIMIT)
  return (
    <div className="place-links">
      <p className="mini-label">
        {title} <span>{items.length}</span>
      </p>
      <div className="chip-row">
        {shown.map((item) => (
          <button key={item.id} type="button" className="chip" onClick={() => onSelectPlace(item.id)}>
            {item.name}
          </button>
        ))}
        {items.length > LINK_LIMIT && (
          <button type="button" className="chip chip-more" onClick={() => setShowAll((value) => !value)}>
            {showAll ? 'Show fewer' : `+${items.length - LINK_LIMIT} more`}
          </button>
        )}
      </div>
    </div>
  )
}

/** Where a place sits (country, NUTS 2 region, NUTS 3 area) and what sits
 * inside it, worked out from the place list's codes. */
export function PlaceContext({
  place,
  places,
  onSelectPlace,
}: {
  place: Place
  places: Place[]
  onSelectPlace: (placeId: number) => void
}) {
  const context = useMemo(() => {
    const byName = (a: Place, b: Place) => a.name.localeCompare(b.name)
    const type = place.place_type
    const country =
      type === 'country'
        ? undefined
        : places.find((item) => item.place_type === 'country' && item.country_code === place.country_code)
    const region =
      type === 'city' || type === 'area' || type === 'destination'
        ? places.find((item) => item.place_type === 'region' && item.nuts_code === place.nuts_code)
        : undefined
    const area =
      type === 'city' || type === 'destination'
        ? places.find((item) => item.place_type === 'area' && item.nuts3_code === place.nuts3_code)
        : undefined
    const inside = (childType: string) =>
      places
        .filter((item) => {
          if (item.place_type !== childType || item.id === place.id) return false
          if (type === 'country') return item.country_code === place.country_code
          if (type === 'region') return item.nuts_code === place.nuts_code
          if (type === 'area') return item.nuts3_code === place.nuts3_code
          return false
        })
        .sort(byName)
    return {
      parents: [country, region, area].filter((item): item is Place => item !== undefined),
      regions: type === 'country' ? inside('region') : [],
      areas: type === 'region' ? inside('area') : [],
      cities: type === 'region' || type === 'area' ? inside('city') : [],
      destinations: inside('destination'),
    }
  }, [place, places])

  const { parents, regions, areas, cities, destinations } = context
  if (!parents.length && !regions.length && !areas.length && !cities.length && !destinations.length) return null

  return (
    <section className="card region-context">
      {parents.length > 0 && (
        <div className="place-links">
          <p className="mini-label">Part of</p>
          <div className="chip-row">
            {parents.map((parent) => (
              <button key={parent.id} type="button" className="chip" onClick={() => onSelectPlace(parent.id)}>
                {parent.name} <em>{placeTypeLabel(parent.place_type)}</em>
              </button>
            ))}
          </div>
        </div>
      )}
      <PlaceLinks title="Curated destinations here" items={destinations} onSelectPlace={onSelectPlace} />
      <PlaceLinks title="NUTS 2 regions" items={regions} onSelectPlace={onSelectPlace} />
      <PlaceLinks title="NUTS 3 areas" items={areas} onSelectPlace={onSelectPlace} />
      <PlaceLinks title="Cities" items={cities} onSelectPlace={onSelectPlace} />
    </section>
  )
}
