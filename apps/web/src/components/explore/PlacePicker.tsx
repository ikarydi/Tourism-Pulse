import { useMemo, useState } from 'react'
import { PLACE_TYPE_LABELS, placeSubtitle } from '../../lib/places'
import type { PlaceRef, QuerySpec } from '../../types/explore'

type Scope = NonNullable<QuerySpec['place_type']> | 'all' | 'custom'

const CHIP_LIMIT = 8
const MATCH_LIMIT = 100
const SCOPES: Scope[] = ['destination', 'city', 'region', 'area', 'country', 'all', 'custom']

function scopeOf(query: QuerySpec): Scope {
  if (query.places) return 'custom'
  return query.place_type ?? 'all'
}

function scopeLabel(scope: Scope, counts: Record<string, number>, total: number): string {
  if (scope === 'all') return `Everything (${total})`
  if (scope === 'custom') return 'Pick places...'
  return `${PLACE_TYPE_LABELS[scope]?.many ?? scope} (${counts[scope] ?? 0})`
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
  const counts = useMemo(() => {
    const byType: Record<string, number> = {}
    for (const place of places) byType[place.place_type] = (byType[place.place_type] ?? 0) + 1
    return byType
  }, [places])
  const needle = search.trim().toLowerCase()
  const matches = needle ? places.filter((place) => place.name.toLowerCase().includes(needle)) : []

  function setScope(next: Scope) {
    if (next === 'custom') onChange({ places: [...selected], place_type: null })
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
      <select
        className="field"
        value={scope}
        onChange={(event) => setScope(event.target.value as Scope)}
        aria-label="Which places"
      >
        {SCOPES.filter((item) => item === 'all' || item === 'custom' || counts[item]).map((item) => (
          <option key={item} value={item}>
            {scopeLabel(item, counts, places.length)}
          </option>
        ))}
      </select>

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
              <button type="button" className="chip chip-more" onClick={() => onChange({ places: [], place_type: null })}>
                Clear
              </button>
            </div>
          )}
          <input
            className="field"
            type="search"
            placeholder={`Search ${places.length.toLocaleString()} places`}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            aria-label="Search places"
          />
          {needle && (
            <ul className="place-list">
              {matches.slice(0, MATCH_LIMIT).map((place) => (
                <li key={place.id}>
                  <label>
                    <input type="checkbox" checked={selected.has(place.id)} onChange={() => toggle(place.id)} />
                    <span>{place.name}</span>
                    <em>{placeSubtitle(place)}</em>
                  </label>
                </li>
              ))}
              {matches.length === 0 && <li className="place-list-note">No places match.</li>}
              {matches.length > MATCH_LIMIT && (
                <li className="place-list-note">{matches.length - MATCH_LIMIT} more; refine the search.</li>
              )}
            </ul>
          )}
        </>
      )}
    </div>
  )
}
