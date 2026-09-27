import { useEffect, useMemo, useState } from 'react'
import { askQuestion, createView, runQuery, updateView } from '../api/explore'
import { ExploreChart } from '../components/charts/ExploreChart'
import { PlacePicker } from '../components/explore/PlacePicker'
import {
  availableTypes,
  CHART_TYPES,
  DEFAULT_CHART,
  DEFAULT_QUERY,
  defaultCollapse,
  formatPeriod,
  GROUP_ORDER,
  recommendChart,
  xForType,
} from '../lib/chart'
import type { Catalog, ChartSpec, ChartType, Collapse, QueryResult, QuerySpec, ViewSpec } from '../types/explore'
import './ExplorePage.css'

export type ExploreDraft = { title: string; spec: ViewSpec; viewId: number | null; question?: string }

const MAX_METRICS = 4

const COLLAPSE_LABELS: Record<Collapse, string> = {
  latest: 'Latest value',
  avg: 'Average',
  sum: 'Total',
  max: 'Highest',
  min: 'Lowest',
}

const EXAMPLE_QUESTIONS = [
  'How does short-term rental share relate to tourism pressure across cities?',
  'Monthly tourism nights in Budapest, Balaton and Debrecen since 2023',
  'Which cities have the highest tourism intensity?',
]

export function ExplorePage({
  catalog,
  draft,
  onSaved,
}: {
  catalog: Catalog | null
  draft: ExploreDraft | null
  onSaved: () => void
}) {
  const [title, setTitle] = useState(draft?.title ?? 'Untitled chart')
  const [query, setQuery] = useState<QuerySpec>(draft?.spec.query ?? DEFAULT_QUERY)
  const [chart, setChart] = useState<ChartSpec>(draft?.spec.chart ?? DEFAULT_CHART)
  // Once the user picks a chart type we stop suggesting one.
  const [chartTouched, setChartTouched] = useState(Boolean(draft))
  const [viewId, setViewId] = useState<number | null>(draft?.viewId ?? null)
  const [result, setResult] = useState<QueryResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [question, setQuestion] = useState(draft?.question ?? '')
  const [asking, setAsking] = useState(false)
  const [askNote, setAskNote] = useState<string | null>(null)
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)

  const metrics = useMemo(
    () => query.metrics.map((id) => catalog?.metrics.find((metric) => metric.id === id)).filter((m) => m !== undefined),
    [catalog, query.metrics],
  )
  const placeCount = useMemo(() => {
    if (!catalog) return 0
    if (query.places) return query.places.length
    return catalog.places.filter((place) =>
      query.place_type === 'country'
        ? place.place_type === 'country'
        : query.place_type === 'destination'
          ? place.place_type !== 'country'
          : true,
    ).length
  }, [catalog, query.places, query.place_type])
  const suggestion = useMemo(() => recommendChart(metrics, placeCount), [metrics, placeCount])
  const shownChart = chartTouched ? chart : suggestion
  const types = availableTypes(metrics)

  // Re-run the query shortly after the selection settles.
  const queryKey = JSON.stringify(query)
  useEffect(() => {
    if (!query.metrics.length || (query.places && !query.places.length)) {
      setResult(null)
      return
    }
    let cancelled = false
    const timer = window.setTimeout(() => {
      setLoading(true)
      setError(null)
      runQuery(query)
        .then((data) => {
          if (cancelled) return
          setResult(data)
          setUpdatedAt(new Date())
        })
        .catch((cause) => !cancelled && setError(cause instanceof Error ? cause.message : 'Query failed'))
        .finally(() => !cancelled && setLoading(false))
    }, 250)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
    // queryKey captures every field of `query`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryKey])

  function toggleMetric(id: string) {
    setSaveState('idle')
    setQuery((current) => {
      if (current.metrics.includes(id)) return { ...current, metrics: current.metrics.filter((m) => m !== id) }
      if (current.metrics.length >= MAX_METRICS) return current
      return { ...current, metrics: [...current.metrics, id] }
    })
  }

  function pickType(type: ChartType) {
    setChartTouched(true)
    setSaveState('idle')
    const collapse = chartTouched ? shownChart.collapse : defaultCollapse(metrics)
    setChart({ ...shownChart, type, x: xForType(type), collapse })
  }

  async function handleAsk(text: string) {
    const trimmed = text.trim()
    if (trimmed.length < 3) return
    setAsking(true)
    setAskNote(null)
    try {
      const answer = await askQuestion(trimmed)
      setTitle(answer.title)
      setQuery(answer.spec.query)
      setChart(answer.spec.chart)
      setChartTouched(true)
      setViewId(null)
      setSaveState('idle')
      setAskNote(answer.explanation)
    } catch (cause) {
      setAskNote(cause instanceof Error ? cause.message : 'Could not answer that question.')
    } finally {
      setAsking(false)
    }
  }

  // Run a question handed over from the command palette once.
  useEffect(() => {
    if (draft?.question) void handleAsk(draft.question)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function save(pinned: boolean) {
    setSaveState('saving')
    const spec: ViewSpec = { query, chart: shownChart }
    try {
      if (viewId !== null) await updateView(viewId, { title, spec, pinned })
      else setViewId((await createView(title, spec)).id)
      setSaveState('saved')
      onSaved()
    } catch {
      setSaveState('error')
    }
  }

  function reset() {
    setTitle('Untitled chart')
    setQuery(DEFAULT_QUERY)
    setChart(DEFAULT_CHART)
    setChartTouched(false)
    setViewId(null)
    setAskNote(null)
    setSaveState('idle')
  }

  const groups = useMemo(() => {
    const needle = search.trim().toLowerCase()
    const map = new Map<string, NonNullable<Catalog>['metrics']>()
    for (const metric of catalog?.metrics ?? []) {
      if (needle && !`${metric.label} ${metric.group} ${metric.description}`.toLowerCase().includes(needle)) continue
      map.set(metric.group, [...(map.get(metric.group) ?? []), metric])
    }
    const rank = (group: string) => (GROUP_ORDER.includes(group) ? GROUP_ORDER.indexOf(group) : GROUP_ORDER.length)
    return [...map].sort(([a], [b]) => rank(a) - rank(b))
  }, [catalog, search])

  if (!catalog) {
    return (
      <div className="state-panel loading-panel">
        <span className="spinner" />
        Loading the data catalog...
      </div>
    )
  }

  return (
    <div className="explore">
      <form
        className="ask-bar"
        onSubmit={(event) => {
          event.preventDefault()
          void handleAsk(question)
        }}
      >
        <span className="ask-icon" aria-hidden="true">✦</span>
        <input
          id="explore-ask"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask a question about the data, e.g. “Which cities have the highest tourism intensity?”"
          aria-label="Ask a question about the data"
        />
        <button type="submit" className="button primary" disabled={asking || question.trim().length < 3}>
          {asking ? 'Thinking...' : 'Ask'}
        </button>
      </form>
      {askNote && <p className="ask-note">{askNote}</p>}

      <div className="explore-grid">
        <aside className="explore-panel data-panel" aria-label="Data">
          <p className="panel-heading">
            Data <span>{query.metrics.length}/{MAX_METRICS} selected</span>
          </p>
          <input
            className="field"
            type="search"
            placeholder="Search metrics"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            aria-label="Search metrics"
          />
          <div className="metric-groups">
            {groups.map(([group, items]) => (
              <section key={group} className="metric-group">
                <p className="metric-group-title">{group}</p>
                <ul>
                  {items.map((metric) => {
                    const active = query.metrics.includes(metric.id)
                    const full = !active && query.metrics.length >= MAX_METRICS
                    return (
                      <li key={metric.id}>
                        <button
                          type="button"
                          className={`metric-item${active ? ' active' : ''}`}
                          onClick={() => toggleMetric(metric.id)}
                          disabled={full}
                          title={metric.description}
                          aria-pressed={active}
                        >
                          <span className="metric-check" aria-hidden="true">{active ? '✓' : '+'}</span>
                          <span className="metric-label">{metric.label}</span>
                          <span className="metric-meta">{metric.grain === 'static' ? 'now' : metric.grain}</span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </section>
            ))}
          </div>
        </aside>

        <section className="explore-panel canvas-panel" aria-label="Chart">
          <div className="canvas-head">
            <input
              className="title-input"
              value={title}
              onChange={(event) => {
                setTitle(event.target.value)
                setSaveState('idle')
              }}
              aria-label="Chart title"
            />
            <div className="canvas-actions">
              <button type="button" className="button ghost" onClick={reset}>
                New
              </button>
              <button
                type="button"
                className="button primary"
                onClick={() => void save(true)}
                disabled={!query.metrics.length || saveState === 'saving'}
              >
                {saveState === 'saving'
                  ? 'Saving...'
                  : saveState === 'saved'
                    ? 'Saved to dashboard'
                    : viewId !== null
                      ? 'Update dashboard chart'
                      : 'Save to dashboard'}
              </button>
            </div>
          </div>
          {saveState === 'error' && <p className="form-error">Could not save the chart. Check that the API is running.</p>}

          {metrics.length > 0 && (
            <div className="type-bar" role="radiogroup" aria-label="Chart type">
              {CHART_TYPES.filter((item) => types.includes(item.type)).map((item) => (
                <button
                  key={item.type}
                  type="button"
                  role="radio"
                  aria-checked={shownChart.type === item.type}
                  className={shownChart.type === item.type ? 'active' : ''}
                  onClick={() => pickType(item.type)}
                  title={item.hint}
                >
                  {item.label}
                  {item.type === suggestion.type && <span className="suggested" title="Suggested for this data" />}
                </button>
              ))}
            </div>
          )}

          <div className="canvas-body">
            {!metrics.length && (
              <div className="canvas-empty">
                <strong>Pick up to four metrics on the left, or ask a question above.</strong>
                <span>Metrics from different sources combine on the same places and dates.</span>
                <div className="example-questions">
                  {EXAMPLE_QUESTIONS.map((example) => (
                    <button
                      key={example}
                      type="button"
                      className="chip"
                      onClick={() => {
                        setQuestion(example)
                        void handleAsk(example)
                      }}
                    >
                      {example}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {metrics.length > 0 && error && <div className="state-panel error">{error}</div>}
            {metrics.length > 0 && !error && !result && <div className="skeleton chart-skeleton" />}
            {metrics.length > 0 && !error && result && (
              <div className={loading ? 'is-refreshing' : ''}>
                <ExploreChart result={result} chart={shownChart} grain={query.grain} />
              </div>
            )}
          </div>

          {result && (
            <p className="freshness">
              <span className={`live-dot${loading ? ' busy' : ''}`} aria-hidden="true" />
              {result.data_through ? `Data through ${formatPeriod(result.data_through, query.grain)}` : 'Current values'} ·{' '}
              {result.places.length} places · {result.rows.length.toLocaleString()} values
              {updatedAt && ` · updated ${updatedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
            </p>
          )}
        </section>

        <aside className="explore-panel settings-panel" aria-label="Settings">
          <p className="panel-heading">Places</p>
          <PlacePicker
            places={catalog.places}
            query={query}
            onChange={(changes) => {
              setSaveState('idle')
              setQuery((current) => ({ ...current, ...changes }))
            }}
          />

          <p className="panel-heading">Time</p>
          <label className="setting">
            <span>Group by</span>
            <select
              className="field"
              value={query.grain}
              onChange={(event) => setQuery((current) => ({ ...current, grain: event.target.value as QuerySpec['grain'] }))}
            >
              <option value="day">Day</option>
              <option value="month">Month</option>
              <option value="year">Year</option>
            </select>
          </label>
          <label className="setting">
            <span>From</span>
            <input
              className="field"
              type="month"
              value={query.start?.slice(0, 7) ?? ''}
              onChange={(event) =>
                setQuery((current) => ({ ...current, start: event.target.value ? `${event.target.value}-01` : null }))
              }
            />
          </label>
          <label className="setting">
            <span>To</span>
            <input
              className="field"
              type="month"
              value={query.end?.slice(0, 7) ?? ''}
              onChange={(event) =>
                setQuery((current) => ({ ...current, end: event.target.value ? `${event.target.value}-01` : null }))
              }
            />
          </label>

          {shownChart.x === 'place' && (
            <>
              <p className="panel-heading">Per place</p>
              <label className="setting">
                <span>Value shown</span>
                <select
                  className="field"
                  value={shownChart.collapse}
                  onChange={(event) => {
                    setChartTouched(true)
                    setChart({ ...shownChart, collapse: event.target.value as Collapse })
                  }}
                >
                  {Object.entries(COLLAPSE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}

          {metrics.length > 0 && (
            <>
              <p className="panel-heading">Selected metrics</p>
              <ul className="selected-metrics">
                {metrics.map((metric) => (
                  <li key={metric.id}>
                    <strong>{metric.label}</strong>
                    <span>
                      {metric.unit} · {metric.source} · {metric.grain === 'static' ? 'current' : `per ${metric.grain}`}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </aside>
      </div>
    </div>
  )
}
