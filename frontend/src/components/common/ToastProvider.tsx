import { CheckCircle2, Info, X, XCircle } from 'lucide-react'
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'

export type ToastTone = 'success' | 'error' | 'info'

export interface ToastItem {
  id: string
  tone: ToastTone
  title: string
  description?: string
}

interface ConfirmOptions {
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  tone?: 'danger' | 'default'
}

interface ToastContextValue {
  push: (tone: ToastTone, title: string, description?: string) => void
  success: (title: string, description?: string) => void
  error: (title: string, description?: string) => void
  info: (title: string, description?: string) => void
  confirm: (options: ConfirmOptions) => Promise<boolean>
}

const ToastContext = createContext<ToastContextValue | null>(null)

let toastId = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const [confirmState, setConfirmState] = useState<
    (ConfirmOptions & { resolve: (value: boolean) => void }) | null
  >(null)
  const timers = useRef<Map<string, number>>(new Map())

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
    const timer = timers.current.get(id)
    if (timer) {
      window.clearTimeout(timer)
      timers.current.delete(id)
    }
  }, [])

  const push = useCallback(
    (tone: ToastTone, title: string, description?: string) => {
      const id = `toast-${++toastId}`
      setToasts((prev) => [...prev.slice(-4), { id, tone, title, description }])
      const timer = window.setTimeout(() => dismiss(id), tone === 'error' ? 6000 : 3800)
      timers.current.set(id, timer)
    },
    [dismiss],
  )

  const confirm = useCallback((options: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      setConfirmState({ ...options, resolve })
    })
  }, [])

  const value = useMemo<ToastContextValue>(
    () => ({
      push,
      success: (title, description) => push('success', title, description),
      error: (title, description) => push('error', title, description),
      info: (title, description) => push('info', title, description),
      confirm,
    }),
    [push, confirm],
  )

  return (
    <ToastContext.Provider value={value}>
      {children}
      {createPortal(
        <div className="pointer-events-none fixed inset-x-0 top-0 z-[100] flex flex-col items-end gap-2 p-4 sm:p-6">
          {toasts.map((toast) => (
            <div
              key={toast.id}
              className={[
                'pointer-events-auto w-full max-w-sm overflow-hidden rounded-lg border shadow-lg backdrop-blur',
                'animate-[toast-in_220ms_ease-out]',
                toast.tone === 'success' && 'border-accent/40 bg-card/95',
                toast.tone === 'error' && 'border-danger/40 bg-card/95',
                toast.tone === 'info' && 'border-primary/40 bg-card/95',
              ]
                .filter(Boolean)
                .join(' ')}
              role="status"
            >
              <div className="flex items-start gap-3 px-4 py-3">
                <div className="mt-0.5 shrink-0">
                  {toast.tone === 'success' && (
                    <CheckCircle2 size={18} className="text-accent" />
                  )}
                  {toast.tone === 'error' && <XCircle size={18} className="text-danger" />}
                  {toast.tone === 'info' && <Info size={18} className="text-primary" />}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-text">{toast.title}</p>
                  {toast.description && (
                    <p className="mt-1 text-xs text-muted">{toast.description}</p>
                  )}
                </div>
                <button
                  type="button"
                  className="rounded p-1 text-muted hover:bg-bg-secondary hover:text-text"
                  onClick={() => dismiss(toast.id)}
                  aria-label="Dismiss"
                >
                  <X size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>,
        document.body,
      )}

      {confirmState &&
        createPortal(
          <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/55 p-4">
            <div
              className="w-full max-w-md rounded-lg border border-border bg-card p-5 shadow-xl"
              role="dialog"
              aria-modal="true"
              aria-labelledby="confirm-title"
            >
              <h2 id="confirm-title" className="text-lg font-semibold text-text">
                {confirmState.title}
              </h2>
              {confirmState.description && (
                <p className="mt-2 text-sm text-muted">{confirmState.description}</p>
              )}
              <div className="mt-5 flex justify-end gap-2">
                <button
                  type="button"
                  className="rounded-md border border-border px-4 py-2 text-sm text-muted hover:text-text"
                  onClick={() => {
                    confirmState.resolve(false)
                    setConfirmState(null)
                  }}
                >
                  {confirmState.cancelLabel || 'Cancel'}
                </button>
                <button
                  type="button"
                  className={[
                    'rounded-md px-4 py-2 text-sm font-medium text-white',
                    confirmState.tone === 'danger'
                      ? 'bg-danger hover:bg-danger/90'
                      : 'bg-primary hover:bg-primary-hover',
                  ].join(' ')}
                  onClick={() => {
                    confirmState.resolve(true)
                    setConfirmState(null)
                  }}
                >
                  {confirmState.confirmLabel || 'Confirm'}
                </button>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
