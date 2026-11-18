import { RefreshCw, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { Select } from '../components/common/Select'
import { StatusBadge } from '../components/common/StatusBadge'
import { useToast } from '../components/common/ToastProvider'
import {
  cancelSchedule,
  createSchedule,
  deleteSchedule,
  fetchClips,
  fetchSchedules,
  fetchYouTubeStatus,
  getErrorMessage,
  retrySchedule,
} from '../services/api'
import type { Clip, PublishSchedule, YouTubeStatus } from '../types'
import { formatDateTime12h, formatDuration } from '../utils/format'

function toUtcIsoFromLocalInput(value: string): string | null {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toISOString()
}

function formatUtc(value: string | null): string {
  if (!value) return 'Immediate / no publishAt'
  return formatDateTime12h(value)
}

export function Schedule() {
  const toast = useToast()
  const [schedules, setSchedules] = useState<PublishSchedule[]>([])
  const [clips, setClips] = useState<Clip[]>([])
  const [yt, setYt] = useState<YouTubeStatus | null>(null)
  const [filter, setFilter] = useState('all')
  const [busy, setBusy] = useState(false)

  const [clipId, setClipId] = useState('')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [privacy, setPrivacy] = useState('private')
  const [publishLocal, setPublishLocal] = useState('')
  const [timezone] = useState(
    Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  )

  const load = useCallback(async () => {
    try {
      const [scheduleItems, clipItems, status] = await Promise.all([
        fetchSchedules(filter === 'all' ? undefined : filter),
        fetchClips(undefined, { status: 'ready', review_status: 'approved' }),
        fetchYouTubeStatus(),
      ])
      setSchedules(scheduleItems)
      setClips(clipItems)
      setYt(status)
    } catch (err) {
      toast.error('Could not load schedules', getErrorMessage(err))
    }
  }, [filter, toast])

  useEffect(() => {
    void load()
  }, [load])

  const selectableClips = useMemo(
    () => clips.filter((c) => c.status === 'ready' && c.stream_url),
    [clips],
  )

  const clipOptions = useMemo(
    () =>
      selectableClips.map((clip) => ({
        value: String(clip.id),
        label: `#${clip.id} · ${clip.title}`,
        description: formatDuration(clip.duration),
      })),
    [selectableClips],
  )

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!clipId) {
      toast.info('Select a clip', 'Choose a rendered clip before scheduling.')
      return
    }
    setBusy(true)
    try {
      const publishAt = toUtcIsoFromLocalInput(publishLocal)
      const created = await createSchedule(Number(clipId), {
        title: title.trim() || 'ClipForge Short',
        description,
        privacy_status: privacy,
        publish_at: publishAt,
        timezone,
      })
      toast.success('Schedule queued', `Schedule #${created.id} is uploading to YouTube.`)
      setDescription('')
      setPublishLocal('')
      await load()
    } catch (err) {
      toast.error('Schedule failed', getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="p-6 md:p-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Scheduled</h1>
          <p className="mt-1 text-sm text-muted">
            Queue approved, rendered clips for YouTube Shorts. Times are stored in UTC; display
            uses your local timezone ({timezone}).
          </p>
        </div>
        <Link to="/settings" className="text-sm text-primary hover:underline">
          YouTube settings
        </Link>
      </header>

      <div className="mb-4 rounded-lg border border-border bg-card px-4 py-3 text-sm">
        {yt?.connected ? (
          <span>
            Connected{yt.channel_title ? ` as ${yt.channel_title}` : ''}. Uploads use YouTube’s
            native <code className="text-xs">publishAt</code> when a future time is set.
          </span>
        ) : yt?.configured ? (
          <span className="text-muted">
            OAuth is configured but not connected.{' '}
            <Link to="/settings" className="text-primary hover:underline">
              Connect YouTube
            </Link>
          </span>
        ) : (
          <span className="text-muted">
            YouTube not configured yet — you can connect later in Settings. Scheduling requires a
            connected channel.
          </span>
        )}
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(320px,0.9fr)_minmax(0,1.2fr)]">
        <form
          onSubmit={(e) => void handleCreate(e)}
          className="space-y-3 rounded-lg border border-border bg-card p-4"
        >
          <h2 className="text-sm font-medium uppercase tracking-wide text-muted">
            Schedule a clip
          </h2>
          <Select
            label="Rendered clip"
            value={clipId}
            placeholder="Select approved clip"
            options={
              clipOptions.length
                ? clipOptions
                : [{ value: '', label: 'No approved ready clips', disabled: true }]
            }
            onChange={(value) => {
              setClipId(value)
              const clip = selectableClips.find((c) => String(c.id) === value)
              if (clip) setTitle(clip.title.slice(0, 100))
            }}
          />
          <label className="block text-xs text-muted">
            Title
            <input
              required
              maxLength={100}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-bg-secondary px-3 py-2 text-sm text-text"
            />
          </label>
          <label className="block text-xs text-muted">
            Description
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="mt-1 w-full rounded-md border border-border bg-bg-secondary px-3 py-2 text-sm text-text"
            />
          </label>
          <Select
            label="Privacy"
            value={privacy}
            options={[
              { value: 'private', label: 'Private' },
              { value: 'unlisted', label: 'Unlisted' },
              { value: 'public', label: 'Public' },
            ]}
            onChange={setPrivacy}
          />
          <label className="block text-xs text-muted">
            Publish at (local time, optional)
            <input
              type="datetime-local"
              value={publishLocal}
              onChange={(e) => setPublishLocal(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-bg-secondary px-3 py-2 text-sm text-text"
            />
            <span className="mt-1 block text-[11px]">
              If set, ClipForge uploads as private and lets YouTube publish at this time (no need to
              keep the app running).
            </span>
          </label>
          <button
            type="submit"
            disabled={busy || !clipId}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-50"
          >
            {busy ? 'Scheduling…' : 'Upload & schedule'}
          </button>
        </form>

        <section className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-medium uppercase tracking-wide text-muted">
              Schedule list
            </h2>
            <Select
              className="min-w-36"
              size="sm"
              value={filter}
              options={[
                { value: 'all', label: 'All' },
                { value: 'queued', label: 'Queued' },
                { value: 'uploading', label: 'Uploading' },
                { value: 'scheduled', label: 'Scheduled' },
                { value: 'published', label: 'Published' },
                { value: 'failed', label: 'Failed' },
                { value: 'cancelled', label: 'Cancelled' },
              ]}
              onChange={setFilter}
            />
          </div>

          {schedules.length === 0 ? (
            <div className="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted">
              No schedules yet.
            </div>
          ) : (
            <div className="space-y-3">
              {schedules.map((item) => (
                <article
                  key={item.id}
                  className="flex gap-3 rounded-lg border border-border bg-card p-3"
                >
                  {item.thumbnail_url ? (
                    <img
                      src={item.thumbnail_url}
                      alt=""
                      className="h-24 w-14 rounded object-cover"
                    />
                  ) : (
                    <div className="flex h-24 w-14 items-center justify-center rounded bg-bg-secondary text-[10px] text-muted">
                      No thumb
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="font-medium">{item.title}</h3>
                        <p className="mt-1 text-xs text-muted">
                          Clip #{item.clip_id}
                          {item.clip_title ? ` · ${item.clip_title}` : ''}
                        </p>
                      </div>
                      <StatusBadge status={item.status} />
                    </div>
                    <p className="mt-2 text-xs text-muted">
                      Publish: {formatUtc(item.publish_at)} · Privacy: {item.privacy_status}
                    </p>
                    {item.youtube_url && (
                      <a
                        href={item.youtube_url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-1 inline-block text-xs text-primary hover:underline"
                      >
                        {item.youtube_url}
                      </a>
                    )}
                    {item.error_message && (
                      <p className="mt-2 text-xs text-danger">{item.error_message}</p>
                    )}
                    <div className="mt-3 flex flex-wrap gap-2">
                      {(item.status === 'failed' || item.status === 'cancelled') && (
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs hover:border-accent"
                          onClick={() =>
                            void retrySchedule(item.id)
                              .then(async () => {
                                toast.success('Retry queued', `Schedule #${item.id}`)
                                await load()
                              })
                              .catch((err) =>
                                toast.error('Retry failed', getErrorMessage(err)),
                              )
                          }
                        >
                          <RefreshCw size={12} /> Retry
                        </button>
                      )}
                      {(item.status === 'queued' || item.status === 'scheduled') && (
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs text-muted hover:border-danger hover:text-danger"
                          onClick={() =>
                            void toast
                              .confirm({
                                title: 'Cancel schedule?',
                                description:
                                  'This marks it cancelled in ClipForge. It does not delete the YouTube video if it already uploaded.',
                                confirmLabel: 'Cancel schedule',
                                tone: 'danger',
                              })
                              .then(async (ok) => {
                                if (!ok) return
                                try {
                                  await cancelSchedule(item.id)
                                  toast.success('Schedule cancelled')
                                  await load()
                                } catch (err) {
                                  toast.error('Cancel failed', getErrorMessage(err))
                                }
                              })
                          }
                        >
                          Cancel
                        </button>
                      )}
                      {(item.status === 'cancelled' ||
                        item.status === 'failed' ||
                        item.status === 'published' ||
                        item.status === 'scheduled') && (
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs text-muted hover:border-danger hover:text-danger"
                          onClick={() =>
                            void toast
                              .confirm({
                                title: 'Remove from list?',
                                description:
                                  'Deletes this schedule record in ClipForge only. Your local clip and any YouTube upload stay as they are.',
                                confirmLabel: 'Delete',
                                tone: 'danger',
                              })
                              .then(async (ok) => {
                                if (!ok) return
                                try {
                                  await deleteSchedule(item.id)
                                  toast.success('Removed from schedule list')
                                  await load()
                                } catch (err) {
                                  toast.error('Delete failed', getErrorMessage(err))
                                }
                              })
                          }
                        >
                          <Trash2 size={12} /> Delete
                        </button>
                      )}
                      {item.video_id && (
                        <Link
                          to={`/editor?video=${item.video_id}&clip=${item.clip_id}`}
                          className="rounded border border-border px-2 py-1 text-xs hover:border-primary"
                        >
                          Open clip
                        </Link>
                      )}
                    </div>
                    <p className="mt-2 font-mono text-[10px] text-muted">
                      #{item.id} · {formatDateTime12h(item.created_at)}
                    </p>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
