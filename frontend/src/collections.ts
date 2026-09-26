// Rules and small helpers for collection names and the collection list.
import type { Collection } from './api/types'

// The API accepts the same rule; checking it here lets the form explain it before any request.
const NAME_RULE = /^[a-z0-9_-]{1,64}$/

export const NAME_RULE_HINT = 'Use 1–64 characters: lowercase letters, digits, - or _.'

export function isValidCollectionName(name: string): boolean {
  return NAME_RULE.test(name)
}

// A collection created in the browser only exists on the server after its first upload.
// Until then it is shown from `draftNames` with no files.
export function withDrafts(collections: Collection[], draftNames: string[]): Collection[] {
  const serverNames = new Set(collections.map((collection) => collection.name))
  const drafts = draftNames
    .filter((name) => !serverNames.has(name))
    .map((name) => ({ name, asset_count: 0 }))
  const all = [...collections, ...drafts]
  all.sort((first, second) => first.name.localeCompare(second.name))
  return all
}

export function defaultCollection(collections: Collection[]): string | null {
  if (collections.some((collection) => collection.name === 'demo')) {
    return 'demo'
  }
  if (collections.length > 0) {
    return collections[0].name
  }
  return null
}
