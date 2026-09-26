// The search box. It sends nothing itself: the typed query is handed to onSearch, and the parent
// shows the results. While a search runs the box is read-only and greyed with a sweeping bar, and the
// Search button becomes Cancel.
import { useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { CloseIcon, SearchIcon, SpinnerIcon } from './icons'

type SearchBarProps = {
  searching: boolean
  onSearch: (query: string) => void
  onCancel: () => void
  onClear: () => void
}

export default function SearchBar({ searching, onSearch, onCancel, onClear }: SearchBarProps) {
  const [text, setText] = useState('')

  // An empty query is not sent: the API would refuse it. Enter during a search does nothing;
  // only the Cancel button or Esc stops it.
  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (searching) {
      return
    }
    const query = text.trim()
    if (query !== '') {
      onSearch(query)
    }
  }

  function clear() {
    setText('')
    onClear()
  }

  // Cancelling returns the page to its starting state, empty box included.
  function cancel() {
    setText('')
    onCancel()
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      if (searching) {
        cancel()
      } else {
        clear()
      }
    }
  }

  return (
    <form onSubmit={handleSubmit} onKeyDown={handleKeyDown} className="flex gap-2">
      <div className="relative flex-1 overflow-hidden rounded-xl">
        {searching ? (
          <SpinnerIcon className="pointer-events-none absolute top-1/2 left-3 size-5 -translate-y-1/2 text-indigo-500" />
        ) : (
          <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-5 -translate-y-1/2 text-gray-400" />
        )}
        <input
          value={text}
          onChange={(event) => setText(event.target.value)}
          readOnly={searching}
          placeholder="Search this collection, e.g. black hair, receipts, a screenshot with text"
          aria-label="Search"
          className={`w-full rounded-xl py-3 pr-10 pl-10 text-sm shadow-xs ring-1 outline-none placeholder:text-gray-400 focus:ring-2 focus:ring-indigo-600 ${
            searching ? 'bg-gray-100 text-gray-500 ring-gray-200' : 'bg-white text-gray-900 ring-gray-300'
          }`}
        />
        {!searching && text !== '' && (
          <button
            type="button"
            onClick={clear}
            aria-label="Clear search"
            className="absolute top-1/2 right-2 -translate-y-1/2 rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <CloseIcon className="size-4" />
          </button>
        )}
        {searching && (
          <span className="pointer-events-none absolute inset-x-0 bottom-0 h-0.5" aria-hidden="true">
            <span className="block h-full w-1/4 animate-sweep rounded-full bg-indigo-500" />
          </span>
        )}
      </div>

      {searching ? (
        <button
          type="button"
          onClick={cancel}
          className="flex items-center gap-1.5 rounded-xl bg-white px-5 text-sm font-semibold text-red-600 shadow-xs ring-1 ring-red-300 hover:bg-red-50"
        >
          <CloseIcon className="size-4" />
          Cancel
        </button>
      ) : (
        <button
          type="submit"
          className="rounded-xl bg-indigo-600 px-5 text-sm font-semibold text-white shadow-xs hover:bg-indigo-500"
        >
          Search
        </button>
      )}
    </form>
  )
}
