// The search filters under the search box, always shown: which reranker scores the results, how to order
// them, and which of them to keep. They can be set before a search. Nothing here talks to the API; a change
// goes up through onChange, the next search uses it, and results already showing load again with the new
// view.
import type { ReactNode } from 'react'
import type { Asset, RerankerChoice, RerankerName, SearchOrder, SearchView, Snippet } from '../api/types'
import { MATCH_COLOURS, MATCH_KINDS, MATCH_LABELS, RERANKER_LABELS, RERANKER_SCOPES } from '../searchView'

type SearchOptionsProps = {
  view: SearchView
  // The rerankers the server has on; the reranker row shows only when there is at least one.
  rerankers: RerankerName[]
  // The reranker in use: the view's, or the server's default while the view names none.
  rerankerChoice: RerankerChoice
  onChange: (view: SearchView) => void
}

const RERANKER_CHOICES: RerankerChoice[] = ['voyage', 'jev', 'both']

// A choice the server cannot serve is shown, greyed out, so the user sees it exists: "both" needs both on.
function rerankerAvailable(choice: RerankerChoice, rerankers: RerankerName[]): boolean {
  if (choice === 'both') {
    return rerankers.includes('voyage') && rerankers.includes('jev')
  }
  return rerankers.includes(choice)
}

const ORDERS: { value: SearchOrder; label: string }[] = [
  { value: 'relevance', label: 'Most relevant' },
  { value: 'exact_first', label: 'Exact first' },
  { value: 'tiered', label: 'Exact, partial, semantic' },
  { value: 'blended', label: 'Best overall' },
]

const ASSET_TYPES: { value: Asset['asset_type']; label: string }[] = [
  { value: 'image', label: 'Images' },
  { value: 'text', label: 'Text files' },
]

// The same words as the "In the …" labels on the result cards. A match on the pixels has no chip, so it is
// always searched.
const PARTS: { value: Snippet['kind']; label: string }[] = [
  { value: 'content', label: 'Text' },
  { value: 'metadata', label: 'Description' },
  { value: 'visible_text', label: 'Text in image' },
  { value: 'filename', label: 'File name' },
]

const CHOSEN = 'bg-text text-surface'

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

export default function SearchOptions({ view, rerankers, rerankerChoice, onChange }: SearchOptionsProps) {
  return (
    <div className="grid gap-x-8 gap-y-2 rounded-xl bg-surface px-4 py-3 shadow-xs ring-1 ring-border sm:grid-cols-2">
      {rerankers.length > 0 && (
        <Row label="Reranker">
          {RERANKER_CHOICES.map((choice) => {
            const available = rerankerAvailable(choice, rerankers)
            return (
              <Chip
                key={choice}
                on={rerankerChoice === choice}
                onClass={CHOSEN}
                disabled={!available}
                title={available ? RERANKER_SCOPES[choice] : 'Not switched on for this server'}
                onClick={() => onChange({ ...view, reranker: choice })}
              >
                {RERANKER_LABELS[choice]}
              </Chip>
            )
          })}
        </Row>
      )}
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
      <span className="w-16 shrink-0 text-xs font-medium tracking-wide text-text-muted uppercase">{label}</span>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  )
}

// A small rounded button that is either on (in `onClass` colours) or off (outlined); a disabled one is faded.
function Chip({
  on,
  onClass,
  onClick,
  disabled = false,
  title,
  children,
}: {
  on: boolean
  onClass: string
  onClick: () => void
  disabled?: boolean
  title?: string
  children: ReactNode
}) {
  const colours = on ? onClass : 'bg-surface text-text-muted ring-1 ring-border-strong hover:bg-surface-hover'
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`rounded-full px-2.5 py-1 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-40 ${colours}`}
    >
      {children}
    </button>
  )
}
