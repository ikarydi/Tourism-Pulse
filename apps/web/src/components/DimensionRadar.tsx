import type { CSSProperties } from 'react'
import { DIMENSIONS } from '../lib/dimensions'
import type { PulseDimensions } from '../types/pulse'
import './DimensionRadar.css'

const SIZE = 340
const CENTER = SIZE / 2
const RADIUS = 118
const RINGS = [25, 50, 75, 100]

function axisPoint(index: number, valueFraction: number, radius = RADIUS) {
  // 6 axes, 60deg apart, starting at the top (-90deg) going clockwise -
  // matches DIMENSIONS' display order everywhere else in the app.
  const angle = -Math.PI / 2 + (index * Math.PI) / 3
  return {
    x: CENTER + Math.cos(angle) * radius * valueFraction,
    y: CENTER + Math.sin(angle) * radius * valueFraction,
  }
}

function polygonPoints(values: number[]): string {
  return values
    .map((value, index) => {
      const { x, y } = axisPoint(index, Math.max(0, Math.min(1, value / 100)))
      return `${x},${y}`
    })
    .join(' ')
}

export function DimensionRadar({
  dimensions,
  onSelectDimension,
  selectedDimension,
}: {
  dimensions: PulseDimensions
  onSelectDimension?: (key: (typeof DIMENSIONS)[number]['key']) => void
  selectedDimension?: string | null
}) {
  const values = DIMENSIONS.map((dimension) => dimensions[dimension.key])
  const fillPoints = polygonPoints(values)

  return (
    <div className="dimension-radar">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label="Pulse dimensions radar chart">
        {RINGS.map((ring) => (
          <polygon
            key={ring}
            className="radar-ring"
            points={polygonPoints(DIMENSIONS.map(() => ring))}
          />
        ))}
        {DIMENSIONS.map((dimension, index) => {
          const outer = axisPoint(index, 1)
          return (
            <line
              key={dimension.key}
              className="radar-spoke"
              x1={CENTER}
              y1={CENTER}
              x2={outer.x}
              y2={outer.y}
            />
          )
        })}
        <polygon className="radar-fill" points={fillPoints} />
        <polygon className="radar-outline" points={fillPoints} />
        {DIMENSIONS.map((dimension, index) => {
          const value = dimensions[dimension.key]
          const point = axisPoint(index, Math.max(0, Math.min(1, value / 100)))
          const isSelected = selectedDimension === dimension.key
          return (
            <circle
              key={dimension.key}
              className={isSelected ? 'radar-point selected' : 'radar-point'}
              cx={point.x}
              cy={point.y}
              r={isSelected ? 6 : 4.5}
              style={{ fill: dimension.color }}
            />
          )
        })}
      </svg>
      <div className="radar-labels">
        {DIMENSIONS.map((dimension, index) => {
          const labelPoint = axisPoint(index, 1.32, RADIUS)
          const value = dimensions[dimension.key]
          const isSelected = selectedDimension === dimension.key
          return (
            <button
              key={dimension.key}
              type="button"
              className={isSelected ? 'radar-label selected' : 'radar-label'}
              style={{
                left: `${(labelPoint.x / SIZE) * 100}%`,
                top: `${(labelPoint.y / SIZE) * 100}%`,
                '--dim-color': dimension.color,
              } as CSSProperties}
              onClick={() => onSelectDimension?.(dimension.key)}
            >
              <span className="radar-label-dot" />
              <span className="radar-label-text">
                {dimension.short}
                <strong>{Math.round(value)}</strong>
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
