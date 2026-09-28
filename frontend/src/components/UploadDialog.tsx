// The window the Upload button opens: the drop box, for dropping or picking files. It sends nothing
// itself: the files go to onFiles, the dialog closes, and the upload panel shows their progress.
// Uses the browser's <dialog> element, which dims the page, keeps keyboard focus inside and closes on Esc.
import { useEffect, useRef } from 'react'
import { CloseIcon } from './icons'
import UploadArea from './UploadArea'

type UploadDialogProps = {
  open: boolean
  collection: string
  onFiles: (files: File[]) => void
  onClose: () => void
}

export default function UploadDialog({ open, collection, onFiles, onClose }: UploadDialogProps) {
  const dialog = useRef<HTMLDialogElement>(null)

  // The dialog is shown and hidden through its DOM methods, following the `open` prop.
  useEffect(() => {
    if (!dialog.current) {
      return
    }
    if (open && !dialog.current.open) {
      dialog.current.showModal()
    }
    if (!open && dialog.current.open) {
      dialog.current.close()
    }
  }, [open])

  function handleFiles(files: File[]) {
    onFiles(files)
    onClose()
  }

  return (
    <dialog
      ref={dialog}
      onClose={onClose}
      className="m-auto w-full max-w-lg rounded-2xl bg-surface p-6 shadow-xl backdrop:bg-ink-900/40 backdrop:backdrop-blur-sm"
    >
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-text">Upload files</h2>
          <p className="mt-0.5 text-sm text-text-muted">
            To <span className="font-medium text-text">{collection}</span>
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="rounded-md p-1 text-text-subtle hover:bg-surface-hover hover:text-text-muted"
        >
          <CloseIcon className="size-5" />
        </button>
      </div>
      <UploadArea onFiles={handleFiles} />
    </dialog>
  )
}
