// What the search view starts as, and the name and colour of each way a result can match, shared by the
// badge on a result card and the filter chips. Exact and partial are one colour, exact the stronger tone,
// since both are word matches; semantic, a match by meaning, has a colour of its own.
import type { MatchKind, SearchView } from './api/types'

// Everything on: every result, exact matches first.
export const DEFAULT_VIEW: SearchView = {
  order: 'exact_first',
  match: ['exact', 'partial', 'semantic'],
  assetType: ['image', 'text'],
  foundIn: ['content', 'metadata', 'image', 'filename'],
}

export const MATCH_KINDS: MatchKind[] = ['exact', 'partial', 'semantic']

export const MATCH_LABELS: Record<MatchKind, string> = {
  exact: 'Exact',
  partial: 'Partial',
  semantic: 'Semantic',
}

export const MATCH_COLOURS: Record<MatchKind, string> = {
  exact: 'bg-indigo-600 text-white',
  partial: 'bg-indigo-100 text-indigo-800',
  semantic: 'bg-teal-100 text-teal-800',
}
