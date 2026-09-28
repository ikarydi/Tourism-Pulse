import * as Plot from '@observablehq/plot'
import { useCallback, useEffect, useState } from 'react'
import { getPlaceEconomy } from '../api/economy'
import { changeTone, compactNights, periodDate, periodLabel, plainPercent, signedPercent } from '../lib/outlook'
import type { Economy, Flights, Prices } from '../types/economy'
import { PlotFigure } from './charts/PlotFigure'
import './AttentionPanel.css'
import './InboundEconomyPanel.css'

const RISE = '#5fd3e8'
const FALL = '#e8836a'
const MUTED = '#8ea0b3'
const PLOT_STYLE = { background: 'transparent', color: MUTED, fontSize: '11px', overflow: 'visible' }

/** Percent values from the API (4.5) to the shared fraction helpers. */
const pct = (value: number | null | undefined) => (value == null ? null : value / 100)

function signedBalance(value: number | null | undefined): string {
  if (value == null) return '—'
  const rounded = Math.round(value)
  return `${rounded > 0 ? '+' : rounded < 0 ? '−' : ''}${Math.abs(rounded)}`
}

function FlightsChart({ flights }: { flights: Flights }) {
  const build = useCallback(
    (width: number) => {
      const data = flights.series
        .filter((row) => row.growth != null)
        .map((row) => ({ date: periodDate(row.period), value: row.growth as number }))
      return Plot.plot({
        width,
        height: 140,
        marginLeft: 40,
        marginTop: 10,
        style: PLOT_STYLE,
        x: { type: 'utc', label: null },
        y: { grid: true, label: null, tickFormat: (value: number) => `${value}%` },
        marks: [
          Plot.ruleY([0], { stroke: MUTED, strokeOpacity: 0.5 }),
          Plot.rectY(data, {
            x: 'date',
            y: 'value',
            interval: 'month',
            inset: 1,
            fill: (row: { value: number }) => (row.value >= 0 ? RISE : FALL),
            fillOpacity: 0.75,
          }),
          Plot.tip(
            data,
            Plot.pointerX({
              x: 'date',
              y: 'value',
              fill: '#101e2e',
              stroke: 'rgba(163, 196, 224, 0.3)',
              title: (row: { date: Date; value: number }) =>
                `${row.date.toLocaleDateString('en', { month: 'long', year: 'numeric', timeZone: 'UTC' })}\n${signedPercent(row.value / 100, 1)} flights vs a year earlier`,
            }),
          ),
        ],
      })
    },
    [flights],
  )
  return <PlotFigure build={build} />
}

function PricesChart({ prices }: { prices: Prices }) {
  const build = useCallback(
    (width: number) => {
      const rows = prices.series.flatMap((row) => [
        ...(row.accommodation != null
          ? [{ date: periodDate(row.period), value: row.accommodation, series: 'Accommodation' }]
          : []),
        ...(row.all_items != null ? [{ date: periodDate(row.period), value: row.all_items, series: 'All prices' }] : []),
      ])
      return Plot.plot({
        width,
        height: 140,
        marginLeft: 40,
        marginTop: 10,
        style: PLOT_STYLE,
        x: { type: 'utc', label: null },
        y: { grid: true, label: null, tickFormat: (value: number) => `${value}%` },
        color: { domain: ['Accommodation', 'All prices'], range: [RISE, MUTED] },
        marks: [
          Plot.ruleY([0], { stroke: MUTED, strokeOpacity: 0.5 }),
          Plot.lineY(rows, { x: 'date', y: 'value', stroke: 'series', strokeWidth: 1.6, curve: 'monotone-x' }),
          Plot.tip(
            rows,
            Plot.pointerX({
              x: 'date',
              y: 'value',
              fill: '#101e2e',
              stroke: 'rgba(163, 196, 224, 0.3)',
              title: (row: { date: Date; value: number; series: string }) =>
                `${row.series}, ${row.date.toLocaleDateString('en', { month: 'long', year: 'numeric', timeZone: 'UTC' })}\n${signedPercent(row.value / 100, 1)} vs a year earlier`,
            }),
          ),
        ],
      })
    },
    [prices],
  )
  return <PlotFigure build={build} />
}

/** Flights at the place's airports, and its country's hotel survey,
 * prices, turnover and origin markets. */
export function InboundEconomyPanel({ placeId }: { placeId: number }) {
  const [economy, setEconomy] = useState<Economy | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    getPlaceEconomy(placeId)
      .then((data) => !cancelled && setEconomy(data))
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [placeId])

  if (failed) return null
  if (!economy) return <div className="card skeleton attention-skeleton" />
  const { flights, survey, prices, turnover, origins } = economy
  if (!flights && !survey && !prices && !origins) return null
  const country = economy.national_place_name
  const national = country && economy.national_place_id !== economy.place_id ? ` · national figures for ${country}` : ''
  const topShare = origins?.top[0]?.share ?? 1

  return (
    <section className="card attention-panel compact economy-panel">
      <header className="attention-head">
        <div>
          <p className="eyebrow">
            Inbound travel &amp; economy · EUROCONTROL, European Commission, Eurostat{national}
          </p>
          <h3>Who is flying in, and what tourism is worth</h3>
        </div>
      </header>

      {economy.highlights.length > 0 && (
        <ul className="attention-highlights">
          {economy.highlights.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}

      <div className="attention-grid">
        {flights && (
          <div className="attention-block">
            <p className="mini-label">
              Flight arrivals <span>{periodLabel(flights.latest_period, 'long')}</span>
            </p>
            <div className="attention-stats">
              <div>
                <strong>{compactNights(flights.arrivals)}</strong>
                <span>flights landed</span>
              </div>
              <div>
                <strong className={changeTone(pct(flights.growth), 0.01)}>{signedPercent(pct(flights.growth), 1)}</strong>
                <span>vs a year earlier, same airports</span>
              </div>
              <div>
                <strong className={changeTone(pct(flights.growth_3m), 0.01)}>{signedPercent(pct(flights.growth_3m), 1)}</strong>
                <span>average of the last 3 months</span>
              </div>
            </div>
            {flights.series.length > 3 && <FlightsChart flights={flights} />}
            <p className="attention-note">
              {flights.airports
                .slice(0, 6)
                .map((airport) => `${airport.icao} ${compactNights(airport.arrivals)}`)
                .join(' · ')}
              {flights.airports.length > 6 ? ` and ${flights.airports.length - 6} more` : ''}
            </p>
          </div>
        )}

        {survey && (
          <div className="attention-block">
            <p className="mini-label">
              Hotel business survey <span>{periodLabel(survey.latest_period, 'long')}, balance of up minus down</span>
            </p>
            {survey.stale && (
              <p className="economy-stale">
                {country ?? 'This country'} last reported in {periodLabel(survey.latest_period, 'long')}; these figures are
                out of date.
              </p>
            )}
            <div className="attention-stats">
              <div>
                <strong>{signedBalance(survey.demand_expected)}</strong>
                <span>
                  expected demand, next 3 months
                  {survey.demand_expected_year_ago != null ? ` (${signedBalance(survey.demand_expected_year_ago)} a year before)` : ''}
                </span>
              </div>
              <div>
                <strong>{signedBalance(survey.demand_past)}</strong>
                <span>demand, past 3 months</span>
              </div>
              <div>
                <strong>{signedBalance(survey.prices_expected)}</strong>
                <span>price expectations</span>
              </div>
              <div>
                <strong>{signedBalance(survey.employment_expected)}</strong>
                <span>hiring expectations</span>
              </div>
            </div>
            <p className="attention-note">
              Balances are not seasonally adjusted, so compare a month with the same month a year earlier.
            </p>
          </div>
        )}

        {prices && (
          <div className="attention-block">
            <p className="mini-label">
              Prices and turnover <span>{periodLabel(prices.latest_period, 'long')}, vs a year earlier</span>
            </p>
            <div className="attention-stats">
              <div>
                <strong>{signedPercent(pct(prices.accommodation), 1)}</strong>
                <span>accommodation prices ({signedPercent(pct(prices.all_items), 1)} all prices)</span>
              </div>
              <div>
                <strong>{signedPercent(pct(prices.restaurants), 1)}</strong>
                <span>restaurants and cafés</span>
              </div>
              <div>
                <strong>{signedPercent(pct(prices.air_fares), 1)}</strong>
                <span>air fares</span>
              </div>
              {turnover && (
                <div>
                  <strong className={changeTone(pct(turnover.accommodation), 0.01)}>
                    {signedPercent(pct(turnover.accommodation), 1)}
                  </strong>
                  <span>accommodation turnover, {periodLabel(turnover.latest_period)}</span>
                </div>
              )}
            </div>
            {prices.series.length > 3 && (
              <>
                <PricesChart prices={prices} />
                <p className="attention-note economy-legend">
                  <span>
                    <i style={{ background: RISE }} />
                    Accommodation
                  </span>
                  <span>
                    <i style={{ background: MUTED }} />
                    All consumer prices
                  </span>
                  <span>annual change, %</span>
                </p>
              </>
            )}
          </div>
        )}

        {origins && origins.top.length > 0 && (
          <div className="attention-block">
            <p className="mini-label">
              Who stayed <span>share of foreign guest nights, {origins.year}</span>
            </p>
            <ul className="share-bars">
              {origins.top.map((item) => {
                const shift = item.previous_share != null ? item.share - item.previous_share : null
                return (
                  <li key={item.key}>
                    <span className="share-label" title={item.name}>
                      {item.name}
                    </span>
                    <span className="share-track">
                      <span className="share-fill origin" style={{ width: `${(item.share / topShare) * 100}%` }} />
                    </span>
                    <span className="share-value">{plainPercent(item.share)}</span>
                    <span className={`share-shift ${changeTone(shift, 0.005)}`}>
                      {shift == null ? '' : `${shift >= 0 ? '+' : '−'}${Math.abs(shift * 100).toFixed(1)} pt`}
                    </span>
                  </li>
                )
              })}
            </ul>
            <p className="attention-note">
              {origins.domestic_share != null
                ? `Residents of ${country ?? 'the country'} spent ${plainPercent(origins.domestic_share)} of all ${compactNights(origins.total_nights)} nights. `
                : ''}
              Shifts are against the previous year.
            </p>
          </div>
        )}
      </div>
    </section>
  )
}
