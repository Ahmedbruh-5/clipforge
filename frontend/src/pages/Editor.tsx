import { LoaderCircle, Scissors, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { CandidateList } from '../components/clips/CandidateList'
import { Select } from '../components/common/Select'
import { StatusBadge } from '../components/common/StatusBadge'
import { useToast } from '../components/common/ToastProvider'
import { CropControls } from '../components/editor/CropControls'
import { ThumbnailPicker } from '../components/editor/ThumbnailPicker'
import { TimelineSelector } from '../components/editor/TimelineSelector'
import { VideoPlayer } from '../components/video/VideoPlayer'
import { useJobPolling } from '../hooks/useJobPolling'
import {
  clearClipThumbnail,
  createClip,
  deleteCandidate,
  deleteClip,
  fetchCandidates,
  fetchClips,
  fetchVideos,
  getErrorMessage,
  mediaUrl,
  promoteCandidate,
  renderClip,
  startDetection,
  updateCandidate,
  updateClip,
  uploadClipThumbnail,
} from '../services/api'
import type { Clip, DetectionCandidate, Job, Video } from '../types'
import { formatDuration, formatTimestamp, parseTimestamp } from '../utils/format'

export function Editor() {
  const [searchParams, setSearchParams] = useSearchParams()
  const toast = useToast()
  const selectedVideoId = Number(searchParams.get('video') || 0) || null

  const [videos, setVideos] = useState<Video[]>([])
  const [clips, setClips] = useState<Clip[]>([])
  const [candidates, setCandidates] = useState<DetectionCandidate[]>([])
  const [disclaimer, setDisclaimer] = useState<string>('')
  const [title, setTitle] = useState('Untitled Clip')
  const [startInput, setStartInput] = useState('0')
  const [endInput, setEndInput] = useState('15')
  const [start, setStart] = useState(0)
  const [end, setEnd] = useState(15)
  const [aspectRatio, setAspectRatio] = useState('9:16')
  const [resolution, setResolution] = useState('1080x1920')
  const [cropX, setCropX] = useState(0.5)
  const [cropY, setCropY] = useState(0.5)
  const [currentTime, setCurrentTime] = useState(0)
  const [seekTo, setSeekTo] = useState<number | undefined>()
  const [editingClipId, setEditingClipId] = useState<number | null>(null)
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [detecting, setDetecting] = useState(false)
  const [job, setJob] = useState<Job | null>(null)
  const clipFromQuery = Number(searchParams.get('clip') || 0) || null

  const selectedVideo = useMemo(
    () => videos.find((v) => v.id === selectedVideoId) ?? null,
    [videos, selectedVideoId],
  )

  const duration = selectedVideo?.duration ?? 0

  const loadClips = useCallback(async (videoId: number) => {
    setClips(await fetchClips(videoId))
  }, [])

  const loadCandidates = useCallback(async (videoId: number) => {
    const result = await fetchCandidates(videoId)
    setCandidates(result.items)
    setDisclaimer(result.disclaimer)
  }, [])

  useEffect(() => {
    fetchVideos()
      .then((items) => {
        setVideos(items)
        if (!selectedVideoId && items[0]) {
          setSearchParams({ video: String(items[0].id) })
        }
      })
      .catch((err) => toast.error('Request failed', getErrorMessage(err)))
  }, [selectedVideoId, setSearchParams])

  useEffect(() => {
    if (!selectedVideoId) {
      setClips([])
      setCandidates([])
      return
    }
    loadClips(selectedVideoId).catch((err) => toast.error('Request failed', getErrorMessage(err)))
    loadCandidates(selectedVideoId).catch(() => setCandidates([]))
  }, [selectedVideoId, loadClips, loadCandidates])

  useEffect(() => {
    if (!selectedVideo) return
    const maxEnd =
      selectedVideo.duration && selectedVideo.duration > 1
        ? Math.min(15, selectedVideo.duration)
        : 15
    setStart(0)
    setEnd(maxEnd)
    setStartInput('0')
    setEndInput(String(maxEnd))
    setTitle(`${selectedVideo.original_filename} clip`)
    setAspectRatio('9:16')
    setResolution('1080x1920')
    setCropX(0.5)
    setCropY(0.5)
    setEditingClipId(null)
    setSelectedCandidateId(null)
    setCurrentTime(0)
    setSeekTo(0)
  }, [selectedVideo?.id])

  useEffect(() => {
    if (!clipFromQuery || clips.length === 0) return
    const clip = clips.find((c) => c.id === clipFromQuery)
    if (clip) loadClipIntoEditor(clip)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clipFromQuery, clips])

  const handleJobUpdate = useCallback(
    async (next: Job) => {
      setJob(next)
      if (next.status === 'completed' && selectedVideoId) {
        if (next.job_type === 'render') {
          toast.success('Render complete', 'Clip exported with crop/thumbnail.')
          await loadClips(selectedVideoId)
        }
        if (next.job_type === 'detect') {
          setDetecting(false)
          toast.success('Detection finished', next.message || undefined)
          await loadCandidates(selectedVideoId)
        }
      }
      if (next.status === 'failed') {
        setDetecting(false)
        toast.error('Job failed', next.error_message || undefined)
        if (selectedVideoId) {
          await loadClips(selectedVideoId)
          await loadCandidates(selectedVideoId)
        }
      }
    },
    [selectedVideoId, loadClips, loadCandidates, toast],
  )

  useJobPolling(job, {
    onUpdate: (next) => {
      void handleJobUpdate(next)
    },
    onError: (message) => toast.error('Request failed', message),
  })

  function applyStart(value: number) {
    const next = Math.max(0, Math.min(value, end - 0.5))
    setStart(next)
    setStartInput(next.toFixed(3))
  }

  function applyEnd(value: number) {
    const ceiling = duration > 0 ? duration : value
    const next = Math.max(start + 0.5, Math.min(value, ceiling))
    setEnd(next)
    setEndInput(next.toFixed(3))
  }

  function commitStartInput() {
    const parsed = parseTimestamp(startInput)
    if (parsed == null) {
      setStartInput(start.toFixed(3))
      return
    }
    applyStart(parsed)
  }

  function commitEndInput() {
    const parsed = parseTimestamp(endInput)
    if (parsed == null) {
      setEndInput(end.toFixed(3))
      return
    }
    applyEnd(parsed)
  }

  async function handleSaveClip() {
    if (!selectedVideoId) return
    setBusy(true)
    try {
      const payload = {
        title,
        start_time: start,
        end_time: end,
        aspect_ratio: aspectRatio,
        resolution,
        crop_x: cropX,
        crop_y: cropY,
      }
      if (editingClipId) {
        const updated = await updateClip(editingClipId, payload)
        setClips((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
        toast.success('Clip updated')
      } else {
        const created = await createClip({
          video_id: selectedVideoId,
          ...payload,
        })
        setClips((prev) => [created, ...prev])
        setEditingClipId(created.id)
        toast.success('Clip created', 'Export when you are ready.')
      }
    } catch (err) {
      toast.error('Action failed', getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleRender(clipId: number) {
    try {
      const started = await renderClip(clipId)
      setJob(started)
      setClips((prev) =>
        prev.map((c) => (c.id === clipId ? { ...c, status: 'rendering' } : c)),
      )
      toast.info('Render started', 'Crop, encode, and thumbnail in progress.')
    } catch (err) {
      toast.error('Action failed', getErrorMessage(err))
    }
  }

  async function handleDetect() {
    if (!selectedVideoId) return
    setDetecting(true)
    try {
      const started = await startDetection(selectedVideoId)
      setJob(started)
      toast.info('Detection started', 'Audio, silence, and scene analysis running.')
    } catch (err) {
      setDetecting(false)
      toast.error('Action failed', getErrorMessage(err))
    }
  }

  function loadClipIntoEditor(clip: Clip) {
    setEditingClipId(clip.id)
    setTitle(clip.title)
    setStart(clip.start_time)
    setEnd(clip.end_time)
    setStartInput(clip.start_time.toFixed(3))
    setEndInput(clip.end_time.toFixed(3))
    setAspectRatio(clip.aspect_ratio || '9:16')
    setResolution(clip.resolution || '1080x1920')
    setCropX(clip.crop_x ?? 0.5)
    setCropY(clip.crop_y ?? 0.5)
    setSeekTo(clip.start_time)
    setCurrentTime(clip.start_time)
  }

  function applyCandidate(candidate: DetectionCandidate) {
    setSelectedCandidateId(candidate.id)
    setStart(candidate.start_time)
    setEnd(candidate.end_time)
    setStartInput(candidate.start_time.toFixed(3))
    setEndInput(candidate.end_time.toFixed(3))
    setSeekTo(candidate.start_time)
    setCurrentTime(candidate.start_time)
    setTitle(`Candidate #${candidate.rank}`)
    setEditingClipId(null)
    toast.info(`Loaded candidate #${candidate.rank}`)
  }

  async function handlePromoteCandidate(candidate: DetectionCandidate) {
    if (candidate.promoted) {
      toast.info('Already promoted', `This candidate is already clip #${candidate.promoted_clip_id}.`)
      return
    }
    try {
      const clip = await promoteCandidate(candidate.id, {
        title: `Candidate #${candidate.rank}`,
        aspect_ratio: aspectRatio,
        resolution,
        crop_x: cropX,
        crop_y: cropY,
      })
      setClips((prev) => [clip, ...prev])
      setCandidates((prev) =>
        prev.map((c) =>
          c.id === candidate.id
            ? { ...c, promoted: true, promoted_clip_id: clip.id }
            : c,
        ),
      )
      loadClipIntoEditor(clip)
      toast.success('Candidate promoted', `Clip #${clip.id} created and flagged.`)
    } catch (err) {
      toast.error('Action failed', getErrorMessage(err))
    }
  }

  async function handleDeleteCandidate(candidate: DetectionCandidate) {
    const ok = await toast.confirm({
      title: 'Delete candidate?',
      description: `Candidate #${candidate.rank} will be removed from the list.`,
      confirmLabel: 'Delete',
      tone: 'danger',
    })
    if (!ok) return
    try {
      await deleteCandidate(candidate.id)
      setCandidates((prev) => prev.filter((c) => c.id !== candidate.id))
      if (selectedCandidateId === candidate.id) setSelectedCandidateId(null)
    } catch (err) {
      toast.error('Action failed', getErrorMessage(err))
    }
  }

  async function handleSaveCandidateEdit(
    candidate: DetectionCandidate,
    changes: { start_time: number; end_time: number; label: string },
  ) {
    const updated = await updateCandidate(candidate.id, changes)
    setCandidates((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
    if (selectedCandidateId === candidate.id) applyCandidate(updated)
  }

  async function handleDeleteClip(clip: Clip) {
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
      if (editingClipId === clip.id) setEditingClipId(null)
    } catch (err) {
      toast.error('Action failed', getErrorMessage(err))
    }
  }

  const clipDuration = Math.max(end - start, 0)

  return (
    <div className="p-6 md:p-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Clip Editor</h1>
          <p className="mt-1 text-sm text-muted">
            Zoomable timeline, candidate editing, 9:16 export, and clip promotion.
          </p>
        </div>
        <Select
          label="Source video"
          className="min-w-64"
          value={selectedVideoId ? String(selectedVideoId) : ''}
          placeholder="Select a video"
          options={videos.map((video) => ({
            value: String(video.id),
            label: video.original_filename,
          }))}
          onChange={(id) => {
            if (id) setSearchParams({ video: id })
          }}
        />
      </header>


      {!selectedVideo ? (
        <div className="rounded-lg border border-border bg-card p-8 text-center text-muted">
          Upload a video in the library to begin editing.
        </div>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(340px,0.85fr)]">
          <section className="space-y-4">
            <VideoPlayer
              src={mediaUrl(selectedVideo.stream_url)}
              currentTime={seekTo}
              onTimeUpdate={setCurrentTime}
            />

            <div className="rounded-lg border border-border bg-card p-4">
              <div className="mb-3 flex items-center justify-between text-sm">
                <span className="text-muted">
                  Playhead{' '}
                  <span className="font-mono text-text">{formatTimestamp(currentTime)}</span>
                </span>
                <span className="text-muted">
                  Duration{' '}
                  <span className="font-mono text-text">{formatDuration(duration)}</span>
                </span>
              </div>
              <TimelineSelector
                duration={duration || Math.max(end, 1)}
                start={start}
                end={end}
                currentTime={currentTime}
                candidates={candidates}
                clips={clips}
                selectedCandidateId={selectedCandidateId}
                onStartChange={applyStart}
                onEndChange={applyEnd}
                onRangeChange={(nextStart, nextEnd) => {
                  setStart(nextStart)
                  setEnd(nextEnd)
                  setStartInput(nextStart.toFixed(3))
                  setEndInput(nextEnd.toFixed(3))
                }}
                onSeek={(value) => {
                  setSeekTo(value)
                  setCurrentTime(value)
                }}
                onSelectCandidate={applyCandidate}
              />
            </div>

            <CandidateList
              candidates={candidates}
              disclaimer={disclaimer}
              detecting={detecting}
              selectedCandidateId={selectedCandidateId}
              onDetect={() => void handleDetect()}
              onUse={applyCandidate}
              onPromote={(c) => void handlePromoteCandidate(c)}
              onDelete={(c) => void handleDeleteCandidate(c)}
              onSaveEdit={handleSaveCandidateEdit}
            />
          </section>

          <section className="space-y-4">
            <div className="rounded-lg border border-border bg-card p-4">
              <h2 className="text-sm font-medium uppercase tracking-wide text-muted">
                {editingClipId ? `Edit clip #${editingClipId}` : 'New clip'}
              </h2>

              <label className="mt-4 block text-xs text-muted">
                Title
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="mt-1 w-full rounded-md border border-border bg-bg-secondary px-3 py-2 text-sm text-text outline-none focus:border-primary"
                />
              </label>

              <div className="mt-3 grid grid-cols-2 gap-3">
                <label className="block text-xs text-muted">
                  Start (s or mm:ss)
                  <input
                    value={startInput}
                    onChange={(e) => setStartInput(e.target.value)}
                    onBlur={commitStartInput}
                    onKeyDown={(e) => e.key === 'Enter' && commitStartInput()}
                    className="mt-1 w-full rounded-md border border-border bg-bg-secondary px-3 py-2 font-mono text-sm text-text outline-none focus:border-primary"
                  />
                </label>
                <label className="block text-xs text-muted">
                  End (s or mm:ss)
                  <input
                    value={endInput}
                    onChange={(e) => setEndInput(e.target.value)}
                    onBlur={commitEndInput}
                    onKeyDown={(e) => e.key === 'Enter' && commitEndInput()}
                    className="mt-1 w-full rounded-md border border-border bg-bg-secondary px-3 py-2 font-mono text-sm text-text outline-none focus:border-primary"
                  />
                </label>
              </div>

              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  className="rounded-md border border-border px-3 py-1.5 text-xs hover:border-primary"
                  onClick={() => {
                    applyStart(currentTime)
                    setSeekTo(currentTime)
                  }}
                >
                  Set start to playhead
                </button>
                <button
                  type="button"
                  className="rounded-md border border-border px-3 py-1.5 text-xs hover:border-primary"
                  onClick={() => {
                    applyEnd(currentTime)
                    setSeekTo(currentTime)
                  }}
                >
                  Set end to playhead
                </button>
              </div>

              <div className="mt-4 rounded-md bg-bg-secondary px-3 py-2 text-sm">
                Selected duration:{' '}
                <span className="font-mono font-medium">{formatDuration(clipDuration)}</span>
                <span className="text-muted"> ({clipDuration.toFixed(2)}s)</span>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busy || clipDuration < 0.5}
                  onClick={() => void handleSaveClip()}
                  className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-50"
                >
                  <Scissors size={16} />
                  {editingClipId ? 'Update clip' : 'Create clip'}
                </button>
                {editingClipId && (
                  <button
                    type="button"
                    className="rounded-md border border-border px-4 py-2 text-sm hover:border-primary"
                    onClick={() => {
                      setEditingClipId(null)
                      setTitle(`${selectedVideo.original_filename} clip`)
                    }}
                  >
                    New selection
                  </button>
                )}
              </div>
            </div>

            <CropControls
              aspectRatio={aspectRatio}
              resolution={resolution}
              cropX={cropX}
              cropY={cropY}
              onAspectRatioChange={setAspectRatio}
              onResolutionChange={setResolution}
              onCropXChange={setCropX}
              onCropYChange={setCropY}
            />

            <ThumbnailPicker
              clip={clips.find((c) => c.id === editingClipId) ?? null}
              onUpload={async (file) => {
                if (!editingClipId) return
                try {
                  const updated = await uploadClipThumbnail(editingClipId, file)
                  setClips((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
                  toast.success('Thumbnail uploaded')
                } catch (err) {
                  toast.error('Action failed', getErrorMessage(err))
                  throw err
                }
              }}
              onClear={async () => {
                if (!editingClipId) return
                try {
                  const updated = await clearClipThumbnail(editingClipId)
                  setClips((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
                  toast.success('Thumbnail removed', 'Export again to auto-generate one.')
                } catch (err) {
                  toast.error('Action failed', getErrorMessage(err))
                  throw err
                }
              }}
            />

            <div className="rounded-lg border border-border bg-card p-4">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-medium uppercase tracking-wide text-muted">
                  Clips for this video
                </h2>
                {job && (job.status === 'queued' || job.status === 'running') && (
                  <span className="inline-flex items-center gap-1 text-xs text-amber-300">
                    <LoaderCircle size={12} className="animate-spin" />
                    {job.job_type} {Math.round(job.progress)}%
                  </span>
                )}
              </div>

              <div className="space-y-2">
                {clips.length === 0 ? (
                  <p className="text-sm text-muted">No clips yet.</p>
                ) : (
                  clips.map((clip) => (
                    <div
                      key={clip.id}
                      className="rounded-md border border-border bg-bg-secondary p-3"
                    >
                      <div className="flex items-start gap-3">
                        {clip.thumbnail_url ? (
                          <img
                            src={clip.thumbnail_url}
                            alt=""
                            className="h-20 w-12 rounded object-cover"
                          />
                        ) : (
                          <div className="flex h-20 w-12 items-center justify-center rounded bg-card text-[10px] text-muted">
                            No thumb
                          </div>
                        )}
                        <div className="min-w-0 flex-1">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="font-medium">{clip.title}</div>
                              <div className="mt-1 font-mono text-xs text-muted">
                                {formatTimestamp(clip.start_time)} →{' '}
                                {formatTimestamp(clip.end_time)} ·{' '}
                                {formatDuration(clip.duration)}
                              </div>
                              <div className="mt-1 text-xs text-muted">
                                {clip.aspect_ratio} · {clip.resolution}
                              </div>
                            </div>
                            <StatusBadge status={clip.status} />
                          </div>
                          {clip.error_message && (
                            <p className="mt-2 text-xs text-danger">{clip.error_message}</p>
                          )}
                          <div className="mt-3 flex flex-wrap gap-2">
                            <button
                              type="button"
                              className="rounded border border-border px-2 py-1 text-xs hover:border-primary"
                              onClick={() => loadClipIntoEditor(clip)}
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              className="rounded border border-border px-2 py-1 text-xs hover:border-accent"
                              disabled={clip.status === 'rendering'}
                              onClick={() => void handleRender(clip.id)}
                            >
                              Export
                            </button>
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
                              onClick={() => void handleDeleteClip(clip)}
                              aria-label={`Delete ${clip.title}`}
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
