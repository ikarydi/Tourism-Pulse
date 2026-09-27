import type { FeatureCollection } from 'geojson'
import type { Layer, PathOptions } from 'leaflet'
import { useEffect, useMemo, useState } from 'react'
import { GeoJSON, Pane } from 'react-leaflet'
import { formatIndicatorValue, ordinal } from '../../lib/observatory'
import type { ObservatoryRanking } from '../../types/observatory'
import { loadShapes, REGION_RAMP, type RegionMeasure } from './regionShapes'

type Reading = { percentile: number; label: string; detail: string }

function readingFor(row: ObservatoryRanking, measure: RegionMeasure): Reading | null {
  if (measure === 'score') {
    return row.score === null
      ? null
      : { percentile: row.score, label: `Pressure ${row.score.toFixed(0)}`, detail: `${row.level} pressure` }
  }
  const indicator = row.indicators.find((item) => item.indicator === measure)
  if (!indicator) return null
  return {
    percentile: indicator.percentile,
    label: formatIndicatorValue(indicator, 'short'),
    detail: `${ordinal(indicator.percentile)} percentile · ${indicator.year}`,
  }
}

/** NUTS 2 or NUTS 3 regions coloured by their European percentile on a measure. */
export function RegionLayer({
  level,
  measure,
  ranking,
  onSelect,
}: {
  level: 2 | 3
  measure: RegionMeasure
  ranking: ObservatoryRanking[]
  onSelect: (placeId: number) => void
}) {
  const [collection, setCollection] = useState<FeatureCollection | null>(null)

  useEffect(() => {
    let cancelled = false
    void loadShapes(level).then((data) => {
      if (!cancelled) setCollection(data)
    })
    return () => {
      cancelled = true
    }
  }, [level])

  const readings = useMemo(() => {
    const map = new Map<number, Reading>()
    for (const row of ranking) {
      const reading = readingFor(row, measure)
      if (reading) map.set(row.place_id, reading)
    }
    return map
  }, [ranking, measure])

  if (!collection) return null

  const style = (feature?: { properties?: { place_id?: number } }): PathOptions => {
    const reading = readings.get(feature?.properties?.place_id ?? -1)
    return {
      className: 'region-shape',
      weight: 0.5,
      color: 'rgba(163, 196, 224, 0.35)',
      fillOpacity: reading ? 0.72 : 0.08,
      fillColor: reading
        ? REGION_RAMP[Math.min(REGION_RAMP.length - 1, Math.floor((reading.percentile / 100) * REGION_RAMP.length))]
        : '#13212f',
    }
  }

  const onEachFeature = (feature: { properties: { place_id: number; name: string } }, layer: Layer) => {
    const reading = readings.get(feature.properties.place_id)
    layer.bindTooltip(
      `<strong>${feature.properties.name}</strong><br/>${reading ? `${reading.label}<br/><span>${reading.detail}</span>` : 'No data'}`,
      { sticky: true, className: 'region-tooltip' },
    )
    layer.on('click', () => onSelect(feature.properties.place_id))
  }

  // Between the land basemap (250) and the destination markers (overlay, 400).
  return (
    <Pane name="regions" style={{ zIndex: 300 }}>
      <GeoJSON
        key={`${level}-${measure}-${readings.size}`}
        data={collection}
        style={style as never}
        onEachFeature={onEachFeature as never}
      />
    </Pane>
  )
}
