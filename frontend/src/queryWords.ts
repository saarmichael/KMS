// The one rule for finding the words of a search query inside a piece of text, used wherever the UI
// marks matches: result snippets, the text in an image, and the detail dialog.

const MINIMUM_WORD_LENGTH = 2
const CONTEXT_BEFORE_MATCH = 40

// Characters like . or ( mean something in a regular expression; escaping makes them plain text.
function escapeForRegex(word: string): string {
  return word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// Matches any query word of 2 or more characters, ignoring case, at the start of a word:
// "note" matches "notes", but "sign" does not match "designing". Null when no word is long enough.
// The parentheses keep the matched word when the pattern is used with split().
export function queryPattern(query: string): RegExp | null {
  const words = query
    .split(/\s+/)
    .filter((word) => word.length >= MINIMUM_WORD_LENGTH)
    .map(escapeForRegex)
  if (words.length === 0) {
    return null
  }
  return new RegExp(`\\b(${words.join('|')})`, 'gi')
}

// About `length` characters of `text` around the first query word found in it, with "…" where the text
// was cut. Null when no query word appears in the text.
export function excerptAround(text: string, query: string, length: number): string | null {
  const pattern = queryPattern(query)
  if (pattern === null) {
    return null
  }
  const matchIndex = text.search(pattern)
  if (matchIndex === -1) {
    return null
  }
  const start = Math.max(0, matchIndex - CONTEXT_BEFORE_MATCH)
  const end = Math.min(text.length, start + length)
  const cutAtStart = start > 0 ? '…' : ''
  const cutAtEnd = end < text.length ? '…' : ''
  return `${cutAtStart}${text.slice(start, end)}${cutAtEnd}`
}
