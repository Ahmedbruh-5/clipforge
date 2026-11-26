import {
  Eye,
  Film,
  ExternalLink,
  RefreshCw,
  ThumbsUp,
  Users,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { useToast } from '../components/common/ToastProvider'
import {
  fetchYouTubeChannelStats,
  fetchYouTubeShorts,
  fetchYouTubeStatus,
  getErrorMessage,
} from '../services/api'
import type {
  YouTubeChannelStats,
  YouTubeShortStats,
  YouTubeStatus,
} from '../types'
import { formatDateTime12h, formatDuration } from '../utils/format'

function formatCount(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(
    value,
  )
}

function formatExactCount(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat().format(value)
}

export function Analytics() {
  const toast = useToast()
  const [yt, setYt] = useState<YouTubeStatus | null>(null)
  const [channel, setChannel] = useState<YouTubeChannelStats | null>(null)
  const [shorts, setShorts] = useState<YouTubeShortStats[]>([])
  const [nextPage, setNextPage] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setAuthError(null)
    try {
      const status = await fetchYouTubeStatus()
      setYt(status)
      if (!status.connected) {
        setChannel(null)
        setShorts([])
        setNextPage(null)
        return
      }
      const [channelStats, shortsList] = await Promise.all([
        fetchYouTubeChannelStats(),
        fetchYouTubeShorts({ max_results: 25 }),
      ])
      setChannel(channelStats)
      setShorts(shortsList.items)
      setNextPage(shortsList.next_page_token)
    } catch (err) {
      const message = getErrorMessage(err)
      if (/expired|revoked|not connected/i.test(message)) {
        setAuthError(message)
        setChannel(null)
        setShorts([])
        setNextPage(null)
      } else {
        toast.error('Analytics failed to load', message)
      }
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    void load()
  }, [load])

  async function loadMore() {
    if (!nextPage || loadingMore) return
    setLoadingMore(true)
    try {
      const more = await fetchYouTubeShorts({ max_results: 25, page_token: nextPage })
      setShorts((prev) => {
        const seen = new Set(prev.map((item) => item.video_id))
        return [...prev, ...more.items.filter((item) => !seen.has(item.video_id))]
      })
      setNextPage(more.next_page_token)
    } catch (err) {
      toast.error('Could not load more Shorts', getErrorMessage(err))
    } finally {
      setLoadingMore(false)
    }
  }

  const cards = [
    {
      label: 'Subscribers',
      value: channel?.hidden_subscriber_count
        ? 'Hidden'
        : formatCount(channel?.subscriber_count),
      detail: channel?.hidden_subscriber_count
        ? undefined
        : formatExactCount(channel?.subscriber_count),
      icon: Users,
    },
    {
      label: 'Channel views',
      value: formatCount(channel?.view_count),
      detail: formatExactCount(channel?.view_count),
      icon: Eye,
    },
    {
      label: 'Videos',
      value: formatExactCount(channel?.video_count),
      icon: Film,
    },
    {
      label: 'Shorts shown',
      value: formatExactCount(shorts.length),
      icon: ThumbsUp,
    },
  ]

  return (
    <div className="p-6 md:p-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
          <p className="mt-1 text-sm text-muted">
            Review your connected YouTube channel and per-Short view counts.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm text-muted transition-colors hover:border-primary hover:text-text disabled:opacity-50"
        >
          <RefreshCw size={15} className={loading ? 'animate-spin' : undefined} />
          Refresh
        </button>
      </header>

      {yt && !yt.connected && !authError ? (
        <div className="mb-6 rounded-lg border border-border bg-card p-4 text-sm">
          <p className="text-muted">
            Connect YouTube in Settings to load channel stats and Shorts performance.
          </p>
          <Link to="/settings" className="mt-2 inline-block text-primary hover:underline">
            Open Settings
          </Link>
        </div>
      ) : null}

      {authError ? (
        <div className="mb-6 rounded-lg border border-danger/40 bg-card p-4 text-sm">
          <p className="text-text">{authError}</p>
          <Link to="/settings" className="mt-2 inline-block text-primary hover:underline">
            Reconnect in Settings
          </Link>
        </div>
      ) : null}

      {channel ? (
        <div className="mb-6 flex items-center gap-3 rounded-lg border border-border bg-card p-4">
          {channel.thumbnail_url ? (
            <img
              src={channel.thumbnail_url}
              alt=""
              className="h-12 w-12 rounded-full object-cover"
            />
          ) : (
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-bg-secondary text-muted">
              <Users size={20} />
            </div>
          )}
          <div>
            <div className="font-medium">{channel.title ?? 'YouTube channel'}</div>
            <div className="text-xs text-muted font-mono">{channel.channel_id}</div>
          </div>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map(({ label, value, detail, icon: Icon }) => (
          <div key={label} className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-wide text-muted">{label}</span>
              <Icon size={16} className="text-muted" />
            </div>
            <div className="mt-3 text-3xl font-semibold">{loading && !channel ? '—' : value}</div>
            {detail && detail !== value ? (
              <div className="mt-1 text-xs text-muted">{detail}</div>
            ) : null}
          </div>
        ))}
      </div>

      <section className="mt-8">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-medium uppercase tracking-wide text-muted">
              Recent Shorts
            </h2>
            <p className="mt-1 text-xs text-muted">
              Uploads ≤ 3 minutes from your channel, newest first.
            </p>
          </div>
        </div>

        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-bg-secondary text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Short</th>
                <th className="px-4 py-3 font-medium">Published</th>
                <th className="px-4 py-3 font-medium">Duration</th>
                <th className="px-4 py-3 font-medium">Views</th>
                <th className="px-4 py-3 font-medium">Likes</th>
                <th className="px-4 py-3 font-medium" />
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted">
                    Loading channel analytics…
                  </td>
                </tr>
              ) : !yt?.connected || authError ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted">
                    Connect YouTube to see Shorts performance.
                  </td>
                </tr>
              ) : shorts.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted">
                    No Shorts found in recent uploads.
                  </td>
                </tr>
              ) : (
                shorts.map((item) => (
                  <tr key={item.video_id} className="border-b border-border/70 last:border-0">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        {item.thumbnail_url ? (
                          <img
                            src={item.thumbnail_url}
                            alt=""
                            className="h-12 w-8 rounded object-cover bg-bg-secondary"
                          />
                        ) : (
                          <div className="h-12 w-8 rounded bg-bg-secondary" />
                        )}
                        <div className="min-w-0">
                          <div className="truncate font-medium">{item.title}</div>
                          <div className="font-mono text-xs text-muted">{item.video_id}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted">
                      {formatDateTime12h(item.published_at)}
                    </td>
                    <td className="px-4 py-3 font-mono text-muted">
                      {formatDuration(item.duration_seconds)}
                    </td>
                    <td className="px-4 py-3 font-medium" title={formatExactCount(item.view_count)}>
                      {formatCount(item.view_count)}
                    </td>
                    <td className="px-4 py-3 text-muted" title={formatExactCount(item.like_count)}>
                      {formatCount(item.like_count)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <a
                        href={item.youtube_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-primary hover:underline"
                      >
                        Open
                        <ExternalLink size={13} />
                      </a>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {nextPage ? (
          <div className="mt-4 flex justify-center">
            <button
              type="button"
              onClick={() => void loadMore()}
              disabled={loadingMore}
              className="rounded-md border border-border bg-card px-4 py-2 text-sm text-muted transition-colors hover:border-primary hover:text-text disabled:opacity-50"
            >
              {loadingMore ? 'Loading…' : 'Load more uploads'}
            </button>
          </div>
        ) : null}
      </section>
    </div>
  )
}
