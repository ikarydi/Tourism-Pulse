import { useCallback, useEffect, useState } from 'react'
import { createView, deleteView, listViews, runQuery, updateView } from '../api/explore'
import { ExploreChart } from '../components/charts/ExploreChart'
import { formatPeriod, xForType } from '../lib/chart'
import type { Catalog, ChartSpec, QueryResult, QuerySpec, SavedView, ViewSpec } from '../types/explore'
import './DashboardPage.css'

const REFRESH_MS = 60_000

function relative(from: Date, now: number): string {
  const seconds = Math.max(0, Math.round((now - from.getTime()) / 1000))
  if (seconds < 10) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.round(seconds / 60)
  return minutes < 60 ? `${minutes} min ago` : `${Math.round(minutes / 60)} h ago`
}

function starter(
  title: string,
  query: Partial<QuerySpec> & Pick<QuerySpec, 'metrics'>,
  chart: Partial<ChartSpec> & Pick<ChartSpec, 'type'>,
): { title: string; spec: ViewSpec } {
  return {
    title,
    spec: {
      query: { places: null, place_type: 'destination', grain: 'year', start: null, end: null, ...query },
      chart: { x: xForType(chart.type), collapse: 'latest', color: null, ...chart },
    },
  }
}

function starterViews(catalog: Catalog): { title: string; spec: ViewSpec }[] {
  const idOf = (name: string) => catalog.places.find((place) => place.name === name)?.id
  const hungary = ['Budapest', 'Balaton', 'Debrecen'].map(idOf).filter((id): id is number => id !== undefined)
  const views = [
    starter(
      'Short-term rental share vs tourism pressure',
      { metrics: ['observatory.str_share', 'observatory.pressure_score'] },
      { type: 'scatter' },
    ),
    starter('Tourism pressure score by city', { metrics: ['observatory.pressure_score'] }, { type: 'bar' }),
    starter('Tourism intensity across Europe', { metrics: ['observatory.tourism_intensity'] }, { type: 'map' }),
  ]
  if (hungary.length) {
    if (catalog.metrics.some((metric) => metric.id === 'signal.tourism_nights')) {
      views.splice(
        1,
        0,
        starter(
          'Monthly tourism nights · Hungary',
          { metrics: ['signal.tourism_nights'], places: hungary, place_type: null, grain: 'month', start: '2023-01-01' },
          { type: 'line', color: 'place' },
        ),
      )
    }
    // Four sources side by side: what "combining data" looks like.
    views.splice(
      views.length - 1,
      0,
      starter(
        'Hungary at a glance · official pressure indicators',
        {
          metrics: [
            'observatory.tourism_intensity',
            'observatory.tourism_density',
            'observatory.str_share',
            'observatory.pressure_score',
          ],
          places: hungary,
          place_type: null,
        },
        { type: 'table' },
      ),
    )
  }
  return views
}

function ChartCard({
  view,
  live,
  now,
  isFirst,
  isLast,
  onOpen,
  onMove,
  onRemove,
}: {
  view: SavedView
  live: boolean
  now: number
  isFirst: boolean
  isLast: boolean
  onOpen: () => void
  onMove: (direction: -1 | 1) => void
  onRemove: () => void
}) {
  const [result, setResult] = useState<QueryResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)
  const [confirming, setConfirming] = useState(false)

  const load = useCallback(
    () =>
      runQuery(view.spec.query)
        .then((data) => {
          setResult(data)
          setError(null)
          setUpdatedAt(new Date())
        })
        .catch((cause) => setError(cause instanceof Error ? cause.message : 'Query failed'))
        .finally(() => setRefreshing(false)),
    [view.spec.query],
  )

  useEffect(() => {
    void load()
  }, [load])

  // Live mode: refresh quietly in the background, keeping the old chart
  // on screen instead of flashing a loader.
  useEffect(() => {
    if (!live) return
    const timer = window.setInterval(() => {
      setRefreshing(true)
      void load()
    }, REFRESH_MS)
    return () => window.clearInterval(timer)
  }, [live, load])

  const wide = view.spec.chart.type === 'map' || view.spec.chart.type === 'heatmap'

  return (
    <article className={`dash-card${wide ? ' wide' : ''}`}>
      <header className="dash-card-head">
        <button type="button" className="dash-card-title" onClick={onOpen} title="Open in Explore">
          {view.title}
        </button>
        <div className="dash-card-actions">
          {confirming ? (
            <>
              <span className="dash-confirm">Remove this chart?</span>
              <button type="button" className="button danger" onClick={onRemove}>
                Remove
              </button>
              <button type="button" className="button ghost" onClick={() => setConfirming(false)}>
                Keep
              </button>
            </>
          ) : (
            <>
              <button type="button" className="icon-button" onClick={() => onMove(-1)} disabled={isFirst} aria-label="Move earlier">
                ↑
              </button>
              <button type="button" className="icon-button" onClick={() => onMove(1)} disabled={isLast} aria-label="Move later">
                ↓
              </button>
              <button type="button" className="icon-button" onClick={onOpen} aria-label="Edit in Explore">
                ✎
              </button>
              <button type="button" className="icon-button" onClick={() => setConfirming(true)} aria-label="Remove from dashboard">
                ×
              </button>
            </>
          )}
        </div>
      </header>

      <div className="dash-card-body">
        {error && <div className="state-panel error">{error}</div>}
        {!error && !result && <div className="skeleton dash-skeleton" />}
        {!error && result && <ExploreChart result={result} chart={view.spec.chart} grain={view.spec.query.grain} height={260} maxBars={12} />}
      </div>

      <footer className="dash-card-foot">
        <span className={`live-dot${refreshing ? ' busy' : live ? '' : ' off'}`} aria-hidden="true" />
        <span>
          {result?.data_through ? `Data through ${formatPeriod(result.data_through, view.spec.query.grain)}` : 'Current values'}
        </span>
        <span>{updatedAt ? `Updated ${relative(updatedAt, now)}` : 'Loading'}</span>
      </footer>
    </article>
  )
}

export function DashboardPage({
  catalog,
  refreshKey,
  onOpenView,
  onNewChart,
  onViewsChanged,
}: {
  catalog: Catalog | null
  refreshKey: number
  onOpenView: (view: SavedView) => void
  onNewChart: () => void
  onViewsChanged: () => void
}) {
  const [views, setViews] = useState<SavedView[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [live, setLive] = useState(true)
  const [now, setNow] = useState(() => Date.now())
  const [seeding, setSeeding] = useState(false)

  const reload = useCallback(() => {
    listViews()
      .then((data) => {
        setViews(data.filter((view) => view.pinned))
        setError(null)
      })
      .catch((cause) => setError(cause instanceof Error ? cause.message : 'Could not load the dashboard.'))
  }, [])

  useEffect(() => {
    reload()
  }, [reload, refreshKey])

  // In live mode, also pick up charts saved or removed in other tabs.
  useEffect(() => {
    if (!live) return
    const timer = window.setInterval(reload, REFRESH_MS)
    return () => window.clearInterval(timer)
  }, [live, reload])

  // One shared clock for every card's "updated x ago".
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 5000)
    return () => window.clearInterval(timer)
  }, [])

  async function seed() {
    if (!catalog) return
    setSeeding(true)
    try {
      // Another tab (or person) may have filled the dashboard since this
      // one last looked: only seed a dashboard that is still empty.
      const current = await listViews()
      if (!current.some((view) => view.pinned)) {
        for (const starter of starterViews(catalog)) await createView(starter.title, starter.spec)
      }
      onViewsChanged()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not add the starter charts.')
    } finally {
      setSeeding(false)
    }
  }

  async function move(index: number, direction: -1 | 1) {
    if (!views) return
    const other = views[index + direction]
    const current = views[index]
    if (!other) return
    await Promise.all([
      updateView(current.id, { position: other.position }),
      updateView(other.id, { position: current.position }),
    ])
    onViewsChanged()
  }

  async function remove(view: SavedView) {
    await deleteView(view.id)
    onViewsChanged()
  }

  return (
    <div className="dashboard">
      <div className="dashboard-toolbar">
        <p>
          Press <kbd>Ctrl</kbd> <kbd>K</kbd> to search or ask a question from anywhere.
        </p>
        <div className="dashboard-toolbar-actions">
          <label className="live-switch">
            <input type="checkbox" checked={live} onChange={(event) => setLive(event.target.checked)} />
            <span className={`live-dot${live ? '' : ' off'}`} aria-hidden="true" />
            Live refresh
          </label>
          <button type="button" className="button primary" onClick={onNewChart}>
            New chart
          </button>
        </div>
      </div>

      {error && <div className="state-panel error">{error}</div>}
      {!views && !error && (
        <div className="dash-grid">
          <div className="skeleton dash-skeleton" />
          <div className="skeleton dash-skeleton" />
        </div>
      )}

      {views && views.length === 0 && (
        <div className="dashboard-empty">
          <strong>Your dashboard is empty</strong>
          <span>Combine any stored data into your own charts, or start from a few useful ones.</span>
          <div className="dashboard-empty-actions">
            <button type="button" className="button primary" onClick={() => void seed()} disabled={seeding || !catalog}>
              {seeding ? 'Adding...' : 'Add starter charts'}
            </button>
            <button type="button" className="button" onClick={onNewChart}>
              Build a chart
            </button>
          </div>
        </div>
      )}

      {views && views.length > 0 && (
        <div className="dash-grid">
          {views.map((view, index) => (
            <ChartCard
              key={`${view.id}-${view.updated_at}`}
              view={view}
              live={live}
              now={now}
              isFirst={index === 0}
              isLast={index === views.length - 1}
              onOpen={() => onOpenView(view)}
              onMove={(direction) => void move(index, direction)}
              onRemove={() => void remove(view)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
