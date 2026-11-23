import { Music2, Trash2, Upload } from 'lucide-react'
import { useEffect, useRef } from 'react'

import type { MusicTrack } from '../../types'
import { Select } from '../common/Select'

interface Props {
  muteOriginal: boolean
  addMusic: boolean
  musicTrackKey: string | null
  musicVolume: number
  tracks: MusicTrack[]
  uploading?: boolean
  onMuteOriginalChange: (mute: boolean) => void
  onAddMusicChange: (add: boolean) => void
  onTrackChange: (key: string | null) => void
  onVolumeChange: (volume: number) => void
  onUpload: (file: File) => void
  onDeleteUserTrack: (track: MusicTrack) => void
}

export function AudioControls({
  muteOriginal,
  addMusic,
  musicTrackKey,
  musicVolume,
  tracks,
  uploading,
  onMuteOriginalChange,
  onAddMusicChange,
  onTrackChange,
  onVolumeChange,
  onUpload,
  onDeleteUserTrack,
}: Props) {
  const fileRef = useRef<HTMLInputElement>(null)
  const builtin = tracks.filter((t) => t.source === 'builtin')
  const user = tracks.filter((t) => t.source === 'user')
  const selected = tracks.find((t) => t.key === musicTrackKey) ?? null

  const trackOptions = [
    ...builtin.map((t) => ({
      value: t.key,
      label: t.title,
      description: t.license ? `${t.license}${t.artist ? ` · ${t.artist}` : ''}` : undefined,
    })),
    ...user.map((t) => ({
      value: t.key,
      label: t.title,
      description: 'Uploaded',
    })),
  ]

  // Keep selection in sync when Add music is on but no key is set yet
  useEffect(() => {
    if (!addMusic || musicTrackKey) return
    const fallback = tracks[0]?.key
    if (fallback) onTrackChange(fallback)
  }, [addMusic, musicTrackKey, tracks, onTrackChange])

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2 text-sm font-medium uppercase tracking-wide text-muted">
        <Music2 size={14} />
        Audio
      </div>
      <p className="mt-1 text-xs text-muted">
        Optional. Mute and add music can both be on. Preview should play the bed; Export
        bakes it into the clip file.
      </p>

      <div className="mt-3 space-y-2">
        <label className="flex cursor-pointer items-start gap-2.5 rounded-md border border-border bg-bg-secondary/50 px-3 py-2.5 text-sm">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={muteOriginal || addMusic}
            disabled={addMusic}
            onChange={(e) => onMuteOriginalChange(e.target.checked)}
          />
          <span>
            <span className="font-medium">Mute original audio</span>
            <span className="mt-0.5 block text-xs text-muted">
              {addMusic
                ? 'On while music is added (source soundtrack stays off).'
                : 'Export without the video soundtrack.'}
            </span>
          </span>
        </label>

        <label className="flex cursor-pointer items-start gap-2.5 rounded-md border border-border bg-bg-secondary/50 px-3 py-2.5 text-sm">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={addMusic}
            onChange={(e) => {
              const on = e.target.checked
              onAddMusicChange(on)
              if (on) {
                onMuteOriginalChange(true)
                if (!musicTrackKey && trackOptions[0]) {
                  onTrackChange(trackOptions[0].value)
                }
              }
            }}
          />
          <span>
            <span className="font-medium">Add music</span>
            <span className="mt-0.5 block text-xs text-muted">
              Replace with a built-in or uploaded track.
            </span>
          </span>
        </label>
      </div>

      {addMusic && (
        <div className="mt-3 space-y-3 border-t border-border pt-3">
          {trackOptions.length > 0 ? (
            <Select
              label="Track"
              size="sm"
              value={musicTrackKey ?? trackOptions[0].value}
              placeholder="Select a track…"
              options={trackOptions}
              onChange={(value) => onTrackChange(value)}
            />
          ) : (
            <p className="text-xs text-muted">No tracks yet — upload an MP3/WAV to get started.</p>
          )}

          {selected?.attribution && (
            <p className="text-[10px] leading-snug text-muted">{selected.attribution}</p>
          )}

          <label className="block text-xs text-muted">
            Music volume ({Math.round(musicVolume * 100)}%)
            <input
              type="range"
              min={0}
              max={2}
              step={0.05}
              value={musicVolume}
              onChange={(e) => onVolumeChange(Number(e.target.value))}
              className="mt-1 w-full accent-[var(--color-primary,#3b82f6)]"
            />
          </label>

          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={fileRef}
              type="file"
              accept=".mp3,.wav,.m4a,.ogg,.aac,audio/*"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0]
                e.target.value = ''
                if (file) onUpload(file)
              }}
            />
            <button
              type="button"
              disabled={uploading}
              onClick={() => fileRef.current?.click()}
              className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs hover:border-primary disabled:opacity-50"
            >
              <Upload size={12} />
              {uploading ? 'Uploading…' : 'Upload music'}
            </button>
            {selected?.source === 'user' && (
              <button
                type="button"
                onClick={() => onDeleteUserTrack(selected)}
                className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs text-muted hover:border-danger hover:text-danger"
              >
                <Trash2 size={12} />
                Delete upload
              </button>
            )}
          </div>

          <div className="rounded-md bg-bg-secondary px-3 py-2 text-[11px] leading-relaxed text-muted">
            Need more free tracks? Download from{' '}
            <a
              className="text-text underline hover:text-primary"
              href="https://mixkit.co/free-stock-music/"
              target="_blank"
              rel="noreferrer"
            >
              Mixkit
            </a>
            ,{' '}
            <a
              className="text-text underline hover:text-primary"
              href="https://pixabay.com/music/"
              target="_blank"
              rel="noreferrer"
            >
              Pixabay
            </a>
            , or{' '}
            <a
              className="text-text underline hover:text-primary"
              href="https://archive.org/details/freemusicarchive"
              target="_blank"
              rel="noreferrer"
            >
              Internet Archive
            </a>
            , then use <span className="text-text">Upload music</span>. Check each
            track&apos;s license before use.
          </div>
        </div>
      )}
    </div>
  )
}
