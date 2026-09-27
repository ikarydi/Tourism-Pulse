import type { IndicatorReading, Observatory } from '../types/observatory'
import './ObservatoryCard.css'

const numberFormatter = new Intl.NumberFormat('en', { maximumFractionDigits: 0 })

function formatReading(reading: IndicatorReading): string {
  if (reading.indicator === 'seasonality_peak_share') {
    return `${(reading.value * 100).toFixed(1)}% of the year's nights in its busiest month`
  }
  if (reading.indicator === 'tourism_intensity') {
    return `${numberFormatter.format(reading.value)} nights per 1,000 residents`
  }
  if (reading.indicator === 'tourism_density') {
    return `${numberFormatter.format(reading.value)} nights per km²`
  }
  return `${numberFormatter.format(reading.value)} ${reading.unit}`
}

// Same bands as the backend's pressure level (observatory/pressure.py).
function band(percentile: number): 'low' | 'moderate' | 'high' {
  if (percentile >= 70) return 'high'
  if (percentile >= 40) return 'moderate'
  return 'low'
}

function ordinal(n: number): string {
  const rounded = Math.round(n)
  const lastTwo = rounded % 100
  const suffix =
    lastTwo >= 11 && lastTwo <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' }[rounded % 10] ?? 'th')
  return `${rounded}${suffix}`
}

export function ObservatoryCard({
  observatory,
  placeName,
}: {
  observatory: Observatory | null
  placeName: string
}) {
  if (!observatory || observatory.score === null || !observatory.indicators.length) {
    return (
      <article className="card observatory-card">
        <p className="eyebrow">Tourism pressure</p>
        <p className="empty-note">No official regional pressure data for this place yet.</p>
      </article>
    )
  }

  const { score, level, region_name, level_name, indicators, method } = observatory

  return (
    <article className={`card observatory-card ${level ?? ''}`}>
      <p className="eyebrow">Tourism pressure</p>

      <div className="observatory-headline">
        <span className="observatory-score">{score.toFixed(0)}</span>
        <div>
          <strong className="observatory-level">{level} pressure</strong>
          <span>
            {/* Countries have no boundary row, so no region name. */}
            {region_name ?? placeName} · {level_name}, ranked against all European{' '}
            {level_name === 'country' ? 'countries' : 'regions at this level'}
          </span>
        </div>
      </div>

      <ul className="observatory-indicators">
        {indicators.map((reading) => (
          <li key={reading.indicator} className={band(reading.percentile)} title={reading.definition}>
            <div className="observatory-indicator-head">
              <span>{reading.label}</span>
              <span className="observatory-rank">
                #{reading.rank} of {reading.peers} · {reading.year}
              </span>
            </div>
            <div className="observatory-track" aria-hidden="true">
              <span className="observatory-fill" style={{ width: `${reading.percentile}%` }} />
            </div>
            <div className="observatory-indicator-foot">
              <span>{formatReading(reading)}</span>
              <span>{ordinal(reading.percentile)} percentile</span>
            </div>
          </li>
        ))}
      </ul>

      {method && (
        <p className="observatory-method">
          {method} Source: {indicators[0].source === 'eurostat' ? 'Eurostat' : indicators[0].source}.
        </p>
      )}
    </article>
  )
}
