import { Select } from '../common/Select'

interface Props {
  aspectRatio: string
  resolution: string
  cropX: number
  cropY: number
  onAspectRatioChange: (value: string) => void
  onResolutionChange: (value: string) => void
  onCropXChange: (value: number) => void
  onCropYChange: (value: number) => void
}

const ASPECT_OPTIONS = [
  { value: '9:16', label: '9:16 vertical' },
  { value: '16:9', label: '16:9 landscape' },
  { value: '1:1', label: '1:1 square' },
  { value: 'source', label: 'Source (no crop)' },
]

const RESOLUTION_OPTIONS = [
  { value: '1080x1920', label: '1080×1920' },
  { value: '720x1280', label: '720×1280' },
  { value: '1080x1080', label: '1080×1080' },
  { value: '1920x1080', label: '1920×1080' },
  { value: 'source', label: 'Source' },
]

export function CropControls({
  aspectRatio,
  resolution,
  cropX,
  cropY,
  onAspectRatioChange,
  onResolutionChange,
  onCropXChange,
  onCropYChange,
}: Props) {
  return (
    <div className="space-y-3 rounded-lg border border-border bg-card p-4">
      <h2 className="text-sm font-medium uppercase tracking-wide text-muted">
        Export framing
      </h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <Select
          label="Aspect ratio"
          value={aspectRatio}
          options={ASPECT_OPTIONS}
          onChange={onAspectRatioChange}
        />
        <Select
          label="Resolution"
          value={resolution}
          options={RESOLUTION_OPTIONS}
          onChange={onResolutionChange}
        />
      </div>

      <label className="block text-xs text-muted">
        Horizontal crop position ({cropX.toFixed(2)})
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={cropX}
          disabled={aspectRatio === 'source'}
          onChange={(e) => onCropXChange(Number(e.target.value))}
          className="mt-1 w-full accent-primary disabled:opacity-40"
        />
        <span className="mt-1 block text-[11px] text-muted">
          0 = left · 0.5 = center · 1 = right (ready for future subject tracking)
        </span>
      </label>

      <label className="block text-xs text-muted">
        Vertical crop position ({cropY.toFixed(2)})
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={cropY}
          disabled={aspectRatio === 'source'}
          onChange={(e) => onCropYChange(Number(e.target.value))}
          className="mt-1 w-full accent-primary disabled:opacity-40"
        />
      </label>
    </div>
  )
}
