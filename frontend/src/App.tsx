// The whole page: a top bar for choosing, creating and deleting collections and for uploading, and the
// main area for the selected collection. All collection and upload state lives here and is passed down
// as props. Uploads live here, not with the file list, so they keep going (and stay in the upload panel)
// when the user switches collection.
//
// How collection data flows:
//   listCollections() -> `collections` state -> withDrafts() -> `allCollections`
//     -> <CollectionDropdown collections>                 (names and counts in the picker)
//     -> <DeleteCollectionDialog name assetCount>         (the selected one)
//   Delete button -> dialog -> handleDelete() -> deleteCollection() -> refreshCollections()
//   selected collection -> <CollectionView collection filesVersion>   (search box, then its files or results)
//
// How an upload flows:
//   Upload button -> <UploadDialog onFiles>, or files dropped anywhere -> <PageDropZone onFiles>
//     -> handleFiles(files) -> uploadAsset() per file, in parallel -> `uploads` state -> <UploadPanel uploads>
//     each file's progress and outcome update its own item as they arrive
//     when a file ends: `filesVersion` + 1, so CollectionFiles reloads its list, and refreshCollections()
import { useEffect, useRef, useState } from 'react'
import { ApiError, deleteCollection, listCollections, uploadAsset } from './api/client'
import type { Collection } from './api/types'
import { defaultCollection, withDrafts } from './collections'
import CollectionDropdown from './components/CollectionDropdown'
import CollectionView from './components/CollectionView'
import DeleteCollectionDialog from './components/DeleteCollectionDialog'
import NewCollectionForm from './components/NewCollectionForm'
import PageDropZone from './components/PageDropZone'
import StatusMessage from './components/StatusMessage'
import UploadDialog from './components/UploadDialog'
import UploadPanel from './components/UploadPanel'
import type { UploadItem } from './components/UploadPanel'
import { ExclamationIcon, FolderIcon, PlusIcon, SpinnerIcon, TrashIcon, UploadIcon } from './components/icons'

export default function App() {
  const [collections, setCollections] = useState<Collection[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [draftNames, setDraftNames] = useState<string[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [uploads, setUploads] = useState<UploadItem[]>([])
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)
  // Goes up by one each time an upload ends; the file list reloads when it changes.
  const [filesVersion, setFilesVersion] = useState(0)
  // A ref, not state: the next upload id is only read when files arrive, never shown.
  const nextUploadId = useRef(1)

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

  // Every file is its own request, to the collection selected when the files arrived, so switching
  // collection mid-upload changes nothing. Each request updates only its own item in `uploads`.
  function handleFiles(files: File[]) {
    if (selected === null) {
      return
    }
    const collection = selected
    const newUploads: UploadItem[] = files.map((file) => {
      const id = nextUploadId.current
      nextUploadId.current += 1
      return { id, file, collection, progress: 0, state: 'uploading', message: null }
    })
    setUploads((current) => [...current, ...newUploads])

    for (const upload of newUploads) {
      const updateThisUpload = (changes: Partial<UploadItem>) => {
        setUploads((current) => current.map((item) => (item.id === upload.id ? { ...item, ...changes } : item)))
      }
      uploadAsset(collection, upload.file, (fraction) => updateThisUpload({ progress: fraction }))
        .then((response) => {
          if (response.deduplicated) {
            const existing = response.asset.filename
            const message =
              existing === upload.file.name
                ? 'Already in this collection.'
                : `Identical to ${existing}, already in this collection.`
            updateThisUpload({ state: 'duplicate', progress: 1, message })
          } else {
            updateThisUpload({ state: 'done', progress: 1 })
          }
        })
        .catch((caught) => {
          const message = caught instanceof ApiError ? caught.detail : 'Upload failed.'
          updateThisUpload({ state: 'error', progress: 1, message })
        })
        .then(() => {
          // A duplicate reloads too: the existing file now lists the new name among its aliases.
          setFilesVersion((version) => version + 1)
          refreshCollections()
        })
    }
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
    // A new key means a new component: switching collection starts with no files, no search and no timers.
    return (
      <CollectionView
        key={selectedCollection.name}
        collection={selectedCollection.name}
        filesVersion={filesVersion}
      />
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex min-h-16 max-w-5xl flex-wrap items-center gap-3 px-4 py-3 sm:px-6">
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
                  onClick={() => setUploadDialogOpen(true)}
                  className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-xs hover:bg-indigo-500"
                >
                  <UploadIcon className="size-4" />
                  Upload
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
      {selectedCollection && (
        <UploadDialog
          open={uploadDialogOpen}
          collection={selectedCollection.name}
          onFiles={handleFiles}
          onClose={() => setUploadDialogOpen(false)}
        />
      )}
      <PageDropZone collection={selectedCollection?.name ?? null} onFiles={handleFiles} />
      <UploadPanel uploads={uploads} onClose={() => setUploads([])} />
    </div>
  )
}
