import * as Plot from '@observablehq/plot'
import { useCallback, useEffect, useState } from 'react'
import { getPlaceAttention } from '../api/attention'
import { changeTone, compactNights, periodDate, periodLabel, plainPercent, signedPercent } from '../lib/outlook'
import type { Attention, WikipediaInsight } from '../types/attention'
import { PlotFigure } from './charts/PlotFigure'
import './AttentionPanel.css'

const LANGUAGES_SHOWN = 8

function ViewsChart({ wiki }: { wiki: WikipediaInsight }) {
  const build = useCallback(
    (width: number) => {
      const data = wiki.series.map((row) => ({ date: periodDate(row.period), value: row.value }))
      return Plot.plot({
        width,
        height: 150,
        marginLeft: 44,
        marginTop: 10,
        style: { background: 'transparent', color: '#8ea0b3', fontSize: '11px', overflow: 'visible' },
        x: { type: 'utc', label: null },
        y: { grid: true, label: null, tickFormat: (value: number) => compactNights(value) },
        marks: [
          Plot.areaY(data, { x: 'date', y: 'value', fill: '#5fd3e8', fillOpacity: 0.12, curve: 'monotone-x' }),
          Plot.lineY(data, { x: 'date', y: 'value', stroke: '#5fd3e8', strokeWidth: 1.6, curve: 'monotone-x' }),
          Plot.tip(
            data,
            Plot.pointerX({
              x: 'date',
              y: 'value',
              fill: '#101e2e',
              stroke: 'rgba(163, 196, 224, 0.3)',
              title: (row: { date: Date; value: number }) =>
                `${row.date.toLocaleDateString('en', { month: 'long', year: 'numeric', timeZone: 'UTC' })}\n${compactNights(row.value)} views`,
            }),
          ),
        ],
      })
    },
    [wiki],
  )
  return <PlotFigure build={build} />
}

/** Wikipedia and GDELT insights for one curated place. */
export function AttentionPanel({ placeId, compact = false }: { placeId: number; compact?: boolean }) {
  const [attention, setAttention] = useState<Attention | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    getPlaceAttention(placeId)
      .then((data) => !cancelled && setAttention(data))
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [placeId])

  if (failed) return null
  if (!attention) return <div className="card skeleton attention-skeleton" />
  const { wikipedia: wiki, news } = attention
  if (!wiki && !news) return null
  const languages = wiki?.languages.slice(0, LANGUAGES_SHOWN) ?? []
  const topShare = languages[0]?.share ?? 1
  const topics = news && news.tourism_articles_12m >= 40 ? news.topics : []

  return (
    <section className={`card attention-panel${compact ? ' compact' : ''}`}>
      <header className="attention-head">
        <div>
          <p className="eyebrow">Online attention · Wikipedia &amp; GDELT</p>
          <h3>What people read and what the news says</h3>
        </div>
      </header>

      {attention.highlights.length > 0 && (
        <ul className="attention-highlights">
          {attention.highlights.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}

      <div className="attention-grid">
        {wiki && (
          <div className="attention-block">
            <p className="mini-label">
              Wikipedia views <span>{periodLabel(wiki.latest_month, 'long')}</span>
            </p>
            <div className="attention-stats">
              <div>
                <strong>{compactNights(wiki.latest_views)}</strong>
                <span>views (English + German articles)</span>
              </div>
              <div>
                <strong className={changeTone(wiki.relative_to_benchmark, 0.02)}>
                  {signedPercent(wiki.relative_to_benchmark)}
                </strong>
                <span>
                  vs the median place ({signedPercent(wiki.latest_vs_last_year)} own, {signedPercent(wiki.benchmark_vs_last_year)}{' '}
                  typical, year on year)
                </span>
              </div>
            </div>
            {wiki.series.length > 3 && <ViewsChart wiki={wiki} />}
          </div>
        )}

        {languages.length > 0 && (
          <div className="attention-block">
            <p className="mini-label">
              Who is looking <span>share of views by language edition, last 12 months</span>
            </p>
            <ul className="share-bars">
              {languages.map((item) => {
                const shift = item.previous_share != null ? item.share - item.previous_share : null
                return (
                  <li key={item.language}>
                    <span className="share-label">{item.name}</span>
                    <span className="share-track">
                      <span className="share-fill" style={{ width: `${(item.share / topShare) * 100}%` }} />
                    </span>
                    <span className="share-value">{plainPercent(item.share)}</span>
                    <span className={`share-shift ${changeTone(shift, 0.005)}`}>
                      {shift == null ? '' : `${shift >= 0 ? '+' : '−'}${Math.abs(shift * 100).toFixed(1)} pt`}
                    </span>
                  </li>
                )
              })}
            </ul>
          </div>
        )}

        {news && (
          <div className="attention-block">
            <p className="mini-label">
              International news <span>GDELT, English-language sources</span>
            </p>
            <div className="attention-stats">
              <div>
                <strong className={changeTone(news.attention_vs_last_year, 0.05)}>{signedPercent(news.attention_vs_last_year)}</strong>
                <span>mentions, last 3 months vs a year earlier</span>
              </div>
              <div>
                <strong>{news.tone_3m != null ? news.tone_3m.toFixed(1) : '—'}</strong>
                <span>
                  tone of tourism coverage
                  {news.tone_3m_last_year != null ? ` (${news.tone_3m_last_year.toFixed(1)} a year earlier)` : ''}
                </span>
              </div>
              <div>
                <strong>{compactNights(news.tourism_articles_12m)}</strong>
                <span>tourism articles in 12 months</span>
              </div>
            </div>
          </div>
        )}

        {topics.length > 0 && (
          <div className="attention-block">
            <p className="mini-label">
              Topics in its tourism coverage <span>share of articles, vs Europe's tourism coverage</span>
            </p>
            <ul className="topic-rows">
              {topics.map((topic) => (
                <li key={topic.topic}>
                  <span className="share-label">{topic.label}</span>
                  <span className="share-track">
                    <span className="share-fill topic" style={{ width: `${Math.min(100, topic.share * 100 * 1.6)}%` }} />
                    {topic.europe_share != null && (
                      <span
                        className="europe-mark"
                        style={{ left: `${Math.min(100, topic.europe_share * 100 * 1.6)}%` }}
                        title={`Europe: ${plainPercent(topic.europe_share)}`}
                      />
                    )}
                  </span>
                  <span className="share-value">{plainPercent(topic.share)}</span>
                  <span className={`share-shift ${topic.lift != null && topic.lift >= 1.5 ? 'hot' : 'flat'}`}>
                    {topic.lift != null ? `${topic.lift.toFixed(1)}×` : ''}
                  </span>
                </li>
              ))}
            </ul>
            <p className="attention-note">The tick marks Europe's share; × is how many times Europe's share.</p>
          </div>
        )}
      </div>
    </section>
  )
}
