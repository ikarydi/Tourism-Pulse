import { useMemo, useState } from 'react'
import { formatDate } from '../lib/format'
import type { ContentItem } from '../types/content'
import './ContentFeed.css'

const CATEGORY_LABELS: Record<string, string> = {
  events: 'Events',
  risk: 'Risk',
  economic: 'Economic',
}

type CategoryFilter = 'all' | 'events' | 'risk' | 'economic' | 'general'

export function ContentFeed({ items }: { items: ContentItem[] }) {
  const [filter, setFilter] = useState<CategoryFilter>('all')

  const counts = useMemo(() => {
    const base: Record<CategoryFilter, number> = {
      all: items.length,
      events: 0,
      risk: 0,
      economic: 0,
      general: 0,
    }
    for (const item of items) {
      if (!item.categories.length) {
        base.general += 1
        continue
      }
      for (const category of item.categories) {
        if (category in CATEGORY_LABELS) {
          base[category as CategoryFilter] += 1
        }
      }
    }
    return base
  }, [items])

  const filtered = items.filter((item) => {
    if (filter === 'all') return true
    if (filter === 'general') return item.categories.length === 0
    return item.categories.includes(filter)
  })

  if (!items.length) {
    return (
      <p className="empty-note">
        No news or video coverage recorded for this place yet - it will appear here once the
        ingestion scheduler picks it up.
      </p>
    )
  }

  return (
    <div className="content-feed">
      <div className="content-filter" role="tablist" aria-label="Filter by topic">
        {(['all', 'events', 'risk', 'economic', 'general'] as const).map((key) => (
          <button
            key={key}
            type="button"
            className={filter === key ? 'active' : ''}
            onClick={() => setFilter(key)}
          >
            {key === 'all' ? 'All' : key === 'general' ? 'General' : CATEGORY_LABELS[key]} (
            {counts[key]})
          </button>
        ))}
      </div>

      <ul className="content-list">
        {filtered.length === 0 && <li className="empty-note">Nothing in this category yet.</li>}
        {filtered.map((item) => (
          <li key={item.id} className="content-item">
            <span className={`content-kind content-kind-${item.kind}`}>
              {item.kind === 'news' ? 'News' : 'Video'}
            </span>
            <div className="content-item-body">
              <a href={item.url} target="_blank" rel="noreferrer">
                {item.title}
              </a>
              <div className="content-item-meta">
                <span>{item.byline ?? item.source}</span>
                {item.published_at && <span>{formatDate(item.published_at)}</span>}
                {item.categories.map((category) => (
                  <span key={category} className="content-tag">
                    {CATEGORY_LABELS[category] ?? category}
                  </span>
                ))}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
