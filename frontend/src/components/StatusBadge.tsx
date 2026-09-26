// A small coloured pill showing where a file is in processing.
import type { AssetStatus } from '../api/types'

const LABELS: Record<AssetStatus, string> = {
  pending: 'Pending',
  processing: 'Processing',
  ready: 'Ready',
  failed: 'Failed',
}

const PILL_COLOURS: Record<AssetStatus, string> = {
  pending: 'bg-gray-100 text-gray-600',
  processing: 'bg-indigo-50 text-indigo-700',
  ready: 'bg-green-50 text-green-700',
  failed: 'bg-red-50 text-red-700',
}

const DOT_COLOURS: Record<AssetStatus, string> = {
  pending: 'bg-gray-400',
  processing: 'bg-indigo-500 animate-pulse',
  ready: 'bg-green-500',
  failed: 'bg-red-500',
}

export default function StatusBadge({ status }: { status: AssetStatus }) {
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${PILL_COLOURS[status]}`}>
      <span className={`size-1.5 rounded-full ${DOT_COLOURS[status]}`} />
      {LABELS[status]}
    </span>
  )
}
