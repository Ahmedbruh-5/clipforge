import { Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { StatusBadge } from '../components/common/StatusBadge'
import { useToast } from '../components/common/ToastProvider'
import { UploadZone } from '../components/video/UploadZone'
import { deleteVideo, fetchVideos, getErrorMessage } from '../services/api'
import type { Video } from '../types'
import { formatBytes, formatDateTime12h, formatDuration, formatResolution } from '../utils/format'

export function Library() {
  const [videos, setVideos] = useState<Video[]>([])
  const [loading, setLoading] = useState(true)
  const toast = useToast()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setVideos(await fetchVideos())
    } catch (err) {
      toast.error('Could not load library', getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    void load()
  }, [load])

  async function handleDelete(id: number, name: string) {
    const ok = await toast.confirm({
      title: 'Delete video?',
      description: `“${name}” and all associated clips will be removed. This cannot be undone.`,
      confirmLabel: 'Delete',
      tone: 'danger',
    })
    if (!ok) return
    try {
      await deleteVideo(id)
      setVideos((prev) => prev.filter((v) => v.id !== id))
      toast.success('Video deleted', name)
    } catch (err) {
      toast.error('Delete failed', getErrorMessage(err))
    }
  }

  return (
    <div className="p-6 md:p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Video Library</h1>
        <p className="mt-1 text-sm text-muted">
          Upload source videos. Metadata is extracted with FFprobe/FFmpeg after upload.
        </p>
      </header>

      <UploadZone
        onUploaded={(video) => {
          setVideos((prev) => [video, ...prev])
        }}
      />

      <div className="mt-6 overflow-hidden rounded-lg border border-border bg-card">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border bg-bg-secondary text-xs uppercase text-muted">
            <tr>
              <th className="px-4 py-3 font-medium">File</th>
              <th className="px-4 py-3 font-medium">Uploaded</th>
              <th className="px-4 py-3 font-medium">Duration</th>
              <th className="px-4 py-3 font-medium">Resolution</th>
              <th className="px-4 py-3 font-medium">Codec</th>
              <th className="px-4 py-3 font-medium">Size</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-muted">
                  Loading…
                </td>
              </tr>
            ) : videos.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-muted">
                  No videos uploaded yet.
                </td>
              </tr>
            ) : (
              videos.map((video) => (
                <tr key={video.id} className="border-b border-border/70 last:border-0">
                  <td className="px-4 py-3">
                    <div className="font-medium">{video.original_filename}</div>
                    {video.error_message && (
                      <div className="mt-1 text-xs text-amber-300">{video.error_message}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-muted">
                    {formatDateTime12h(video.created_at)}
                  </td>
                  <td className="px-4 py-3 font-mono text-muted">
                    {formatDuration(video.duration)}
                  </td>
                  <td className="px-4 py-3 text-muted">
                    {formatResolution(video.width, video.height)}
                  </td>
                  <td className="px-4 py-3 text-muted">{video.codec ?? '—'}</td>
                  <td className="px-4 py-3 text-muted">{formatBytes(video.file_size)}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={video.status} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Link
                        to={`/editor?video=${video.id}`}
                        className="rounded-md border border-border px-2.5 py-1.5 text-xs hover:border-primary hover:text-primary"
                      >
                        Edit
                      </Link>
                      <button
                        type="button"
                        className="rounded-md border border-border p-1.5 text-muted hover:border-danger hover:text-danger"
                        onClick={() => void handleDelete(video.id, video.original_filename)}
                        aria-label={`Delete ${video.original_filename}`}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
