// The card in the bottom-right corner that follows every upload: one bar for everything sent so far,
// and one row per file with its own bar, then a tick, a note that it was already there, or why it was
// refused. It can be folded down to its header, and closed once nothing is still uploading.
//
// How data reaches it:
//   App.handleFiles -> `uploads` state, each item updated as its bytes go out and when it ends
//     -> <UploadPanel uploads> -> the header counts, the overall bar, one row per item
//   × -> onClose -> App clears the finished uploads
import { useState } from 'react'
import { CheckIcon, ChevronDownIcon, CloseIcon, ExclamationIcon } from './icons'

export type UploadItem = {
  id: number
  file: File
  collection: string
  // The fraction of the file sent so far, from 0 to 1.
  progress: number
  state: 'uploading' | 'done' | 'duplicate' | 'error'
  // Set for a duplicate (which file it matches) and for an error (why it was refused).
  message: string | null
}

type UploadPanelProps = {
  uploads: UploadItem[]
  onClose: () => void
}

export default function UploadPanel({ uploads, onClose }: UploadPanelProps) {
  const [folded, setFolded] = useState(false)

  if (uploads.length === 0) {
    return null
  }

  const uploadingCount = uploads.filter((upload) => upload.state === 'uploading').length
  const failedCount = uploads.filter((upload) => upload.state === 'error').length
  const finishedCount = uploads.length - uploadingCount

  // The overall bar counts bytes, not files, so one large file does not jump it forward at the end.
  let totalBytes = 0
  let sentBytes = 0
  for (const upload of uploads) {
    totalBytes += upload.file.size
    sentBytes += upload.file.size * upload.progress
  }
  const overallFraction = totalBytes > 0 ? sentBytes / totalBytes : 1

  let title = `${uploads.length} ${uploads.length === 1 ? 'upload' : 'uploads'} complete`
  if (uploadingCount > 0) {
    title = `Uploading ${uploadingCount} ${uploadingCount === 1 ? 'file' : 'files'}`
  } else if (failedCount > 0) {
    title = `${finishedCount - failedCount} uploaded, ${failedCount} failed`
  }

  return (
    <section
      aria-label="Uploads"
      className="fixed right-4 bottom-4 z-40 w-96 max-w-[calc(100vw-2rem)] overflow-hidden rounded-2xl bg-white shadow-xl ring-1 ring-gray-200"
    >
      <div className="flex items-center gap-2 bg-gray-900 px-4 py-3 text-white">
        <h2 className="min-w-0 flex-1 truncate text-sm font-semibold">{title}</h2>
        <button
          type="button"
          onClick={() => setFolded(!folded)}
          aria-label={folded ? 'Show uploads' : 'Hide uploads'}
          className="rounded-md p-1 text-gray-300 hover:bg-white/10 hover:text-white"
        >
          <ChevronDownIcon className={`size-4 transition-transform ${folded ? 'rotate-180' : ''}`} />
        </button>
        {/* Closing mid-upload would hide files still on their way, so it waits until all have ended. */}
        <button
          type="button"
          onClick={onClose}
          disabled={uploadingCount > 0}
          aria-label="Close"
          title={uploadingCount > 0 ? 'Available once every upload has ended' : 'Close'}
          className="rounded-md p-1 text-gray-300 hover:bg-white/10 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <CloseIcon className="size-4" />
        </button>
      </div>

      {uploadingCount > 0 && (
        <div className="border-b border-gray-100 px-4 py-2.5">
          <div className="flex justify-between text-xs text-gray-500">
            <span>
              {finishedCount} of {uploads.length} done
            </span>
            <span>{Math.round(overallFraction * 100)}%</span>
          </div>
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-gray-100">
            <div className="h-full rounded-full bg-indigo-600 transition-[width]" style={{ width: `${overallFraction * 100}%` }} />
          </div>
        </div>
      )}

      {!folded && (
        <ul className="max-h-72 divide-y divide-gray-100 overflow-y-auto">
          {uploads.map((upload) => (
            <li key={upload.id} className="px-4 py-2.5">
              <div className="flex items-center gap-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-gray-900">{upload.file.name}</p>
                  <p className="truncate text-xs text-gray-500">To {upload.collection}</p>
                </div>
                {upload.state === 'uploading' && (
                  <span className="text-xs text-gray-500 tabular-nums">{Math.round(upload.progress * 100)}%</span>
                )}
                {upload.state === 'done' && <CheckIcon className="size-5 shrink-0 text-green-600" />}
                {upload.state === 'duplicate' && <CheckIcon className="size-5 shrink-0 text-gray-400" />}
                {upload.state === 'error' && <ExclamationIcon className="size-5 shrink-0 text-red-600" />}
              </div>
              {upload.state === 'uploading' && (
                <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className="h-full rounded-full bg-indigo-500 transition-[width]"
                    style={{ width: `${upload.progress * 100}%` }}
                  />
                </div>
              )}
              {upload.message && (
                <p className={`mt-1 text-xs ${upload.state === 'error' ? 'text-red-700' : 'text-gray-500'}`}>
                  {upload.message}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
