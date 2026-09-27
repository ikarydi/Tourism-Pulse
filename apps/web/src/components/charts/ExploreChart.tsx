import * as Plot from '@observablehq/plot'
import { useCallback, useMemo } from 'react'
import {
  axisLabel,
  collapseRows,
  formatPeriod,
  formatValue,
  labelMargin,
  pearson,
  placeName,
  SERIES_COLORS,
  wantsLog,
} from '../../lib/chart'
import type { ChartSpec, Metric, QueryResult } from '../../types/explore'
import { MapChart } from './MapChart'
import { PlotFigure } from './PlotFigure'
import './ExploreChart.css'

const TEXT = '#8ea0b3'
const LABEL_CHARS = 32

// Category labels past the margin are shortened; tooltips keep the full name.
const shortLabel = (label: string) => (label.length > LABEL_CHARS ? `${label.slice(0, LABEL_CHARS - 1)}…` : label)
const TIP = { fill: '#101e2e', stroke: 'rgba(163, 196, 224, 0.3)' }
const STYLE = {
  background: 'transparent',
  color: TEXT,
  fontSize: '11px',
  fontFamily: "'Inter', 'Helvetica Neue', sans-serif",
  overflow: 'visible',
}

function tickFormat(metric: Metric) {
  return metric.unit.startsWith('share') ? '.0%' : '~s'
}

function Panel({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="chart-panel">
      {title && <p className="chart-panel-title">{title}</p>}
      {children}
    </div>
  )
}

function LineChart({ result, metric, height }: { result: QueryResult; metric: Metric; height: number }) {
  const build = useCallback(
    (width: number) => {
      const data = result.rows
        .filter((row) => row.metric === metric.id && row.period)
        .map((row) => ({
          date: new Date(`${row.period}T00:00:00Z`),
          value: row.value,
          place: placeName(result.places, row.place_id),
        }))
      const names = [...new Set(data.map((d) => d.place))]
      return Plot.plot({
        width,
        height,
        style: STYLE,
        marginLeft: 56,
        marginRight: 16,
        // Sparkline-sized cards already name the metric in their header.
        marginTop: height < 200 ? 10 : undefined,
        x: { type: 'utc', label: null },
        y: { grid: true, label: height < 200 ? null : axisLabel(metric), tickFormat: tickFormat(metric) },
        color: { domain: names, range: SERIES_COLORS, legend: names.length > 1 },
        marks: [
          Plot.lineY(data, { x: 'date', y: 'value', stroke: 'place', strokeWidth: 2, curve: 'monotone-x' }),
          Plot.dot(data, { x: 'date', y: 'value', fill: 'place', r: 2.5 }),
          Plot.tip(
            data,
            Plot.pointerX({
              x: 'date',
              y: 'value',
              ...TIP,
              title: (d: { place: string; date: Date; value: number }) =>
                `${d.place}\n${d.date.toISOString().slice(0, 10)}\n${formatValue(metric, d.value)}`,
            }),
          ),
        ],
      })
    },
    [result, metric, height],
  )
  return <PlotFigure build={build} />
}

const HEATMAP_ROWS = 40

function Heatmap({ result, metric, grain }: { result: QueryResult; metric: Metric; grain: string }) {
  const latest = useMemo(() => collapseRows(result.rows, 'latest').get(metric.id) ?? new Map<number, number>(), [result, metric])
  const build = useCallback(
    (width: number) => {
      // Many places: keep the rows with the highest latest values.
      const keep = new Set(
        [...latest].sort((a, b) => b[1] - a[1]).slice(0, HEATMAP_ROWS).map(([placeId]) => placeId),
      )
      const rows = result.rows.filter((row) => row.metric === metric.id && row.period && keep.has(row.place_id))
      const periods = [...new Set(rows.map((row) => row.period as string))].sort()
      const labels = periods.map((period) => formatPeriod(period, grain))
      const data = rows.map((row) => ({
        period: formatPeriod(row.period, grain),
        place: placeName(result.places, row.place_id),
        value: row.value,
      }))
      const places = [...new Set(data.map((d) => d.place))].sort()
      const step = Math.max(1, Math.ceil(labels.length / Math.max(4, Math.floor(width / 70))))
      return Plot.plot({
        width,
        height: Math.max(160, places.length * 16 + 70),
        style: STYLE,
        marginLeft: labelMargin(places),
        marginBottom: 40,
        padding: 0.06,
        x: { domain: labels, label: null, tickFormat: (d: string, i: number) => (i % step ? '' : d) },
        y: { domain: places, label: null, tickFormat: shortLabel },
        color: { scheme: 'plasma', legend: true, label: axisLabel(metric), tickFormat: tickFormat(metric) },
        marks: [
          Plot.cell(data, {
            x: 'period',
            y: 'place',
            fill: 'value',
            tip: { ...TIP, format: { fill: (v: number) => formatValue(metric, v) } },
          }),
        ],
      })
    },
    [result, metric, grain, latest],
  )
  return (
    <>
      <PlotFigure build={build} />
      {latest.size > HEATMAP_ROWS && (
        <p className="chart-footnote">
          Top {HEATMAP_ROWS} of {latest.size} places by latest value.
        </p>
      )}
    </>
  )
}

function BarChart({
  result,
  metric,
  chart,
  maxBars,
  seeAll = 'Open the chart to see all.',
}: {
  result: QueryResult
  metric: Metric
  chart: ChartSpec
  maxBars?: number
  seeAll?: string
}) {
  const values = collapseRows(result.rows, chart.collapse).get(metric.id) ?? new Map<number, number>()
  const total = values.size
  const build = useCallback(
    (width: number) => {
      const values = collapseRows(result.rows, chart.collapse).get(metric.id) ?? new Map()
      const data = [...values]
        .map(([placeId, value]) => ({ place: placeName(result.places, placeId), value }))
        .sort((a, b) => b.value - a.value)
        .slice(0, maxBars ?? Infinity)
      return Plot.plot({
        width,
        height: Math.max(140, data.length * 18 + 50),
        style: STYLE,
        marginLeft: labelMargin(data.map((d) => d.place)),
        marginRight: 56,
        x: { grid: true, label: axisLabel(metric), tickFormat: tickFormat(metric) },
        y: { label: null, tickFormat: shortLabel },
        marks: [
          Plot.barX(data, {
            x: 'value',
            y: 'place',
            sort: { y: '-x' },
            fill: '#5fd3e8',
            fillOpacity: 0.85,
            title: (d: { place: string; value: number }) => `${d.place}: ${formatValue(metric, d.value)}`,
          }),
          Plot.text(data, {
            x: 'value',
            y: 'place',
            text: (d: { value: number }) => formatValue(metric, d.value),
            dx: 4,
            textAnchor: 'start',
            fill: TEXT,
          }),
          Plot.ruleX([0], { stroke: 'rgba(163, 196, 224, 0.3)' }),
        ],
      })
    },
    [result, metric, chart.collapse, maxBars],
  )
  return (
    <>
      <PlotFigure build={build} />
      {maxBars !== undefined && total > maxBars && (
        <p className="chart-footnote">
          Top {maxBars} of {total} places. {seeAll}
        </p>
      )}
    </>
  )
}

function ScatterChart({ result, chart, height }: { result: QueryResult; chart: ChartSpec; height: number }) {
  // Memoized as one unit so the figure is only rebuilt when the data changes.
  const scatter = useMemo(() => {
    const [xMetric, yMetric, sizeMetric] = result.metrics
    const collapsed = collapseRows(result.rows, chart.collapse)
    const xs = collapsed.get(xMetric.id) ?? new Map<number, number>()
    const ys = collapsed.get(yMetric.id) ?? new Map<number, number>()
    const sizes = sizeMetric ? collapsed.get(sizeMetric.id) : undefined
    const points = [...xs]
      .filter(([placeId]) => ys.has(placeId))
      .map(([placeId, x]) => ({
        place: placeName(result.places, placeId),
        x,
        y: ys.get(placeId) as number,
        size: sizes?.get(placeId),
      }))
    const logX = wantsLog(points.map((point) => point.x))
    const logY = wantsLog(points.map((point) => point.y))
    return { xMetric, yMetric, sizeMetric, points, logX, logY }
  }, [result, chart.collapse])
  const { xMetric, yMetric, sizeMetric, points, logX, logY } = scatter
  // On a log axis, correlate the logs: raw values would let the one
  // extreme place that triggered the log scale dominate r.
  const r = pearson(
    points.map((p) => (logX ? Math.log(p.x) : p.x)),
    points.map((p) => (logY ? Math.log(p.y) : p.y)),
  )

  const build = useCallback(
    (width: number) => {
      const { xMetric, yMetric, sizeMetric, points, logX, logY } = scatter
      return Plot.plot({
        width,
        height,
        style: STYLE,
        marginLeft: 60,
        grid: true,
        x: { label: axisLabel(xMetric), tickFormat: tickFormat(xMetric), type: logX ? 'log' : 'linear' },
        y: { label: axisLabel(yMetric), tickFormat: tickFormat(yMetric), type: logY ? 'log' : 'linear' },
        r: { range: [3, 14] },
        marks: [
          points.length >= 3 && !logX && !logY
            ? Plot.linearRegressionY(points, { x: 'x', y: 'y', stroke: TEXT, strokeOpacity: 0.6, fill: TEXT, fillOpacity: 0.06 })
            : null,
          Plot.dot(points, {
            x: 'x',
            y: 'y',
            r: sizeMetric ? 'size' : 5,
            fill: '#5fd3e8',
            fillOpacity: 0.8,
            stroke: '#05090f',
          }),
          points.length <= 30
            ? Plot.text(points, { x: 'x', y: 'y', text: 'place', dy: -10, fill: TEXT, fontSize: 10 })
            : null,
          Plot.tip(
            points,
            Plot.pointer({
              x: 'x',
              y: 'y',
              ...TIP,
              title: (d: { place: string; x: number; y: number; size?: number }) =>
                [
                  d.place,
                  `${xMetric.label}: ${formatValue(xMetric, d.x)}`,
                  `${yMetric.label}: ${formatValue(yMetric, d.y)}`,
                  sizeMetric && d.size !== undefined ? `${sizeMetric.label}: ${formatValue(sizeMetric, d.size)}` : '',
                ]
                  .filter(Boolean)
                  .join('\n'),
            }),
          ),
        ],
      })
    },
    [scatter, height],
  )

  return (
    <>
      <PlotFigure build={build} />
      <p className="chart-footnote">
        {points.length} places with both values
        {r !== null && ` · correlation r = ${r.toFixed(2)}${logX || logY ? ' (of logs)' : ''}`}
        {sizeMetric && ` · dot size: ${sizeMetric.label}`}
        {(logX || logY) &&
          ` · log scale on ${[logX && xMetric.label, logY && yMetric.label].filter(Boolean).join(' and ')} (values span 100× or more)`}
      </p>
    </>
  )
}

const TABLE_ROWS = 200

function DataTable({ result, chart }: { result: QueryResult; chart: ChartSpec }) {
  const collapsed = collapseRows(result.rows, chart.collapse)
  const placeIds = [...new Set(result.rows.map((row) => row.place_id))]
  const first = result.metrics[0]
  placeIds.sort((a, b) => (collapsed.get(first.id)?.get(b) ?? -Infinity) - (collapsed.get(first.id)?.get(a) ?? -Infinity))
  const shown = placeIds.slice(0, TABLE_ROWS)
  return (
    <div className="chart-table-wrap">
      <table className="chart-table">
        <thead>
          <tr>
            <th>Place</th>
            {result.metrics.map((metric) => (
              <th key={metric.id}>
                {metric.label}
                <span>{metric.unit}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((placeId) => (
            <tr key={placeId}>
              <td>{placeName(result.places, placeId)}</td>
              {result.metrics.map((metric) => {
                const value = collapsed.get(metric.id)?.get(placeId)
                return <td key={metric.id}>{value === undefined ? '—' : formatValue(metric, value)}</td>
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {placeIds.length > TABLE_ROWS && (
        <p className="chart-footnote">
          First {TABLE_ROWS} of {placeIds.length} places, by {first.label}.
        </p>
      )}
    </div>
  )
}

export function ExploreChart({
  result,
  chart,
  grain,
  height = 320,
  maxBars,
}: {
  result: QueryResult
  chart: ChartSpec
  grain: string
  height?: number
  // Compact views (dashboard cards) show only the top bars.
  maxBars?: number
}) {
  if (!result.rows.length) {
    return <div className="chart-empty">No data for this selection. Try other places or a wider date range.</div>
  }

  const timed = result.metrics.filter((metric) => metric.grain !== 'static')
  const staticOnly = result.metrics.filter((metric) => metric.grain === 'static')
  const small = result.metrics.length > 1

  let body: React.ReactNode
  if (chart.type === 'scatter' && result.metrics.length >= 2) {
    body = <ScatterChart result={result} chart={chart} height={height} />
  } else if (chart.type === 'table') {
    body = <DataTable result={result} chart={chart} />
  } else if (chart.type === 'map') {
    const metric = result.metrics[0]
    body = (
      <MapChart
        metric={metric}
        values={collapseRows(result.rows, chart.collapse).get(metric.id) ?? new Map()}
        places={result.places}
        height={height + 60}
      />
    )
  } else if (chart.type === 'bar' || (chart.type === 'scatter' && result.metrics.length < 2)) {
    body = result.metrics.map((metric) => (
      <Panel key={metric.id} title={small ? metric.label : undefined}>
        <BarChart
          result={result}
          metric={metric}
          chart={chart}
          maxBars={maxBars ?? 40}
          seeAll={maxBars === undefined ? 'Switch to Map or Table to see more.' : undefined}
        />
      </Panel>
    ))
  } else {
    body = (
      <>
        {timed.map((metric) => (
          <Panel key={metric.id} title={small ? metric.label : undefined}>
            {chart.type === 'heatmap' ? (
              <Heatmap result={result} metric={metric} grain={grain} />
            ) : (
              <LineChart result={result} metric={metric} height={small ? Math.max(200, height * 0.7) : height} />
            )}
          </Panel>
        ))}
        {staticOnly.length > 0 && (
          <p className="chart-footnote">
            {staticOnly.map((metric) => metric.label).join(', ')} has no time axis; use a bar, scatter, map or table.
          </p>
        )}
      </>
    )
  }

  return (
    <div className="explore-chart">
      {body}
      {result.notes.map((note) => (
        <p key={note} className="chart-footnote chart-note">
          {note}
        </p>
      ))}
      {result.truncated && <p className="chart-footnote chart-note">Result truncated at 20,000 rows; narrow the selection.</p>}
    </div>
  )
}
