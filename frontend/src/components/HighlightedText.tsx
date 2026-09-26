// Shows a piece of text with every word of the search query marked, so the user sees why it matched.
// A match by meaning (e.g. "brunette" for "black hair") has no word in common and shows unmarked.

const MINIMUM_WORD_LENGTH = 2

// Characters like . or ( mean something in a regular expression; escaping makes them plain text.
function escapeForRegex(word: string): string {
  return word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export default function HighlightedText({ text, query }: { text: string; query: string }) {
  const words = query
    .split(/\s+/)
    .filter((word) => word.length >= MINIMUM_WORD_LENGTH)
    .map(escapeForRegex)
  if (words.length === 0) {
    return <>{text}</>
  }

  // \b only matches at the start of a word, so "note" marks "notes" but "sign" does not mark "designing".
  // The parentheses make split() keep the matched words: every odd-numbered piece is a match.
  const pattern = new RegExp(`\\b(${words.join('|')})`, 'gi')
  const pieces = text.split(pattern)

  return (
    <>
      {pieces.map((piece, index) =>
        index % 2 === 1 ? (
          <mark key={index} className="rounded-sm bg-indigo-100 px-0.5 text-indigo-900">
            {piece}
          </mark>
        ) : (
          piece
        ),
      )}
    </>
  )
}
