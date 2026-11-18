import { Clapperboard, Film, CalendarClock, ListChecks } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { StatusBadge } from '../components/common/StatusBadge'
import { useToast } from '../components/common/ToastProvider'
import { fetchDashboard, getErrorMessage } from '../services/api'
import type { DashboardStats } from '../types'
import { formatBytes, formatDuration } from '../utils/format'

export function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const toast = useToast()

  useEffect(() => {
    fetchDashboard()
      .then(setStats)
      .catch((err) => toast.error('Dashboard failed to load', getErrorMessage(err)))
  }, [toast])

  const cards = [
    { label: 'Uploaded videos', value: stats?.total_videos ?? '—', icon: Film },
    { label: 'Generated clips', value: stats?.total_clips ?? '—', icon: Clapperboard },
    {
      label: 'Awaiting review',
      value: stats?.clips_pending_review ?? stats?.clips_draft ?? '—',
      icon: ListChecks,
      to: '/review',
    },
    {
      label: 'Approved clips',
      value: stats?.clips_approved ?? 0,
      icon: CalendarClock,
      to: '/review?filter=approved',
    },
  ]

  return (
    <div className="p-6 md:p-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-muted">
          Local-first clipping overview. Review approved clips before YouTube scheduling.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map(({ label, value, icon: Icon, to }) => {
          const inner = (
            <>
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase tracking-wide text-muted">{label}</span>
                <Icon size={16} className="text-muted" />
              </div>
              <div className="mt-3 text-3xl font-semibold">{value}</div>
            </>
          )
          return to ? (
            <Link
              key={label}
              to={to}
              className="rounded-lg border border-border bg-card p-4 transition-colors hover:border-primary"
            >
              {inner}
            </Link>
          ) : (
            <div key={label} className="rounded-lg border border-border bg-card p-4">
              {inner}
            </div>
          )
        })}
      </div>

      <section className="mt-8">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium uppercase tracking-wide text-muted">
            Recent videos
          </h2>
          <div className="flex gap-3 text-sm">
            <Link to="/review" className="text-primary hover:underline">
              Review clips
            </Link>
            <Link to="/library" className="text-primary hover:underline">
              Open library
            </Link>
          </div>
        </div>
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-bg-secondary text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Duration</th>
                <th className="px-4 py-3 font-medium">Size</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Clips</th>
              </tr>
            </thead>
            <tbody>
              {(stats?.recent_videos ?? []).length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted">
                    No videos yet. Upload one from the library.
                  </td>
                </tr>
              ) : (
                stats?.recent_videos.map((video) => (
                  <tr key={video.id} className="border-b border-border/70 last:border-0">
                    <td className="px-4 py-3">
                      <Link
                        to={`/editor?video=${video.id}`}
                        className="font-medium hover:text-primary"
                      >
                        {video.original_filename}
                      </Link>
                    </td>
                    <td className="px-4 py-3 font-mono text-muted">
                      {formatDuration(video.duration)}
                    </td>
                    <td className="px-4 py-3 text-muted">{formatBytes(video.file_size)}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={video.status} />
                    </td>
                    <td className="px-4 py-3 text-muted">{video.clip_count}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
