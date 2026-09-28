import { useEffect, useState } from 'react'
import { getPlaceForecast } from '../api/forecast'
import { changeTone, compactNights, periodLabel, plainPercent, signedPercent } from '../lib/outlook'
import type { PlaceForecast } from '../types/forecast'
import { ForecastChart } from './charts/ForecastChart'
import './ForecastCard.css'

export function OutlookFigures({ forecast }: { forecast: PlaceForecast }) {
  return (
    <dl className="outlook-figures">
      {forecast.outlook.map((item) => (
        <div key={item.months}>
          <dt>Next {item.months} months vs last year</dt>
          <dd className={changeTone(item.change)}>{signedPercent(item.change, 1)}</dd>
          <span>
            {compactNights(item.forecast)} nights forecast, {compactNights(item.last_year)} a year earlier
          </span>
        </div>
      ))}
      {forecast.backtest?.mape != null && (
        <div>
          <dt>Backtest error</dt>
          <dd>{plainPercent(forecast.backtest.mape, 1)}</dd>
          <span>
            {forecast.backtest.scored} past forecasts · 80% range held {plainPercent(forecast.backtest.coverage_80)}
          </span>
        </div>
      )}
    </dl>
  )
}

/** Outlook for one place on its detail page; renders nothing without a forecast. */
export function ForecastCard({ placeId, onOpenOutlook }: { placeId: number; onOpenOutlook?: () => void }) {
  const [forecast, setForecast] = useState<PlaceForecast | null>(null)

  useEffect(() => {
    let cancelled = false
    getPlaceForecast(placeId)
      .then((data) => !cancelled && setForecast(data))
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [placeId])

  if (!forecast) return null
  return (
    <section className="card forecast-card">
      <header className="forecast-card-head">
        <div>
          <p className="eyebrow">Outlook · official nights</p>
          <h3>
            {periodLabel(forecast.points[0].period)} – {periodLabel(forecast.points[forecast.points.length - 1].period)}
          </h3>
          <p className="forecast-card-sub">
            From official data to {periodLabel(forecast.origin, 'long')}
            {forecast.validated ? ' · validated method' : ' · not yet validated at this level'}
          </p>
        </div>
        {onOpenOutlook && (
          <button type="button" className="button" onClick={onOpenOutlook}>
            Open Outlook
          </button>
        )}
      </header>
      <OutlookFigures forecast={forecast} />
      <ForecastChart forecast={forecast} height={220} />
    </section>
  )
}
