import { useEffect, useState } from 'react'
import { CircleMarker, MapContainer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { getPlacePulseSummary } from '../../api/pulse'
import { DIMENSIONS } from '../../lib/dimensions'
import { formatChange, scoreStatus } from '../../lib/format'
import type { Place } from '../../types/place'
import type { Pulse } from '../../types/pulse'
import './EuropeMap.css'
import { getObservatoryRanking } from '../../api/observatory'
import type { ObservatoryRanking } from '../../types/observatory'
import { LandBasemap } from './LandBasemap'
import { RegionLayer } from './RegionLayer'
import { loadShapes, REGION_MEASURES, REGION_RAMP, type RegionMeasure } from './regionShapes'

// Centered/zoomed to frame continental Europe at a glance.
const EUROPE_CENTER: [number, number] = [52.5, 14]
const EUROPE_ZOOM = 4
// The outline basemap is 1:50m; past this zoom its coastlines look coarse.
const MAX_ZOOM = 8

type LocatedPlace = Place & { latitude: number; longitude: number }

function isLocated(place: Place): place is LocatedPlace {
  return typeof place.latitude === 'number' && typeof place.longitude === 'number'
}

// Colors follow the same trend semantics used everywhere else in the app
// (status-good/status-bad/status-warn), so a user who has seen one
// recognizes the other. CSS custom properties resolve fine when assigned
// via Leaflet's inline path styles.
function trendColor(pulse: Pulse | null | undefined): string {
  if (!pulse) return 'var(--text-faint)'
  if (pulse.trend.direction === 'up') return 'var(--status-good)'
  if (pulse.trend.direction === 'down') return 'var(--status-bad)'
  return 'var(--status-warn)'
}

function trendArrow(pulse: Pulse | null | undefined): string {
  if (!pulse) return '?'
  if (pulse.trend.direction === 'up') return '↗'
  if (pulse.trend.direction === 'down') return '↘'
  return '→'
}

// Bubble-map sizing: stronger destinations read as visually heavier,
// scaled down for country-level points so they don't dominate the city
// markers they sit alongside.
function markerRadius(pulse: Pulse | null | undefined, isCountry: boolean): number {
  const base = isCountry ? 3.5 : 6
  const boost = isCountry ? 5 : 9
  if (!pulse) return base
  return base + (Math.max(0, Math.min(100, pulse.pulse)) / 100) * boost
}

function MapInfoPanel({
  place,
  pulse,
  loading,
  onClose,
  onJumpToDetail,
}: {
  place: Place
  pulse: Pulse | null
  loading: boolean
  onClose: () => void
  onJumpToDetail: () => void
}) {
  return (
    <div className="map-info-panel">
      <button type="button" className="map-info-close" onClick={onClose} aria-label="Close">
        ×
      </button>
      <p className="eyebrow">Selected destination</p>
      <div className="map-info-heading">
        <h3>{place.name}</h3>
        <span className={`scope-badge ${place.place_type === 'country' ? 'national' : 'city'}`}>
          {place.place_type === 'country' ? 'National' : 'City'}
        </span>
      </div>
      {loading && (
        <div className="map-info-loading">
          <span className="spinner" />
          Loading pulse...
        </div>
      )}
      {!loading && !pulse && <p className="map-info-empty">No pulse data available for this destination yet.</p>}
      {!loading && pulse && (
        <>
          <div className="map-info-score-row">
            <div className="map-info-score">
              <strong>{Math.round(pulse.pulse)}</strong>
              <span className={`badge badge-${scoreStatus(pulse.pulse) === 'Strong' ? 'good' : scoreStatus(pulse.pulse) === 'Moderate' ? 'warn' : 'bad'}`}>
                {scoreStatus(pulse.pulse)}
              </span>
            </div>
            <div className={`map-info-trend ${pulse.trend.direction}`}>
              <span className="trend-symbol">{trendArrow(pulse)}</span>
              <span>{formatChange(pulse.trend.change)} pts</span>
            </div>
            <div className="map-info-confidence">
              <strong>{Math.round(pulse.confidence.coverage)}%</strong>
              <span>coverage</span>
            </div>
          </div>
          <div className="map-info-dimensions">
            {DIMENSIONS.map((dimension) => {
              const value = pulse.dimensions[dimension.key]
              return (
                <div className="map-info-dimension" key={dimension.key}>
                  <span>{dimension.short}</span>
                  <div className="dimension-row-track">
                    <span
                      className="dimension-row-fill"
                      style={{ width: `${value}%`, background: dimension.color }}
                    />
                  </div>
                  <strong>{value === 0 ? '—' : Math.round(value)}</strong>
                </div>
              )
            })}
          </div>
          <button type="button" className="map-info-detail-link" onClick={onJumpToDetail}>
            Open destination page &rarr;
          </button>
        </>
      )}
    </div>
  )
}

type Mover = { place: LocatedPlace; pulse: Pulse }

function TrendingPanel({ movers, onSelect }: { movers: { up: Mover[]; down: Mover[] }; onSelect: (placeId: number) => void }) {
  if (!movers.up.length && !movers.down.length) return null

  return (
    <div className="map-trending-panel">
      <p className="eyebrow">Trending now</p>
      <div className="map-trending-columns">
        <div>
          <p className="mini-label positive">Rising</p>
          <ul>
            {movers.up.map(({ place, pulse }) => (
              <li key={place.id}>
                <button type="button" onClick={() => onSelect(place.id)}>
                  <span className="map-trending-dot up" />
                  {place.name}
                  <strong>{formatChange(pulse.trend.change)}</strong>
                </button>
              </li>
            ))}
            {!movers.up.length && <li className="map-trending-empty">No risers right now.</li>}
          </ul>
        </div>
        <div>
          <p className="mini-label caution">Falling</p>
          <ul>
            {movers.down.map(({ place, pulse }) => (
              <li key={place.id}>
                <button type="button" onClick={() => onSelect(place.id)}>
                  <span className="map-trending-dot down" />
                  {place.name}
                  <strong>{formatChange(pulse.trend.change)}</strong>
                </button>
              </li>
            ))}
            {!movers.down.length && <li className="map-trending-empty">No fallers right now.</li>}
          </ul>
        </div>
      </div>
    </div>
  )
}

export function EuropeMap({
  places,
  onSelectPlace,
  onOpenPlace,
}: {
  places: Place[]
  onSelectPlace: (placeId: number) => void
  // Navigate to a place's page (markers' info panel, clicked regions).
  onOpenPlace: (placeId: number) => void
}) {
  const located = places.filter(isLocated)
  const unlocated = places.filter((place) => !isLocated(place) && place.place_type !== 'country').length

  const [pulses, setPulses] = useState<Record<number, Pulse | null>>({})
  const [pulsesLoading, setPulsesLoading] = useState(located.length > 0)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [measure, setMeasure] = useState<RegionMeasure | 'off'>('score')
  const [level, setLevel] = useState<2 | 3>(2)
  const [ranking, setRanking] = useState<ObservatoryRanking[] | null>(null)

  // The regional layer's values: one bulk ranking of every place.
  useEffect(() => {
    if (measure === 'off' || ranking) return
    let cancelled = false
    // Fetch the shapes alongside the values, not after them.
    void loadShapes(level)
    getObservatoryRanking()
      .then((rows) => !cancelled && setRanking(rows))
      .catch(() => !cancelled && setRanking([]))
    return () => {
      cancelled = true
    }
  }, [measure, ranking, level])

  // The regional layer goes first: it is the bulk of the map, and ~90 Pulse
  // calculations sharing the API with it would hold it back for seconds.
  const regionsSettled = measure === 'off' || ranking !== null

  useEffect(() => {
    if (!located.length || !regionsSettled) return

    let cancelled = false

    async function loadPulses() {
      setPulsesLoading(true)
      const entries = await Promise.all(
        located.map(async (place): Promise<[number, Pulse | null]> => {
          try {
            return [place.id, await getPlacePulseSummary(place.id)]
          } catch {
            return [place.id, null]
          }
        }),
      )
      if (!cancelled) {
        setPulses(Object.fromEntries(entries))
        setPulsesLoading(false)
      }
    }

    void loadPulses()

    return () => {
      cancelled = true
    }
    // Depends on `places` (the real input), not the `located` array derived
    // from it each render - `located` is recomputed fresh from `places` on
    // every run of this effect, so there's no stale-closure risk here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [places, regionsSettled])

  const selectedPlace = located.find((place) => place.id === selectedId) ?? null

  const movedPlaces: Mover[] = located.flatMap((place) => {
    const pulse = pulses[place.id]
    return pulse ? [{ place, pulse }] : []
  })
  const risers = [...movedPlaces].filter((mover) => mover.pulse.trend.change > 0).sort((a, b) => b.pulse.trend.change - a.pulse.trend.change).slice(0, 3)
  const fallers = [...movedPlaces].filter((mover) => mover.pulse.trend.change < 0).sort((a, b) => a.pulse.trend.change - b.pulse.trend.change).slice(0, 3)

  return (
    <div className="map-wrap">
      <div className="map-viewport">
        <div className="map-frame">
          {selectedPlace && (
            <MapInfoPanel
              place={selectedPlace}
              pulse={pulses[selectedPlace.id] ?? null}
              loading={pulsesLoading && !(selectedPlace.id in pulses)}
              onClose={() => setSelectedId(null)}
              onJumpToDetail={() => onOpenPlace(selectedPlace.id)}
            />
          )}
          <TrendingPanel
            movers={{ up: risers, down: fallers }}
            onSelect={(placeId) => {
              setSelectedId(placeId)
              onSelectPlace(placeId)
            }}
          />
          <div className="map-layer-panel">
            <label htmlFor="map-layer-measure" className="mini-label">
              Regions coloured by
            </label>
            <select
              id="map-layer-measure"
              className="field"
              value={measure}
              onChange={(event) => setMeasure(event.target.value as RegionMeasure | 'off')}
            >
              {REGION_MEASURES.map((item) => (
                <option key={item.key} value={item.key}>
                  {item.label}
                </option>
              ))}
              <option value="off">Nothing (markers only)</option>
            </select>
            {measure !== 'off' && (
              <>
                <div className="segmented" role="radiogroup" aria-label="Region level">
                  {([2, 3] as const).map((value) => (
                    <button
                      key={value}
                      type="button"
                      role="radio"
                      aria-checked={level === value}
                      className={level === value ? 'active' : ''}
                      onClick={() => setLevel(value)}
                    >
                      {value === 2 ? 'NUTS 2 regions' : 'NUTS 3 areas'}
                    </button>
                  ))}
                </div>
                <div className="map-layer-legend">
                  <span>Lower</span>
                  <span className="map-layer-ramp" style={{ background: `linear-gradient(90deg, ${REGION_RAMP.join(', ')})` }} />
                  <span>Higher</span>
                </div>
                <p className="map-layer-note">
                  {ranking ? 'Percentile among European regions at the same level. Click a region to open it.' : 'Loading regions...'}
                </p>
              </>
            )}
          </div>
          <div className="map-legend">
            <span>
              <i style={{ background: 'var(--status-good)' }} /> Trending up
            </span>
            <span>
              <i style={{ background: 'var(--status-bad)' }} /> Trending down
            </span>
            <span>
              <i style={{ background: 'var(--status-warn)' }} /> Stable
            </span>
            <span>
              <i style={{ background: 'var(--text-faint)' }} /> No data yet
            </span>
          </div>
          <MapContainer
            center={EUROPE_CENTER}
            zoom={EUROPE_ZOOM}
            minZoom={3}
            maxZoom={MAX_ZOOM}
            scrollWheelZoom
            className="europe-map"
          >
            <LandBasemap />
            {measure !== 'off' && ranking && (
              <RegionLayer level={level} measure={measure} ranking={ranking} onSelect={onOpenPlace} />
            )}
            {located.map((place) => {
              const pulse = pulses[place.id] ?? null
              const isCountry = place.place_type === 'country'
              return (
                <CircleMarker
                  key={place.id}
                  center={[place.latitude, place.longitude]}
                  radius={markerRadius(pulse, isCountry)}
                  pathOptions={{
                    // A bright ring + trend-colored fill reads as a clean
                    // dot regardless of what's underneath (dark land vs.
                    // darker water), rather than a flat blob that can blend
                    // into the basemap.
                    color: place.id === selectedId ? 'var(--text)' : 'rgba(238, 244, 249, .55)',
                    fillColor: trendColor(pulse),
                    fillOpacity: place.id === selectedId ? 0.95 : 0.8,
                    weight: place.id === selectedId ? 2.5 : 1.5,
                  }}
                  eventHandlers={{
                    click: () => {
                      setSelectedId(place.id)
                      onSelectPlace(place.id)
                    },
                  }}
                />
              )
            })}
          </MapContainer>
        </div>
      </div>
      <p className="map-footnote">
        Markers are curated destinations and countries: size shows Pulse strength, colour its trend. Regions show
        official Eurostat indicators.
        {unlocated > 0 && ` ${unlocated} destination${unlocated === 1 ? '' : 's'} not yet located.`}
      </p>
    </div>
  )
}
