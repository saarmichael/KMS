// The whole page: a top bar for choosing, creating and deleting collections, and the main area for
// the selected collection. All collection state lives here and is passed down as props.
//
// How collection data flows:
//   listCollections() -> `collections` state -> withDrafts() -> `allCollections`
//     -> <CollectionDropdown collections>                 (names and counts in the picker)
//     -> <DeleteCollectionDialog name assetCount>         (the selected one)
//   Delete button -> dialog -> handleDelete() -> deleteCollection() -> refreshCollections()
//   selected collection -> <CollectionFiles collection>   (its files, uploads and retries)
//     after an upload it calls onCollectionChanged = refreshCollections, so the counts reload
import { useEffect, useState } from 'react'
import { ApiError, deleteCollection, listCollections } from './api/client'
import type { Collection } from './api/types'
import { defaultCollection, withDrafts } from './collections'
import CollectionDropdown from './components/CollectionDropdown'
import CollectionFiles from './components/CollectionFiles'
import DeleteCollectionDialog from './components/DeleteCollectionDialog'
import NewCollectionForm from './components/NewCollectionForm'
import StatusMessage from './components/StatusMessage'
import { ExclamationIcon, FolderIcon, PlusIcon, SpinnerIcon, StackIcon, TrashIcon } from './components/icons'

export default function App() {
  const [collections, setCollections] = useState<Collection[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [draftNames, setDraftNames] = useState<string[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState(false)

  // ---- Talks to the API -------------------------------------------------------------------

  function refreshCollections(): Promise<void> {
    return listCollections()
      .then((loaded) => {
        setCollections(loaded)
        setLoadError(null)
        // Keeps the current choice; picks the default only when nothing is selected yet.
        setSelected((current) => current ?? defaultCollection(loaded))
      })
      .catch((caught) => {
        setLoadError(caught instanceof ApiError ? caught.detail : 'Something went wrong.')
      })
  }

  // Loads the collections once, when the page opens.
  useEffect(() => {
    refreshCollections()
  }, [])

  // Errors are left to propagate so the dialog can show them.
  async function handleDelete() {
    if (selected === null) {
      return
    }
    await deleteCollection(selected)
    setDraftNames(draftNames.filter((name) => name !== selected))
    setSelected(null)
    setDeleting(false)
    await refreshCollections()
  }

  function handleTryAgain() {
    setLoadError(null)
    refreshCollections()
  }

  // ---- Local only: no request ---------------------------------------------------------------

  function handleCreate(name: string) {
    if (!draftNames.includes(name)) {
      setDraftNames([...draftNames, name])
    }
    setSelected(name)
    setCreating(false)
  }

  const allCollections = withDrafts(collections ?? [], draftNames)
  const selectedCollection = allCollections.find((collection) => collection.name === selected)

  function renderMain() {
    if (loadError) {
      return (
        <StatusMessage
          icon={<ExclamationIcon className="size-12" />}
          title="Could not load collections"
          text={loadError}
          action={
            <button
              type="button"
              onClick={handleTryAgain}
              className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-xs hover:bg-indigo-500"
            >
              Try again
            </button>
          }
        />
      )
    }
    if (collections === null) {
      return <StatusMessage icon={<SpinnerIcon className="size-8 text-indigo-600" />} title="Loading collections…" />
    }
    if (!selectedCollection) {
      return (
        <StatusMessage
          icon={<FolderIcon className="size-12" />}
          title="No collections yet"
          text="Create one with + New to start uploading files."
        />
      )
    }
    // A new key means a new component: switching collection starts with an empty list and no timers.
    return (
      <CollectionFiles
        key={selectedCollection.name}
        collection={selectedCollection.name}
        onCollectionChanged={refreshCollections}
      />
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-3 px-4 py-3 sm:px-6">
          <div className="mr-3 flex items-center gap-2">
            <div className="flex size-8 items-center justify-center rounded-lg bg-indigo-600">
              <StackIcon className="size-5 text-white" />
            </div>
            <span className="text-lg font-semibold text-gray-900">KMS</span>
          </div>

          {collections !== null && (
            <>
              <CollectionDropdown collections={allCollections} selected={selected} onSelect={setSelected} />
              {creating ? (
                <NewCollectionForm onCreate={handleCreate} onCancel={() => setCreating(false)} />
              ) : (
                <button
                  type="button"
                  onClick={() => setCreating(true)}
                  className="flex items-center gap-1.5 rounded-lg bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-xs ring-1 ring-gray-300 hover:bg-gray-50"
                >
                  <PlusIcon className="size-4" />
                  New
                </button>
              )}
              {selectedCollection && (
                <button
                  type="button"
                  onClick={() => setDeleting(true)}
                  className="ml-auto flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-gray-500 hover:bg-red-50 hover:text-red-600"
                >
                  <TrashIcon className="size-4" />
                  Delete
                </button>
              )}
            </>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">{renderMain()}</main>

      {selectedCollection && (
        <DeleteCollectionDialog
          name={selectedCollection.name}
          assetCount={selectedCollection.asset_count}
          open={deleting}
          onConfirm={handleDelete}
          onClose={() => setDeleting(false)}
        />
      )}
    </div>
  )
}
