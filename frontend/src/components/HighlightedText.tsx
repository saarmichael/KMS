// Shows a piece of text with every word of the search query marked, so the user sees why it matched.
// A match by meaning (e.g. "brunette" for "black hair") has no word in common and shows unmarked.
import type { Ref } from 'react'
import { queryPattern } from '../queryWords'

type HighlightedTextProps = {
  text: string
  query: string
  // Put on the first marked word, so a parent can scroll to it.
  firstMarkRef?: Ref<HTMLElement>
}

export default function HighlightedText({ text, query, firstMarkRef }: HighlightedTextProps) {
  const pattern = queryPattern(query)
  if (pattern === null) {
    return <>{text}</>
  }

  // split() keeps the matched words because the pattern captures them: every odd-numbered piece is a match.
  const pieces = text.split(pattern)

  return (
    <>
      {pieces.map((piece, index) =>
        index % 2 === 1 ? (
          <mark
            key={index}
            ref={index === 1 ? firstMarkRef : undefined}
            className="rounded-sm bg-indigo-100 px-0.5 text-indigo-900"
          >
            {piece}
          </mark>
        ) : (
          piece
        ),
      )}
    </>
  )
}
