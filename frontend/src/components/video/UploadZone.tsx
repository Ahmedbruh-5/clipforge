import { Upload } from 'lucide-react'
import { useRef, useState } from 'react'

import { useToast } from '../common/ToastProvider'
import { getErrorMessage, uploadVideo } from '../../services/api'
import type { Video } from '../../types'

interface Props {
  onUploaded: (video: Video) => void
}

export function UploadZone({ onUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [progress, setProgress] = useState<number | null>(null)
  const [dragging, setDragging] = useState(false)
  const toast = useToast()

  async function handleFile(file: File | undefined) {
    if (!file) return
    setProgress(0)
    try {
      const video = await uploadVideo(file, setProgress)
      onUploaded(video)
      toast.success('Upload complete', video.original_filename)
    } catch (err) {
      toast.error('Upload failed', getErrorMessage(err))
    } finally {
      setProgress(null)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <div
      className={[
        'rounded-lg border border-dashed p-6 transition-colors',
        dragging ? 'border-primary bg-primary/10' : 'border-border bg-card',
      ].join(' ')}
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        void handleFile(e.dataTransfer.files[0])
      }}
    >
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="rounded-full bg-bg-secondary p-3 text-primary">
          <Upload size={22} />
        </div>
        <div>
          <p className="text-sm font-medium">Upload a long-form video</p>
          <p className="mt-1 text-xs text-muted">
            MP4, MOV, MKV, WEBM · max 2 GB · originals are never overwritten
          </p>
        </div>
        <button
          type="button"
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-50"
          disabled={progress !== null}
          onClick={() => inputRef.current?.click()}
        >
          {progress !== null ? `Uploading ${progress}%` : 'Choose file'}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".mp4,.mov,.mkv,.webm,video/*"
          className="hidden"
          onChange={(e) => void handleFile(e.target.files?.[0])}
        />
        {progress !== null && (
          <div className="h-1.5 w-full max-w-sm overflow-hidden rounded bg-bg-secondary">
            <div
              className="h-full bg-primary transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
      </div>
    </div>
  )
}
