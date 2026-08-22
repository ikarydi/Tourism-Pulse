import { DIMENSIONS } from '../lib/dimensions'
import type { DimensionKey, PulseDimensions } from '../types/pulse'
import './DimensionList.css'

export function DimensionList({
  dimensions,
  selectedDimension,
  onSelectDimension,
}: {
  dimensions: PulseDimensions
  selectedDimension: DimensionKey | null
  onSelectDimension: (key: DimensionKey) => void
}) {
  return (
    <ul className="dimension-list">
      {DIMENSIONS.map((dimension) => {
        const value = dimensions[dimension.key]
        const isSelected = selectedDimension === dimension.key
        return (
          <li key={dimension.key}>
            <button
              type="button"
              className={isSelected ? 'dimension-row selected' : 'dimension-row'}
              onClick={() => onSelectDimension(dimension.key)}
            >
              <span className="dimension-row-label">{dimension.label}</span>
              <span className="dimension-row-track">
                <span
                  className="dimension-row-fill"
                  style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: dimension.color }}
                />
              </span>
              <span className="dimension-row-value">{value === 0 ? '—' : Math.round(value)}</span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
