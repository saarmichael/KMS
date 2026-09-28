// One search result: thumbnail, title, which file it was found in, and the passage or description that
// matched. The coloured bar on the left edge shows how close the match is; nothing is faded.
//
// How data reaches it:
//   SearchResults `results` state -> <SearchResultCard result query>
//     result.asset    -> thumbnail (assetFileUrl), title, "Found in" filename (query words marked) and aliases
//     result.snippet  -> what matched ("In the text" ...) and the text, with the query words marked; a
//                        passage is cut to start just before its first query word, and the query words
//                        the cut left out are counted: "2 more matches in this passage →". A result
//                        matched by meaning, whatever the kind of snippet, starts on its closest
//                        sentence instead (snippet.sentence_start / sentence_end) -> <ClosestSentenceText>
//     asset.metadata.visible_text -> for an image whose text contains a query word: "Text in the image",
//                        unless the snippet already is that text
//     result.score    -> closeness() -> colour of the edge bar and its tooltip
//     result.match    -> the badge: exact, partial or semantic, in its colour
//   a click on the card -> onOpen(asset, snippet, query) -> the detail dialog, with the matches marked
import { assetFileUrl } from '../api/client'
import type { Asset, SearchResult, Snippet } from '../api/types'
import { closeness } from '../closeness'
import { MATCH_COLOURS, MATCH_LABELS } from '../searchView'
import { countMatches, excerptAround } from '../queryWords'
import ClosestSentenceText from './ClosestSentenceText'
import type { SentenceRange } from './ClosestSentenceText'
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
  visible_text: 'In the text in the image',
  filename: 'In the file name',
}

export default function SearchResultCard({ result, query, onOpen }: SearchResultCardProps) {
  const { asset, score, snippet } = result
  const match = closeness(score)
  const title = asset.metadata ? asset.metadata.title : asset.filename

  // The API gives no position for a match in an image's text, so the query words are looked up here. When
  // the snippet is the image's text, the preview already shows it.
  let imageTextExcerpt: string | null = null
  if (asset.asset_type === 'image' && asset.metadata?.visible_text && snippet.kind !== 'visible_text') {
    imageTextExcerpt = excerptAround(asset.metadata.visible_text, query, IMAGE_TEXT_EXCERPT_LENGTH)
  }

  // A passage from the middle of a file gets "…" where it was cut: before it unless it starts the file,
  // after it unless it ends a sentence. A description or a file name is whole.
  let opening = ''
  let closing = ''
  if (snippet.kind === 'content') {
    if (snippet.start_char !== null && snippet.start_char > 0) {
      opening = '…'
    }
    if (!/[.!?]$/.test(snippet.text.trim())) {
      closing = '…'
    }
  }
  const fullText = `${opening}${snippet.text}${closing}`

  // The card shows three lines, so the preview starts where the reason for the match is; otherwise it could
  // fall below the cut. A result matched by meaning starts on the sentence the search named closest to the
  // query, which is marked; a passage or an image's text without one starts just before its first query word.
  let previewText = fullText
  let previewSentence: SentenceRange | null = null
  if (snippet.sentence_start !== null && snippet.sentence_end !== null) {
    // The server counts characters, and Array.from splits the text the same way.
    const characters = Array.from(snippet.text)
    const cutBefore = snippet.sentence_start > 0 || opening !== '' ? '…' : ''
    previewText = `${cutBefore}${characters.slice(snippet.sentence_start).join('')}${closing}`
    previewSentence = {
      start: cutBefore.length,
      end: cutBefore.length + snippet.sentence_end - snippet.sentence_start,
    }
  } else if (snippet.kind === 'content' || snippet.kind === 'visible_text') {
    previewText = excerptAround(fullText, query, PASSAGE_EXCERPT_LENGTH) ?? fullText
  }

  // Query words in a passage that the preview left out; the card says how many, so the user knows the
  // dialog has more to show.
  let moreMatches = 0
  if (snippet.kind === 'content') {
    moreMatches = countMatches(fullText, query) - countMatches(previewText, query)
  }

  return (
    <li
      title={match.label}
      onClick={() => onOpen(asset, snippet, query)}
      className="relative flex cursor-pointer gap-4 overflow-hidden rounded-xl bg-surface p-3 pl-5 shadow-xs ring-1 ring-border transition-shadow hover:shadow-md hover:ring-border-strong"
    >
      <span className={`absolute inset-y-0 left-0 w-1 ${match.barClass}`} aria-hidden="true" />

      {asset.asset_type === 'image' ? (
        <img src={assetFileUrl(asset.id)} alt="" className="size-28 shrink-0 rounded-lg bg-surface-hover object-cover" />
      ) : (
        <div className="flex size-28 shrink-0 items-center justify-center rounded-lg bg-accent-soft">
          <DocumentIcon className="size-12 text-accent" />
        </div>
      )}

      <div className="min-w-0 flex-1 py-1">
        <h3 className="truncate text-sm font-semibold text-text">
          <button type="button" className="max-w-full truncate text-left hover:text-accent-text">
            {title}
          </button>
        </h3>
        <p className="truncate text-xs text-text-muted">
          Found in{' '}
          <span className="font-medium text-text-muted">
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
          <p className="text-xs font-medium tracking-wide text-accent-text uppercase">{SNIPPET_LABELS[snippet.kind]}</p>
        </div>
        {/* Text read from an image is set in monospace, as it is in the dialog's visible-text box. */}
        <p
          className={`mt-0.5 line-clamp-3 text-text-muted ${snippet.kind === 'visible_text' ? 'font-mono text-xs' : 'text-sm'}`}
        >
          <ClosestSentenceText text={previewText} query={query} sentence={previewSentence} />
        </p>
        {moreMatches > 0 && (
          <p className="mt-1 text-xs font-medium text-accent-text">
            {moreMatches} more {moreMatches === 1 ? 'match' : 'matches'} in this passage →
          </p>
        )}
        {imageTextExcerpt && (
          <>
            <p className="mt-2 text-xs font-medium tracking-wide text-accent-text uppercase">Text in the image</p>
            <p className="mt-0.5 line-clamp-2 font-mono text-xs text-text-muted">
              <HighlightedText text={imageTextExcerpt} query={query} />
            </p>
          </>
        )}
      </div>
    </li>
  )
}
