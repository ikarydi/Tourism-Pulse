import { useEffect, useMemo, useState } from 'react'
import './App.css'
import { getPlaces } from './api/places'
import { DetailPage } from './pages/DetailPage'
import { MapPage } from './pages/MapPage'
import { OverviewPage } from './pages/OverviewPage'
import type { Place } from './types/place'

type View = 'overview' | 'map' | 'detail'

function App() {
  const [view, setView] = useState<View>('map')
  const [places, setPlaces] = useState<Place[]>([])
  const [selectedPlaceId, setSelectedPlaceId] = useState<number | null>(null)
  const [loadingPlaces, setLoadingPlaces] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getPlaces()
      .then((availablePlaces) => {
        setPlaces(availablePlaces)
        if (availablePlaces.length) setSelectedPlaceId(availablePlaces[0].id)
      })
      .catch((cause) => setError(cause instanceof Error ? cause.message : 'Unable to load places.'))
      .finally(() => setLoadingPlaces(false))
  }, [])

  const selectedPlace = useMemo(
    () => places.find((place) => place.id === selectedPlaceId) ?? null,
    [places, selectedPlaceId],
  )

  function handlePlaceChange(placeId: number, options?: { keepView?: boolean }) {
    setSelectedPlaceId(placeId)
    if (!options?.keepView) setView('detail')
  }

  const title = selectedPlace ? `${selectedPlace.name}${selectedPlace.country_code ? `, ${selectedPlace.country_code}` : ''}` : 'Select a place'

  return (
    <main className="dashboard-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="brand-mark">TP</span>
          <span>Tourism Pulse</span>
        </div>
        <div className="live-indicator">
          <span /> Live intelligence
        </div>
      </header>

      <section className="dashboard-content">
        <div className={`page-heading${view === 'map' ? ' page-heading-compact' : ''}`}>
          <div>
            <p className="eyebrow">
              Destination intelligence / {view === 'overview' ? 'All destinations' : view === 'map' ? 'Map' : 'Detail'}
            </p>
            <h1>Tourism Pulse</h1>
            <p className="subheading">
              A live, AI-narrated read on destination demand, capacity, events, environment, risk, and economics.
            </p>
          </div>

          <div className="view-switch-row">
            <div className="view-tabs">
              <button type="button" className={view === 'overview' ? 'active' : ''} onClick={() => setView('overview')}>
                All destinations
              </button>
              <button type="button" className={view === 'map' ? 'active' : ''} onClick={() => setView('map')}>
                Map
              </button>
              <button
                type="button"
                className={view === 'detail' ? 'active' : ''}
                onClick={() => setView('detail')}
                disabled={!selectedPlace}
              >
                Detail
              </button>
            </div>
            {view === 'detail' && (
              <div className="place-control">
                <label htmlFor="place-select">Monitoring</label>
                <select
                  id="place-select"
                  value={selectedPlace?.id ?? ''}
                  onChange={(event) => handlePlaceChange(Number(event.target.value))}
                  disabled={loadingPlaces || !places.length}
                >
                  <option value="">{loadingPlaces ? 'Loading places...' : 'No places available'}</option>
                  {places.map((place) => (
                    <option key={place.id} value={place.id}>
                      {place.name}
                      {place.country_code ? ` · ${place.country_code}` : ''}
                      {place.place_type === 'country' ? ' (national)' : ''}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>

        {error && (
          <div className="state-panel error">
            <strong>Connection issue</strong>
            <span>{error}</span>
          </div>
        )}

        {!loadingPlaces && !places.length && !error && (
          <div className="state-panel">
            <strong>No places available</strong>
            <span>Add a place in the API to begin monitoring destinations.</span>
          </div>
        )}

        {loadingPlaces && (
          <div className="state-panel loading-panel">
            <span className="spinner" />
            Loading destinations...
          </div>
        )}

        {!loadingPlaces && !!places.length && view === 'overview' && (
          <OverviewPage places={places} onSelectPlace={(placeId) => handlePlaceChange(placeId)} />
        )}

        {!loadingPlaces && !!places.length && view === 'map' && (
          <MapPage
            places={places}
            selectedPlace={selectedPlace}
            onSelectPlace={(placeId) => handlePlaceChange(placeId, { keepView: true })}
          />
        )}

        {!loadingPlaces && view === 'detail' && selectedPlace && (
          <>
            <p className="detail-place-title">{title}</p>
            <DetailPage place={selectedPlace} />
          </>
        )}
      </section>

      <footer>
        <span>Tourism Pulse / Intelligence console</span>
        <span>Updated from live API data</span>
      </footer>
    </main>
  )
}

export default App
