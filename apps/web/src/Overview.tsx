import { useEffect, useState } from 'react'
import { getPlacePulseSummary, type Place, type Pulse } from './api'
import { dimensions, scoreStatus } from './format'

type SortKey = 'pulse' | 'demand' | 'capacity' | 'events' | 'environment' | 'name'
type ScopeFilter = 'all' | 'destination' | 'country'

type Row = {
  place: Place
  pulse: Pulse | null
  error: boolean
}

export function Overview({ places, onSelectPlace }: { places: Place[]; onSelectPlace: (placeId: number) => void }) {
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(places.length > 0)
  const [scopeFilter, setScopeFilter] = useState<ScopeFilter>('all')
  const [sortKey, setSortKey] = useState<SortKey>('pulse')

  useEffect(() => {
    if (!places.length) return

    let cancelled = false

    async function loadRows() {
      setLoading(true)
      const results = await Promise.all(
        places.map(async (place): Promise<Row> => {
          try {
            const pulse = await getPlacePulseSummary(place.id)
            return { place, pulse, error: false }
          } catch {
            return { place, pulse: null, error: true }
          }
        }),
      )
      if (!cancelled) {
        setRows(results)
        setLoading(false)
      }
    }

    void loadRows()

    return () => { cancelled = true }
  }, [places])

  const cityCount = rows.filter((row) => row.place.place_type !== 'country').length
  const countryCount = rows.filter((row) => row.place.place_type === 'country').length

  const filtered = rows.filter((row) => scopeFilter === 'all'
    || (scopeFilter === 'country' ? row.place.place_type === 'country' : row.place.place_type !== 'country'))

  const sorted = [...filtered].sort((a, b) => {
    if (sortKey === 'name') return a.place.name.localeCompare(b.place.name)
    const valueOf = (row: Row) => row.pulse ? (sortKey === 'pulse' ? row.pulse.pulse : row.pulse.dimensions[sortKey]) : -1
    return valueOf(b) - valueOf(a)
  })

  if (loading) {
    return <div className="state-panel loading-panel"><span className="spinner" />Loading {places.length} destinations...</div>
  }

  if (!rows.length) {
    return <div className="state-panel"><strong>No destinations yet</strong><span>Add a destination in the API to see it here.</span></div>
  }

  return (
    <section className="overview">
      <div className="overview-controls">
        <div className="overview-filter" role="tablist" aria-label="Filter by scope">
          <button type="button" className={scopeFilter === 'all' ? 'active' : ''} onClick={() => setScopeFilter('all')}>All ({rows.length})</button>
          <button type="button" className={scopeFilter === 'destination' ? 'active' : ''} onClick={() => setScopeFilter('destination')}>Cities ({cityCount})</button>
          <button type="button" className={scopeFilter === 'country' ? 'active' : ''} onClick={() => setScopeFilter('country')}>National ({countryCount})</button>
        </div>
        <div className="overview-sort">
          <label htmlFor="overview-sort-select">Sort by</label>
          <select id="overview-sort-select" value={sortKey} onChange={(event) => setSortKey(event.target.value as SortKey)}>
            <option value="pulse">Pulse</option>
            {dimensions.map((dimension) => <option key={dimension.key} value={dimension.key}>{dimension.label}</option>)}
            <option value="name">Name</option>
          </select>
        </div>
      </div>
      <div className="overview-table-wrap">
        <table className="overview-table">
          <thead>
            <tr>
              <th>Destination</th>
              <th>Scope</th>
              <th>Pulse</th>
              {dimensions.map((dimension) => <th key={dimension.key}>{dimension.label}</th>)}
              <th>Coverage</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(({ place, pulse, error }) => (
              <tr key={place.id} className="overview-row" onClick={() => onSelectPlace(place.id)}>
                <td className="overview-name"><strong>{place.name}</strong>{place.country_code ? <span className="overview-country"> · {place.country_code}</span> : null}</td>
                <td><span className={`scope-badge ${place.place_type === 'country' ? 'national' : 'city'}`}>{place.place_type === 'country' ? 'National' : 'City'}</span></td>
                {!pulse || error ? (
                  <td colSpan={dimensions.length + 2} className="overview-empty">No pulse data yet</td>
                ) : (
                  <>
                    <td className={`overview-pulse ${scoreStatus(pulse.pulse).toLowerCase()}`}>{Math.round(pulse.pulse)}</td>
                    {dimensions.map((dimension) => {
                      const value = pulse.dimensions[dimension.key]
                      return <td key={dimension.key} className={value === 0 ? 'overview-missing' : ''}>{value === 0 ? '—' : Math.round(value)}</td>
                    })}
                    <td>{Math.round(pulse.confidence.coverage)}%</td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="overview-footnote">National rows carry country-level demand only (Eurostat has no per-city breakdown); city rows carry weather and events. A dash means that dimension has no signal yet, not a score of zero.</p>
    </section>
  )
}
