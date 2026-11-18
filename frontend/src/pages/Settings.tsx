import { Link2, Unlink } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { useToast } from '../components/common/ToastProvider'
import {
  connectYouTube,
  disconnectYouTube,
  fetchYouTubeStatus,
  getErrorMessage,
} from '../services/api'
import type { YouTubeStatus } from '../types'

export function Settings() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [status, setStatus] = useState<YouTubeStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const toast = useToast()

  const load = useCallback(async () => {
    try {
      setStatus(await fetchYouTubeStatus())
    } catch (err) {
      toast.error('Could not load YouTube status', getErrorMessage(err))
    }
  }, [toast])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const result = searchParams.get('youtube')
    if (!result) return
    if (result === 'connected') {
      toast.success('YouTube connected', 'Your channel is ready for scheduling.')
      void load()
    } else if (result === 'error') {
      toast.error(
        'YouTube connection failed',
        searchParams.get('reason') || 'Authorization was cancelled or failed.',
      )
    }
    setSearchParams({}, { replace: true })
  }, [searchParams, setSearchParams, load, toast])

  async function handleConnect() {
    setBusy(true)
    try {
      const result = await connectYouTube()
      if (!result.configured || !result.auth_url) {
        toast.info(
          'Connect later',
          result.message ||
            'Add Google OAuth credentials to backend/.env when you are ready.',
        )
        return
      }
      toast.info('Redirecting to Google', 'Complete sign-in to connect YouTube.')
      window.location.href = result.auth_url
    } catch (err) {
      toast.error('Connect failed', getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleDisconnect() {
    const ok = await toast.confirm({
      title: 'Disconnect YouTube?',
      description: 'Local OAuth tokens will be removed from this machine.',
      confirmLabel: 'Disconnect',
      tone: 'danger',
    })
    if (!ok) return
    setBusy(true)
    try {
      await disconnectYouTube()
      toast.success('YouTube disconnected')
      await load()
    } catch (err) {
      toast.error('Disconnect failed', getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="p-6 md:p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted">
          Local defaults and YouTube account connection. Refresh tokens never leave the backend.
        </p>
      </header>

      <div className="space-y-4">
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="text-sm font-medium">YouTube connection</h2>
          <p className="mt-1 text-sm text-muted">
            Connect when ready. The rest of ClipForge works without YouTube.
          </p>

          <div className="mt-4 grid gap-2 text-sm">
            <div className="flex justify-between gap-3">
              <span className="text-muted">OAuth configured</span>
              <span>{status?.configured ? 'Yes' : 'Not yet — connect later'}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-muted">Channel connected</span>
              <span>{status?.connected ? 'Yes' : 'No'}</span>
            </div>
            {status?.channel_title && (
              <div className="flex justify-between gap-3">
                <span className="text-muted">Channel</span>
                <span>{status.channel_title}</span>
              </div>
            )}
            <div className="flex justify-between gap-3">
              <span className="text-muted">Redirect URI</span>
              <span className="font-mono text-xs text-muted">{status?.redirect_uri}</span>
            </div>
          </div>

          {status?.setup_hint && (
            <div className="mt-4 rounded-md bg-bg-secondary px-3 py-3 text-xs text-muted">
              <p className="font-medium text-text">Connect later setup</p>
              <ol className="mt-2 list-decimal space-y-1 pl-4">
                <li>Create a Google Cloud project and enable YouTube Data API v3</li>
                <li>Create OAuth client credentials</li>
                <li>
                  Add authorized redirect URI:{' '}
                  <code className="text-text">{status.redirect_uri}</code>
                </li>
                <li>
                  Put <code className="text-text">GOOGLE_CLIENT_ID</code> and{' '}
                  <code className="text-text">GOOGLE_CLIENT_SECRET</code> in{' '}
                  <code className="text-text">backend/.env</code>
                </li>
                <li>Restart the backend, then click Connect YouTube</li>
              </ol>
              <p className="mt-2">{status.setup_hint}</p>
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => void handleConnect()}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-50"
            >
              <Link2 size={16} />
              {status?.connected ? 'Reconnect YouTube' : 'Connect YouTube'}
            </button>
            {status?.connected && (
              <button
                type="button"
                disabled={busy}
                onClick={() => void handleDisconnect()}
                className="inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 text-sm hover:border-danger hover:text-danger disabled:opacity-50"
              >
                <Unlink size={16} />
                Disconnect
              </button>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="text-sm font-medium">Current defaults</h2>
          <ul className="mt-3 space-y-2 text-sm text-muted">
            <li>Upload limit: 2 GB</li>
            <li>Formats: MP4, MOV, MKV, WEBM</li>
            <li>Default export: 9:16 · 1080×1920 · H.264/AAC</li>
            <li>Detection weights: audio 50% · scene 20% · visual 30%</li>
            <li>
              Tokens stored locally in <code className="text-text">storage/secrets/</code>
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}
