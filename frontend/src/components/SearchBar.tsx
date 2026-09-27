// The search box. It sends nothing itself: the typed query is handed to onSearch, and the parent
// shows the results. While a search runs the box is read-only and greyed with a sweeping bar, and the
// Search button becomes Cancel. On the home view the box is large with its button centred below it;
// `compact`, used above the results, puts the button beside a smaller box.
import { useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { CloseIcon, SearchIcon, SpinnerIcon } from './icons'

type SearchBarProps = {
  compact: boolean
  searching: boolean
  onSearch: (query: string) => void
  onCancel: () => void
  onClear: () => void
}

export default function SearchBar({ compact, searching, onSearch, onCancel, onClear }: SearchBarProps) {
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
    // The two layouts differ only in classes, never in elements, so switching between them keeps the
    // input (and what is typed in it) in place.
    <form
      onSubmit={handleSubmit}
      onKeyDown={handleKeyDown}
      className={compact ? 'flex gap-2' : 'flex flex-col items-center gap-5'}
    >
      {/* overflow-hidden keeps the sweeping bar inside the rounded box. It would also clip an outline or
          shadow drawn around the input, so the input has a border (drawn inside it) and the shadow is here. */}
      <div
        className={`relative w-full flex-1 overflow-hidden rounded-full ${
          compact ? 'shadow-sm' : 'shadow-lg shadow-indigo-900/10'
        }`}
      >
        {searching ? (
          <SpinnerIcon className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-indigo-500" />
        ) : (
          <SearchIcon
            className={`pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 ${
              compact ? 'size-5 text-gray-400' : 'size-6 text-indigo-500'
            }`}
          />
        )}
        <input
          value={text}
          onChange={(event) => setText(event.target.value)}
          readOnly={searching}
          placeholder="Search this collection, e.g. black hair, receipts, a screenshot with text"
          aria-label="Search"
          className={`w-full rounded-full border-2 pr-12 outline-none focus:border-indigo-600 ${
            compact ? 'py-2 pl-12 text-base placeholder:text-gray-400' : 'py-4 pl-13 text-lg placeholder:text-gray-500'
          } ${
            searching
              ? 'border-gray-200 bg-gray-100 text-gray-500'
              : 'border-gray-300 bg-white text-gray-900 hover:border-indigo-300'
          }`}
        />
        {!searching && text !== '' && (
          <button
            type="button"
            onClick={clear}
            aria-label="Clear search"
            className="absolute top-1/2 right-3 -translate-y-1/2 rounded-full p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <CloseIcon className="size-5" />
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
          className="flex shrink-0 items-center gap-1.5 rounded-full bg-white px-6 py-2.5 text-sm font-semibold text-red-600 shadow-xs ring-1 ring-red-300 hover:bg-red-50"
        >
          <CloseIcon className="size-4" />
          Cancel
        </button>
      ) : (
        <button
          type="submit"
          className="shrink-0 rounded-full bg-indigo-600 px-6 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-indigo-500"
        >
          Search
        </button>
      )}
    </form>
  )
}
