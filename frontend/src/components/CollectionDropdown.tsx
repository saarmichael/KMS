// The collection picker: a button showing the selected collection, which opens a list of all
// collections with their file counts.
import { useEffect, useRef, useState } from 'react'
import type { Collection } from '../api/types'
import { CheckIcon, ChevronDownIcon, FolderIcon } from './icons'

type CollectionDropdownProps = {
  collections: Collection[]
  selected: string | null
  onSelect: (name: string) => void
}

function CountPill({ count }: { count: number }) {
  return <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">{count}</span>
}

export default function CollectionDropdown({ collections, selected, onSelect }: CollectionDropdownProps) {
  const [open, setOpen] = useState(false)
  const container = useRef<HTMLDivElement>(null)

  // While the list is open, a click anywhere outside it or the Esc key closes it.
  useEffect(() => {
    if (!open) {
      return
    }
    function closeOnOutsideClick(event: MouseEvent) {
      if (container.current && !container.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('mousedown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  if (collections.length === 0) {
    return (
      <button
        type="button"
        disabled
        className="flex items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm text-gray-400 ring-1 ring-gray-200"
      >
        <FolderIcon className="size-5" />
        No collections
      </button>
    )
  }

  const current = collections.find((collection) => collection.name === selected)

  function pick(name: string) {
    onSelect(name)
    setOpen(false)
  }

  return (
    <div ref={container} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex min-w-52 items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm font-medium text-gray-900 shadow-xs ring-1 ring-gray-300 hover:bg-gray-50"
      >
        <FolderIcon className="size-5 text-gray-400" />
        <span className="truncate">{current ? current.name : 'Choose a collection'}</span>
        {current && <CountPill count={current.asset_count} />}
        <ChevronDownIcon className="ml-auto size-4 text-gray-400" />
      </button>

      {open && (
        <ul className="absolute left-0 z-10 mt-2 max-h-80 w-64 overflow-auto rounded-xl bg-white p-1 shadow-lg ring-1 ring-gray-900/5">
          {collections.map((collection) => {
            const isSelected = collection.name === selected
            return (
              <li key={collection.name}>
                <button
                  type="button"
                  onClick={() => pick(collection.name)}
                  className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${
                    isSelected ? 'bg-indigo-50 font-medium text-indigo-700' : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <CheckIcon className={`size-4 ${isSelected ? 'text-indigo-600' : 'invisible'}`} />
                  <span className="truncate">{collection.name}</span>
                  <span className="ml-auto">
                    <CountPill count={collection.asset_count} />
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
