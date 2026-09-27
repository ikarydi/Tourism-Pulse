import { NAV, type View } from './nav'
import { NavIcon } from './NavIcon'

export function Sidebar({
  view,
  detailEnabled,
  onNavigate,
  onOpenPalette,
}: {
  view: View
  detailEnabled: boolean
  onNavigate: (view: View) => void
  onOpenPalette: () => void
}) {
  return (
    <nav className="sidebar" aria-label="Main">
      <div className="sidebar-brand">
        <span className="brand-mark">TP</span>
        <span className="sidebar-brand-name">Tourism Pulse</span>
      </div>

      <button type="button" className="sidebar-search" onClick={onOpenPalette}>
        <NavIcon path="M11 18a7 7 0 1 1 0-14 7 7 0 0 1 0 14zM20 20l-4-4" />
        <span>Search or ask</span>
        <kbd>Ctrl K</kbd>
      </button>

      <ul className="sidebar-nav">
        {NAV.map((item) => (
          <li key={item.view}>
            <button
              type="button"
              className={view === item.view ? 'active' : ''}
              aria-current={view === item.view ? 'page' : undefined}
              disabled={item.view === 'detail' && !detailEnabled}
              onClick={() => onNavigate(item.view)}
              title={item.label}
            >
              <NavIcon path={item.icon} />
              <span>{item.label}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}
