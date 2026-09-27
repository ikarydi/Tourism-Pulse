import { useMemo, useState } from 'react'
import type { PlaceRef, QuerySpec } from '../../types/explore'

type Scope = 'destination' | 'country' | 'all' | 'custom'

const CHIP_LIMIT = 8

function scopeOf(query: QuerySpec): Scope {
  if (query.places) return 'custom'
  return query.place_type ?? 'all'
}

/** Which places a query covers: a whole scope, or a hand-picked set. */
export function PlacePicker({
  places,
  query,
  onChange,
}: {
  places: PlaceRef[]
  query: QuerySpec
  onChange: (changes: Pick<QuerySpec, 'places' | 'place_type'>) => void
}) {
  const [search, setSearch] = useState('')
  const [showAll, setShowAll] = useState(false)
  const scope = scopeOf(query)
  const selected = useMemo(() => new Set(query.places ?? []), [query.places])
  const matches = places.filter((place) => place.name.toLowerCase().includes(search.trim().toLowerCase()))

  function setScope(next: Scope) {
    if (next === 'custom') onChange({ places: [...selected].length ? [...selected] : [], place_type: null })
    else onChange({ places: null, place_type: next === 'all' ? null : next })
  }

  function toggle(id: number) {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onChange({ places: [...next], place_type: null })
  }

  return (
    <div className="place-picker">
      <div className="segmented" role="radiogroup" aria-label="Places">
        {(
          [
            ['destination', 'Cities'],
            ['country', 'Countries'],
            ['all', 'All'],
            ['custom', 'Pick'],
          ] as [Scope, string][]
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={scope === value}
            className={scope === value ? 'active' : ''}
            onClick={() => setScope(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {scope === 'custom' && (
        <>
          {selected.size > 0 && (
            <div className="chip-row">
              {/* Long selections collapse so the panel stays usable. */}
              {[...selected].slice(0, showAll ? undefined : CHIP_LIMIT).map((id) => (
                <button key={id} type="button" className="chip" onClick={() => toggle(id)} title="Remove">
                  {places.find((place) => place.id === id)?.name ?? id} ×
                </button>
              ))}
              {selected.size > CHIP_LIMIT && (
                <button type="button" className="chip chip-more" onClick={() => setShowAll((value) => !value)}>
                  {showAll ? 'Show fewer' : `+${selected.size - CHIP_LIMIT} more`}
                </button>
              )}
              <button
                type="button"
                className="chip chip-more"
                onClick={() => onChange({ places: [], place_type: null })}
              >
                Clear
              </button>
            </div>
          )}
          <input
            className="field"
            type="search"
            placeholder="Search places"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            aria-label="Search places"
          />
          <ul className="place-list">
            {matches.map((place) => (
              <li key={place.id}>
                <label>
                  <input type="checkbox" checked={selected.has(place.id)} onChange={() => toggle(place.id)} />
                  <span>{place.name}</span>
                  <em>{place.place_type === 'country' ? 'country' : place.country_code}</em>
                </label>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
