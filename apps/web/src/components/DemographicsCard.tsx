import type { Signal } from '../api/signals'
import { formatCompactNumber, formatNumber } from '../lib/format'
import type { PlaceDemographics } from '../types/demographics'
import './DemographicsCard.css'

export function DemographicsCard({
  demographics,
  visitorPressureSignal,
}: {
  demographics: PlaceDemographics[]
  visitorPressureSignal: Signal | undefined
}) {
  const sorted = [...demographics].sort((a, b) => a.year - b.year)
  const latest = sorted[sorted.length - 1]
  const earliest = sorted[0]
  const maxPopulation = Math.max(...sorted.map((row) => row.population), 1)

  // The pressure signal is derived once (population x tourism volume) and
  // can outlive - or exist independently of - the raw population rows this
  // card also displays, so it must not be hidden just because `demographics`
  // is empty.
  if (!sorted.length && !visitorPressureSignal) {
    return (
      <article className="card demographics-card">
        <p className="eyebrow">Population &amp; visitor pressure</p>
        <p className="empty-note">No population or visitor-pressure data recorded for this place yet.</p>
      </article>
    )
  }

  return (
    <article className="card demographics-card">
      <p className="eyebrow">Population &amp; visitor pressure</p>

      {latest ? (
        <div className="demographics-headline">
          <strong>{formatNumber(latest.population)}</strong>
          <span>residents ({latest.year}, {latest.source})</span>
        </div>
      ) : (
        <p className="empty-note">No population history recorded for this place yet.</p>
      )}

      {visitorPressureSignal && (
        <div className="pressure-callout">
          <span className="pressure-value">{visitorPressureSignal.value.toFixed(2)}</span>
          <span>
            {visitorPressureSignal.unit ?? 'visitor-nights per resident'} - how heavily tourism
            volume weighs against the local population.
          </span>
        </div>
      )}

      {!!sorted.length && (
        <div className="demographics-bars">
          {sorted.map((row) => (
            <div className="demographics-bar-row" key={row.id}>
              <span className="demographics-bar-year">{row.year}</span>
              <span className="demographics-bar-track">
                <span
                  className="demographics-bar-fill"
                  style={{ width: `${(row.population / maxPopulation) * 100}%` }}
                />
              </span>
              <span className="demographics-bar-value">{formatCompactNumber(row.population)}</span>
            </div>
          ))}
        </div>
      )}

      {sorted.length > 1 && earliest.population > 0 && (
        <p className="demographics-note">
          {(((latest.population - earliest.population) / earliest.population) * 100).toFixed(1)}%
          change in recorded population from {earliest.year} to {latest.year}.
        </p>
      )}
    </article>
  )
}
