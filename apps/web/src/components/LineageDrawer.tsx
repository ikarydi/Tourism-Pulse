import { useEffect, useState } from 'react'
import { getSignalLineage } from '../api/lineage'
import { formatDateTime } from '../lib/format'
import type { SignalLineage } from '../types/lineage'
import './LineageDrawer.css'

export function LineageDrawer({
  placeId,
  signalId,
  onClose,
}: {
  placeId: number
  signalId: number
  onClose: () => void
}) {
  const [lineage, setLineage] = useState<SignalLineage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getSignalLineage(placeId, signalId)
      .then((result) => {
        if (!cancelled) setLineage(result)
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : 'Failed to load lineage.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [placeId, signalId])

  return (
    <div className="lineage-scrim" onClick={onClose}>
      <aside className="lineage-drawer" onClick={(event) => event.stopPropagation()}>
        <div className="lineage-drawer-head">
          <div>
            <p className="eyebrow">Lineage · Why is this number what it is</p>
            <h3>Signal #{signalId}</h3>
          </div>
          <button type="button" className="lineage-close" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        {loading && (
          <div className="skeleton-text">
            <span className="spinner" />
            Loading lineage chain...
          </div>
        )}

        {error && <div className="state-panel error">{error}</div>}

        {lineage && (
          <div className="lineage-chain">
            <LineageStep
              label="Signal"
              title={lineage.signal_type.replaceAll('_', ' ')}
              detail={`${lineage.value} ${lineage.unit ?? ''} · ${lineage.source} · ${formatDateTime(lineage.observed_at)}`}
            />

            {lineage.source_observation ? (
              <LineageStep
                label="Source observation"
                title={lineage.source_observation.dataset}
                detail={`Retrieved ${formatDateTime(lineage.source_observation.retrieved_at)} · checksum ${lineage.source_observation.checksum.slice(0, 12)}…`}
                url={lineage.source_observation.source_url}
              />
            ) : (
              <div className="lineage-gap">
                No raw fetch behind this signal - likely entered directly rather than via an
                ingestion adapter.
              </div>
            )}

            {lineage.source_detail && (
              <LineageStep
                label="Source"
                title={lineage.source_detail.name}
                detail={`${lineage.source_detail.category} · reliability ${lineage.source_detail.reliability}`}
              />
            )}

            {!!lineage.quality_results.length && (
              <div className="lineage-quality">
                <p className="mini-label">Data-quality checks</p>
                <ul>
                  {lineage.quality_results.slice(0, 10).map((result, index) => (
                    <li key={`${result.check_name}-${index}`} className={result.passed ? 'pass' : result.severity}>
                      <span>{result.check_name.replaceAll('_', ' ')}</span>
                      <span>{result.passed ? 'passed' : result.severity}</span>
                    </li>
                  ))}
                </ul>
                {lineage.quality_results.length > 10 && (
                  <p className="empty-note">
                    +{lineage.quality_results.length - 10} more checks recorded against this
                    source observation.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </aside>
    </div>
  )
}

function LineageStep({
  label,
  title,
  detail,
  url,
}: {
  label: string
  title: string
  detail: string
  url?: string | null
}) {
  return (
    <div className="lineage-step">
      <div className="lineage-step-rail">
        <span className="lineage-step-dot" />
        <span className="lineage-step-line" />
      </div>
      <div className="lineage-step-body">
        <p className="mini-label">{label}</p>
        <strong>{title}</strong>
        <p>{detail}</p>
        {url && (
          <a href={url} target="_blank" rel="noreferrer">
            source URL ↗
          </a>
        )}
      </div>
    </div>
  )
}
