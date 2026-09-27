// A large dialog with everything about one file: the file itself (the image, or the text with the
// matched passage marked), what the model wrote about it, and links to open or download it.
//
// How data reaches it:
//   CollectionView `detail` state -> <AssetDetailDialog asset snippet>
//     image -> <img src={assetFileUrl(id)}>
//     text  -> getAssetText(id) -> `text` state -> shown in full; snippet start_char..end_char marked
//     asset.metadata -> description, tags, visible text, type, model
//     query (when opened from a search) -> its words marked in the visible text, the first one scrolled to
//     <FileActions asset> -> Open in new tab / Download
import { useEffect, useRef, useState } from 'react'
import type { MouseEvent, ReactNode } from 'react'
import { ApiError, assetFileUrl, getAssetText } from '../api/client'
import type { Asset, Snippet } from '../api/types'
import { formatAge, formatBytes } from '../format'
import FileActions from './FileActions'
import HighlightedText from './HighlightedText'
import { CloseIcon, SpinnerIcon } from './icons'
import StatusBadge from './StatusBadge'

type AssetDetailDialogProps = {
  asset: Asset
  snippet: Snippet | null
  query: string | null
  onClose: () => void
}

export default function AssetDetailDialog({ asset, snippet, query, onClose }: AssetDetailDialogProps) {
  const dialog = useRef<HTMLDialogElement>(null)
  const textBox = useRef<HTMLPreElement>(null)
  const markedPassage = useRef<HTMLElement>(null)
  const visibleTextBox = useRef<HTMLDivElement>(null)
  const firstVisibleTextMark = useRef<HTMLElement>(null)
  const [text, setText] = useState<string | null>(null)
  const [textError, setTextError] = useState<string | null>(null)

  // ---- Talks to the API -------------------------------------------------------------------

  // A text file's content is fetched when the dialog opens; an image is loaded by the <img> itself.
  useEffect(() => {
    if (asset.asset_type !== 'text') {
      return
    }
    getAssetText(asset.id)
      .then((loaded) => setText(loaded))
      .catch((caught) => setTextError(caught instanceof ApiError ? caught.detail : 'Could not load the file.'))
  }, [asset.id, asset.asset_type])

  // ---- Display ------------------------------------------------------------------------------

  // The dialog exists only while it is open, so it opens as a modal as soon as it is on the page.
  useEffect(() => {
    dialog.current?.showModal()
  }, [])

  // Once the text is on screen, only the text box scrolls so the marked passage sits in its middle;
  // the dialog itself stays put, title in view. offsetTop is measured from the box (it is `relative`).
  useEffect(() => {
    if (textBox.current && markedPassage.current) {
      textBox.current.scrollTop = markedPassage.current.offsetTop - textBox.current.clientHeight / 2
    }
  }, [text])

  // The same for the first query word marked in an image's visible text, inside its own box.
  useEffect(() => {
    if (visibleTextBox.current && firstVisibleTextMark.current) {
      visibleTextBox.current.scrollTop =
        firstVisibleTextMark.current.offsetTop - visibleTextBox.current.clientHeight / 2
    }
  }, [])

  // A click on the dimmed area outside the white panel lands on the <dialog> element itself.
  function handleDialogClick(event: MouseEvent<HTMLDialogElement>) {
    if (event.target === dialog.current) {
      onClose()
    }
  }

  const metadata = asset.metadata
  const title = metadata ? metadata.title : asset.filename

  function renderText() {
    if (textError) {
      return <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{textError}</p>
    }
    if (text === null) {
      return (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <SpinnerIcon className="size-4 text-indigo-600" />
          Loading the file…
        </div>
      )
    }

    let content: ReactNode = text
    if (snippet && snippet.kind === 'content' && snippet.start_char !== null && snippet.end_char !== null) {
      // The server counts offsets in characters; Array.from splits the text the same way (an emoji is
      // one character here, but two units in a plain JavaScript string).
      const characters = Array.from(text)
      const before = characters.slice(0, snippet.start_char).join('')
      const passage = characters.slice(snippet.start_char, snippet.end_char).join('')
      const after = characters.slice(snippet.end_char).join('')
      content = (
        <>
          {before}
          <mark ref={markedPassage} className="rounded-sm bg-indigo-100 text-indigo-900">
            {passage}
          </mark>
          {after}
        </>
      )
    }

    return (
      <pre
        ref={textBox}
        className="relative max-h-[50vh] overflow-auto rounded-lg bg-gray-50 p-4 font-mono text-sm whitespace-pre-wrap text-gray-800 ring-1 ring-gray-200">
        {content}
      </pre>
    )
  }

  return (
    <dialog
      ref={dialog}
      onClose={onClose}
      onClick={handleDialogClick}
      className="m-auto max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-2xl bg-white shadow-xl backdrop:bg-gray-900/40 backdrop:backdrop-blur-sm"
    >
      <div className="space-y-6 p-6">
        <div className="flex items-start gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="truncate text-lg font-semibold text-gray-900">{title}</h2>
              <StatusBadge status={asset.status} />
            </div>
            {/* Without metadata the title already is the filename. */}
            {metadata && <p className="truncate text-sm text-gray-500">{asset.filename}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <CloseIcon className="size-5" />
          </button>
        </div>

        <FileActions asset={asset} />

        {asset.asset_type === 'image' ? (
          // Shown at its own size at most, so a small image is not stretched and blurred.
          <img
            src={assetFileUrl(asset.id)}
            alt={title}
            className="mx-auto max-h-[60vh] max-w-full rounded-lg bg-gray-100"
          />
        ) : (
          renderText()
        )}

        {asset.status === 'failed' && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{asset.error}</p>
        )}
        {(asset.status === 'pending' || asset.status === 'processing') && (
          <p className="text-sm text-gray-500">The description and tags appear once processing finishes.</p>
        )}

        <dl className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
          {metadata && (
            <>
              <Field label="Description" wide>
                {metadata.description}
              </Field>
              {metadata.tags.length > 0 && (
                <Field label="Tags" wide>
                  <div className="flex flex-wrap gap-1.5">
                    {metadata.tags.map((tag) => (
                      <span key={tag} className="rounded-md bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">
                        {tag}
                      </span>
                    ))}
                  </div>
                </Field>
              )}
              {metadata.visible_text && (
                <Field label="Visible text" wide>
                  <div
                    ref={visibleTextBox}
                    className="relative max-h-60 overflow-auto rounded-lg bg-gray-50 px-3 py-2 font-mono text-xs whitespace-pre-wrap ring-1 ring-gray-200"
                  >
                    {query ? (
                      <HighlightedText text={metadata.visible_text} query={query} firstMarkRef={firstVisibleTextMark} />
                    ) : (
                      metadata.visible_text
                    )}
                  </div>
                </Field>
              )}
              {metadata.image_type && <Field label="Type">{metadata.image_type}</Field>}
              {metadata.vision_model && <Field label="Described by">{metadata.vision_model}</Field>}
            </>
          )}
          <Field label="File">
            {asset.filename}
            {asset.aliases.length > 0 && (
              <span className="block text-gray-500">also uploaded as {asset.aliases.join(', ')}</span>
            )}
            <span className="block text-gray-500">
              {asset.mime} · {formatBytes(asset.size_bytes)}
            </span>
          </Field>
          <Field label="Uploaded">
            {new Date(asset.created_at).toLocaleString()}
            <span className="block text-gray-500">{formatAge(asset.created_at)}</span>
          </Field>
        </dl>
      </div>
    </dialog>
  )
}

// One labelled value in the details list; `wide` makes it span both columns.
function Field({ label, wide = false, children }: { label: string; wide?: boolean; children: ReactNode }) {
  return (
    <div className={wide ? 'sm:col-span-2' : ''}>
      <dt className="text-xs font-medium tracking-wide text-gray-500 uppercase">{label}</dt>
      <dd className="mt-1 text-sm text-gray-800">{children}</dd>
    </div>
  )
}
