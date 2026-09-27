// One search result: thumbnail, title, which file it was found in, and the passage or description that
// matched. The coloured bar on the left edge shows how close the match is; nothing is faded.
//
// How data reaches it:
//   SearchResults `results` state -> <SearchResultCard result query>
//     result.asset    -> thumbnail (assetFileUrl), title, "Found in" filename (query words marked) and aliases
//     result.snippet  -> what matched ("In the text" ...) and the text, with the query words marked; a
//                        passage is cut to start just before its first query word, and the query words
//                        the cut left out are counted: "2 more matches in this passage →". A passage
//                        matched by meaning starts on its closest sentence instead, marked in teal
//                        (snippet.sentence_start_char / sentence_end_char)
//     asset.metadata.visible_text -> for an image whose text contains a query word: "Text in the image"
//     result.score    -> closeness() -> colour of the edge bar and its tooltip
//     result.match    -> the badge: exact, partial or semantic, in its colour
//   a click on the card -> onOpen(asset, snippet, query) -> the detail dialog, with the matches marked
import { assetFileUrl } from '../api/client'
import type { Asset, SearchResult, Snippet } from '../api/types'
import { closeness } from '../closeness'
import { CLOSEST_SENTENCE_CLASS, CLOSEST_SENTENCE_TITLE, MATCH_COLOURS, MATCH_LABELS } from '../searchView'
import { countMatches, excerptAround } from '../queryWords'
import HighlightedText from './HighlightedText'
import { DocumentIcon } from './icons'

type SearchResultCardProps = {
  result: SearchResult
  query: string
  onOpen: (asset: Asset, snippet: Snippet, query: string) => void
}

const IMAGE_TEXT_EXCERPT_LENGTH = 160
// About three lines of the card; the snippet is clamped to three lines anyway.
const PASSAGE_EXCERPT_LENGTH = 300

const SNIPPET_LABELS: Record<Snippet['kind'], string> = {
  content: 'In the text',
  metadata: 'In the description',
  image: 'In the image',
  filename: 'In the file name',
}

export default function SearchResultCard({ result, query, onOpen }: SearchResultCardProps) {
  const { asset, score, snippet } = result
  const match = closeness(score)
  const title = asset.metadata ? asset.metadata.title : asset.filename

  // The API gives no position for a match in an image's text, so the query words are looked up here.
  let imageTextExcerpt: string | null = null
  if (asset.asset_type === 'image' && asset.metadata?.visible_text) {
    imageTextExcerpt = excerptAround(asset.metadata.visible_text, query, IMAGE_TEXT_EXCERPT_LENGTH)
  }

  // A passage from the middle of a file gets "…" where it was cut: before it unless it starts the file,
  // after it unless it ends a sentence. A passage is longer than the three lines the card shows, so the
  // card starts just before the first query word in it; otherwise that word could fall below the cut.
  let snippetText = snippet.text
  // Query words in the passage that the cut left out; the card says how many, so the user knows the
  // dialog has more to show.
  let moreMatches = 0
  // A passage matched by meaning may hold no query word at all. The server then names the sentence closest
  // in meaning to the query, and the card starts on that sentence and marks it instead.
  let closestSentence: { before: string; sentence: string; after: string } | null = null
  if (snippet.kind === 'content') {
    const cutAtStart = snippet.start_char !== null && snippet.start_char > 0
    const endsSentence = /[.!?]$/.test(snippet.text.trim())
    const passage = `${cutAtStart ? '…' : ''}${snippet.text}${endsSentence ? '' : '…'}`
    snippetText = excerptAround(passage, query, PASSAGE_EXCERPT_LENGTH) ?? passage
    moreMatches = countMatches(passage, query) - countMatches(snippetText, query)

    if (snippet.start_char !== null && snippet.sentence_start_char !== null && snippet.sentence_end_char !== null) {
      // The sentence's offsets are in the file; less the passage's start, they are in the passage. The
      // server counts characters, and Array.from splits the text the same way.
      const characters = Array.from(snippet.text)
      const sentenceStart = snippet.sentence_start_char - snippet.start_char
      const sentenceEnd = snippet.sentence_end_char - snippet.start_char
      closestSentence = {
        before: sentenceStart > 0 || cutAtStart ? '…' : '',
        sentence: characters.slice(sentenceStart, sentenceEnd).join(''),
        after: `${characters.slice(sentenceEnd).join('')}${endsSentence ? '' : '…'}`,
      }
      const shownText = closestSentence.sentence + closestSentence.after
      moreMatches = countMatches(passage, query) - countMatches(shownText, query)
    }
  }

  return (
    <li
      title={match.label}
      onClick={() => onOpen(asset, snippet, query)}
      className="relative flex cursor-pointer gap-4 overflow-hidden rounded-xl bg-white p-3 pl-5 shadow-xs ring-1 ring-gray-200 transition-shadow hover:shadow-md hover:ring-gray-300"
    >
      <span className={`absolute inset-y-0 left-0 w-1 ${match.barClass}`} aria-hidden="true" />

      {asset.asset_type === 'image' ? (
        <img src={assetFileUrl(asset.id)} alt="" className="size-28 shrink-0 rounded-lg bg-gray-100 object-cover" />
      ) : (
        <div className="flex size-28 shrink-0 items-center justify-center rounded-lg bg-indigo-50">
          <DocumentIcon className="size-12 text-indigo-400" />
        </div>
      )}

      <div className="min-w-0 flex-1 py-1">
        <h3 className="truncate text-sm font-semibold text-gray-900">
          <button type="button" className="max-w-full truncate text-left hover:text-indigo-700">
            {title}
          </button>
        </h3>
        <p className="truncate text-xs text-gray-500">
          Found in{' '}
          <span className="font-medium text-gray-700">
            <HighlightedText text={asset.filename} query={query} />
          </span>
          {asset.aliases.length > 0 && (
            <span title={`This file is identical to: ${asset.aliases.join(', ')}`}>
              {' '}· identical to {asset.aliases.join(', ')}
            </span>
          )}
        </p>

        <div className="mt-2 flex items-center gap-2">
          <span className={`rounded px-1.5 py-0.5 text-[11px] font-semibold ${MATCH_COLOURS[result.match]}`}>
            {MATCH_LABELS[result.match]}
          </span>
          <p className="text-xs font-medium tracking-wide text-indigo-600 uppercase">{SNIPPET_LABELS[snippet.kind]}</p>
        </div>
        <p className="mt-0.5 line-clamp-3 text-sm text-gray-700">
          {closestSentence ? (
            <>
              {closestSentence.before}
              <mark className={CLOSEST_SENTENCE_CLASS} title={CLOSEST_SENTENCE_TITLE}>
                <HighlightedText text={closestSentence.sentence} query={query} />
              </mark>
              <HighlightedText text={closestSentence.after} query={query} />
            </>
          ) : (
            <HighlightedText text={snippetText} query={query} />
          )}
        </p>
        {moreMatches > 0 && (
          <p className="mt-1 text-xs font-medium text-indigo-600">
            {moreMatches} more {moreMatches === 1 ? 'match' : 'matches'} in this passage →
          </p>
        )}
        {imageTextExcerpt && (
          <>
            <p className="mt-2 text-xs font-medium tracking-wide text-indigo-600 uppercase">Text in the image</p>
            <p className="mt-0.5 line-clamp-2 font-mono text-xs text-gray-700">
              <HighlightedText text={imageTextExcerpt} query={query} />
            </p>
          </>
        )}
      </div>
    </li>
  )
}
