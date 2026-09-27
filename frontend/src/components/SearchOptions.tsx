// The controls above the search results: how to order them, and which of them to keep. Nothing here
// talks to the API; a change goes up through onChange, and the results load again with the new view.
import type { ReactNode } from 'react'
import type { Asset, SearchOrder, SearchView, Snippet } from '../api/types'
import { MATCH_COLOURS, MATCH_KINDS, MATCH_LABELS } from '../searchView'

type SearchOptionsProps = {
  view: SearchView
  onChange: (view: SearchView) => void
}

const ORDERS: { value: SearchOrder; label: string }[] = [
  { value: 'exact_first', label: 'Exact first' },
  { value: 'tiered', label: 'Exact, partial, semantic' },
  { value: 'blended', label: 'Best overall' },
]

const ASSET_TYPES: { value: Asset['asset_type']; label: string }[] = [
  { value: 'image', label: 'Images' },
  { value: 'text', label: 'Text files' },
]

// The same words as the "In the …" labels on the result cards.
const PARTS: { value: Snippet['kind']; label: string }[] = [
  { value: 'content', label: 'Text' },
  { value: 'metadata', label: 'Description' },
  { value: 'image', label: 'Image' },
  { value: 'filename', label: 'File name' },
]

const CHOSEN = 'bg-gray-800 text-white'

// The list with `value` added or taken out. The last value is never taken out: a filter that keeps
// nothing would only ever show an empty list.
function toggled<T>(chosen: T[], value: T): T[] {
  if (!chosen.includes(value)) {
    return [...chosen, value]
  }
  if (chosen.length === 1) {
    return chosen
  }
  return chosen.filter((item) => item !== value)
}

export default function SearchOptions({ view, onChange }: SearchOptionsProps) {
  return (
    <div className="grid gap-x-8 gap-y-2 rounded-xl bg-white px-4 py-3 shadow-xs ring-1 ring-gray-200 sm:grid-cols-2">
      <Row label="Order">
        {ORDERS.map((order) => (
          <Chip
            key={order.value}
            on={view.order === order.value}
            onClass={CHOSEN}
            onClick={() => onChange({ ...view, order: order.value })}
          >
            {order.label}
          </Chip>
        ))}
      </Row>
      <Row label="Match">
        {MATCH_KINDS.map((kind) => (
          <Chip
            key={kind}
            on={view.match.includes(kind)}
            onClass={MATCH_COLOURS[kind]}
            onClick={() => onChange({ ...view, match: toggled(view.match, kind) })}
          >
            {MATCH_LABELS[kind]}
          </Chip>
        ))}
      </Row>
      <Row label="Type">
        {ASSET_TYPES.map((assetType) => (
          <Chip
            key={assetType.value}
            on={view.assetType.includes(assetType.value)}
            onClass={CHOSEN}
            onClick={() => onChange({ ...view, assetType: toggled(view.assetType, assetType.value) })}
          >
            {assetType.label}
          </Chip>
        ))}
      </Row>
      <Row label="Found in">
        {PARTS.map((part) => (
          <Chip
            key={part.value}
            on={view.foundIn.includes(part.value)}
            onClass={CHOSEN}
            onClick={() => onChange({ ...view, foundIn: toggled(view.foundIn, part.value) })}
          >
            {part.label}
          </Chip>
        ))}
      </Row>
    </div>
  )
}

// One labelled line of chips.
function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-16 shrink-0 text-xs font-medium tracking-wide text-gray-500 uppercase">{label}</span>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  )
}

// A small rounded button that is either on (in `onClass` colours) or off (outlined).
function Chip({
  on,
  onClass,
  onClick,
  children,
}: {
  on: boolean
  onClass: string
  onClick: () => void
  children: ReactNode
}) {
  const colours = on ? onClass : 'bg-white text-gray-500 ring-1 ring-gray-300 hover:bg-gray-50'
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={`rounded-full px-2.5 py-1 text-xs font-medium ${colours}`}
    >
      {children}
    </button>
  )
}
