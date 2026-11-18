const STYLES: Record<string, string> = {
  ready: 'bg-accent/15 text-accent border-accent/30',
  draft: 'bg-primary/15 text-primary border-primary/30',
  rendering: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  processing: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  queued: 'bg-muted/20 text-muted border-border',
  failed: 'bg-danger/15 text-danger border-danger/30',
  completed: 'bg-accent/15 text-accent border-accent/30',
  running: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  pending: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  approved: 'bg-accent/15 text-accent border-accent/30',
  rejected: 'bg-danger/15 text-danger border-danger/30',
  uploading: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  scheduled: 'bg-primary/15 text-primary border-primary/30',
  published: 'bg-accent/15 text-accent border-accent/30',
  cancelled: 'bg-muted/20 text-muted border-border',
}

export function StatusBadge({ status }: { status: string }) {
  const style = STYLES[status] ?? 'bg-muted/20 text-muted border-border'
  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium capitalize ${style}`}
    >
      {status}
    </span>
  )
}
