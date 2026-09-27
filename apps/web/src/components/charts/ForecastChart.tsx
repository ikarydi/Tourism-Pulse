import * as Plot from '@observablehq/plot'
import { useCallback } from 'react'
import { compactNights, periodDate, periodLabel } from '../../lib/outlook'
import type { PlaceForecast } from '../../types/forecast'
import { PlotFigure } from './PlotFigure'

const TEXT = '#8ea0b3'
const ACTUAL = '#5fd3e8'
const FORECAST = '#e8c26a'
const LAST_YEAR = 'rgba(163, 196, 224, 0.55)'
const TIP = { fill: '#101e2e', stroke: 'rgba(163, 196, 224, 0.3)' }

/** Official nights, then the forecast with 80% and 95% ranges and last
 * year's figures for the same months. */
export function ForecastChart({ forecast, height = 300 }: { forecast: PlaceForecast; height?: number }) {
  const build = useCallback(
    (width: number) => {
      const history = forecast.history.map((row) => ({ date: periodDate(row.period), value: row.value }))
      const last = forecast.history[forecast.history.length - 1]
      // Join the forecast line to the last actual so there is no gap.
      const anchor = last
        ? [{ date: periodDate(last.period), point: last.value, low_80: last.value, high_80: last.value, low_95: last.value, high_95: last.value }]
        : []
      const points = forecast.points.map((row) => ({ ...row, date: periodDate(row.period) }))
      const band = [...anchor, ...points]
      const lastYear = points.filter((row) => row.last_year != null)
      return Plot.plot({
        width,
        height,
        marginLeft: 52,
        marginRight: 12,
        marginTop: 14,
        style: { background: 'transparent', color: TEXT, fontSize: '11px', overflow: 'visible' },
        x: { type: 'utc', label: null },
        y: { grid: true, label: null, tickFormat: (value: number) => compactNights(value), nice: true },
        marks: [
          Plot.areaY(band, { x: 'date', y1: 'low_95', y2: 'high_95', fill: FORECAST, fillOpacity: 0.1, curve: 'monotone-x' }),
          Plot.areaY(band, { x: 'date', y1: 'low_80', y2: 'high_80', fill: FORECAST, fillOpacity: 0.2, curve: 'monotone-x' }),
          Plot.lineY(lastYear, {
            x: 'date',
            y: 'last_year',
            stroke: LAST_YEAR,
            strokeDasharray: '2,3',
            strokeWidth: 1.2,
            curve: 'monotone-x',
          }),
          Plot.lineY(history, { x: 'date', y: 'value', stroke: ACTUAL, strokeWidth: 1.8, curve: 'monotone-x' }),
          Plot.lineY(band, { x: 'date', y: 'point', stroke: FORECAST, strokeWidth: 1.8, strokeDasharray: '5,3', curve: 'monotone-x' }),
          Plot.dot(points, { x: 'date', y: 'point', r: 2.2, fill: FORECAST }),
          last ? Plot.ruleX([periodDate(last.period)], { stroke: 'rgba(163, 196, 224, 0.35)', strokeDasharray: '1,3' }) : null,
          Plot.tip(
            points,
            Plot.pointerX({
              x: 'date',
              y: 'point',
              ...TIP,
              title: (row: (typeof points)[number]) =>
                [
                  `${periodLabel(row.period, 'long')} (${row.horizon} month${row.horizon > 1 ? 's' : ''} ahead)`,
                  `Forecast ${compactNights(row.point)}`,
                  `80% range ${compactNights(row.low_80)} – ${compactNights(row.high_80)}`,
                  row.last_year != null ? `Last year ${compactNights(row.last_year)}` : '',
                ]
                  .filter(Boolean)
                  .join('\n'),
            }),
          ),
          Plot.tip(
            history,
            Plot.pointerX({
              x: 'date',
              y: 'value',
              ...TIP,
              title: (row: { date: Date; value: number }) =>
                `${row.date.toLocaleDateString('en', { month: 'long', year: 'numeric', timeZone: 'UTC' })}\nOfficial ${compactNights(row.value)}`,
            }),
          ),
        ],
      })
    },
    [forecast, height],
  )
  return (
    <div className="forecast-chart">
      <PlotFigure build={build} />
      <div className="forecast-legend" aria-hidden="true">
        <span><i className="swatch actual" /> Official</span>
        <span><i className="swatch forecast" /> Forecast</span>
        <span><i className="swatch band" /> 80% / 95% range</span>
        <span><i className="swatch last-year" /> Same month last year</span>
      </div>
    </div>
  )
}
