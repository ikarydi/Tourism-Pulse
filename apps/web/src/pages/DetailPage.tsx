import { useEffect, useState } from 'react'
import { getPlaceDemographics } from '../api/demographics'
import { getPlaceContent } from '../api/content'
import { getPlaceAnomaly, getPlaceHistory, getPlacePulse, getPlaceTrend } from '../api/pulse'
import { getPlaceSignals, type Signal } from '../api/signals'
import { ContentFeed } from '../components/ContentFeed'
import { DemographicsCard } from '../components/DemographicsCard'
import { EconomicCard } from '../components/EconomicCard'
import { EvidencePanel } from '../components/EvidencePanel'
import { HistoryChart } from '../components/HistoryChart'
import { LineageDrawer } from '../components/LineageDrawer'
import { NarrativePanel } from '../components/NarrativePanel'
import { RiskBanner } from '../components/RiskBanner'
import { PulseHero } from '../features/pulse/PulseHero'
import type { ContentItem } from '../types/content'
import type { PlaceDemographics } from '../types/demographics'
import type { Place } from '../types/place'
import type { DimensionKey, Pulse, PulseAnomaly, PulseSnapshot, PulseTrend } from '../types/pulse'
import './DetailPage.css'

type State = {
  pulse: Pulse | null
  history: PulseSnapshot[]
  trend: PulseTrend | null
  anomaly: PulseAnomaly | null
  signals: Signal[]
  demographics: PlaceDemographics[]
  content: ContentItem[]
}

const EMPTY_STATE: State = {
  pulse: null,
  history: [],
  trend: null,
  anomaly: null,
  signals: [],
  demographics: [],
  content: [],
}

export function DetailPage({ place }: { place: Place }) {
  const [state, setState] = useState<State>(EMPTY_STATE)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedDimension, setSelectedDimension] = useState<DimensionKey | null>(null)
  const [inspectedSignalId, setInspectedSignalId] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setState(EMPTY_STATE)
    setSelectedDimension(null)

    async function load() {
      const [pulseResult, historyResult, trendResult, anomalyResult, signalsResult, demographicsResult, contentResult] =
        await Promise.allSettled([
          getPlacePulse(place.id),
          getPlaceHistory(place.id),
          getPlaceTrend(place.id),
          getPlaceAnomaly(place.id),
          getPlaceSignals(place.id),
          getPlaceDemographics(place.id),
          getPlaceContent(place.id),
        ])

      if (cancelled) return

      if (pulseResult.status === 'rejected') {
        const reason = pulseResult.reason
        const message = reason instanceof Error ? reason.message : 'Unable to load pulse data.'
        // "No signals" is an expected empty state (a place with nothing
        // recorded yet), not a failure worth an error panel.
        if (!message.includes('No signals')) setError(message)
      }

      setState({
        pulse: pulseResult.status === 'fulfilled' ? pulseResult.value : null,
        history: historyResult.status === 'fulfilled' ? historyResult.value : [],
        trend: trendResult.status === 'fulfilled' ? trendResult.value : null,
        anomaly: anomalyResult.status === 'fulfilled' ? anomalyResult.value : null,
        signals: signalsResult.status === 'fulfilled' ? signalsResult.value : [],
        demographics: demographicsResult.status === 'fulfilled' ? demographicsResult.value : [],
        content: contentResult.status === 'fulfilled' ? contentResult.value : [],
      })
      setLoading(false)
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [place.id])

  const { pulse, history, trend, anomaly, signals, demographics, content } = state
  const visitorPressureSignal = signals.find((signal) => signal.signal_type === 'visitor_pressure')
  const turnoverSignal = signals.find((signal) => signal.signal_type === 'tourism_turnover_growth')

  if (loading) {
    return (
      <div className="state-panel loading-panel">
        <span className="spinner" />
        Loading destination intelligence...
      </div>
    )
  }

  if (error) {
    return (
      <div className="state-panel error">
        <strong>Connection issue</strong>
        <span>{error}</span>
      </div>
    )
  }

  if (!pulse) {
    return (
      <div className="state-panel">
        <strong>No pulse data yet</strong>
        <span>{place.name} does not have enough signals or events to calculate a pulse.</span>
      </div>
    )
  }

  const activeDimension = selectedDimension ?? 'demand'
  const activeEvidence = pulse.evidence?.[activeDimension]

  return (
    <div className="detail-page">
      <RiskBanner riskValue={pulse.dimensions.risk} evidence={pulse.evidence?.risk} />

      <PulseHero
        place={place}
        pulse={pulse}
        trend={trend}
        selectedDimension={selectedDimension}
        onSelectDimension={setSelectedDimension}
      />

      <div className="detail-grid">
        <NarrativePanel
          narrative={pulse.narrative}
          headline={pulse.interpretation.headline}
          strengths={pulse.interpretation.strengths}
          weaknesses={pulse.interpretation.weaknesses}
        />
        <EvidencePanel
          dimension={activeDimension}
          evidence={activeEvidence}
          onInspectSignal={setInspectedSignalId}
        />
      </div>

      <div className="detail-grid">
        <DemographicsCard demographics={demographics} visitorPressureSignal={visitorPressureSignal} />
        <EconomicCard
          turnoverSignal={turnoverSignal}
          relatedArticles={pulse.evidence?.economic?.related_articles ?? []}
        />
      </div>

      <section className="section-block">
        <div className="section-title">
          <div>
            <p className="eyebrow">Intelligence feed</p>
            <h2>News &amp; video coverage</h2>
          </div>
          <span>{content.length} items</span>
        </div>
        <div className="card content-feed-card">
          <ContentFeed items={content} />
        </div>
      </section>

      <section className="section-block">
        <div className="section-title">
          <div>
            <p className="eyebrow">Signal over time</p>
            <h2>Pulse history</h2>
          </div>
        </div>
        <div className="card history-card">
          <HistoryChart history={history} />
        </div>
      </section>

      {anomaly?.detected && (
        <section className="section-block">
          <div className="card anomaly-card">
            <p className="eyebrow">Anomaly</p>
            <strong>{anomaly.message}</strong>
            <span>Severity: {anomaly.severity}</span>
          </div>
        </section>
      )}

      {inspectedSignalId !== null && (
        <LineageDrawer
          placeId={place.id}
          signalId={inspectedSignalId}
          onClose={() => setInspectedSignalId(null)}
        />
      )}
    </div>
  )
}
