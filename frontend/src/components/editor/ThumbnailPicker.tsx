import { ImagePlus, Trash2 } from 'lucide-react'
import { useRef, useState } from 'react'

import type { Clip } from '../../types'

interface Props {
  clip: Clip | null
  disabled?: boolean
  onUpload: (file: File) => Promise<void>
  onClear: () => Promise<void>
}

export function ThumbnailPicker({ clip, disabled, onUpload, onClear }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  if (!clip) {
    return (
      <div className="rounded-lg border border-border bg-card p-4 text-sm text-muted">
        Create or select a clip to add a custom thumbnail from your system.
      </div>
    )
  }

  async function handleFile(file: File | undefined) {
    if (!file) return
    setLocalError(null)
    setBusy(true)
    try {
      await onUpload(file)
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h2 className="text-sm font-medium uppercase tracking-wide text-muted">Thumbnail</h2>
      <p className="mt-1 text-xs text-muted">
        Choose a JPG/PNG/WEBP from your computer. Custom thumbs are kept when you re-export.
      </p>

      <div className="mt-4 flex items-start gap-4">
        {clip.thumbnail_url ? (
          <img
            src={clip.thumbnail_url}
            alt=""
            className="h-32 w-20 rounded object-cover border border-border"
          />
        ) : (
          <div className="flex h-32 w-20 items-center justify-center rounded border border-dashed border-border bg-bg-secondary text-[10px] text-muted">
            No thumb
          </div>
        )}

        <div className="min-w-0 flex-1 space-y-2">
          <div className="text-xs text-muted">
            Source:{' '}
            <span className="text-text">
              {clip.thumbnail_custom ? 'Custom upload' : clip.thumbnail_url ? 'Auto from video' : 'None'}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={disabled || busy}
              onClick={() => inputRef.current?.click()}
              className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-xs hover:border-primary disabled:opacity-50"
            >
              <ImagePlus size={14} />
              {busy ? 'Uploading…' : 'Choose image'}
            </button>
            {clip.thumbnail_url && (
              <button
                type="button"
                disabled={disabled || busy}
                onClick={() => {
                  setBusy(true)
                  void onClear()
                    .catch((err) =>
                      setLocalError(err instanceof Error ? err.message : 'Clear failed'),
                    )
                    .finally(() => setBusy(false))
                }}
                className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-xs text-muted hover:border-danger hover:text-danger disabled:opacity-50"
              >
                <Trash2 size={14} />
                Remove
              </button>
            )}
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".jpg,.jpeg,.png,.webp,.bmp,image/*"
            className="hidden"
            onChange={(e) => void handleFile(e.target.files?.[0])}
          />
          {localError && <p className="text-xs text-danger">{localError}</p>}
        </div>
      </div>
    </div>
  )
}
