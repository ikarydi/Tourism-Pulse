import { useMemo, useState } from 'react'
import { isCurated, placeSubtitle } from '../../lib/places'
import type { SavedView } from '../../types/explore'
import type { Place } from '../../types/place'
import { NAV, type View } from './nav'

type Item =
  | { kind: 'page'; key: string; label: string; hint: string; view: View }
  | { kind: 'place'; key: string; label: string; hint: string; placeId: number }
  | { kind: 'view'; key: string; label: string; hint: string; saved: SavedView }
  | { kind: 'ask'; key: string; label: string; hint: string; question: string }

export function CommandPalette({
  places,
  views,
  detailEnabled,
  onClose,
  onNavigate,
  onOpenPlace,
  onOpenView,
  onAsk,
}: {
  places: Place[]
  views: SavedView[]
  detailEnabled: boolean
  onClose: () => void
  onNavigate: (view: View) => void
  onOpenPlace: (placeId: number) => void
  onOpenView: (view: SavedView) => void
  onAsk: (question: string) => void
}) {
  // Mounted only while open (see App), so every opening starts empty.
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)

  const items = useMemo<Item[]>(() => {
    const needle = query.trim().toLowerCase()
    const matches = (text: string) => !needle || text.toLowerCase().includes(needle)
    const pages: Item[] = NAV.filter((item) => (item.view !== 'detail' || detailEnabled) && matches(item.label)).map(
      (item) => ({ kind: 'page', key: `page-${item.view}`, label: item.label, hint: 'Page', view: item.view }),
    )
    const rank = (name: string) => (name.toLowerCase().startsWith(needle) ? 0 : 1)
    const placeItems: Item[] = places
      .filter((place) => needle && matches(place.name))
      // Names starting with the query first, curated places before generated ones.
      .sort((a, b) => rank(a.name) - rank(b.name) || Number(isCurated(b)) - Number(isCurated(a)))
      .slice(0, 10)
      .map((place) => ({
        kind: 'place',
        key: `place-${place.id}`,
        label: place.name,
        hint: placeSubtitle(place),
        placeId: place.id,
      }))
    const viewItems: Item[] = views
      .filter((view) => matches(view.title))
      .slice(0, 5)
      .map((view) => ({ kind: 'view', key: `view-${view.id}`, label: view.title, hint: 'Saved chart', saved: view }))
    const ask: Item[] =
      needle.length >= 3
        ? [{ kind: 'ask', key: 'ask', label: `Ask: “${query.trim()}”`, hint: 'Chart from a question', question: query.trim() }]
        : []
    return [...placeItems, ...viewItems, ...pages, ...ask]
  }, [query, places, views, detailEnabled])

  function choose(item: Item | undefined) {
    if (!item) return
    onClose()
    if (item.kind === 'page') onNavigate(item.view)
    else if (item.kind === 'place') onOpenPlace(item.placeId)
    else if (item.kind === 'view') onOpenView(item.saved)
    else onAsk(item.question)
  }

  return (
    <div className="palette-backdrop" onMouseDown={onClose} role="presentation">
      <div
        className="palette"
        role="dialog"
        aria-modal="true"
        aria-label="Search pages, places and charts"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <input
          autoFocus
          className="palette-input"
          value={query}
          placeholder="Search places, pages and charts, or ask a question"
          aria-label="Search"
          aria-controls="palette-results"
          aria-activedescendant={items[active] ? `palette-${items[active].key}` : undefined}
          onChange={(event) => {
            setQuery(event.target.value)
            setActive(0)
          }}
          onKeyDown={(event) => {
            if (event.key === 'Escape') onClose()
            else if (event.key === 'ArrowDown') {
              event.preventDefault()
              setActive((index) => Math.min(items.length - 1, index + 1))
            } else if (event.key === 'ArrowUp') {
              event.preventDefault()
              setActive((index) => Math.max(0, index - 1))
            } else if (event.key === 'Enter') {
              event.preventDefault()
              choose(items[active])
            }
          }}
        />
        <ul id="palette-results" className="palette-results" role="listbox">
          {items.length === 0 && <li className="palette-empty">No matches</li>}
          {items.map((item, index) => (
            <li
              key={item.key}
              id={`palette-${item.key}`}
              role="option"
              aria-selected={index === active}
              className={`${index === active ? 'active' : ''}${item.kind === 'ask' ? ' ask' : ''}`}
              onMouseEnter={() => setActive(index)}
              onClick={() => choose(item)}
            >
              <span>{item.label}</span>
              <em>{item.hint}</em>
            </li>
          ))}
        </ul>
        <p className="palette-foot">
          <kbd>↑</kbd> <kbd>↓</kbd> to move · <kbd>Enter</kbd> to open · <kbd>Esc</kbd> to close
        </p>
      </div>
    </div>
  )
}
