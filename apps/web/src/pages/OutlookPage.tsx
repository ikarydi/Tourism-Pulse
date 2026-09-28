import { useEffect, useMemo, useState } from 'react'
import { getForecasts, getPlaceForecast } from '../api/forecast'
import { ForecastChart } from '../components/charts/ForecastChart'
import { OutlookFigures } from '../components/ForecastCard'
import { changeTone, compactNights, periodLabel, plainPercent, signedPercent } from '../lib/outlook'
import type { ForecastSummary, PlaceForecast } from '../types/forecast'
import './OutlookPage.css'

type Scope = 'country' | 'region'

function ValidationStrip() {
  return (
    <section className="card outlook-validation" aria-label="How the forecasts were tested">
      <div>
        <p className="eyebrow">How good is it?</p>
        <p className="outlook-validation-lead">
          Tested before launch on 30 European countries, 1–12 months ahead, with the rules fixed in advance (Gate 2).
        </p>
      </div>
      <dl>
        <div>
          <dt>Average error</dt>
          <dd>4.96%</dd>
          <span>against 5.35% for last year's figure</span>
        </div>
        <div>
          <dt>Beat last year's figure</dt>
          <dd>20 / 30</dd>
          <span>countries; too few to claim it outright</span>
        </div>
        <div>
          <dt>Online attention helped</dt>
          <dd>26 / 30</dd>
          <span>countries, mostly 4–12 months ahead</span>
        </div>
        <div>
          <dt>80% ranges held</dt>
          <dd>81%</dd>
          <span>of outcomes</span>
        </div>
      </dl>
    </section>
  )
}

function ForecastDetail({ summary, onOpenPlace }: { summary: ForecastSummary; onOpenPlace: (placeId: number) => void }) {
  const [forecast, setForecast] = useState<PlaceForecast | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    getPlaceForecast(summary.place_id)
      .then((data) => !cancelled && setForecast(data))
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [summary.place_id])

  if (failed) return <div className="card empty-note">The forecast for {summary.name} could not be loaded.</div>
  if (!forecast) return <div className="card skeleton outlook-detail-skeleton" />

  return (
    <section className="card outlook-detail">
      <header className="outlook-detail-head">
        <div>
          <p className="eyebrow">{summary.place_type === 'country' ? 'Country' : 'Region'} · official nights</p>
          <h2>{summary.name}</h2>
          <p className="outlook-detail-sub">
            Official data to {periodLabel(forecast.origin, 'long')} · issued{' '}
            {new Date(forecast.issued_at).toLocaleDateString('en', { day: 'numeric', month: 'short', year: 'numeric' })}
          </p>
        </div>
        <button type="button" className="button" onClick={() => onOpenPlace(summary.place_id)}>
          Open place page
        </button>
      </header>

      <OutlookFigures forecast={forecast} />
      <ForecastChart forecast={forecast} />

      <div className="outlook-tables">
        <div className="outlook-table-wrap">
          <table className="outlook-months">
            <thead>
              <tr>
                <th>Month</th>
                <th>Forecast</th>
                <th>80% range</th>
                <th>Last year</th>
                <th>Change</th>
              </tr>
            </thead>
            <tbody>
              {forecast.points.map((point) => {
                const change = point.last_year ? point.point / point.last_year - 1 : null
                return (
                  <tr key={point.period}>
                    <td>{periodLabel(point.period)}</td>
                    <td>{compactNights(point.point)}</td>
                    <td className="muted">
                      {compactNights(point.low_80)} – {compactNights(point.high_80)}
                    </td>
                    <td className="muted">{point.last_year != null ? compactNights(point.last_year) : '—'}</td>
                    <td className={changeTone(change)}>{signedPercent(change, 1)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <div className="outlook-method">
          <p className="mini-label">Method</p>
          <p>{forecast.method}</p>
          {forecast.backtest && forecast.backtest.by_horizon.length > 0 && (
            <>
              <p className="mini-label">Backtest error by horizon</p>
              <div className="horizon-bars">
                {forecast.backtest.by_horizon.map((row) => (
                  <div key={row.horizon} title={`${row.horizon} months ahead: ${plainPercent(row.mape, 1)} over ${row.scored} forecasts`}>
                    <span style={{ height: `${Math.min(100, row.mape * 1000)}%` }} />
                    <em>{row.horizon}</em>
                  </div>
                ))}
              </div>
              <p className="outlook-method-note">
                Months ahead; bar height is the average error ({plainPercent(forecast.backtest.mape, 1)} overall,{' '}
                {forecast.backtest.scored} forecasts from 2024–26 origins).
              </p>
            </>
          )}
          <p className="mini-label">Live track record</p>
          <p>
            {forecast.track_record?.scored
              ? `${forecast.track_record.scored} forecasts scored so far, average error ${plainPercent(forecast.track_record.mape, 1)}.`
              : 'Starts with this forecast: each month is scored when Eurostat publishes it, and forecasts are never edited afterwards.'}
          </p>
        </div>
      </div>
    </section>
  )
}

export function OutlookPage({
  focusPlaceId = null,
  onOpenPlace,
}: {
  focusPlaceId?: number | null
  onOpenPlace: (placeId: number) => void
}) {
  const [rows, setRows] = useState<ForecastSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [scope, setScope] = useState<Scope>('country')
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(focusPlaceId)

  useEffect(() => {
    let cancelled = false
    getForecasts()
      .then((data) => {
        if (cancelled) return
        setRows(data)
        // Opened from a place page: show that place's pool.
        const focus = data.find((row) => row.place_id === focusPlaceId)
        if (focus && focus.place_type !== 'country') setScope('region')
      })
      .catch((err: Error) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [focusPlaceId])

  const shown = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return (rows ?? [])
      .filter((row) => (scope === 'country' ? row.place_type === 'country' : row.place_type !== 'country'))
      .filter((row) => !needle || row.name.toLowerCase().includes(needle))
      .sort((a, b) => (b.next_12_change ?? -Infinity) - (a.next_12_change ?? -Infinity))
  }, [rows, scope, search])

  const selected = shown.find((row) => row.place_id === selectedId) ?? shown[0] ?? null
  const counts = {
    country: rows?.filter((row) => row.place_type === 'country').length ?? 0,
    region: rows?.filter((row) => row.place_type !== 'country').length ?? 0,
  }

  if (error) return <div className="state-panel error"><strong>Forecasts unavailable</strong><span>{error}</span></div>
  if (!rows) return <div className="state-panel loading-panel"><span className="spinner" />Loading forecasts...</div>
  if (!rows.length)
    return (
      <div className="state-panel">
        <strong>No forecasts yet</strong>
        <span>Run python -m tourism_pulse_api.forecasting to issue them.</span>
      </div>
    )

  return (
    <div className="outlook-page">
      <ValidationStrip />
      <div className="outlook-layout">
        <section className="card outlook-list">
          <div className="segmented" role="radiogroup" aria-label="Places">
            {(['country', 'region'] as const).map((value) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={scope === value}
                className={scope === value ? 'active' : ''}
                onClick={() => {
                  setScope(value)
                  setSelectedId(null)
                }}
              >
                {value === 'country' ? `Countries (${counts.country})` : `Regions (${counts.region})`}
              </button>
            ))}
          </div>
          <input
            id="outlook-search"
            className="field"
            type="search"
            placeholder="Find a place"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          {scope === 'region' && (
            <p className="outlook-list-note">
              Regions: official data only, not yet validated. Regional figures are published later, so early months are
              estimates of months already past.
            </p>
          )}
          <div className="outlook-list-head" aria-hidden="true">
            <span>Place</span>
            <span>Next 3 mo.</span>
            <span>Next 12 mo.</span>
          </div>
          <ul>
            {shown.map((row) => (
              <li key={row.place_id}>
                <button
                  type="button"
                  className={row.place_id === selected?.place_id ? 'active' : ''}
                  onClick={() => setSelectedId(row.place_id)}
                >
                  <span className="outlook-list-name">
                    {row.name}
                    {row.country_code && row.place_type !== 'country' && <em> · {row.country_code}</em>}
                  </span>
                  <span className={changeTone(row.next_3_change)}>{signedPercent(row.next_3_change, 1)}</span>
                  <span className={changeTone(row.next_12_change)}>{signedPercent(row.next_12_change, 1)}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
        {selected && <ForecastDetail key={selected.place_id} summary={selected} onOpenPlace={onOpenPlace} />}
      </div>
    </div>
  )
}
