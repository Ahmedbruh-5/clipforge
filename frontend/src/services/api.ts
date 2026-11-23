import axios from 'axios'

import type {
  Clip,
  ClipCreatePayload,
  DashboardStats,
  DetectionCandidate,
  Job,
  MusicTrack,
  PublishSchedule,
  ScheduleCreatePayload,
  Video,
  YouTubeConnectResponse,
  YouTubeStatus,
} from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 300_000,
})

export async function fetchDashboard(): Promise<DashboardStats> {
  const { data } = await api.get<DashboardStats>('/dashboard')
  return data
}

export async function fetchVideos(): Promise<Video[]> {
  const { data } = await api.get<{ items: Video[]; total: number }>('/videos')
  return data.items
}

export async function fetchVideo(id: number): Promise<Video> {
  const { data } = await api.get<Video>(`/videos/${id}`)
  return data
}

export async function uploadVideo(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<Video> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<Video>('/videos/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (!onProgress || !event.total) return
      onProgress(Math.round((event.loaded / event.total) * 100))
    },
  })
  return data
}

export async function deleteVideo(id: number): Promise<void> {
  await api.delete(`/videos/${id}`)
}

export async function fetchClips(
  videoId?: number,
  filters?: { status?: string; review_status?: string },
): Promise<Clip[]> {
  const { data } = await api.get<{ items: Clip[]; total: number }>('/clips', {
    params: {
      ...(videoId != null ? { video_id: videoId } : {}),
      ...(filters?.status ? { status: filters.status } : {}),
      ...(filters?.review_status ? { review_status: filters.review_status } : {}),
    },
  })
  return data.items
}

export async function fetchClip(id: number): Promise<Clip> {
  const { data } = await api.get<Clip>(`/clips/${id}`)
  return data
}

export async function createClip(payload: ClipCreatePayload): Promise<Clip> {
  const { data } = await api.post<Clip>('/clips', payload)
  return data
}

export async function updateClip(
  id: number,
  payload: Partial<ClipCreatePayload> & { title?: string; review_status?: string },
): Promise<Clip> {
  const { data } = await api.put<Clip>(`/clips/${id}`, payload)
  return data
}

export async function updateCandidate(
  id: number,
  payload: { start_time?: number; end_time?: number; label?: string; notes?: string },
): Promise<DetectionCandidate> {
  const { data } = await api.put<DetectionCandidate>(`/candidates/${id}`, payload)
  return data
}

export async function deleteCandidate(id: number): Promise<void> {
  await api.delete(`/candidates/${id}`)
}

export async function promoteCandidate(
  id: number,
  payload?: {
    title?: string
    aspect_ratio?: string
    resolution?: string
    crop_x?: number
    crop_y?: number
    audio_mode?: string
    music_track_key?: string | null
    music_volume?: number
  },
): Promise<Clip> {
  const { data } = await api.post<Clip>(`/candidates/${id}/promote`, payload ?? {})
  return data
}

export async function fetchMusicTracks(): Promise<MusicTrack[]> {
  const { data } = await api.get<{ items: MusicTrack[]; total: number }>('/music/tracks')
  return data.items
}

export async function uploadMusicTrack(file: File): Promise<MusicTrack> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<MusicTrack>('/music/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function deleteMusicTrack(filename: string): Promise<void> {
  await api.delete(`/music/user/${encodeURIComponent(filename)}`)
}

export async function deleteClip(id: number): Promise<void> {
  await api.delete(`/clips/${id}`)
}

export async function renderClip(id: number): Promise<Job> {
  const { data } = await api.post<Job>(`/clips/${id}/render`)
  return data
}

export async function uploadClipThumbnail(id: number, file: File): Promise<Clip> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<Clip>(`/clips/${id}/thumbnail`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function clearClipThumbnail(id: number): Promise<Clip> {
  const { data } = await api.delete<Clip>(`/clips/${id}/thumbnail`)
  return data
}

export async function fetchJob(id: number): Promise<Job> {
  const { data } = await api.get<Job>(`/jobs/${id}`)
  return data
}

export async function startDetection(videoId: number): Promise<Job> {
  const { data } = await api.post<Job>(`/videos/${videoId}/detect`)
  return data
}

export async function fetchCandidates(videoId: number): Promise<{
  items: DetectionCandidate[]
  total: number
  disclaimer: string
}> {
  const { data } = await api.get(`/videos/${videoId}/candidates`)
  return data
}

export async function fetchYouTubeStatus(): Promise<YouTubeStatus> {
  const { data } = await api.get<YouTubeStatus>('/youtube/status')
  return data
}

export async function connectYouTube(): Promise<YouTubeConnectResponse> {
  const { data } = await api.post<YouTubeConnectResponse>('/youtube/connect')
  return data
}

export async function disconnectYouTube(): Promise<void> {
  await api.post('/youtube/disconnect')
}

export async function fetchSchedules(status?: string): Promise<PublishSchedule[]> {
  const { data } = await api.get<{ items: PublishSchedule[]; total: number }>(
    '/schedules',
    { params: status ? { status } : undefined },
  )
  return data.items
}

export async function createSchedule(
  clipId: number,
  payload: ScheduleCreatePayload,
): Promise<PublishSchedule> {
  const { data } = await api.post<PublishSchedule>(`/clips/${clipId}/schedule`, payload)
  return data
}

export async function cancelSchedule(id: number): Promise<void> {
  await api.post(`/schedules/${id}/cancel`)
}

export async function deleteSchedule(id: number): Promise<void> {
  await api.delete(`/schedules/${id}`)
}

export async function retrySchedule(id: number): Promise<PublishSchedule> {
  const { data } = await api.post<PublishSchedule>(`/schedules/${id}/retry`)
  return data
}

export function mediaUrl(path: string | null | undefined): string | undefined {
  if (!path) return undefined
  return path
}

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map((d) => d.msg ?? JSON.stringify(d)).join('; ')
    }
    return error.message
  }
  if (error instanceof Error) return error.message
  return 'Unexpected error'
}
