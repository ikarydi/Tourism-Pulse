import type { FeatureCollection } from 'geojson'
import { useEffect, useState } from 'react'
import { GeoJSON, Pane } from 'react-leaflet'

// Keyless basemap: Natural Earth land outlines (public domain), built by
// scripts/build_basemap.py and served from public/. CARTO's free tiles
// started returning an "API key required" watermark, and these maps never
// needed more than dark land on dark sea - their markers carry the data.
const BASEMAP_URL = '/basemap/europe-land.geojson'

let cached: Promise<FeatureCollection | null> | null = null

function loadLand(): Promise<FeatureCollection | null> {
  cached ??= fetch(BASEMAP_URL)
    .then((response) => (response.ok ? (response.json() as Promise<FeatureCollection>) : null))
    .catch(() => null)
  return cached
}

export function LandBasemap() {
  const [land, setLand] = useState<FeatureCollection | null>(null)

  useEffect(() => {
    let cancelled = false
    void loadLand().then((data) => {
      if (!cancelled) setLand(data)
    })
    return () => {
      cancelled = true
    }
  }, [])

  // Its own pane below Leaflet's overlay pane (z 400): the outlines load
  // after the markers, and in the shared pane they were drawn on top of
  // them, half-hiding every coastal marker.
  return (
    <Pane name="basemap" style={{ zIndex: 250 }}>
      {land && (
        <GeoJSON
          data={land}
          interactive={false}
          attribution='<a href="https://www.naturalearthdata.com/" target="_blank" rel="noreferrer">Natural Earth</a>'
          style={{ className: 'basemap-land' }}
        />
      )}
    </Pane>
  )
}
