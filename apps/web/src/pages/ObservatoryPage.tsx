import { useEffect, useMemo, useState } from 'react'
import { getObservatoryRanking } from '../api/observatory'
import { formatIndicatorValue, OBSERVATORY_INDICATORS, pressureBand } from '../lib/observatory'
import { PLACE_TYPE_LABELS } from '../lib/places'
import type { ObservatoryRanking } from '../types/observatory'
import type { Place } from '../types/place'
import './ObservatoryPage.css'

type SortKey = 'score' | 'name' | (typeof OBSERVATORY_INDICATORS)[number]['key']

const PAGE_SIZE = 50
const TYPE_ORDER = ['destination', 'city', 'region', 'area', 'country']

function percentileOf(row: ObservatoryRanking, key: string): number {
  return row.indicators.find((reading) => reading.indicator === key)?.percentile ?? -1
}

export function ObservatoryPage({
  places,
  onSelectPlace,
}: {
  places: Place[]
  onSelectPlace: (placeId: number) => void
}) {
  const [rows, setRows] = useState<ObservatoryRanking[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [placeType, setPlaceType] = useState<string>('destination')
  const [country, setCountry] = useState<string>('')
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('score')
  const [shown, setShown] = useState(PAGE_SIZE)

  useEffect(() => {
    let cancelled = false
    getObservatoryRanking()
      .then((ranking) => !cancelled && setRows(ranking))
      .catch((cause) => !cancelled && setError(cause instanceof Error ? cause.message : 'Unable to load the observatory.'))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  const counts = useMemo(() => {
    const byType: Record<string, number> = {}
    for (const row of rows) byType[row.place_type] = (byType[row.place_type] ?? 0) + 1
    return byType
  }, [rows])

  const countries = useMemo(() => {
    const names = new Map<string, string>()
    for (const place of places) if (place.place_type === 'country' && place.country_code) names.set(place.country_code, place.name)
    return [...new Set(rows.map((row) => row.country_code).filter((code): code is string => Boolean(code)))]
      .map((code) => ({ code, name: names.get(code) ?? code }))
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [rows, places])

  const sorted = useMemo(() => {
    const needle = search.trim().toLowerCase()
    const filtered = rows.filter(
      (row) =>
        (placeType === 'all' || row.place_type === placeType) &&
        (!country || row.country_code === country) &&
        (!needle || row.place_name.toLowerCase().includes(needle)),
    )
    return filtered.sort((a, b) => {
      if (sortKey === 'name') return a.place_name.localeCompare(b.place_name)
      if (sortKey === 'score') return (b.score ?? -1) - (a.score ?? -1)
      return percentileOf(b, sortKey) - percentileOf(a, sortKey)
    })
  }, [rows, placeType, country, search, sortKey])

  if (loading) {
    return (
      <div className="state-panel loading-panel">
        <span className="spinner" />
        Ranking every place against Europe...
      </div>
    )
  }

  if (error) {
    return (
      <div className="state-panel error">
        <strong>Connection issue</strong>
        <span>{error}</span>
      </div>
    )
  }

  if (!rows.length) {
    return (
      <div className="state-panel">
        <strong>No regional data yet</strong>
        <span>Load NUTS regions and Eurostat regional indicators to rank places.</span>
      </div>
    )
  }

  const resetPaging = () => setShown(PAGE_SIZE)

  return (
    <section className="overview observatory-page">
      <div className="observatory-toolbar">
        <div className="observatory-filters">
          <label className="observatory-filter">
            <span>Show</span>
            <select
              className="field"
              value={placeType}
              onChange={(event) => {
                setPlaceType(event.target.value)
                resetPaging()
              }}
            >
              {TYPE_ORDER.filter((type) => counts[type]).map((type) => (
                <option key={type} value={type}>
                  {PLACE_TYPE_LABELS[type]?.many ?? type} ({counts[type]})
                </option>
              ))}
              <option value="all">Everything ({rows.length})</option>
            </select>
          </label>
          <label className="observatory-filter">
            <span>Country</span>
            <select
              className="field"
              value={country}
              onChange={(event) => {
                setCountry(event.target.value)
                resetPaging()
              }}
            >
              <option value="">All countries</option>
              {countries.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label className="observatory-filter observatory-search">
            <span>Find</span>
            <input
              className="field"
              type="search"
              placeholder="Place name"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                resetPaging()
              }}
            />
          </label>
        </div>
        <label className="observatory-filter">
          <span>Sort by</span>
          <select className="field" value={sortKey} onChange={(event) => setSortKey(event.target.value as SortKey)}>
            <option value="score">Pressure score</option>
            {OBSERVATORY_INDICATORS.map((indicator) => (
              <option key={indicator.key} value={indicator.key}>
                {indicator.short}
              </option>
            ))}
            <option value="name">Name</option>
          </select>
        </label>
      </div>

      <p className="observatory-count">
        {sorted.length.toLocaleString()} place{sorted.length === 1 ? '' : 's'}
        {sorted.length > shown && `, showing the first ${shown}`}
      </p>

      <div className="overview-table-wrap">
        <table className="overview-table observatory-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Place</th>
              <th>Data from</th>
              <th>Pressure</th>
              {OBSERVATORY_INDICATORS.map((indicator) => (
                <th key={indicator.key}>{indicator.short}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.slice(0, shown).map((row, index) => (
              <tr key={row.place_id} className="overview-row" onClick={() => onSelectPlace(row.place_id)}>
                <td className="observatory-position">{index + 1}</td>
                <td className="overview-name">
                  <strong>{row.place_name}</strong>
                  {row.country_code ? <span className="overview-country"> · {row.country_code}</span> : null}
                </td>
                <td className="observatory-region">
                  {row.region_name ?? row.nuts_code}
                  <span>{row.level_name}</span>
                </td>
                <td className={`observatory-score-cell ${row.level ?? ''}`}>
                  <strong>{row.score?.toFixed(0)}</strong>
                  <span>{row.level}</span>
                </td>
                {OBSERVATORY_INDICATORS.map((indicator) => {
                  const reading = row.indicators.find((item) => item.indicator === indicator.key)
                  if (!reading) {
                    return (
                      <td key={indicator.key} className="overview-missing">
                        —
                      </td>
                    )
                  }
                  return (
                    <td
                      key={indicator.key}
                      className={`observatory-indicator-cell ${pressureBand(reading.percentile)}`}
                      title={`${reading.label}: rank ${reading.rank} of ${reading.peers} (${reading.level_name}, ${reading.year})`}
                    >
                      <span className="observatory-mini-track">
                        <span style={{ width: `${reading.percentile}%` }} />
                      </span>
                      <span className="observatory-mini-value">{formatIndicatorValue(reading, 'short')}</span>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sorted.length > shown && (
        <div className="observatory-more">
          <button type="button" className="button" onClick={() => setShown((value) => value + PAGE_SIZE)}>
            Show {Math.min(PAGE_SIZE, sorted.length - shown)} more
          </button>
        </div>
      )}
      <p className="overview-footnote">
        Pressure is the mean of each indicator's percentile among European regions at the same NUTS level (NUTS 3 where
        Eurostat publishes it, else NUTS 2; countries among countries). Bars show that percentile: a full bar means the
        most pressured region in Europe. Source: Eurostat, latest year available.
      </p>
    </section>
  )
}
