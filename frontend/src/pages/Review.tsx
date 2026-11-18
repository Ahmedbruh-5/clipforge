import { Check, ExternalLink, Trash2, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Select } from '../components/common/Select'
import { StatusBadge } from '../components/common/StatusBadge'
import { useToast } from '../components/common/ToastProvider'
import {
  deleteClip,
  fetchClips,
  getErrorMessage,
  updateClip,
} from '../services/api'
import type { Clip } from '../types'
import { formatDuration, formatTimestamp } from '../utils/format'

type ReviewFilter = 'all' | 'pending' | 'approved' | 'rejected'
type StatusFilter = 'all' | 'draft' | 'ready' | 'failed' | 'rendering'

export function Review() {
  const [searchParams, setSearchParams] = useSearchParams()
  const toast = useToast()
  const initialFilter = (searchParams.get('filter') as ReviewFilter) || 'pending'
  const [clips, setClips] = useState<Clip[]>([])
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>(
    ['all', 'pending', 'approved', 'rejected'].includes(initialFilter)
      ? initialFilter
      : 'pending',
  )
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const items = await fetchClips(undefined, {
        review_status: reviewFilter === 'all' ? undefined : reviewFilter,
        status: statusFilter === 'all' ? undefined : statusFilter,
      })
      setClips(items)
    } catch (err) {
      toast.error('Could not load clips', getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [reviewFilter, statusFilter, toast])

  useEffect(() => {
    void load()
  }, [load])

  const counts = useMemo(() => {
    return {
      total: clips.length,
      ready: clips.filter((c) => c.status === 'ready').length,
    }
  }, [clips])

  async function setReview(clip: Clip, review_status: 'approved' | 'rejected' | 'pending') {
    try {
      const updated = await updateClip(clip.id, { review_status })
      setClips((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
      toast.success(
        review_status === 'approved'
          ? 'Clip approved'
          : review_status === 'rejected'
            ? 'Clip rejected'
            : 'Review reset',
        clip.title,
      )
    } catch (err) {
      toast.error('Review update failed', getErrorMessage(err))
    }
  }

  async function handleDelete(clip: Clip) {
    const ok = await toast.confirm({
      title: 'Delete clip?',
      description: `“${clip.title}” will be permanently deleted.`,
      confirmLabel: 'Delete',
      tone: 'danger',
    })
    if (!ok) return
    try {
      await deleteClip(clip.id)
      setClips((prev) => prev.filter((c) => c.id !== clip.id))
      toast.success('Clip deleted', clip.title)
    } catch (err) {
      toast.error('Delete failed', getErrorMessage(err))
    }
  }

  return (
    <div className="p-6 md:p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Clip Review</h1>
        <p className="mt-1 text-sm text-muted">
          Approve or reject clips before scheduling. Rendering status stays separate from review.
        </p>
      </header>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Select
          label="Review"
          className="min-w-40"
          size="sm"
          value={reviewFilter}
          options={[
            { value: 'pending', label: 'Pending' },
            { value: 'approved', label: 'Approved' },
            { value: 'rejected', label: 'Rejected' },
            { value: 'all', label: 'All' },
          ]}
          onChange={(value) => {
            setReviewFilter(value)
            if (value === 'pending') setSearchParams({})
            else setSearchParams({ filter: value })
          }}
        />
        <Select
          label="Render status"
          className="min-w-40"
          size="sm"
          value={statusFilter}
          options={[
            { value: 'all', label: 'All' },
            { value: 'draft', label: 'Draft' },
            { value: 'ready', label: 'Ready' },
            { value: 'rendering', label: 'Rendering' },
            { value: 'failed', label: 'Failed' },
          ]}
          onChange={setStatusFilter}
        />
        <div className="pb-1.5 text-xs text-muted">
          Showing {counts.total} · ready {counts.ready}
        </div>
      </div>

      {loading ? (
        <div className="rounded-lg border border-border bg-card p-8 text-center text-muted">
          Loading clips…
        </div>
      ) : clips.length === 0 ? (
        <div className="rounded-lg border border-border bg-card p-8 text-center text-muted">
          No clips match these filters. Create clips in the editor first.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {clips.map((clip) => (
            <article
              key={clip.id}
              className="flex flex-col overflow-hidden rounded-lg border border-border bg-card"
            >
              <div className="relative aspect-[9/16] max-h-64 bg-bg-secondary">
                {clip.thumbnail_url ? (
                  <img
                    src={clip.thumbnail_url}
                    alt=""
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-muted">
                    No thumbnail
                  </div>
                )}
              </div>
              <div className="flex flex-1 flex-col gap-3 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h2 className="font-medium leading-snug">{clip.title}</h2>
                    <p className="mt-1 text-xs text-muted">
                      {clip.video_title ?? `Video #${clip.video_id}`}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <StatusBadge status={clip.status} />
                    <StatusBadge status={clip.review_status} />
                  </div>
                </div>
                <div className="font-mono text-xs text-muted">
                  {formatTimestamp(clip.start_time)} → {formatTimestamp(clip.end_time)} ·{' '}
                  {formatDuration(clip.duration)}
                </div>
                <div className="text-xs text-muted">
                  {clip.aspect_ratio} · {clip.resolution}
                </div>
                <div className="mt-auto flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded border border-accent/40 px-2 py-1 text-xs text-accent hover:bg-accent/10"
                    onClick={() => void setReview(clip, 'approved')}
                  >
                    <Check size={12} /> Approve
                  </button>
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded border border-danger/40 px-2 py-1 text-xs text-danger hover:bg-danger/10"
                    onClick={() => void setReview(clip, 'rejected')}
                  >
                    <X size={12} /> Reject
                  </button>
                  <Link
                    to={`/editor?video=${clip.video_id}&clip=${clip.id}`}
                    className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs hover:border-primary"
                  >
                    <ExternalLink size={12} /> Edit
                  </Link>
                  {clip.stream_url && (
                    <a
                      href={clip.stream_url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded border border-border px-2 py-1 text-xs hover:border-primary"
                    >
                      Open MP4
                    </a>
                  )}
                  <button
                    type="button"
                    className="rounded border border-border p-1 text-muted hover:border-danger hover:text-danger"
                    onClick={() => void handleDelete(clip)}
                    aria-label={`Delete ${clip.title}`}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
