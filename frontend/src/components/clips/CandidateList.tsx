import { Check, Flag, Pencil, Sparkles, Trash2, X } from 'lucide-react'
import { useState } from 'react'

import type { DetectionCandidate } from '../../types'
import { formatDuration, formatTimestamp } from '../../utils/format'

interface Props {
  candidates: DetectionCandidate[]
  disclaimer?: string
  detecting: boolean
  selectedCandidateId?: number | null
  onDetect: () => void
  onUse: (candidate: DetectionCandidate) => void
  onPromote: (candidate: DetectionCandidate) => void
  onDelete: (candidate: DetectionCandidate) => void
  onSaveEdit: (
    candidate: DetectionCandidate,
    changes: { start_time: number; end_time: number; label: string },
  ) => Promise<void>
}

export function CandidateList({
  candidates,
  disclaimer,
  detecting,
  selectedCandidateId = null,
  onDetect,
  onUse,
  onPromote,
  onDelete,
  onSaveEdit,
}: Props) {
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editStart, setEditStart] = useState('')
  const [editEnd, setEditEnd] = useState('')
  const [editLabel, setEditLabel] = useState('')
  const [saving, setSaving] = useState(false)

  function beginEdit(candidate: DetectionCandidate) {
    setEditingId(candidate.id)
    setEditStart(candidate.start_time.toFixed(3))
    setEditEnd(candidate.end_time.toFixed(3))
    setEditLabel(candidate.label)
  }

  async function saveEdit(candidate: DetectionCandidate) {
    const start = Number(editStart)
    const end = Number(editEnd)
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return
    setSaving(true)
    try {
      await onSaveEdit(candidate, {
        start_time: start,
        end_time: end,
        label: editLabel,
      })
      setEditingId(null)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium uppercase tracking-wide text-muted">
            Detection candidates
          </h2>
          <p className="mt-1 text-xs text-muted">
            Edit ranges, promote to clips, or load into the timeline.
          </p>
        </div>
        <button
          type="button"
          disabled={detecting}
          onClick={onDetect}
          className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-xs hover:border-primary disabled:opacity-50"
        >
          <Sparkles size={14} />
          {detecting ? 'Detecting…' : 'Run detection'}
        </button>
      </div>

      {disclaimer && candidates.length > 0 && (
        <p className="mb-3 rounded-md bg-bg-secondary px-3 py-2 text-xs text-muted">
          {disclaimer}
        </p>
      )}

      <div className="max-h-96 space-y-2 overflow-auto">
        {candidates.length === 0 ? (
          <p className="text-sm text-muted">
            No candidates yet. Run detection after uploading a video.
          </p>
        ) : (
          candidates.map((candidate) => {
            const selected = candidate.id === selectedCandidateId
            const editing = editingId === candidate.id
            const promoted = Boolean(candidate.promoted)
            return (
              <div
                key={candidate.id}
                className={[
                  'rounded-md border bg-bg-secondary p-3',
                  promoted
                    ? 'border-accent/50'
                    : selected
                      ? 'border-primary'
                      : 'border-border',
                ].join(' ')}
              >
                {editing ? (
                  <div className="space-y-2">
                    <input
                      value={editLabel}
                      onChange={(e) => setEditLabel(e.target.value)}
                      className="w-full rounded border border-border bg-card px-2 py-1 text-sm"
                      placeholder="Label"
                    />
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        value={editStart}
                        onChange={(e) => setEditStart(e.target.value)}
                        className="rounded border border-border bg-card px-2 py-1 font-mono text-xs"
                        placeholder="Start"
                      />
                      <input
                        value={editEnd}
                        onChange={(e) => setEditEnd(e.target.value)}
                        className="rounded border border-border bg-card px-2 py-1 font-mono text-xs"
                        placeholder="End"
                      />
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        disabled={saving}
                        className="inline-flex items-center gap-1 rounded border border-accent/40 px-2 py-1 text-xs text-accent"
                        onClick={() => void saveEdit(candidate)}
                      >
                        <Check size={12} /> Save
                      </button>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs"
                        onClick={() => setEditingId(null)}
                      >
                        <X size={12} /> Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
                          <span>
                            #{candidate.rank} · {candidate.label}
                          </span>
                          {promoted && (
                            <span className="inline-flex items-center gap-1 rounded border border-accent/40 bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-accent">
                              <Flag size={10} />
                              Promoted
                              {candidate.promoted_clip_id
                                ? ` · clip #${candidate.promoted_clip_id}`
                                : ''}
                            </span>
                          )}
                        </div>
                        <div className="mt-1 font-mono text-xs text-muted">
                          {formatTimestamp(candidate.start_time)} →{' '}
                          {formatTimestamp(candidate.end_time)} ·{' '}
                          {formatDuration(candidate.duration)}
                        </div>
                      </div>
                      <div className="text-right text-xs">
                        <div className="font-mono text-accent">
                          {(candidate.score * 100).toFixed(0)}
                        </div>
                        <div className="text-muted">score</div>
                      </div>
                    </div>
                    <div className="mt-2 grid grid-cols-3 gap-2 text-[11px] text-muted">
                      <span>Audio {(candidate.audio_score * 100).toFixed(0)}%</span>
                      <span>Scene {(candidate.scene_score * 100).toFixed(0)}%</span>
                      <span>Motion {(candidate.visual_score * 100).toFixed(0)}%</span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="rounded border border-border px-2 py-1 text-xs hover:border-primary"
                        onClick={() => onUse(candidate)}
                      >
                        Use on timeline
                      </button>
                      <button
                        type="button"
                        disabled={promoted}
                        className={[
                          'rounded border px-2 py-1 text-xs',
                          promoted
                            ? 'cursor-not-allowed border-accent/30 text-accent/70'
                            : 'border-border hover:border-accent',
                        ].join(' ')}
                        onClick={() => onPromote(candidate)}
                        title={
                          promoted
                            ? 'Already promoted — open the clip from the list below'
                            : 'Save this candidate as a clip'
                        }
                      >
                        {promoted ? 'Already promoted' : 'Promote to clip'}
                      </button>
                      <button
                        type="button"
                        className="rounded border border-border p-1 text-muted hover:border-primary"
                        onClick={() => beginEdit(candidate)}
                        aria-label="Edit candidate"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        type="button"
                        className="rounded border border-border p-1 text-muted hover:border-danger hover:text-danger"
                        onClick={() => onDelete(candidate)}
                        aria-label="Delete candidate"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
