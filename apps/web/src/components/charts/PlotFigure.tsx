import { useEffect, useRef, useState } from 'react'

/** Mounts an Observable Plot figure and redraws it at the container's width. */
export function PlotFigure({ build }: { build: (width: number) => Element }) {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)

  useEffect(() => {
    const element = ref.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const element = ref.current
    if (!element || width < 50) return
    const figure = build(width)
    element.replaceChildren(figure)
    return () => figure.remove()
  }, [build, width])

  return <div ref={ref} className="plot-figure" />
}
