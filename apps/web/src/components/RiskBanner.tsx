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
  const alertSignal = evidence?.contributing_signals.find(
    (signal) => signal.signal_type === 'disaster_alert_severity',
  )

  // A risk score of 0 means one of two very different things: a real
  // GDACS reading that happens to be severe (elevated danger - worth a
  // banner), or simply no disaster data ingested for this place at all
  // (missing data, same as every other dimension defaulting to 0 with
  // nothing to show) - DimensionList already renders that second case as
  // "-", not "0". Gating on `alertSignal` (a real contributing signal)
  // rather than the bare threshold is what tells the two apart; without
  // it, most places with no GDACS coverage would show a false "elevated
  // risk" alarm.
  if (!alertSignal || riskValue >= ELEVATED_RISK_THRESHOLD) return null

  const topArticle = evidence?.related_articles[0]

  return (
    <div className="risk-banner">
      <span className="risk-banner-icon">⚠</span>
      <div>
        <strong>Elevated risk signal</strong>
        <p>
          {`GDACS alert score ${alertSignal.value} for this destination's country.`}
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
