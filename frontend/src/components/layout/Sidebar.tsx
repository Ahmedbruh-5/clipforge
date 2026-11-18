import {
  CalendarClock,
  Clapperboard,
  LayoutDashboard,
  Library,
  ListChecks,
  Settings,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'

const links = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/library', label: 'Video Library', icon: Library },
  { to: '/editor', label: 'Clip Editor', icon: Clapperboard },
  { to: '/review', label: 'Clip Review', icon: ListChecks },
  { to: '/schedule', label: 'Scheduled', icon: CalendarClock },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function Sidebar() {
  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-bg-secondary">
      <div className="border-b border-border px-5 py-5">
        <div className="text-lg font-semibold tracking-tight text-text">ClipForge</div>
        <div className="mt-1 text-xs text-muted">Local clipping studio</div>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-3">
        {links.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              [
                'flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors',
                isActive
                  ? 'bg-card text-text'
                  : 'text-muted hover:bg-card/60 hover:text-text',
              ].join(' ')
            }
          >
            <Icon size={18} strokeWidth={1.75} />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-border px-4 py-3 text-xs text-muted">
        Phase 6 · YouTube schedule
      </div>
    </aside>
  )
}
