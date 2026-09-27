// Shows a piece of snippet text with the query words marked and, when the search named one, the sentence
// closest in meaning to the query marked in the semantic colour. The same component shows every kind of
// snippet text: a passage of a file, a description, the text read from an image, a file name.
//
// How data reaches it:
//   SearchResultCard -> the card's preview of snippet.text, with the sentence moved to where the preview starts
//   AssetDetailDialog -> the passage in the file text, the description, the visible text, or the file name line
import type { Ref } from 'react'
import { CLOSEST_SENTENCE_CLASS, CLOSEST_SENTENCE_TITLE } from '../searchView'
import HighlightedText from './HighlightedText'

// Where the sentence sits, counted in characters of the text it belongs to.
export type SentenceRange = {
  start: number
  end: number
}

type ClosestSentenceTextProps = {
  text: string
  query: string
  // Null when the search named no sentence; the text then shows with its query words marked only.
  sentence: SentenceRange | null
  // Put on the marked sentence, so a parent can scroll to it.
  sentenceRef?: Ref<HTMLElement>
  // Put on the first marked query word when there is no sentence, so a parent can scroll to it.
  firstMarkRef?: Ref<HTMLElement>
}

export default function ClosestSentenceText({ text, query, sentence, sentenceRef, firstMarkRef }: ClosestSentenceTextProps) {
  if (sentence === null) {
    return <HighlightedText text={text} query={query} firstMarkRef={firstMarkRef} />
  }

  // The server counts characters; Array.from splits the text the same way (an emoji is one character here,
  // but two units in a plain JavaScript string).
  const characters = Array.from(text)
  const before = characters.slice(0, sentence.start).join('')
  const sentenceText = characters.slice(sentence.start, sentence.end).join('')
  const after = characters.slice(sentence.end).join('')

  return (
    <>
      <HighlightedText text={before} query={query} />
      <mark ref={sentenceRef} className={CLOSEST_SENTENCE_CLASS} title={CLOSEST_SENTENCE_TITLE}>
        <HighlightedText text={sentenceText} query={query} />
      </mark>
      <HighlightedText text={after} query={query} />
    </>
  )
}
