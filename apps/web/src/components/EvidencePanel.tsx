import { DIMENSION_BY_KEY } from '../lib/dimensions'
import { formatDate } from '../lib/format'
import type { DimensionEvidence, DimensionKey } from '../types/pulse'
import './EvidencePanel.css'

export function EvidencePanel({
  dimension,
  evidence,
  onInspectSignal,
}: {
  dimension: DimensionKey
  evidence: DimensionEvidence | undefined
  onInspectSignal: (signalId: number) => void
}) {
  const meta = DIMENSION_BY_KEY[dimension]
  const hasAnyEvidence =
    evidence &&
    (evidence.contributing_signals.length ||
      evidence.related_articles.length ||
      evidence.related_videos.length ||
      evidence.related_events.length)

  return (
    <article className="card evidence-panel">
      <div className="evidence-heading">
        <span className="evidence-dot" style={{ background: meta.color }} />
        <div>
          <p className="eyebrow">Why · {meta.label}</p>
          <h3>{meta.description}</h3>
        </div>
      </div>

      {!hasAnyEvidence && (
        <p className="empty-note evidence-empty">
          No specific evidence recorded for this dimension yet - it may be relying on
          older or bulk-averaged signals not captured in this drill-down.
        </p>
      )}

      {!!evidence?.contributing_signals.length && (
        <section>
          <p className="mini-label">Contributing signals</p>
          <ul className="evidence-list">
            {evidence.contributing_signals.map((signal) => (
              <li key={signal.id}>
                <button
                  type="button"
                  className="evidence-signal-row"
                  onClick={() => onInspectSignal(signal.id)}
                >
                  <span className="evidence-signal-type">
                    {signal.signal_type.replaceAll('_', ' ')}
                  </span>
                  <span className="evidence-signal-value">
                    {signal.value.toLocaleString()} {signal.unit ?? ''}
                  </span>
                  <span className="evidence-signal-source">{signal.source}</span>
                  <span className="evidence-signal-date">{formatDate(signal.observed_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!!evidence?.related_events.length && (
        <section>
          <p className="mini-label">Related events</p>
          <ul className="evidence-list">
            {evidence.related_events.map((event) => (
              <li key={event.id} className="evidence-plain-row">
                <span>{event.name}</span>
                <span className="evidence-plain-meta">
                  {event.event_type} · {formatDate(event.start_at)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!!evidence?.related_articles.length && (
        <section>
          <p className="mini-label">Related articles</p>
          <ul className="evidence-list">
            {evidence.related_articles.map((article) => (
              <li key={article.url} className="evidence-plain-row">
                <a href={article.url} target="_blank" rel="noreferrer">
                  {article.title}
                </a>
                <span className="evidence-plain-meta">{article.source}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!!evidence?.related_videos.length && (
        <section>
          <p className="mini-label">Related videos</p>
          <ul className="evidence-list">
            {evidence.related_videos.map((video) => (
              <li key={video.video_id} className="evidence-plain-row">
                <a
                  href={`https://www.youtube.com/watch?v=${video.video_id}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {video.title}
                </a>
                <span className="evidence-plain-meta">{video.channel ?? 'Unknown channel'}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  )
}
