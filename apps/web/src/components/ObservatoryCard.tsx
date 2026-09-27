import { formatIndicatorValue, ordinal, pressureBand } from '../lib/observatory'
import type { Observatory } from '../types/observatory'
import './ObservatoryCard.css'

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
            {region_name ?? placeName} · {level_name}. Each indicator is ranked against European{' '}
            {level_name === 'country' ? 'countries' : 'regions at the same level'}.
          </span>
        </div>
      </div>

      <ul className="observatory-indicators">
        {indicators.map((reading) => (
          <li key={reading.indicator} className={pressureBand(reading.percentile)} title={reading.definition}>
            <div className="observatory-indicator-head">
              <span>{reading.label}</span>
              <span className="observatory-rank">
                #{reading.rank} of {reading.peers} · {reading.year}
                {reading.region_code !== observatory.nuts_code && ` · ${reading.level_name}`}
              </span>
            </div>
            <div className="observatory-track" aria-hidden="true">
              <span className="observatory-fill" style={{ width: `${reading.percentile}%` }} />
            </div>
            <div className="observatory-indicator-foot">
              <span>{formatIndicatorValue(reading)}</span>
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
