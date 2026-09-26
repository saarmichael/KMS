// What needs attention after an upload batch: files the server refused, and files that were already
// in the collection. Files that went in fine need no notice; they appear as tiles.
import { CloseIcon } from './icons'

export type UploadNotice = {
  kind: 'error' | 'duplicate'
  text: string
}

type UploadNoticesProps = {
  notices: UploadNotice[]
  onDismiss: () => void
}

export default function UploadNotices({ notices, onDismiss }: UploadNoticesProps) {
  if (notices.length === 0) {
    return null
  }

  return (
    <div className="relative rounded-xl bg-white p-4 pr-12 shadow-xs ring-1 ring-gray-200">
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="absolute top-3 right-3 rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
      >
        <CloseIcon className="size-4" />
      </button>
      <ul className="space-y-1.5 text-sm">
        {notices.map((notice, index) => (
          <li key={index} className={notice.kind === 'error' ? 'text-red-700' : 'text-gray-600'}>
            {notice.text}
          </li>
        ))}
      </ul>
    </div>
  )
}
