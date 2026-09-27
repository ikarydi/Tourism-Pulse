import { useCallback, useEffect, useMemo, useState } from 'react'
import './App.css'
import { request } from './api/client'
import { getCatalog, listViews } from './api/explore'
import { getPlaces } from './api/places'
import { CommandPalette } from './components/shell/CommandPalette'
import { NAV, type View } from './components/shell/nav'
import { Sidebar } from './components/shell/Sidebar'
import { DEFAULT_CHART, DEFAULT_QUERY } from './lib/chart'
import { DashboardPage } from './pages/DashboardPage'
import { DetailPage } from './pages/DetailPage'
import { ExplorePage, type ExploreDraft } from './pages/ExplorePage'
import { MapPage } from './pages/MapPage'
import { ObservatoryPage } from './pages/ObservatoryPage'
import { OverviewPage } from './pages/OverviewPage'
import type { Catalog, SavedView } from './types/explore'
import type { Place } from './types/place'

const HEALTH_POLL_MS = 30_000

function App() {
  const [view, setView] = useState<View>('dashboard')
  const [places, setPlaces] = useState<Place[]>([])
  const [selectedPlaceId, setSelectedPlaceId] = useState<number | null>(null)
  const [loadingPlaces, setLoadingPlaces] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [savedViews, setSavedViews] = useState<SavedView[]>([])
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [draft, setDraft] = useState<ExploreDraft | null>(null)
  // Bumped to remount Explore with a new draft, and to refresh saved views.
  const [exploreKey, setExploreKey] = useState(0)
  const [viewsVersion, setViewsVersion] = useState(0)
  const [apiOnline, setApiOnline] = useState<boolean | null>(null)
  const [checkedAt, setCheckedAt] = useState<Date | null>(null)

  useEffect(() => {
    getPlaces()
      .then((availablePlaces) => {
        setPlaces(availablePlaces)
        if (availablePlaces.length) setSelectedPlaceId(availablePlaces[0].id)
      })
      .catch((cause) => setError(cause instanceof Error ? cause.message : 'Unable to load places.'))
      .finally(() => setLoadingPlaces(false))
    getCatalog()
      .then(setCatalog)
      .catch(() => setCatalog(null))
  }, [])

  useEffect(() => {
    listViews()
      .then(setSavedViews)
      .catch(() => setSavedViews([]))
  }, [viewsVersion])

  // Live status: is the API reachable right now?
  useEffect(() => {
    const check = () =>
      request('/health')
        .then(() => setApiOnline(true))
        .catch(() => setApiOnline(false))
        .finally(() => setCheckedAt(new Date()))
    check()
    const timer = window.setInterval(check, HEALTH_POLL_MS)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setPaletteOpen((open) => !open)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const selectedPlace = useMemo(
    () => places.find((place) => place.id === selectedPlaceId) ?? null,
    [places, selectedPlaceId],
  )

  const openExplore = useCallback((next: ExploreDraft | null) => {
    setDraft(next)
    setExploreKey((key) => key + 1)
    setView('explore')
  }, [])

  const openSavedView = useCallback(
    (saved: SavedView) => openExplore({ title: saved.title, spec: saved.spec, viewId: saved.id }),
    [openExplore],
  )

  const ask = useCallback(
    (question: string) =>
      openExplore({ title: question, spec: { query: DEFAULT_QUERY, chart: DEFAULT_CHART }, viewId: null, question }),
    [openExplore],
  )

  function openPlace(placeId: number, options?: { keepView?: boolean }) {
    setSelectedPlaceId(placeId)
    if (!options?.keepView) setView('detail')
  }

  const nav = NAV.find((item) => item.view === view) ?? NAV[0]
  const title =
    view === 'detail' && selectedPlace
      ? `${selectedPlace.name}${selectedPlace.country_code ? `, ${selectedPlace.country_code}` : ''}`
      : nav.label

  return (
    <div className="app-shell">
      <Sidebar
        view={view}
        detailEnabled={Boolean(selectedPlace)}
        onNavigate={setView}
        onOpenPalette={() => setPaletteOpen(true)}
      />

      <main className="app-main">
        <header className="app-topbar">
          <div className="app-topbar-title">
            <h1>{title}</h1>
            <p>{nav.description}</p>
          </div>
          <div className="app-topbar-actions">
            {view === 'detail' && (
              <select
                className="field place-select"
                value={selectedPlace?.id ?? ''}
                onChange={(event) => openPlace(Number(event.target.value))}
                disabled={loadingPlaces || !places.length}
                aria-label="Destination"
              >
                {places.map((place) => (
                  <option key={place.id} value={place.id}>
                    {place.name}
                    {place.country_code ? ` · ${place.country_code}` : ''}
                    {place.place_type === 'country' ? ' (national)' : ''}
                  </option>
                ))}
              </select>
            )}
            <span
              className={`status-pill${apiOnline === false ? ' offline' : ''}`}
              title={checkedAt ? `Checked ${checkedAt.toLocaleTimeString()}` : undefined}
            >
              <span className={`live-dot${apiOnline === false ? ' off' : apiOnline === null ? ' busy' : ''}`} aria-hidden="true" />
              {apiOnline === false ? 'API offline' : apiOnline === null ? 'Connecting' : 'Live'}
            </span>
          </div>
        </header>

        <section className="app-content">
          {error && (
            <div className="state-panel error">
              <strong>Connection issue</strong>
              <span>{error}</span>
            </div>
          )}

          {view === 'dashboard' && (
            <DashboardPage
              catalog={catalog}
              refreshKey={viewsVersion}
              onOpenView={openSavedView}
              onNewChart={() => openExplore(null)}
              onViewsChanged={() => setViewsVersion((version) => version + 1)}
            />
          )}

          {view === 'explore' && (
            <ExplorePage
              key={exploreKey}
              catalog={catalog}
              draft={draft}
              onSaved={() => setViewsVersion((version) => version + 1)}
            />
          )}

          {loadingPlaces && view !== 'dashboard' && view !== 'explore' && (
            <div className="state-panel loading-panel">
              <span className="spinner" />
              Loading destinations...
            </div>
          )}

          {!loadingPlaces && !!places.length && view === 'destinations' && (
            <OverviewPage places={places} onSelectPlace={(placeId) => openPlace(placeId)} />
          )}

          {!loadingPlaces && !!places.length && view === 'map' && (
            <MapPage
              places={places}
              selectedPlace={selectedPlace}
              onSelectPlace={(placeId) => openPlace(placeId, { keepView: true })}
            />
          )}

          {!loadingPlaces && !!places.length && view === 'observatory' && (
            <ObservatoryPage onSelectPlace={(placeId) => openPlace(placeId)} />
          )}

          {!loadingPlaces && view === 'detail' && selectedPlace && <DetailPage place={selectedPlace} />}
        </section>
      </main>

      {paletteOpen && (
        <CommandPalette
        places={catalog?.places ?? []}
        views={savedViews}
        detailEnabled={Boolean(selectedPlace)}
        onClose={() => setPaletteOpen(false)}
        onNavigate={setView}
        onOpenPlace={(placeId) => openPlace(placeId)}
        onOpenView={openSavedView}
        onAsk={ask}
        />
      )}
    </div>
  )
}

export default App
