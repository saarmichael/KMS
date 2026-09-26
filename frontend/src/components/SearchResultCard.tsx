// One search result: thumbnail, title, which file it was found in, and the passage or description that
// matched. The coloured bar on the left edge shows how close the match is; nothing is faded.
//
// How data reaches it:
//   SearchResults `results` state -> <SearchResultCard result query>
//     result.asset    -> thumbnail (assetFileUrl), title, "Found in" filename and aliases
//     result.snippet  -> what matched ("In the text" ...) and the text, with the query words marked
//     asset.metadata.visible_text -> for an image whose text contains a query word: "Text in the image"
//     result.score    -> closeness() -> colour of the edge bar and its tooltip
//   a click on the card -> onOpen(asset, snippet, query) -> the detail dialog, with the matches marked
import { assetFileUrl } from '../api/client'
import type { Asset, SearchResult, Snippet } from '../api/types'
import { closeness } from '../closeness'
import { excerptAround } from '../queryWords'
import HighlightedText from './HighlightedText'
import { DocumentIcon } from './icons'

type SearchResultCardProps = {
  result: SearchResult
  query: string
  onOpen: (asset: Asset, snippet: Snippet, query: string) => void
}

const IMAGE_TEXT_EXCERPT_LENGTH = 160

const SNIPPET_LABELS: Record<Snippet['kind'], string> = {
  content: 'In the text',
  metadata: 'In the description',
  image: 'In the image',
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
  // after it unless it ends a sentence.
  let snippetText = snippet.text
  if (snippet.kind === 'content') {
    const cutAtStart = snippet.start_char !== null && snippet.start_char > 0
    const endsSentence = /[.!?]$/.test(snippet.text.trim())
    snippetText = `${cutAtStart ? '…' : ''}${snippet.text}${endsSentence ? '' : '…'}`
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
          Found in <span className="font-medium text-gray-700">{asset.filename}</span>
          {asset.aliases.length > 0 && (
            <span title={`This file is identical to: ${asset.aliases.join(', ')}`}>
              {' '}· identical to {asset.aliases.join(', ')}
            </span>
          )}
        </p>

        <p className="mt-2 text-xs font-medium tracking-wide text-indigo-600 uppercase">{SNIPPET_LABELS[snippet.kind]}</p>
        <p className="mt-0.5 line-clamp-3 text-sm text-gray-700">
          <HighlightedText text={snippetText} query={query} />
        </p>
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
