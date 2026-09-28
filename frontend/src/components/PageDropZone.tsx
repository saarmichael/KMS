// Files dragged anywhere onto the page are uploaded to the selected collection, without opening the
// upload dialog first. While files are dragged over the page, an overlay says where they will go.
// It sends nothing itself: dropped files go to onFiles, and the parent uploads them.
import { useEffect, useRef, useState } from 'react'
import { UploadIcon } from './icons'

type PageDropZoneProps = {
  collection: string | null
  onFiles: (files: File[]) => void
}

export default function PageDropZone({ collection, onFiles }: PageDropZoneProps) {
  const [dragging, setDragging] = useState(false)
  // dragenter and dragleave fire for every element the pointer crosses, so a single dragleave does not
  // mean the drag has left the page. Counting enters minus leaves does: the drag is out at zero.
  // A ref, not a variable inside the effect, so the count survives the effect running again mid-drag.
  const depth = useRef(0)

  // The listeners go on `window`, so a drop anywhere counts, whatever element is under the pointer.
  // They are added when the component appears and removed by the cleanup, and added again when the
  // collection or onFiles changes, so a drop always goes to the collection selected at that moment.
  useEffect(() => {
    // A drag of selected text or a link carries no files and is left alone.
    function carriesFiles(event: DragEvent): boolean {
      return event.dataTransfer?.types.includes('Files') ?? false
    }

    function handleDragEnter(event: DragEvent) {
      if (!carriesFiles(event)) {
        return
      }
      depth.current += 1
      if (collection !== null) {
        setDragging(true)
      }
    }

    // Without preventDefault the browser would refuse the drop, or open the file in place of the app.
    function handleDragOver(event: DragEvent) {
      if (carriesFiles(event)) {
        event.preventDefault()
      }
    }

    function handleDragLeave(event: DragEvent) {
      if (!carriesFiles(event)) {
        return
      }
      depth.current -= 1
      if (depth.current === 0) {
        setDragging(false)
      }
    }

    // A drop the upload dialog's box already took arrives here with defaultPrevented set, and is skipped.
    function handleDrop(event: DragEvent) {
      if (!carriesFiles(event)) {
        return
      }
      depth.current = 0
      setDragging(false)
      if (event.defaultPrevented) {
        return
      }
      event.preventDefault()
      const files = Array.from(event.dataTransfer?.files ?? [])
      if (collection !== null && files.length > 0) {
        onFiles(files)
      }
    }

    window.addEventListener('dragenter', handleDragEnter)
    window.addEventListener('dragover', handleDragOver)
    window.addEventListener('dragleave', handleDragLeave)
    window.addEventListener('drop', handleDrop)
    return () => {
      window.removeEventListener('dragenter', handleDragEnter)
      window.removeEventListener('dragover', handleDragOver)
      window.removeEventListener('dragleave', handleDragLeave)
      window.removeEventListener('drop', handleDrop)
    }
  }, [collection, onFiles])

  if (!dragging || collection === null) {
    return null
  }

  // pointer-events-none: the overlay only shows; the drag events still reach the page under it.
  return (
    <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-accent/10 p-4 backdrop-blur-[1px]">
      <div className="absolute inset-3 rounded-2xl border-2 border-dashed border-accent" />
      <div className="flex flex-col items-center rounded-2xl bg-surface px-10 py-8 text-center shadow-xl">
        <UploadIcon className="size-10 text-accent" />
        <p className="mt-3 text-base font-semibold text-text">Drop files to upload</p>
        <p className="mt-1 text-sm text-text-muted">
          To <span className="font-medium text-text">{collection}</span>
        </p>
      </div>
    </div>
  )
}
