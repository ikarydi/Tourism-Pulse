import { useEffect, useState } from 'react'
import { getPlaceDemographics } from '../api/demographics'
import { getPlaceObservatory } from '../api/observatory'
import { DemographicsCard } from '../components/DemographicsCard'
import { ObservatoryCard } from '../components/ObservatoryCard'
import { ForecastCard } from '../components/ForecastCard'
import { InboundEconomyPanel } from '../components/InboundEconomyPanel'
import { PlaceContext } from '../components/PlaceContext'
import { PlaceStatistics } from '../components/PlaceStatistics'
import { formatNumber } from '../lib/format'
import { placeSubtitle, placeTypeLabel } from '../lib/places'
import type { PlaceDemographics } from '../types/demographics'
import type { Catalog } from '../types/explore'
import type { Observatory } from '../types/observatory'
import type { Place } from '../types/place'
import type { ExploreDraft } from './ExplorePage'
import './RegionDetail.css'

/** Statistics-first page for places without a Pulse: EU regions, areas and cities. */
export function RegionDetail({
  place,
  places,
  catalog,
  onOpenExplore,
  onSelectPlace,
  onOpenOutlook,
}: {
  place: Place
  places: Place[]
  catalog: Catalog | null
  onOpenExplore: (draft: ExploreDraft) => void
  onSelectPlace: (placeId: number) => void
  onOpenOutlook?: () => void
}) {
  const [observatory, setObservatory] = useState<Observatory | null>(null)
  // null while loading, so an empty result can hide the card instead of flashing it.
  const [demographics, setDemographics] = useState<PlaceDemographics[] | null>(null)

  useEffect(() => {
    let cancelled = false
    getPlaceObservatory(place.id)
      .then((data) => !cancelled && setObservatory(data))
      .catch(() => undefined)
    getPlaceDemographics(place.id)
      .then((data) => !cancelled && setDemographics(data))
      .catch(() => !cancelled && setDemographics([]))
    return () => {
      cancelled = true
    }
  }, [place.id])

  const latestPopulation = [...(demographics ?? [])].sort((a, b) => b.year - a.year)[0]
  const hasDemographics = demographics === null || demographics.length > 0
  const codes = [
    place.place_type === 'region' && place.nuts_code ? `NUTS ${place.nuts_code}` : null,
    place.place_type === 'area' && place.nuts3_code ? `NUTS ${place.nuts3_code}` : null,
    place.urau_code ? `Urban Audit ${place.urau_code}` : null,
  ].filter(Boolean)

  return (
    <div className="detail-page">
      <section className="card region-hero">
        <div className="region-hero-main">
          <p className="eyebrow">{placeSubtitle(place)}</p>
          <h2>{place.name}</h2>
          {codes.length > 0 && <p className="region-codes">{codes.join(' · ')}</p>}
          <p className="region-note">
            Official statistics from Eurostat. Live signals and the Pulse score are tracked for curated destinations
            only.
          </p>
        </div>
        <dl className="region-facts">
          <div>
            <dt>Tourism pressure</dt>
            <dd className={observatory?.level ?? ''}>
              {observatory?.score != null ? observatory.score.toFixed(0) : '—'}
              <span>{observatory?.level ?? 'no data'}</span>
            </dd>
          </div>
          <div>
            <dt>Population</dt>
            <dd>
              {latestPopulation ? formatNumber(latestPopulation.population) : '—'}
              <span>{latestPopulation ? latestPopulation.year : ''}</span>
            </dd>
          </div>
          <div>
            <dt>Type</dt>
            <dd className="region-type">{placeTypeLabel(place.place_type)}</dd>
          </div>
        </dl>
      </section>

      <PlaceContext place={place} places={places} onSelectPlace={onSelectPlace} />
      <ForecastCard placeId={place.id} onOpenOutlook={onOpenOutlook} />

      <div className={hasDemographics ? 'detail-grid' : 'detail-grid detail-grid-single'}>
        <ObservatoryCard observatory={observatory} placeName={place.name} />
        {hasDemographics && <DemographicsCard demographics={demographics ?? []} visitorPressureSignal={undefined} />}
      </div>

      <InboundEconomyPanel placeId={place.id} />

      <PlaceStatistics place={place} catalog={catalog} onOpenExplore={onOpenExplore} />
    </div>
  )
}
