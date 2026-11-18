export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = bytes
  for (const unit of units) {
    value /= 1024
    if (value < 1024 || unit === 'TB') {
      return `${value.toFixed(value >= 10 || unit === 'KB' ? 0 : 1)} ${unit}`
    }
  }
  return `${bytes} B`
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return '—'
  const total = Math.max(0, Math.floor(seconds))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${m}:${String(s).padStart(2, '0')}`
}

export function formatTimestamp(seconds: number): string {
  if (!Number.isFinite(seconds)) return '0.000'
  const sign = seconds < 0 ? '-' : ''
  const abs = Math.abs(seconds)
  const h = Math.floor(abs / 3600)
  const m = Math.floor((abs % 3600) / 60)
  const s = abs % 60
  const frac = s.toFixed(3).padStart(6, '0')
  if (h > 0) {
    return `${sign}${h}:${String(m).padStart(2, '0')}:${frac}`
  }
  return `${sign}${m}:${frac}`
}

export function parseTimestamp(input: string): number | null {
  const trimmed = input.trim()
  if (!trimmed) return null

  if (/^\d+(\.\d+)?$/.test(trimmed)) {
    return Number(trimmed)
  }

  const parts = trimmed.split(':').map((p) => p.trim())
  if (parts.length === 2 || parts.length === 3) {
    const nums = parts.map(Number)
    if (nums.some((n) => Number.isNaN(n))) return null
    if (parts.length === 2) {
      return nums[0] * 60 + nums[1]
    }
    return nums[0] * 3600 + nums[1] * 60 + nums[2]
  }
  return null
}

export function formatResolution(width: number | null, height: number | null): string {
  if (!width || !height) return '—'
  return `${width}×${height}`
}
