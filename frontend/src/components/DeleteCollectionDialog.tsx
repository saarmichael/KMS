// Asks for confirmation before a collection is deleted. Uses the browser's <dialog> element, which
// dims the page, keeps keyboard focus inside and closes on Esc.
import { useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'
import { TrashIcon } from './icons'

type DeleteCollectionDialogProps = {
  name: string
  assetCount: number
  open: boolean
  onConfirm: () => Promise<void>
  onClose: () => void
}

export default function DeleteCollectionDialog({ name, assetCount, open, onConfirm, onClose }: DeleteCollectionDialogProps) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Runs the delete the parent passed in; a failure stays in the dialog as a message.
  async function handleDelete() {
    setBusy(true)
    setError(null)
    try {
      await onConfirm()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  // The dialog is shown and hidden through its DOM methods, following the `open` prop.
  useEffect(() => {
    if (!dialog.current) {
      return
    }
    if (open && !dialog.current.open) {
      setError(null)
      dialog.current.showModal()
    }
    if (!open && dialog.current.open) {
      dialog.current.close()
    }
  }, [open])

  let filesSentence = `Its ${assetCount} files are deleted with it.`
  if (assetCount === 0) {
    filesSentence = 'It has no files yet.'
  } else if (assetCount === 1) {
    filesSentence = 'Its 1 file is deleted with it.'
  }

  return (
    <dialog
      ref={dialog}
      onClose={onClose}
      className="m-auto w-full max-w-md rounded-2xl bg-surface p-6 shadow-xl backdrop:bg-ink-900/40 backdrop:backdrop-blur-sm"
    >
      <div className="flex gap-4">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-danger-soft">
          <TrashIcon className="size-5 text-danger" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-text">Delete collection</h2>
          <p className="mt-2 text-sm text-text-muted">
            Delete <span className="font-semibold text-text">{name}</span>? {filesSentence} This cannot be
            undone.
          </p>
          {error && <p className="mt-3 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
        </div>
      </div>
      <div className="mt-6 flex justify-end gap-3">
        <button
          type="button"
          onClick={onClose}
          disabled={busy}
          className="rounded-lg bg-surface px-3 py-2 text-sm font-semibold text-text shadow-xs ring-1 ring-border-strong hover:bg-surface-hover disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleDelete}
          disabled={busy}
          className="rounded-lg bg-danger px-3 py-2 text-sm font-semibold text-white shadow-xs hover:bg-danger/90 disabled:opacity-50"
        >
          {busy ? 'Deleting…' : 'Delete'}
        </button>
      </div>
    </dialog>
  )
}
