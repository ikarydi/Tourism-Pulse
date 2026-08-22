import type { Signal } from '../api/signals'
import { formatDate } from '../lib/format'
import type { EvidenceArticle } from '../types/pulse'
import './EconomicCard.css'

export function EconomicCard({
  turnoverSignal,
  relatedArticles,
}: {
  turnoverSignal: Signal | undefined
  relatedArticles: EvidenceArticle[]
}) {
  const hasData = turnoverSignal !== undefined

  return (
    <article className="card economic-card">
      <p className="eyebrow">Tourism-sector economics</p>

      {!hasData && (
        <p className="empty-note">No turnover-growth data recorded for this place yet.</p>
      )}

      {hasData && (
        <div className={`economic-headline ${turnoverSignal.value >= 0 ? 'positive' : 'negative'}`}>
          <strong>
            {turnoverSignal.value >= 0 ? '+' : ''}
            {turnoverSignal.value.toFixed(1)}
            {turnoverSignal.unit ?? '%'}
          </strong>
          <span>
            turnover growth · {turnoverSignal.source} · {formatDate(turnoverSignal.observed_at)}
          </span>
        </div>
      )}

      {!!relatedArticles.length && (
        <div className="economic-articles">
          <p className="mini-label">Related coverage</p>
          <ul>
            {relatedArticles.map((article) => (
              <li key={article.url}>
                <a href={article.url} target="_blank" rel="noreferrer">
                  {article.title}
                </a>
                <span>{article.source}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  )
}
