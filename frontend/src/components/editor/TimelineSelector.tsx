import { useMemo, useRef, useState } from 'react'

import type { Clip, DetectionCandidate } from '../../types'
import { formatDuration, formatTimestamp } from '../../utils/format'

interface Props {
  duration: number
  start: number
  end: number
  currentTime: number
  candidates?: DetectionCandidate[]
  clips?: Clip[]
  selectedCandidateId?: number | null
  onStartChange: (value: number) => void
  onEndChange: (value: number) => void
  onRangeChange?: (start: number, end: number) => void
  onSeek: (value: number) => void
  onSelectCandidate?: (candidate: DetectionCandidate) => void
}

type DragMode = 'playhead' | 'start' | 'end' | 'move' | null

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

export function TimelineSelector({
  duration,
  start,
  end,
  currentTime,
  candidates = [],
  clips = [],
  selectedCandidateId = null,
  onStartChange,
  onEndChange,
  onRangeChange,
  onSeek,
  onSelectCandidate,
}: Props) {
  const trackRef = useRef<HTMLDivElement>(null)
  const [zoom, setZoom] = useState(1)
  const [viewStart, setViewStart] = useState(0)
  const [dragMode, setDragMode] = useState<DragMode>(null)
  const dragOrigin = useRef({ time: 0, start: 0, end: 0 })

  const safeDuration = Math.max(duration, 0.001)
  const viewWindow = safeDuration / zoom
  const clampedViewStart = clamp(viewStart, 0, Math.max(0, safeDuration - viewWindow))
  const viewEnd = clampedViewStart + viewWindow

  const toPct = (time: number) =>
    ((time - clampedViewStart) / Math.max(viewWindow, 0.001)) * 100

  const timeFromClientX = (clientX: number) => {
    const rect = trackRef.current?.getBoundingClientRect()
    if (!rect || rect.width <= 0) return clampedViewStart
    const ratio = clamp((clientX - rect.left) / rect.width, 0, 1)
    return clampedViewStart + ratio * viewWindow
  }

  const ticks = useMemo(() => {
    const count = zoom >= 3 ? 12 : zoom >= 2 ? 8 : 6
    const step = viewWindow / count
    return Array.from({ length: count + 1 }, (_, i) => clampedViewStart + i * step)
  }, [clampedViewStart, viewWindow, zoom])

  function beginDrag(mode: DragMode, clientX: number) {
    setDragMode(mode)
    const time = timeFromClientX(clientX)
    dragOrigin.current = { time, start, end }
  }

  function onPointerMove(clientX: number) {
    if (!dragMode) return
    const time = timeFromClientX(clientX)
    if (dragMode === 'playhead') {
      onSeek(time)
      return
    }
    if (dragMode === 'start') {
      onStartChange(clamp(time, 0, end - 0.5))
      return
    }
    if (dragMode === 'end') {
      onEndChange(clamp(time, start + 0.5, safeDuration))
      return
    }
    if (dragMode === 'move') {
      const delta = time - dragOrigin.current.time
      const length = dragOrigin.current.end - dragOrigin.current.start
      let nextStart = dragOrigin.current.start + delta
      let nextEnd = dragOrigin.current.end + delta
      if (nextStart < 0) {
        nextStart = 0
        nextEnd = length
      }
      if (nextEnd > safeDuration) {
        nextEnd = safeDuration
        nextStart = safeDuration - length
      }
      if (onRangeChange) {
        onRangeChange(nextStart, nextEnd)
      } else {
        onStartChange(nextStart)
        onEndChange(nextEnd)
      }
    }
  }

  const startPct = toPct(start)
  const endPct = toPct(end)
  const playPct = toPct(currentTime)

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <div className="flex items-center gap-2">
          <span>Zoom {zoom.toFixed(1)}x</span>
          <button
            type="button"
            className="rounded border border-border px-2 py-1 hover:border-primary"
            onClick={() => setZoom((z) => clamp(z - 0.5, 1, 6))}
          >
            −
          </button>
          <button
            type="button"
            className="rounded border border-border px-2 py-1 hover:border-primary"
            onClick={() => setZoom((z) => clamp(z + 0.5, 1, 6))}
          >
            +
          </button>
          <button
            type="button"
            className="rounded border border-border px-2 py-1 hover:border-primary"
            onClick={() => {
              setZoom(1)
              setViewStart(0)
            }}
          >
            Fit
          </button>
        </div>
        <div className="font-mono">
          view {formatTimestamp(clampedViewStart)} – {formatTimestamp(viewEnd)}
        </div>
      </div>

      {zoom > 1 && (
        <input
          type="range"
          min={0}
          max={Math.max(safeDuration - viewWindow, 0)}
          step={0.01}
          value={clampedViewStart}
          onChange={(e) => setViewStart(Number(e.target.value))}
          className="w-full accent-primary"
          aria-label="Timeline pan"
        />
      )}

      <div className="relative h-4 text-[10px] text-muted">
        {ticks.map((tick) => {
          const pct = toPct(tick)
          if (pct < -2 || pct > 102) return null
          return (
            <span
              key={tick}
              className="absolute -translate-x-1/2 font-mono"
              style={{ left: `${pct}%` }}
            >
              {formatDuration(tick)}
            </span>
          )
        })}
      </div>

      <div
        ref={trackRef}
        className="relative h-16 touch-none select-none overflow-hidden rounded-md border border-border bg-bg-secondary"
        onPointerDown={(e) => {
          if ((e.target as HTMLElement).dataset.handle) return
          beginDrag('playhead', e.clientX)
          onSeek(timeFromClientX(e.clientX))
          ;(e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId)
        }}
        onPointerMove={(e) => onPointerMove(e.clientX)}
        onPointerUp={() => setDragMode(null)}
        onPointerCancel={() => setDragMode(null)}
      >
        {/* Existing clips */}
        {clips.map((clip) => {
          const left = toPct(clip.start_time)
          const right = toPct(clip.end_time)
          if (right < 0 || left > 100) return null
          return (
            <div
              key={`clip-${clip.id}`}
              className="absolute top-1 h-2 rounded-sm bg-accent/35"
              style={{
                left: `${clamp(left, 0, 100)}%`,
                width: `${clamp(right - left, 0.4, 100)}%`,
              }}
              title={clip.title}
            />
          )
        })}

        {/* Detection candidates */}
        {candidates.map((candidate) => {
          const left = toPct(candidate.start_time)
          const right = toPct(candidate.end_time)
          if (right < 0 || left > 100) return null
          const active = candidate.id === selectedCandidateId
          return (
            <button
              key={`cand-${candidate.id}`}
              type="button"
              className={[
                'absolute bottom-1 h-2 rounded-sm border',
                active
                  ? 'border-primary bg-primary/50'
                  : 'border-amber-400/50 bg-amber-400/25 hover:bg-amber-400/40',
              ].join(' ')}
              style={{
                left: `${clamp(left, 0, 100)}%`,
                width: `${clamp(right - left, 0.4, 100)}%`,
              }}
              title={`#${candidate.rank} ${(candidate.score * 100).toFixed(0)}`}
              onClick={(e) => {
                e.stopPropagation()
                onSelectCandidate?.(candidate)
              }}
            />
          )
        })}

        {/* Selection range */}
        <div
          className="absolute inset-y-3 rounded bg-primary/25"
          style={{
            left: `${clamp(startPct, 0, 100)}%`,
            width: `${clamp(endPct - startPct, 0.5, 100)}%`,
          }}
          onPointerDown={(e) => {
            e.stopPropagation()
            beginDrag('move', e.clientX)
            ;(e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId)
          }}
        />

        {/* Start / end handles */}
        <div
          data-handle="start"
          className="absolute top-2 bottom-2 z-10 w-1.5 -translate-x-1/2 cursor-ew-resize rounded bg-primary"
          style={{ left: `${clamp(startPct, 0, 100)}%` }}
          onPointerDown={(e) => {
            e.stopPropagation()
            beginDrag('start', e.clientX)
            ;(e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId)
          }}
        />
        <div
          data-handle="end"
          className="absolute top-2 bottom-2 z-10 w-1.5 -translate-x-1/2 cursor-ew-resize rounded bg-primary"
          style={{ left: `${clamp(endPct, 0, 100)}%` }}
          onPointerDown={(e) => {
            e.stopPropagation()
            beginDrag('end', e.clientX)
            ;(e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId)
          }}
        />

        {/* Playhead */}
        <div
          className="pointer-events-none absolute top-0 bottom-0 z-20 w-0.5 bg-accent"
          style={{ left: `${clamp(playPct, 0, 100)}%` }}
        />
      </div>

      <div className="flex flex-wrap gap-4 text-[11px] text-muted">
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-3 rounded-sm bg-primary/40" /> Selection
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-3 rounded-sm bg-amber-400/40" /> Candidates
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-3 rounded-sm bg-accent/40" /> Existing clips
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-3 w-0.5 bg-accent" /> Playhead
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-xs text-muted">
          Start
          <input
            type="range"
            min={0}
            max={Math.max(end - 0.5, 0)}
            step={0.01}
            value={start}
            onChange={(e) => onStartChange(Number(e.target.value))}
            className="mt-1 w-full accent-primary"
          />
          <span className="mt-1 block font-mono text-sm text-text">
            {formatDuration(start)}
          </span>
        </label>
        <label className="block text-xs text-muted">
          End
          <input
            type="range"
            min={Math.min(start + 0.5, safeDuration)}
            max={safeDuration}
            step={0.01}
            value={end}
            onChange={(e) => onEndChange(Number(e.target.value))}
            className="mt-1 w-full accent-primary"
          />
          <span className="mt-1 block font-mono text-sm text-text">
            {formatDuration(end)}
          </span>
        </label>
      </div>
    </div>
  )
}
