// What the search view starts as, and the name and colour of each way a result can match, shared by the
// badge on a result card and the filter chips. Exact and partial are one colour, exact the stronger tone,
// since both are word matches; semantic, a match by meaning, has a colour of its own.
import type { MatchKind, RerankerChoice, SearchView } from './api/types'

// Everything on: every result, the most relevant first, by the server's default reranker. `image` has no chip,
// so it stays in `foundIn` for good.
export const DEFAULT_VIEW: SearchView = {
  reranker: null,
  order: 'relevance',
  match: ['exact', 'partial', 'semantic'],
  assetType: ['image', 'text'],
  foundIn: ['content', 'metadata', 'image', 'visible_text', 'filename'],
}

export const MATCH_KINDS: MatchKind[] = ['exact', 'partial', 'semantic']

export const MATCH_LABELS: Record<MatchKind, string> = {
  exact: 'Exact',
  partial: 'Partial',
  semantic: 'Semantic',
}

export const MATCH_COLOURS: Record<MatchKind, string> = {
  exact: 'bg-accent text-on-accent',
  partial: 'bg-accent-soft text-accent-soft-text',
  semantic: 'bg-meaning-soft text-meaning',
}

// The sentence of a passage matched by meaning that is closest to the query, marked in the semantic colour
// on the card and in the detail dialog.
export const CLOSEST_SENTENCE_CLASS = 'rounded-sm bg-meaning-soft px-0.5 text-meaning'
export const CLOSEST_SENTENCE_TITLE = 'Closest in meaning to your query'

// The reranker chips, and the heading of each column when both are shown. Each says which results it scores.
export const RERANKER_LABELS: Record<RerankerChoice, string> = {
  voyage: 'Voyage',
  jev: 'Jev',
  both: 'Both',
}

export const RERANKER_SCOPES: Record<RerankerChoice, string> = {
  voyage: 'Scores the top 20 results',
  jev: 'Scores every result',
  both: 'Voyage and Jev side by side',
}
