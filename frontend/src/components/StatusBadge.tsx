// A small coloured pill showing where a file is in processing.
import type { AssetStatus } from '../api/types'

const LABELS: Record<AssetStatus, string> = {
  pending: 'Pending',
  processing: 'Processing',
  ready: 'Ready',
  failed: 'Failed',
}

const PILL_COLOURS: Record<AssetStatus, string> = {
  pending: 'bg-surface-hover text-text-muted',
  processing: 'bg-accent-soft text-accent-text',
  ready: 'bg-success-soft text-success',
  failed: 'bg-danger-soft text-danger',
}

const DOT_COLOURS: Record<AssetStatus, string> = {
  pending: 'bg-text-subtle',
  processing: 'bg-accent animate-pulse',
  ready: 'bg-success',
  failed: 'bg-danger',
}

export default function StatusBadge({ status }: { status: AssetStatus }) {
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${PILL_COLOURS[status]}`}>
      <span className={`size-1.5 rounded-full ${DOT_COLOURS[status]}`} />
      {LABELS[status]}
    </span>
  )
}
