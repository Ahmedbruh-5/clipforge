import { Check, ChevronDown } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'

export interface SelectOption<T extends string = string> {
  value: T
  label: string
  description?: string
  disabled?: boolean
}

interface Props<T extends string = string> {
  value: T
  options: SelectOption<T>[]
  onChange: (value: T) => void
  placeholder?: string
  disabled?: boolean
  className?: string
  label?: string
  size?: 'sm' | 'md'
}

export function Select<T extends string = string>({
  value,
  options,
  onChange,
  placeholder = 'Select…',
  disabled,
  className,
  label,
  size = 'md',
}: Props<T>) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const listId = useId()
  const selected = options.find((o) => o.value === value)

  useEffect(() => {
    if (!open) return
    function onDoc(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div ref={rootRef} className={['relative', className].filter(Boolean).join(' ')}>
      {label && <div className="mb-1 text-xs text-muted">{label}</div>}
      <button
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((v) => !v)}
        className={[
          'flex w-full items-center justify-between gap-2 rounded-md border border-border bg-bg-secondary text-left text-text outline-none transition-colors',
          'hover:border-primary/60 focus:border-primary disabled:cursor-not-allowed disabled:opacity-50',
          size === 'sm' ? 'px-2.5 py-1.5 text-xs' : 'px-3 py-2 text-sm',
          open ? 'border-primary' : '',
        ].join(' ')}
      >
        <span className={selected ? 'truncate' : 'truncate text-muted'}>
          {selected?.label ?? placeholder}
        </span>
        <ChevronDown
          size={size === 'sm' ? 14 : 16}
          className={['shrink-0 text-muted transition-transform', open ? 'rotate-180' : ''].join(
            ' ',
          )}
        />
      </button>

      {open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-md border border-border bg-card py-1 shadow-xl"
        >
          {options.map((option) => {
            const active = option.value === value
            return (
              <li key={option.value} role="option" aria-selected={active}>
                <button
                  type="button"
                  disabled={option.disabled}
                  className={[
                    'flex w-full items-start gap-2 px-3 py-2 text-left text-sm transition-colors',
                    option.disabled
                      ? 'cursor-not-allowed opacity-40'
                      : active
                        ? 'bg-primary/15 text-text'
                        : 'text-text hover:bg-bg-secondary',
                  ].join(' ')}
                  onClick={() => {
                    if (option.disabled) return
                    onChange(option.value)
                    setOpen(false)
                  }}
                >
                  <span className="mt-0.5 w-4 shrink-0">
                    {active && <Check size={14} className="text-primary" />}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate">{option.label}</span>
                    {option.description && (
                      <span className="mt-0.5 block text-xs text-muted">
                        {option.description}
                      </span>
                    )}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
