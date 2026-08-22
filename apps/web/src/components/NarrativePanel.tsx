import './NarrativePanel.css'

export function NarrativePanel({
  narrative,
  headline,
  strengths,
  weaknesses,
}: {
  narrative: string | null
  headline: string
  strengths: string[]
  weaknesses: string[]
}) {
  return (
    <article className="card narrative-panel">
      <div className="narrative-heading">
        <div>
          <p className="eyebrow">Intelligence</p>
          <h2>{headline}</h2>
        </div>
        {narrative && <span className="badge ai-badge">AI-generated</span>}
      </div>

      {narrative ? (
        <p className="narrative-text">{narrative}</p>
      ) : (
        <p className="narrative-fallback">
          No AI narrative available for this reading yet - configure{' '}
          <code>GROQ_API_KEY</code> on the API to enable it (a free key is available at{' '}
          <a href="https://console.groq.com" target="_blank" rel="noreferrer">
            console.groq.com
          </a>
          ). The deterministic findings below are always available regardless.
        </p>
      )}

      <div className="narrative-columns">
        <div>
          <p className="mini-label positive">Strengths</p>
          <ul>
            {strengths.length ? (
              strengths.map((item) => <li key={item}>{item}</li>)
            ) : (
              <li className="empty-note">No clear strengths detected.</li>
            )}
          </ul>
        </div>
        <div>
          <p className="mini-label caution">Watch</p>
          <ul>
            {weaknesses.length ? (
              weaknesses.map((item) => <li key={item}>{item}</li>)
            ) : (
              <li className="empty-note">No clear weaknesses detected.</li>
            )}
          </ul>
        </div>
      </div>
    </article>
  )
}
