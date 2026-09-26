// A small inline form for naming a new collection. It only calls onCreate with a valid name.
import { useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { isValidCollectionName, NAME_RULE_HINT } from '../collections'

type NewCollectionFormProps = {
  onCreate: (name: string) => void
  onCancel: () => void
}

export default function NewCollectionForm({ onCreate, onCancel }: NewCollectionFormProps) {
  const [name, setName] = useState('')
  const isValid = isValidCollectionName(name)
  // An empty field is not an error yet; the hint turns red only once something invalid is typed.
  const showError = name !== '' && !isValid

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (isValid) {
      onCreate(name)
    }
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      onCancel()
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        <input
          autoFocus
          value={name}
          onChange={(event) => setName(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="new-collection"
          aria-label="New collection name"
          className={`w-48 rounded-lg bg-white px-3 py-2 text-sm text-gray-900 ring-1 outline-none placeholder:text-gray-400 focus:ring-2 ${
            showError ? 'ring-red-300 focus:ring-red-500' : 'ring-gray-300 focus:ring-indigo-600'
          }`}
        />
        <button
          type="submit"
          disabled={!isValid}
          className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-xs hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Create
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100"
        >
          Cancel
        </button>
      </div>
      <p className={`text-xs ${showError ? 'text-red-600' : 'text-gray-500'}`}>{NAME_RULE_HINT}</p>
    </form>
  )
}
