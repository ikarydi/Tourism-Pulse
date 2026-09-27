export type View = 'dashboard' | 'explore' | 'map' | 'observatory' | 'destinations' | 'detail'

export const NAV: { view: View; label: string; description: string; icon: string }[] = [
  {
    view: 'dashboard',
    label: 'Dashboard',
    description: 'Your own charts, refreshed from the live API.',
    icon: 'M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z',
  },
  {
    view: 'explore',
    label: 'Explore',
    description: 'Combine any stored data into a chart, or ask a question.',
    icon: 'M4 19V5M4 19h16M8 15l3-4 3 2 4-6',
  },
  {
    view: 'map',
    label: 'Map',
    description: 'Live Pulse and trends across European destinations.',
    icon: 'M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14',
  },
  {
    view: 'observatory',
    label: 'Pressure observatory',
    description: 'Official tourism-pressure indicators, ranked against every European region.',
    icon: 'M12 3a9 9 0 1 0 9 9M12 12l6-6M12 7v5h5',
  },
  {
    view: 'destinations',
    label: 'Destinations',
    description: 'Every destination and country with its current Pulse.',
    icon: 'M4 6h16M4 12h16M4 18h10',
  },
  {
    view: 'detail',
    label: 'Destination',
    description: 'Evidence, narrative and indicators for one place.',
    icon: 'M12 21s-7-6.2-7-11a7 7 0 1 1 14 0c0 4.8-7 11-7 11zM12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z',
  },
]
