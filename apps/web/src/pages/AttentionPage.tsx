import { useEffect, useMemo, useState } from 'react'
import { getAttention } from '../api/attention'
import { AttentionPanel } from '../components/AttentionPanel'
import { changeTone, periodLabel, plainPercent, signedPercent } from '../lib/outlook'
import type { AttentionSummary } from '../types/attention'
import './AttentionPage.css'

type SortKey = 'wiki_relative' | 'news_vs_last_year' | 'tone_change' | 'top_topic_lift' | 'name'
type Scope = 'all' | 'destination' | 'country'

const SORTS: { key: SortKey; label: string }[] = [
  { key: 'wiki_relative', label: 'Wikipedia interest vs typical' },
  { key: 'news_vs_last_year', label: 'News mentions vs last year' },
  { key: 'tone_change', label: 'Change in news tone' },
  { key: 'top_topic_lift', label: 'Standout news topic' },
  { key: 'name', label: 'Name' },
]

export function AttentionPage({ onOpenPlace }: { onOpenPlace: (placeId: number) => void }) {
  const [rows, setRows] = useState<AttentionSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('wiki_relative')
  const [scope, setScope] = useState<Scope>('all')
  const [selectedId, setSelectedId] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    getAttention()
      .then((data) => !cancelled && setRows(data))
      .catch((err: Error) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [])

  const sorted = useMemo(() => {
    const list = (rows ?? []).filter((row) => scope === 'all' || row.place_type === scope)
    if (sortKey === 'name') return [...list].sort((a, b) => a.name.localeCompare(b.name))
    return [...list].sort((a, b) => (b[sortKey] ?? -Infinity) - (a[sortKey] ?? -Infinity))
  }, [rows, sortKey, scope])

  const benchmark = rows?.find((row) => row.wiki_vs_last_year != null && row.wiki_relative != null)
  const typical =
    benchmark && benchmark.wiki_vs_last_year != null && benchmark.wiki_relative != null
      ? (1 + benchmark.wiki_vs_last_year) / (1 + benchmark.wiki_relative) - 1
      : null
  const selected = sorted.find((row) => row.place_id === selectedId) ?? null

  if (error) return <div className="state-panel error"><strong>Attention data unavailable</strong><span>{error}</span></div>
  if (!rows) return <div className="state-panel loading-panel"><span className="spinner" />Reading Wikipedia and news signals...</div>

  return (
    <div className="attention-page">
      <section className="card attention-intro">
        <div>
          <p className="eyebrow">Reading the signals</p>
          <p>
            Wikipedia views show who is researching a place, by language. GDELT shows how often international news
            mentions it and what its tourism coverage is about. Wikipedia's own traffic has been falling since 2024
            {typical != null && benchmark?.wiki_month ? (
              <>
                {' '}
                ({signedPercent(typical)} for the median place in {periodLabel(benchmark.wiki_month, 'long')})
              </>
            ) : null}
            , so interest is shown against that typical change. In the forecasting backtest, this attention improved
            forecasts 4–12 months ahead in 26 of 30 countries.
          </p>
        </div>
      </section>

      <div className="attention-toolbar">
        <div className="segmented" role="radiogroup" aria-label="Places">
          {(['all', 'destination', 'country'] as const).map((value) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={scope === value}
              className={scope === value ? 'active' : ''}
              onClick={() => setScope(value)}
            >
              {value === 'all' ? 'All' : value === 'destination' ? 'Destinations' : 'Countries'}
            </button>
          ))}
        </div>
        <label className="attention-sort">
          <span>Sort by</span>
          <select id="attention-sort" className="field" value={sortKey} onChange={(event) => setSortKey(event.target.value as SortKey)}>
            {SORTS.map((item) => (
              <option key={item.key} value={item.key}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="attention-table-wrap card">
        <table className="attention-table">
          <thead>
            <tr>
              <th>Place</th>
              <th title="Year-on-year change in Wikipedia views, relative to the median tracked place">Wikipedia vs typical</th>
              <th>Language gaining ground</th>
              <th title="International news mentions, last 3 months vs a year earlier">News mentions</th>
              <th title="Mean GDELT tone of tourism coverage, last 3 months, and change on a year earlier">Tourism news tone</th>
              <th title="The topic its tourism coverage carries most often relative to Europe's tourism coverage">Standout topic</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr
                key={row.place_id}
                className={row.place_id === selectedId ? 'active' : ''}
                onClick={() => setSelectedId(row.place_id === selectedId ? null : row.place_id)}
              >
                <td className="attention-name">
                  <strong>{row.name}</strong>
                  <span>{row.place_type === 'country' ? 'Country' : row.country_code}</span>
                </td>
                <td className={changeTone(row.wiki_relative, 0.02)}>{signedPercent(row.wiki_relative)}</td>
                <td>
                  {row.language_gainer ? (
                    <>
                      {row.language_gainer}{' '}
                      <span className="muted">+{((row.language_gain ?? 0) * 100).toFixed(1)} pt</span>
                    </>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td className={changeTone(row.news_vs_last_year, 0.05)}>{signedPercent(row.news_vs_last_year)}</td>
                <td>
                  {row.tone_3m != null ? row.tone_3m.toFixed(1) : '—'}
                  {row.tone_change != null && (
                    <span className={`muted ${changeTone(row.tone_change, 0.3)}`}>
                      {' '}
                      ({row.tone_change >= 0 ? '+' : '−'}
                      {Math.abs(row.tone_change).toFixed(1)})
                    </span>
                  )}
                </td>
                <td>
                  {row.top_topic ? (
                    <>
                      {row.top_topic}{' '}
                      <span className={row.top_topic_lift && row.top_topic_lift >= 1.5 ? 'hot' : 'muted'}>
                        {plainPercent(row.top_topic_share)} · {row.top_topic_lift?.toFixed(1)}×
                      </span>
                    </>
                  ) : (
                    <span className="muted">too little coverage</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="attention-selected">
          <div className="attention-selected-head">
            <h2>{selected.name}</h2>
            <button type="button" className="button" onClick={() => onOpenPlace(selected.place_id)}>
              Open place page
            </button>
          </div>
          <AttentionPanel key={selected.place_id} placeId={selected.place_id} />
        </div>
      )}
    </div>
  )
}
