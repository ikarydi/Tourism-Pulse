import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import './App.css'
import { getPlaceAnomaly, getPlaceAttractions, getPlaceEvents, getPlaceHistory, getPlacePulse, getPlacePulseSummary, getPlaceSignals, getPlaceTrend, getPlaces, type Attraction, type Event, type Place, type Pulse, type PulseAnomaly, type PulseSnapshot, type PulseTrend, type Signal } from './api'
import { dimensions, formatChange, formatDateTime, formatObservationDate, scoreStatus } from './format'
import { Overview } from './Overview'
import { EuropeMap } from './EuropeMap'

function trendInterpretation(direction: string, momentumUnknown: boolean) {
  if (momentumUnknown) return 'Momentum cannot yet be determined'
  if (direction === 'up') return 'Tourism momentum is improving'
  if (direction === 'down') return 'Tourism momentum is weakening'
  return 'Tourism momentum is holding steady'
}

function confidenceLabel(score: number) {
  if (score < 40) return 'low'
  if (score < 70) return 'moderate'
  return 'high'
}

function HistoryChart({ history }: { history: PulseSnapshot[] }) {
  if (!history.length) return <div className="chart-empty">No historical pulse data for this place yet.</div>

  const points = [...history].reverse()
  const chartWidth = 720
  const chartHeight = 220
  const padding = { top: 18, right: 18, bottom: 34, left: 42 }
  const innerWidth = chartWidth - padding.left - padding.right
  const innerHeight = chartHeight - padding.top - padding.bottom
  const x = (index: number) => padding.left + (points.length === 1 ? innerWidth / 2 : (index / (points.length - 1)) * innerWidth)
  const y = (value: number) => padding.top + ((100 - value) / 100) * innerHeight
  const path = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${x(index)} ${y(point.pulse)}`).join(' ')
  const latest = points[points.length - 1]
  const labelStep = Math.max(1, Math.ceil(points.length / 6))

  return (
    <div className="chart-wrap">
      <svg className="history-chart" viewBox={`0 0 ${chartWidth} ${chartHeight}`} role="img" aria-label="Pulse history chart">
        {[0, 25, 50, 75, 100].map((value) => (
          <g key={value}>
            <line className="grid-line" x1={padding.left} x2={chartWidth - padding.right} y1={y(value)} y2={y(value)} />
            <text className="axis-label" x={padding.left - 10} y={y(value) + 4} textAnchor="end">{value}</text>
          </g>
        ))}
        <path className="chart-line" d={path} />
        {points.map((point, index) => <circle className={point.id === latest.id ? 'chart-point latest' : 'chart-point'} cx={x(index)} cy={y(point.pulse)} key={point.id} r={point.id === latest.id ? 5 : 3} />)}
        {points.map((point, index) => (index % labelStep === 0 || index === points.length - 1) && (
          <text className="date-label" key={point.id} x={x(index)} y={chartHeight - 8} textAnchor={index === 0 ? 'start' : index === points.length - 1 ? 'end' : 'middle'}>{formatDateTime(point.calculated_at)}</text>
        ))}
      </svg>
      <div className="chart-legend"><span className="legend-dot" /> Most recent snapshot</div>
    </div>
  )
}

function App() {
  const [view, setView] = useState<'overview' | 'map' | 'detail'>('map')
  const [places, setPlaces] = useState<Place[]>([])
  const [selectedPlaceId, setSelectedPlaceId] = useState<number | null>(null)
  const [pulse, setPulse] = useState<Pulse | null>(null)
  const [history, setHistory] = useState<PulseSnapshot[]>([])
  const [trend, setTrend] = useState<PulseTrend | null>(null)
  const [anomaly, setAnomaly] = useState<PulseAnomaly | null>(null)
  const [signals, setSignals] = useState<Signal[]>([])
  const [events, setEvents] = useState<Event[]>([])
  const [attractions, setAttractions] = useState<Attraction[]>([])
  const [nowMs, setNowMs] = useState<number | null>(null)
  const [nationalPulseEntry, setNationalPulseEntry] = useState<{ placeId: number; pulse: Pulse | null } | null>(null)
  const [loadingPlaces, setLoadingPlaces] = useState(true)
  const [loadingPulse, setLoadingPulse] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [intelligenceError, setIntelligenceError] = useState(false)
  const mapDetailRef = useRef<HTMLDivElement>(null)
  const selectedPlace = useMemo(() => places.find((place) => place.id === (selectedPlaceId ?? places[0]?.id)), [places, selectedPlaceId])
  const nationalPlace = useMemo(
    () => selectedPlace && selectedPlace.place_type !== 'country'
      ? places.find((place) => place.place_type === 'country' && place.country_code === selectedPlace.country_code) ?? null
      : null,
    [places, selectedPlace],
  )

  async function loadPlaceData(placeId: number) {
    setLoadingPulse(true)
    setError(null)
    setPulse(null)
    setTrend(null)
    setAnomaly(null)
    setSignals([])
    setEvents([])
    setAttractions([])
    setIntelligenceError(false)
    try {
      const [nextPulse, nextHistory, nextTrend, nextAnomaly, nextSignals, nextEvents, nextAttractions] = await Promise.allSettled([
        getPlacePulse(placeId),
        getPlaceHistory(placeId),
        getPlaceTrend(placeId),
        getPlaceAnomaly(placeId),
        getPlaceSignals(placeId),
        getPlaceEvents(placeId),
        getPlaceAttractions(placeId),
      ])
      if (nextPulse.status === 'rejected') {
        if (nextPulse.reason instanceof Error && nextPulse.reason.message.includes('No signals')) {
          setHistory(nextHistory.status === 'fulfilled' ? nextHistory.value : [])
          return
        }
        throw nextPulse.reason
      }
      setPulse(nextPulse.value)
      setHistory(nextHistory.status === 'fulfilled' ? nextHistory.value : [])
      setTrend(nextTrend.status === 'fulfilled' ? nextTrend.value : null)
      setAnomaly(nextAnomaly.status === 'fulfilled' ? nextAnomaly.value : null)
      setSignals(nextSignals.status === 'fulfilled' ? nextSignals.value : [])
      setEvents(nextEvents.status === 'fulfilled' ? nextEvents.value : [])
      setAttractions(nextAttractions.status === 'fulfilled' ? nextAttractions.value : [])
      setNowMs(Date.now())
      setIntelligenceError(nextTrend.status === 'rejected' || nextAnomaly.status === 'rejected')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load pulse data.')
      setHistory([])
    } finally {
      setLoadingPulse(false)
    }
  }

  useEffect(() => {
    if (!nationalPlace) return
    let cancelled = false
    const placeId = nationalPlace.id
    getPlacePulseSummary(placeId)
      .then((next) => { if (!cancelled) setNationalPulseEntry({ placeId, pulse: next }) })
      .catch(() => { if (!cancelled) setNationalPulseEntry({ placeId, pulse: null }) })
    return () => { cancelled = true }
  }, [nationalPlace])
  // Derived, not raw state: self-corrects immediately when nationalPlace
  // changes (e.g. switching between two non-Hungary cities), rather than
  // showing a stale previous country's figure until the new fetch resolves.
  const nationalPulseLoaded = nationalPlace !== null && nationalPulseEntry?.placeId === nationalPlace.id
  const nationalPulse = nationalPulseLoaded ? (nationalPulseEntry?.pulse ?? null) : null

  useEffect(() => {
    getPlaces()
      .then((availablePlaces) => {
        setPlaces(availablePlaces)
        if (availablePlaces.length) void loadPlaceData(availablePlaces[0].id)
      })
      .catch((cause) => setError(cause instanceof Error ? cause.message : 'Unable to load places.'))
      .finally(() => setLoadingPlaces(false))
  }, [])

  const title = selectedPlace ? `${selectedPlace.name}${selectedPlace.country_code ? `, ${selectedPlace.country_code}` : ''}` : 'Select a place'
  const momentumUnknown = trend?.direction === 'insufficient_data' || trend?.momentum === 'unknown'
  const trendDirection = trend?.direction ?? pulse?.trend.direction ?? 'stable'
  const trendChange = trend?.change_24h ?? pulse?.trend.change ?? 0
  const sourceLabel: Record<string, string> = { ksh: 'KSH', eurostat: 'Eurostat', 'open-meteo': 'Open-Meteo', osm: 'OpenStreetMap' }
  const sourceSignalCandidates: Partial<Record<typeof dimensions[number]['key'], { signalType: string; source: string; label: string }[]>> = {
    demand: [
      { signalType: 'tourism_nights', source: 'ksh', label: 'tourism nights' },
      { signalType: 'tourism_nights', source: 'eurostat', label: 'tourism nights' },
      { signalType: 'occupancy_rate', source: 'eurostat', label: 'occupancy rate' },
    ],
    capacity: [
      { signalType: 'accommodation_capacity', source: 'ksh', label: 'accommodation capacity' },
      { signalType: 'accommodation_capacity_annual', source: 'eurostat', label: 'accommodation capacity' },
      { signalType: 'hotel_count', source: 'osm', label: 'hotel density' },
      { signalType: 'restaurant_count', source: 'osm', label: 'restaurant density' },
    ],
    environment: [{ signalType: 'weather_comfort', source: 'open-meteo', label: 'weather comfort' }],
  }
  const dimensionSourceIndicators = Object.fromEntries(
    Object.entries(sourceSignalCandidates).map(([dimensionKey, candidates]) => [
      dimensionKey,
      (() => {
        for (const spec of candidates) {
          const matchingSignal = signals.find((signal) => signal.signal_type === spec.signalType && signal.source === spec.source)
          if (matchingSignal) return { sourceName: sourceLabel[spec.source] ?? spec.source, label: spec.label, signal: matchingSignal }
        }
        return null
      })(),
    ]),
  ) as Partial<Record<typeof dimensions[number]['key'], { sourceName: string; label: string; signal: Signal } | null>>
  const sortedSignals = [...signals].sort((a, b) => new Date(b.observed_at).getTime() - new Date(a.observed_at).getTime())
  const hotels = attractions.filter((attraction) => attraction.category === 'hotel')
  const restaurants = attractions.filter((attraction) => attraction.category === 'restaurant')
  const nextTicketmasterEvent = nowMs === null ? null : events
    .filter((event) => event.source === 'ticketmaster' && new Date(event.start_at).getTime() >= nowMs)
    .sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime())[0] ?? null
  const weakDimensions = pulse ? dimensions.filter((dimension) => pulse.dimensions[dimension.key] < 40) : []
  const missingDimensions = pulse ? dimensions.filter((dimension) => pulse.dimensions[dimension.key] === 0) : []
  const watchItems = pulse ? [
    ...missingDimensions.map((dimension) => `${dimension.label} data is missing.`),
    ...weakDimensions.filter((dimension) => pulse.dimensions[dimension.key] !== 0).map((dimension) => `${dimension.label} is below 40.`),
    ...(trendDirection === 'down' ? ['Momentum is declining.'] : []),
    ...(anomaly?.detected ? ['An unusual pulse movement was detected.'] : []),
    ...(pulse.confidence.coverage < 100 ? ['Coverage is partial, so interpret the pulse cautiously.'] : []),
  ] : []
  const summary = pulse
    ? anomaly?.detected
      ? `${trendInterpretation(trendDirection, momentumUnknown)} while confidence remains ${confidenceLabel(pulse.confidence.score)}. ${anomaly.message}`
      : momentumUnknown
        ? 'Insufficient historical data for comparison.'
        : trendDirection === 'stable'
          ? 'Current conditions are stable with no significant anomaly detected.'
          : `${trendInterpretation(trendDirection, momentumUnknown)} while confidence remains ${confidenceLabel(pulse.confidence.score)}.`
    : ''

  function handlePlaceChange(placeId: number, options?: { keepView?: boolean }) {
    setSelectedPlaceId(placeId)
    if (!options?.keepView) setView('detail')
    void loadPlaceData(placeId)
  }

  // Selecting a destination from the map shouldn't navigate away from the
  // map - the detail content loads and renders below it, on the same page.
  function handleMapPlaceChange(placeId: number) {
    handlePlaceChange(placeId, { keepView: true })
  }

  function scrollToMapDetail() {
    mapDetailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  // National-level fallback: demand and capacity both have sources that are
  // country-scoped only for most of Europe (Eurostat), so a city place with
  // no city-level source for that dimension shows 0 with no explanation
  // otherwise. Cross-links to the national figure when one exists; says so
  // plainly when it doesn't (rather than looking like a broken feature).
  function renderDimensionFootnote(dimension: typeof dimensions[number], value: number) {
    const indicator = dimensionSourceIndicators[dimension.key]
    if (indicator) return <div className="dimension-source">{indicator.sourceName} · {indicator.label} — {Math.round(indicator.signal.value * 10) / 10} {indicator.signal.unit ?? ''} ({(indicator.sourceName === 'Open-Meteo' ? formatDateTime : formatObservationDate)(indicator.signal.observed_at)})</div>
    if (dimension.key === 'events' && nextTicketmasterEvent) return <div className="dimension-source">Ticketmaster · next: {nextTicketmasterEvent.name} ({formatDateTime(nextTicketmasterEvent.start_at)})</div>
    if ((dimension.key === 'demand' || dimension.key === 'capacity') && value === 0 && nationalPlace) {
      if (!nationalPulseLoaded) return <div className="dimension-source dimension-source-pending">Checking {nationalPlace.name}'s national {dimension.label.toLowerCase()}…</div>
      const nationalValue = nationalPulse?.dimensions[dimension.key] ?? 0
      if (nationalValue > 0) return <button type="button" className="dimension-source dimension-source-link" onClick={() => handlePlaceChange(nationalPlace.id)}>No city-level {dimension.label.toLowerCase()} source yet — {nationalPlace.name} reports {Math.round(nationalValue)} nationally →</button>
      return <div className="dimension-source dimension-source-missing">No {dimension.label.toLowerCase()} data source for {nationalPlace.name} yet.</div>
    }
    return null
  }

  return (
    <main className="dashboard-shell">
      <header className="topbar"><div className="brand-lockup"><span className="brand-mark">TP</span><span>TOURISM PULSE</span></div><div className="live-indicator"><span /> Live intelligence</div></header>
      <section className="dashboard-content">
        <div className={`page-heading${view === 'map' ? ' page-heading-compact' : ''}`}><div><p className="eyebrow">DESTINATION INTELLIGENCE / {view === 'overview' ? 'ALL DESTINATIONS' : view === 'map' ? 'MAP' : 'DETAIL'}</p><h1>Tourism Pulse</h1><p className="subheading">A live read on destination momentum, readiness, and atmosphere.</p></div><div className="view-switch-row"><div className="view-tabs"><button type="button" className={view === 'overview' ? 'active' : ''} onClick={() => setView('overview')}>All destinations</button><button type="button" className={view === 'map' ? 'active' : ''} onClick={() => setView('map')}>Map</button><button type="button" className={view === 'detail' ? 'active' : ''} onClick={() => setView('detail')} disabled={!selectedPlace}>Detail</button></div>{view === 'detail' && <div className="place-control"><label htmlFor="place-select">Monitoring</label><select id="place-select" value={selectedPlace?.id ?? ''} onChange={(event) => handlePlaceChange(Number(event.target.value))} disabled={loadingPlaces || !places.length}><option value="">{loadingPlaces ? 'Loading places...' : 'No places available'}</option>{places.map((place) => <option key={place.id} value={place.id}>{place.name}{place.country_code ? ` · ${place.country_code}` : ''}{place.place_type === 'country' ? ' (national)' : ''}</option>)}</select></div>}</div></div>
        {error && <div className="state-panel error-panel"><strong>Connection issue</strong><span>{error}</span><button type="button" onClick={() => selectedPlaceId !== null && void loadPlaceData(selectedPlaceId)}>Retry</button></div>}
        {!loadingPlaces && !places.length && !error && <div className="state-panel"><strong>No places available</strong><span>Add a place in the API to begin monitoring destinations.</span></div>}
        {view === 'overview' && !!places.length && <Overview places={places} onSelectPlace={handlePlaceChange} />}
        {view === 'map' && !!places.length && <EuropeMap places={places} onSelectPlace={handleMapPlaceChange} onJumpToDetail={scrollToMapDetail} />}
        {(view === 'detail' || view === 'map') && selectedPlace && loadingPulse && <div className="state-panel loading-panel"><span className="spinner" />Loading destination intelligence...</div>}
        {(view === 'detail' || view === 'map') && !loadingPulse && selectedPlace && !pulse && !error && <div className="state-panel"><strong>No pulse data yet</strong><span>{title} does not have enough signals or events to calculate a pulse.</span><button type="button" onClick={() => void loadPlaceData(selectedPlace.id)}>Refresh data</button></div>}
        {(view === 'detail' || view === 'map') && !loadingPulse && pulse && <div ref={mapDetailRef}>
          <section className="hero-grid"><div className="pulse-hero"><div><p className="eyebrow">CURRENT PULSE / {title.toUpperCase()}</p><h2>{title}</h2></div><div className="score-row"><div className="score-number">{Math.round(pulse.pulse)}</div><div className="score-meta"><span className={`status-pill ${scoreStatus(pulse.pulse).toLowerCase()}`}>{scoreStatus(pulse.pulse)}</span><span>out of 100</span></div></div><div className="pulse-bar"><span style={{ width: `${Math.min(100, Math.max(0, pulse.pulse))}%` }} /></div><p className="hero-note">The destination is currently showing <strong>{scoreStatus(pulse.pulse).toLowerCase()} momentum</strong> across the monitored signals.</p></div><div className="trend-card"><div className="card-heading"><span className="eyebrow">MOMENTUM</span><span className={`trend-icon ${trendDirection}`}>{momentumUnknown ? '?' : trendDirection === 'up' ? '↗' : trendDirection === 'down' ? '↘' : '→'}</span></div><div className="trend-value">{formatChange(pulse.trend.change)} <small>pts</small></div><div className={`trend-label ${trendDirection}`}>{momentumUnknown ? 'Not yet determined' : trendDirection === 'up' ? 'Moving upward' : trendDirection === 'down' ? 'Cooling off' : 'Holding steady'}</div><p>{momentumUnknown ? 'Insufficient historical data for comparison.' : 'Compared with the previous calculation'}</p></div></section>
          <section className="section-block"><div className="section-title"><div><p className="eyebrow">SIGNAL MIX</p><h2>Four dimensions</h2></div><span>0 — 100 scale</span></div><div className="dimension-grid">{dimensions.map((dimension) => { const value = pulse.dimensions[dimension.key]; return <article className="dimension-card" key={dimension.key}><div className="dimension-top"><span>{dimension.label}</span><strong>{Math.round(value)}</strong></div><div className="dimension-track"><span className={dimension.tone} style={{ width: `${value}%` }} /></div><div className="dimension-foot"><span>{scoreStatus(value)}</span><span>{value.toFixed(1)} / 100</span></div>{renderDimensionFootnote(dimension, value)}</article> })}</div></section>
          <section className="section-block"><div className="section-title"><div><p className="eyebrow">EVIDENCE</p><h2>Raw signals</h2></div><span>{sortedSignals.length} recorded</span></div>{sortedSignals.length ? <div className="raw-signals-wrap"><table className="raw-signals-table"><thead><tr><th>Type</th><th>Value</th><th>Source</th><th>Observed</th></tr></thead><tbody>{sortedSignals.map((signal) => <tr key={signal.id}><td>{signal.signal_type.replace(/_/g, ' ')}</td><td>{Number(signal.value).toLocaleString()} <span className="raw-signal-unit">{signal.unit ?? ''}</span></td><td><span className="scope-badge city">{sourceLabel[signal.source] ?? signal.source}</span></td><td>{formatDateTime(signal.observed_at)}</td></tr>)}</tbody></table></div> : <p className="watch-clear">No raw signals recorded for this place yet.</p>}</section>
          <section className="section-block"><div className="section-title"><div><p className="eyebrow">NEARBY</p><h2>Hotels &amp; restaurants</h2></div><span>{attractions.length} mapped</span></div>{attractions.length ? <><div className="poi-summary-row"><div className="poi-summary-card"><strong>{hotels.length}</strong><span>hotels</span></div><div className="poi-summary-card"><strong>{restaurants.length}</strong><span>restaurants</span></div></div><div className="poi-columns"><div><p className="mini-label">Sample hotels</p><ul className="poi-list">{hotels.slice(0, 6).map((hotel) => <li key={hotel.id}>{hotel.name}</li>)}{!hotels.length && <li className="poi-list-empty">None mapped nearby.</li>}</ul></div><div><p className="mini-label">Sample restaurants</p><ul className="poi-list">{restaurants.slice(0, 6).map((restaurant) => <li key={restaurant.id}>{restaurant.name}</li>)}{!restaurants.length && <li className="poi-list-empty">None mapped nearby.</li>}</ul></div></div><p className="poi-attribution">Data © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors, ODbL.</p></> : <p className="watch-clear">No hotel or restaurant data mapped for this place yet.</p>}</section>
          <section className="middle-grid"><article className="insight-card"><div className="section-title"><div><p className="eyebrow">INTELLIGENCE / INTERPRETATION</p><h2>Readout</h2></div><span className={`quality-tag ${pulse.interpretation.data_quality}`}>{pulse.interpretation.data_quality}</span></div><h3>{pulse.interpretation.headline}</h3><div className="insight-columns"><div><p className="mini-label positive">Strengths</p><ul>{pulse.interpretation.strengths.length ? pulse.interpretation.strengths.map((item) => <li key={item}>{item}</li>) : <li>No clear strengths detected.</li>}</ul></div><div><p className="mini-label caution">Watch / weaknesses</p><ul>{pulse.interpretation.weaknesses.length ? pulse.interpretation.weaknesses.map((item) => <li key={item}>{item}</li>) : <li>No clear weaknesses detected.</li>}</ul></div></div></article><article className={`confidence-card ${pulse.confidence.coverage < 100 ? 'caution-card' : ''}`}><div className="section-title"><div><p className="eyebrow">CONFIDENCE &amp; COVERAGE</p><h2>Trust signal</h2></div></div><div className="confidence-ring" style={{ '--confidence': `${pulse.confidence.score * 3.6}deg` } as CSSProperties}><div><strong>{pulse.confidence.score.toFixed(1)}%</strong><span>confidence</span></div></div><div className="coverage-row"><span>Coverage</span><strong>{pulse.confidence.coverage.toFixed(0)}%</strong></div><div className="coverage-track"><span style={{ width: `${pulse.confidence.coverage}%` }} /></div><div className="supported-row"><span>Supported dimensions</span><strong>{Math.round((pulse.confidence.coverage / 100) * 4)} / 4</strong></div><p className="confidence-note">Confidence reflects reliability, freshness, and coverage. {pulse.confidence.coverage < 100 ? 'Partial coverage means this pulse should be interpreted cautiously.' : 'All four dimensions are currently covered.'}</p></article></section>
          <section className="section-block history-section"><div className="section-title"><div><p className="eyebrow">SIGNAL OVER TIME</p><h2>Pulse history</h2></div><button className="refresh-button" type="button" onClick={() => void loadPlaceData(selectedPlace?.id ?? 0)} aria-label="Refresh pulse data">↻ <span>Refresh</span></button></div><HistoryChart history={history} /></section>
          <section className="section-block intelligence-section"><div className="section-title"><div><p className="eyebrow">INTELLIGENCE</p><h2>What is changing now</h2></div><span>Deterministic signal analysis</span></div>{intelligenceError && <div className="intelligence-inline-error">Trend or anomaly detail is temporarily unavailable.</div>}<div className="intelligence-grid"><article className={`intelligence-card trend-intelligence ${momentumUnknown ? 'stable' : trendDirection}`}><div className="intelligence-card-heading"><span className="mini-label">TREND / MOMENTUM</span><span className="trend-symbol">{momentumUnknown ? '?' : trendDirection === 'up' ? '↗' : trendDirection === 'down' ? '↘' : '→'}</span></div><strong>{trendInterpretation(trendDirection, momentumUnknown)}</strong><div className="intelligence-metric">{formatChange(trendChange)} <small>pts</small></div><p>{momentumUnknown ? 'Insufficient historical data for comparison.' : trend ? `${trend.momentum} momentum · ${trend.change_7d === null ? 'No 7-day comparison' : `${formatChange(trend.change_7d)} pts over 7 days`}` : 'Trend detail is unavailable for this place.'}</p></article><article className={`intelligence-card anomaly-intelligence ${anomaly?.detected ? 'attention' : 'normal'}`}><div className="intelligence-card-heading"><span className="mini-label">ANOMALY</span><span className="anomaly-status">{anomaly?.detected ? 'Attention' : 'Normal'}</span></div><strong>{anomaly?.detected ? 'Unusual pulse movement detected' : 'No significant anomaly detected'}</strong><p>{anomaly ? anomaly.message : 'Anomaly detail is unavailable for this place.'}</p>{anomaly?.detected && <div className="anomaly-detail"><span>Severity: {anomaly.severity}</span>{anomaly.change !== null && <span>Change: {formatChange(anomaly.change)} pts</span>}</div>}{anomaly?.drivers.length ? <div className="driver-list">{anomaly.drivers.map((driver) => <span key={driver}>{driver}</span>)}</div> : null}</article></div><div className="intelligence-lower-grid"><article className="summary-card"><p className="eyebrow">INTELLIGENCE SUMMARY</p><h3>{summary}</h3><div className="summary-facts"><span>Pulse <strong>{pulse.pulse.toFixed(1)}</strong></span><span>Confidence <strong>{pulse.confidence.score.toFixed(1)}%</strong></span><span>Coverage <strong>{pulse.confidence.coverage.toFixed(0)}%</strong></span></div></article><article className="watch-card"><div className="section-title"><div><p className="eyebrow">ACTION / WATCH LIST</p><h2>What to watch</h2></div></div>{watchItems.length ? <ul>{watchItems.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="watch-clear">No immediate watch items from the current signals.</p>}</article></div></section>
        </div>}
      </section>
      <footer><span>TOURISM PULSE / INTELLIGENCE CONSOLE</span><span>Updated from live API data</span></footer>
    </main>
  )
}

export default App
