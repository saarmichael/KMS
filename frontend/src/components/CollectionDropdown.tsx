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
  return <span className="rounded-full bg-surface-hover px-2 py-0.5 text-xs font-medium text-text-muted">{count}</span>
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
        className="flex items-center gap-2 rounded-lg bg-surface px-3 py-2 text-sm text-text-subtle ring-1 ring-border"
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
        className="flex min-w-52 items-center gap-2 rounded-lg bg-surface px-3 py-2 text-sm font-medium text-text shadow-xs ring-1 ring-border-strong hover:bg-surface-hover"
      >
        <FolderIcon className="size-5 text-text-subtle" />
        <span className="truncate">{current ? current.name : 'Choose a collection'}</span>
        {current && <CountPill count={current.asset_count} />}
        <ChevronDownIcon className="ml-auto size-4 text-text-subtle" />
      </button>

      {open && (
        <ul className="absolute left-0 z-10 mt-2 max-h-80 w-64 overflow-auto rounded-xl bg-surface p-1 shadow-lg ring-1 ring-border">
          {collections.map((collection) => {
            const isSelected = collection.name === selected
            return (
              <li key={collection.name}>
                <button
                  type="button"
                  onClick={() => pick(collection.name)}
                  className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${
                    isSelected ? 'bg-accent-soft font-medium text-accent-text' : 'text-text-muted hover:bg-surface-hover'
                  }`}
                >
                  <CheckIcon className={`size-4 ${isSelected ? 'text-accent-text' : 'invisible'}`} />
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
