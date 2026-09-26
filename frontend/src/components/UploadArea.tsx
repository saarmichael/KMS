// The drop box for new files. It sends nothing itself: dropped or picked files are handed to
// onFiles, and the parent uploads them.
import { useRef, useState } from 'react'
import type { ChangeEvent, DragEvent } from 'react'
import { SpinnerIcon, UploadIcon } from './icons'

type UploadAreaProps = {
  onFiles: (files: File[]) => void
  uploadingCount: number
}

export default function UploadArea({ onFiles, uploadingCount }: UploadAreaProps) {
  const [dragging, setDragging] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  function handFilesUp(fileList: FileList | null) {
    if (fileList && fileList.length > 0) {
      onFiles(Array.from(fileList))
    }
  }

  // Without preventDefault the browser would open the dropped file itself.
  function handleDragOver(event: DragEvent) {
    event.preventDefault()
    setDragging(true)
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    handFilesUp(event.dataTransfer.files)
  }

  function handlePicked(event: ChangeEvent<HTMLInputElement>) {
    handFilesUp(event.target.files)
    // Clearing the input lets the same file be picked again later.
    event.target.value = ''
  }

  if (uploadingCount > 0) {
    const files = uploadingCount === 1 ? '1 file' : `${uploadingCount} files`
    return (
      <div className="flex items-center justify-center gap-3 rounded-xl border-2 border-dashed border-indigo-300 bg-indigo-50/50 px-6 py-8 text-sm font-medium text-indigo-700">
        <SpinnerIcon className="size-5" />
        Uploading {files}…
      </div>
    )
  }

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`flex flex-col items-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors ${
        dragging ? 'border-indigo-400 bg-indigo-50' : 'border-gray-300 bg-white'
      }`}
    >
      <UploadIcon className={`size-8 ${dragging ? 'text-indigo-500' : 'text-gray-400'}`} />
      <p className="mt-3 text-sm text-gray-700">
        Drop files here, or{' '}
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          className="font-semibold text-indigo-600 hover:text-indigo-500"
        >
          browse
        </button>
      </p>
      <p className="mt-1 text-xs text-gray-500">Images and text files, up to 10 MB each</p>
      <input ref={fileInput} type="file" multiple onChange={handlePicked} className="hidden" />
    </div>
  )
}
