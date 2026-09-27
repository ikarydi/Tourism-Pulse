import type { FeatureCollection } from 'geojson'
import type { Layer } from 'leaflet'
import { useEffect, useState } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Pane, Tooltip } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { LandBasemap } from '../../features/map/LandBasemap'
import { loadShapes, REGION_RAMP } from '../../features/map/regionShapes'
import { formatValue } from '../../lib/chart'
import type { Metric, PlaceRef } from '../../types/explore'

type Point = { place: PlaceRef; value: number }

// Low -> high, the same ramp as the map page's regional layer.
const RAMP = REGION_RAMP

// Colour and size follow each place's rank, not its raw value: one
// extreme region (the Greek islands' tourism intensity) would otherwise
// squash every other place into the lowest colour band.
function colorFor(rank: number): string {
  return RAMP[Math.min(RAMP.length - 1, Math.floor(rank * RAMP.length))]
}

/** Regions or areas drawn as their own shapes, coloured by rank. */
function ShapeLayer({
  level,
  metric,
  values,
  rankOf,
}: {
  level: 2 | 3
  metric: Metric
  values: Map<number, number>
  rankOf: Map<number, number>
}) {
  const [shapes, setShapes] = useState<FeatureCollection | null>(null)
  useEffect(() => {
    let cancelled = false
    void loadShapes(level).then((data) => !cancelled && setShapes(data))
    return () => {
      cancelled = true
    }
  }, [level])
  if (!shapes) return null
  return (
    <Pane name="chart-regions" style={{ zIndex: 300 }}>
      <GeoJSON
        key={`${level}-${values.size}`}
        data={shapes}
        style={(feature) => {
          const rank = rankOf.get(feature?.properties?.place_id ?? -1)
          return {
            weight: 0.4,
            color: 'rgba(163, 196, 224, 0.3)',
            fillOpacity: rank === undefined ? 0.05 : 0.75,
            fillColor:
              rank === undefined
                ? '#13212f'
                : REGION_RAMP[Math.min(REGION_RAMP.length - 1, Math.floor(rank * REGION_RAMP.length))],
          }
        }}
        onEachFeature={(feature, layer: Layer) => {
          const value = values.get(feature.properties.place_id)
          layer.bindTooltip(
            `<strong>${feature.properties.name}</strong><br/>${value === undefined ? 'No data' : `${metric.label}: ${formatValue(metric, value)}`}`,
            { sticky: true, className: 'region-tooltip' },
          )
        }}
      />
    </Pane>
  )
}

export function MapChart({
  metric,
  values,
  places,
  height,
}: {
  metric: Metric
  values: Map<number, number>
  places: PlaceRef[]
  height: number
}) {
  const points: Point[] = []
  for (const place of places) {
    const value = values.get(place.id)
    if (value !== undefined && place.latitude !== null && place.longitude !== null) {
      points.push({ place, value })
    }
  }
  const notOnMap = [...values.keys()].filter((id) => !points.some((point) => point.place.id === id)).length
  const min = Math.min(...points.map((point) => point.value))
  const max = Math.max(...points.map((point) => point.value))
  // All regions (or all areas): draw their shapes instead of dots.
  const types = new Set(points.map((point) => point.place.place_type))
  const shapeLevel = types.size === 1 && types.has('region') ? 2 : types.size === 1 && types.has('area') ? 3 : null
  const ordered = [...points].sort((a, b) => a.value - b.value)
  const rankOf = new Map(ordered.map((point, index) => [point.place.id, points.length > 1 ? index / (points.length - 1) : 0.5]))
  const bounds = points.length
    ? ([
        [Math.min(...points.map((p) => p.place.latitude as number)), Math.min(...points.map((p) => p.place.longitude as number))],
        [Math.max(...points.map((p) => p.place.latitude as number)), Math.max(...points.map((p) => p.place.longitude as number))],
      ] as [[number, number], [number, number]])
    : undefined

  return (
    <div className="map-chart">
      <MapContainer
        center={[50, 12]}
        zoom={4}
        bounds={bounds}
        boundsOptions={{ padding: [24, 24] }}
        minZoom={3}
        maxZoom={8}
        scrollWheelZoom={false}
        style={{ height }}
        className="map-chart-canvas"
      >
        <LandBasemap />
        {shapeLevel !== null && (
          <ShapeLayer level={shapeLevel} metric={metric} values={values} rankOf={rankOf} />
        )}
        {shapeLevel === null && [...ordered].reverse().map(({ place, value }) => {
          const rank = rankOf.get(place.id) ?? 0.5
          return (
            <CircleMarker
              key={place.id}
              center={[place.latitude as number, place.longitude as number]}
              radius={4 + 10 * rank}
              pathOptions={{
                color: 'rgba(238, 244, 249, .6)',
                weight: 1,
                fillColor: colorFor(rank),
                fillOpacity: 0.85,
              }}
            >
              <Tooltip direction="top">
                <strong>{place.name}</strong>
                <br />
                {metric.label}: {formatValue(metric, value)}
              </Tooltip>
            </CircleMarker>
          )
        })}
      </MapContainer>
      <div className="map-chart-legend">
        <span>Lowest {formatValue(metric, min)}</span>
        <span className="map-chart-ramp" style={{ background: `linear-gradient(90deg, ${RAMP.join(', ')})` }} />
        <span>Highest {formatValue(metric, max)}</span>
        <span className="map-chart-note">colour and size show each place's rank</span>
        {notOnMap > 0 && <span className="map-chart-note">{notOnMap} without a map position (countries)</span>}
      </div>
    </div>
  )
}
