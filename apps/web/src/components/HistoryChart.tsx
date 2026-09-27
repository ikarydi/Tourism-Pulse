import { useState } from 'react'
import { DIMENSIONS } from '../lib/dimensions'
import { formatDateTime } from '../lib/format'
import type { DimensionKey, PulseSnapshot } from '../types/pulse'
import './HistoryChart.css'

const CHART_WIDTH = 760
const CHART_HEIGHT = 220
const PADDING = { top: 18, right: 18, bottom: 34, left: 42 }
const INNER_WIDTH = CHART_WIDTH - PADDING.left - PADDING.right
const INNER_HEIGHT = CHART_HEIGHT - PADDING.top - PADDING.bottom
// Rough width of one "Aug 22, 2:17 PM" label in viewBox units.
const DATE_LABEL_WIDTH = 90

type SeriesKey = 'pulse' | DimensionKey

export function HistoryChart({ history }: { history: PulseSnapshot[] }) {
  const [series, setSeries] = useState<SeriesKey>('pulse')

  if (!history.length) {
    return <div className="chart-empty">No historical pulse data for this place yet.</div>
  }

  const points = [...history].reverse()
  const x = (index: number) =>
    PADDING.left + (points.length === 1 ? INNER_WIDTH / 2 : (index / (points.length - 1)) * INNER_WIDTH)
  const y = (value: number) => PADDING.top + ((100 - value) / 100) * INNER_HEIGHT
  const valueOf = (point: PulseSnapshot) => point[series]
  const path = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${x(index)} ${y(valueOf(point))}`).join(' ')
  const latest = points[points.length - 1]
  const labelStep = Math.max(1, Math.ceil(points.length / 6))
  const color = series === 'pulse' ? 'var(--accent)' : DIMENSIONS.find((d) => d.key === series)?.color

  return (
    <div>
      <div className="history-series-picker" role="tablist" aria-label="Choose a series">
        <button type="button" className={series === 'pulse' ? 'active' : ''} onClick={() => setSeries('pulse')}>
          Pulse
        </button>
        {DIMENSIONS.map((dimension) => (
          <button
            key={dimension.key}
            type="button"
            className={series === dimension.key ? 'active' : ''}
            onClick={() => setSeries(dimension.key)}
          >
            {dimension.short}
          </button>
        ))}
      </div>
      <div className="chart-wrap">
        <svg className="history-chart" viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} role="img" aria-label="Pulse history chart">
          {[0, 25, 50, 75, 100].map((value) => (
            <g key={value}>
              <line className="grid-line" x1={PADDING.left} x2={CHART_WIDTH - PADDING.right} y1={y(value)} y2={y(value)} />
              <text className="axis-label" x={PADDING.left - 10} y={y(value) + 4} textAnchor="end">
                {value}
              </text>
            </g>
          ))}
          <path className="chart-line" d={path} style={{ stroke: color }} />
          {points.map((point, index) => (
            <circle
              key={point.id}
              className={point.id === latest.id ? 'chart-point latest' : 'chart-point'}
              cx={x(index)}
              cy={y(valueOf(point))}
              r={point.id === latest.id ? 5 : 3}
              style={{ stroke: color, fill: point.id === latest.id ? color : undefined }}
            />
          ))}
          {points.map(
            (point, index) =>
              // The last point is always labelled (right-aligned); drop a stepped
              // label close enough to run into it.
              ((index % labelStep === 0 && x(points.length - 1) - x(index) >= DATE_LABEL_WIDTH * 1.5) ||
                index === points.length - 1) && (
                <text
                  className="date-label"
                  key={point.id}
                  x={x(index)}
                  y={CHART_HEIGHT - 8}
                  textAnchor={index === 0 ? 'start' : index === points.length - 1 ? 'end' : 'middle'}
                >
                  {formatDateTime(point.calculated_at)}
                </text>
              ),
          )}
        </svg>
      </div>
    </div>
  )
}
