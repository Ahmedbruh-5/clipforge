import { useEffect, useRef } from 'react'

interface Props {
  src?: string
  onTimeUpdate?: (time: number) => void
  onLoadedMetadata?: (duration: number) => void
  currentTime?: number
  muted?: boolean
  className?: string
  onPlay?: () => void
  onPause?: () => void
  onSeeked?: (time: number) => void
}

export function VideoPlayer({
  src,
  onTimeUpdate,
  onLoadedMetadata,
  currentTime,
  muted = false,
  className,
  onPlay,
  onPause,
  onSeeked,
}: Props) {
  const ref = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    if (ref.current && currentTime != null) {
      if (Math.abs(ref.current.currentTime - currentTime) > 0.35) {
        ref.current.currentTime = currentTime
      }
    }
  }, [currentTime])

  useEffect(() => {
    if (ref.current) {
      ref.current.muted = muted
    }
  }, [muted])

  if (!src) {
    return (
      <div
        className={`flex aspect-video items-center justify-center rounded-lg border border-border bg-bg-secondary text-sm text-muted ${className ?? ''}`}
      >
        Select a video to preview
      </div>
    )
  }

  return (
    <video
      ref={ref}
      key={src}
      src={src}
      controls
      muted={muted}
      className={`aspect-video w-full rounded-lg border border-border bg-black object-contain ${className ?? ''}`}
      onTimeUpdate={(e) => onTimeUpdate?.(e.currentTarget.currentTime)}
      onLoadedMetadata={(e) => onLoadedMetadata?.(e.currentTarget.duration)}
      onPlay={() => onPlay?.()}
      onPause={() => onPause?.()}
      onSeeked={(e) => onSeeked?.(e.currentTarget.currentTime)}
    />
  )
}
