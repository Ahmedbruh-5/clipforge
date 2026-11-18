import { useEffect, useRef } from 'react'

interface Props {
  src?: string
  onTimeUpdate?: (time: number) => void
  onLoadedMetadata?: (duration: number) => void
  currentTime?: number
  className?: string
}

export function VideoPlayer({
  src,
  onTimeUpdate,
  onLoadedMetadata,
  currentTime,
  className,
}: Props) {
  const ref = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    if (ref.current && currentTime != null) {
      if (Math.abs(ref.current.currentTime - currentTime) > 0.35) {
        ref.current.currentTime = currentTime
      }
    }
  }, [currentTime])

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
      className={`aspect-video w-full rounded-lg border border-border bg-black object-contain ${className ?? ''}`}
      onTimeUpdate={(e) => onTimeUpdate?.(e.currentTarget.currentTime)}
      onLoadedMetadata={(e) => onLoadedMetadata?.(e.currentTarget.duration)}
    />
  )
}
