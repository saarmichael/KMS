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
          className={`w-48 rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 outline-none placeholder:text-text-subtle focus:ring-2 ${
            showError ? 'ring-danger/40 focus:ring-danger' : 'ring-border-strong focus:ring-accent'
          }`}
        />
        <button
          type="submit"
          disabled={!isValid}
          className="rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-on-accent shadow-xs hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
        >
          Create
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg px-3 py-2 text-sm font-medium text-text-muted hover:bg-surface-hover"
        >
          Cancel
        </button>
      </div>
      <p className={`text-xs ${showError ? 'text-danger' : 'text-text-muted'}`}>{NAME_RULE_HINT}</p>
    </form>
  )
}
