import { useEffect, useState } from 'react'
import { getObservatoryRanking } from '../api/observatory'
import { formatIndicatorValue, OBSERVATORY_INDICATORS, pressureBand } from '../lib/observatory'
import type { ObservatoryRanking } from '../types/observatory'
import './ObservatoryPage.css'

type ScopeFilter = 'all' | 'destination' | 'country'
type SortKey = 'score' | 'name' | (typeof OBSERVATORY_INDICATORS)[number]['key']

function percentileOf(row: ObservatoryRanking, key: string): number {
  return row.indicators.find((reading) => reading.indicator === key)?.percentile ?? -1
}

export function ObservatoryPage({ onSelectPlace }: { onSelectPlace: (placeId: number) => void }) {
  const [rows, setRows] = useState<ObservatoryRanking[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [scopeFilter, setScopeFilter] = useState<ScopeFilter>('destination')
  const [sortKey, setSortKey] = useState<SortKey>('score')

  useEffect(() => {
    let cancelled = false
    getObservatoryRanking()
      .then((ranking) => {
        if (!cancelled) setRows(ranking)
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : 'Unable to load the observatory.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return (
      <div className="state-panel loading-panel">
        <span className="spinner" />
        Ranking destinations against Europe...
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
        <span>Load NUTS regions and Eurostat regional indicators to rank destinations.</span>
      </div>
    )
  }

  const cityCount = rows.filter((row) => row.place_type !== 'country').length
  const countryCount = rows.length - cityCount
  const filtered = rows.filter(
    (row) =>
      scopeFilter === 'all' ||
      (scopeFilter === 'country' ? row.place_type === 'country' : row.place_type !== 'country'),
  )
  const sorted = [...filtered].sort((a, b) => {
    if (sortKey === 'name') return a.place_name.localeCompare(b.place_name)
    if (sortKey === 'score') return (b.score ?? -1) - (a.score ?? -1)
    return percentileOf(b, sortKey) - percentileOf(a, sortKey)
  })

  return (
    <section className="overview observatory-page">
      <div className="overview-controls">
        <div className="overview-filter" role="tablist" aria-label="Filter by scope">
          <button
            type="button"
            className={scopeFilter === 'destination' ? 'active' : ''}
            onClick={() => setScopeFilter('destination')}
          >
            Cities ({cityCount})
          </button>
          <button type="button" className={scopeFilter === 'country' ? 'active' : ''} onClick={() => setScopeFilter('country')}>
            National ({countryCount})
          </button>
          <button type="button" className={scopeFilter === 'all' ? 'active' : ''} onClick={() => setScopeFilter('all')}>
            All ({rows.length})
          </button>
        </div>
        <div className="overview-sort">
          <label htmlFor="observatory-sort-select">Sort by</label>
          <select
            id="observatory-sort-select"
            value={sortKey}
            onChange={(event) => setSortKey(event.target.value as SortKey)}
          >
            <option value="score">Pressure score</option>
            {OBSERVATORY_INDICATORS.map((indicator) => (
              <option key={indicator.key} value={indicator.key}>
                {indicator.short}
              </option>
            ))}
            <option value="name">Name</option>
          </select>
        </div>
      </div>

      <div className="overview-table-wrap">
        <table className="overview-table observatory-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Destination</th>
              <th>Region</th>
              <th>Pressure</th>
              {OBSERVATORY_INDICATORS.map((indicator) => (
                <th key={indicator.key}>{indicator.short}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, index) => (
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
      <p className="overview-footnote">
        Pressure is the mean of each indicator's percentile among European regions at the same NUTS level
        (NUTS 3 where Eurostat publishes it, else NUTS 2; countries among countries). Bars show that percentile:
        a full bar means the most pressured region in Europe. Source: Eurostat, latest year available.
      </p>
    </section>
  )
}
