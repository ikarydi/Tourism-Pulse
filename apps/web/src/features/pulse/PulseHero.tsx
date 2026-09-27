import { DimensionList } from '../../components/DimensionList'
import { DimensionRadar } from '../../components/DimensionRadar'
import { formatChange, scoreStatus } from '../../lib/format'
import type { DimensionKey, Pulse, PulseTrend } from '../../types/pulse'
import './PulseHero.css'

function trendArrow(direction: string, momentumUnknown: boolean) {
  if (momentumUnknown) return '?'
  if (direction === 'up') return '↗'
  if (direction === 'down') return '↘'
  return '→'
}

export function PulseHero({
  place,
  pulse,
  trend,
  selectedDimension,
  onSelectDimension,
}: {
  place: { name: string; country_code?: string | null }
  pulse: Pulse
  trend: PulseTrend | null
  selectedDimension: DimensionKey | null
  onSelectDimension: (key: DimensionKey) => void
}) {
  const momentumUnknown = trend?.direction === 'insufficient_data' || trend?.momentum === 'unknown'
  const direction = trend?.direction ?? pulse.trend.direction
  const change = trend?.change_24h ?? pulse.trend.change
  const status = scoreStatus(pulse.pulse)

  return (
    <section className="pulse-hero card">
      <div className="pulse-hero-top">
        <div>
          <p className="eyebrow">
            Current pulse / {place.name.toUpperCase()}
            {place.country_code ? ` · ${place.country_code}` : ''}
          </p>
          <div className="pulse-hero-score-row">
            <span className="pulse-hero-score">{Math.round(pulse.pulse)}</span>
            <div className="pulse-hero-score-meta">
              <span className={`badge badge-${status === 'Strong' ? 'good' : status === 'Moderate' ? 'warn' : 'bad'}`}>
                {status}
              </span>
              <span>out of 100</span>
            </div>
          </div>
        </div>
        <div className={`pulse-hero-trend ${momentumUnknown ? 'stable' : direction}`}>
          <span className="pulse-hero-trend-arrow">{trendArrow(direction, momentumUnknown)}</span>
          <div>
            <strong>{formatChange(change)} pts</strong>
            <span>{momentumUnknown ? 'Not yet determined' : 'vs. previous calculation'}</span>
          </div>
        </div>
      </div>

      <div className="pulse-hero-body">
        <DimensionRadar
          dimensions={pulse.dimensions}
          selectedDimension={selectedDimension}
          onSelectDimension={onSelectDimension}
        />
        <DimensionList
          dimensions={pulse.dimensions}
          selectedDimension={selectedDimension}
          onSelectDimension={onSelectDimension}
        />
      </div>

      <div className="pulse-hero-footer">
        <span>Confidence <strong>{pulse.confidence.score.toFixed(0)}%</strong></span>
        <span>Coverage <strong>{pulse.confidence.coverage.toFixed(0)}%</strong></span>
        <span className={`badge badge-neutral quality-${pulse.interpretation.data_quality}`}>
          {pulse.interpretation.data_quality} data quality
        </span>
      </div>
    </section>
  )
}
