import { useEffect, useMemo, useState } from 'react'
import { runQuery } from '../api/explore'
import { formatPeriod, formatValue } from '../lib/chart'
import type { ExploreDraft } from '../pages/ExplorePage'
import type { Catalog, Metric, QueryResult, QuerySpec } from '../types/explore'
import type { Place } from '../types/place'
import { ExploreChart } from './charts/ExploreChart'
import './PlaceStatistics.css'

// What is worth showing for each kind of place, in reading order. Metrics
// the catalog does not have (no data loaded) are skipped.
const PLAN: Record<string, string[]> = {
  country: [
    'signal.tourism_nights',
    'signal.tourist_arrivals',
    'signal.wikipedia_views_monthly',
    'signal.gdelt_tourism_share',
    'signal.gdelt_tourism_tone',
    'signal.platform_nights_annual',
    'population',
    'observatory.str_share',
    'observatory.tourism_intensity',
  ],
  destination: [
    'signal.tourism_nights',
    'signal.wikipedia_views_monthly',
    'signal.gdelt_attention_share',
    'signal.tourism_nights_annual',
    'signal.foreign_nights_annual',
    'signal.nights_per_resident_annual',
    'signal.museum_visitors_annual',
    'observatory.str_share',
    'observatory.tourism_intensity',
  ],
  region: [
    'signal.tourism_nights',
    'signal.tourism_nights_annual',
    'signal.platform_nights_annual',
    'signal.accommodation_capacity_annual',
    'population',
    'observatory.str_share',
    'observatory.tourism_intensity',
    'observatory.tourism_density',
    'observatory.seasonality_peak_share',
  ],
  city: [
    'signal.tourism_nights_annual',
    'signal.accommodation_capacity_annual',
    'signal.nights_per_resident_annual',
    'signal.domestic_nights_annual',
    'signal.foreign_nights_annual',
    'signal.museum_visitors_annual',
    'observatory.str_share',
    'observatory.tourism_intensity',
  ],
}
PLAN.area = PLAN.region

const MONTHLY_START = '2016-01-01'
const MAX_PER_QUERY = 4

type Panel = { metric: Metric; grain: QuerySpec['grain']; result: QueryResult }

function chunks<T>(items: T[], size: number): T[][] {
  const out: T[][] = []
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size))
  return out
}

function queriesFor(place: Place, metrics: Metric[]): QuerySpec[] {
  const base = { places: [place.id], place_type: null, end: null }
  const monthly = metrics.filter((metric) => metric.grain === 'month' || metric.grain === 'day')
  const yearly = metrics.filter((metric) => metric.grain === 'year')
  return [
    ...chunks(monthly, MAX_PER_QUERY).map((group) => ({
      ...base,
      metrics: group.map((m) => m.id),
      grain: 'month' as const,
      start: MONTHLY_START,
    })),
    ...chunks(yearly, MAX_PER_QUERY).map((group) => ({
      ...base,
      metrics: group.map((m) => m.id),
      grain: 'year' as const,
      start: null,
    })),
  ]
}

function StatCard({ panel, place, onOpenExplore }: { panel: Panel; place: Place; onOpenExplore: (draft: ExploreDraft) => void }) {
  const { metric, grain, result } = panel
  const latest = result.rows[result.rows.length - 1]
  const open = () =>
    onOpenExplore({
      title: `${metric.label} · ${place.name}`,
      viewId: null,
      spec: {
        query: {
          metrics: [metric.id],
          places: [place.id],
          place_type: null,
          grain,
          start: grain === 'month' ? MONTHLY_START : null,
          end: null,
        },
        chart: { type: 'line', x: 'time', collapse: 'latest', color: 'place' },
      },
    })

  return (
    <article className="stat-card">
      <header>
        <div>
          <p className="stat-card-title">{metric.label}</p>
          <p className="stat-card-sub">
            {metric.source} · {metric.unit}
          </p>
        </div>
        <button type="button" className="icon-button" onClick={open} aria-label={`Open ${metric.label} in Explore`} title="Open in Explore">
          ↗
        </button>
      </header>
      <p className="stat-card-value">
        {formatValue(metric, latest.value)}
        <span>{formatPeriod(latest.period, grain)}</span>
      </p>
      {result.rows.length >= 2 ? (
        <ExploreChart result={result} chart={{ type: 'line', x: 'time', collapse: 'latest', color: 'place' }} grain={grain} height={150} />
      ) : (
        <p className="chart-footnote">One value so far.</p>
      )}
    </article>
  )
}

export function PlaceStatistics({
  place,
  catalog,
  onOpenExplore,
}: {
  place: Place
  catalog: Catalog | null
  onOpenExplore: (draft: ExploreDraft) => void
}) {
  const [panels, setPanels] = useState<Panel[] | null>(null)
  const metrics = useMemo(() => {
    const wanted = PLAN[place.place_type] ?? PLAN.region
    return wanted
      .map((id) => catalog?.metrics.find((metric) => metric.id === id))
      .filter((metric): metric is Metric => metric !== undefined)
  }, [catalog, place.place_type])

  useEffect(() => {
    if (!catalog) return
    let cancelled = false
    const specs = queriesFor(place, metrics)
    Promise.all(specs.map((spec) => runQuery(spec).then((result) => ({ spec, result }))))
      .then((answers) => {
        if (cancelled) return
        const found: Panel[] = []
        for (const { spec, result } of answers) {
          for (const metric of result.metrics) {
            const rows = result.rows.filter((row) => row.metric === metric.id)
            if (!rows.length) continue
            found.push({ metric, grain: spec.grain, result: { ...result, metrics: [metric], rows, notes: [] } })
          }
        }
        // Keep the plan's reading order.
        found.sort((a, b) => metrics.indexOf(a.metric) - metrics.indexOf(b.metric))
        setPanels(found)
      })
      .catch(() => !cancelled && setPanels([]))
    return () => {
      cancelled = true
    }
  }, [catalog, place, metrics])

  return (
    <section className="section-block">
      <div className="section-title">
        <div>
          <p className="eyebrow">Official statistics &amp; attention</p>
          <h2>History</h2>
        </div>
        {panels && <span>{panels.length} series</span>}
      </div>
      {!panels && (
        <div className="stat-grid">
          {[0, 1, 2].map((key) => (
            <div key={key} className="skeleton stat-skeleton" />
          ))}
        </div>
      )}
      {panels && panels.length === 0 && (
        <div className="card empty-note stat-empty">No official statistics are loaded for this place yet.</div>
      )}
      {panels && panels.length > 0 && (
        <div className="stat-grid">
          {panels.map((panel) => (
            <StatCard key={panel.metric.id} panel={panel} place={place} onOpenExplore={onOpenExplore} />
          ))}
        </div>
      )}
    </section>
  )
}
