export interface Video {
  id: number
  filename: string
  original_filename: string
  file_size: number
  mime_type: string | null
  duration: number | null
  width: number | null
  height: number | null
  fps: number | null
  codec: string | null
  status: string
  error_message: string | null
  created_at: string
  updated_at: string
  stream_url: string | null
  clip_count: number
}

export interface Clip {
  id: number
  video_id: number
  title: string
  start_time: number
  end_time: number
  duration: number
  status: string
  review_status: string
  output_path: string | null
  thumbnail_path: string | null
  thumbnail_custom: boolean
  aspect_ratio: string
  resolution: string
  crop_x: number | null
  crop_y: number | null
  error_message: string | null
  created_at: string
  updated_at: string
  stream_url: string | null
  thumbnail_url: string | null
  video_title: string | null
}

export interface DetectionCandidate {
  id: number
  video_id: number
  start_time: number
  end_time: number
  duration: number
  score: number
  audio_score: number
  scene_score: number
  visual_score: number
  rank: number
  label: string
  notes: string | null
  created_at: string
}

export interface Job {
  id: number
  job_type: string
  status: string
  progress: number
  video_id: number | null
  clip_id: number | null
  message: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface DashboardStats {
  total_videos: number
  total_clips: number
  clips_draft: number
  clips_ready: number
  clips_failed: number
  clips_pending_review: number
  clips_approved: number
  scheduled_uploads: number
  published_clips: number
  recent_videos: Video[]
}

export interface ClipCreatePayload {
  video_id: number
  title: string
  start_time: number
  end_time: number
  aspect_ratio?: string
  resolution?: string
  crop_x?: number
  crop_y?: number
  review_status?: string
}

export interface YouTubeStatus {
  configured: boolean
  connected: boolean
  channel_title: string | null
  channel_id: string | null
  redirect_uri: string
  can_connect_later: boolean
  setup_hint: string | null
}

export interface YouTubeConnectResponse {
  auth_url: string | null
  state: string | null
  configured: boolean
  message: string | null
}

export interface PublishSchedule {
  id: number
  clip_id: number
  title: string
  description: string
  privacy_status: string
  publish_at: string | null
  timezone: string
  status: string
  youtube_video_id: string | null
  youtube_url: string | null
  idempotency_key: string
  error_message: string | null
  created_at: string
  updated_at: string
  clip_title: string | null
  thumbnail_url: string | null
  video_id: number | null
}

export interface ScheduleCreatePayload {
  title: string
  description?: string
  privacy_status: string
  publish_at?: string | null
  timezone?: string
}
