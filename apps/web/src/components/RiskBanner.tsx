import type { DimensionEvidence } from '../types/pulse'
import './RiskBanner.css'

// The risk dimension's normalizer inverts polarity on purpose (see
// pulse.disaster_risk's docstring) - unlike every other dimension, a
// LOW risk score means elevated danger, not a weak reading. This
// threshold is a considered starting point for "worth a banner", not a
// measured constant.
const ELEVATED_RISK_THRESHOLD = 60

export function RiskBanner({
  riskValue,
  evidence,
}: {
  riskValue: number
  evidence: DimensionEvidence | undefined
}) {
  if (riskValue >= ELEVATED_RISK_THRESHOLD) return null

  const alertSignal = evidence?.contributing_signals.find(
    (signal) => signal.signal_type === 'disaster_alert_severity',
  )
  const topArticle = evidence?.related_articles[0]

  return (
    <div className="risk-banner">
      <span className="risk-banner-icon">⚠</span>
      <div>
        <strong>Elevated risk signal</strong>
        <p>
          {alertSignal
            ? `GDACS alert score ${alertSignal.value} for this destination's country.`
            : `Risk dimension reading is low (${Math.round(riskValue)}/100).`}
          {topArticle && (
            <>
              {' '}
              Related coverage:{' '}
              <a href={topArticle.url} target="_blank" rel="noreferrer">
                {topArticle.title}
              </a>
              .
            </>
          )}
        </p>
      </div>
    </div>
  )
}
