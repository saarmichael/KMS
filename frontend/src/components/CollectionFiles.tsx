// The files of one collection: the upload area, what happened to the last upload, and one tile per
// file. This component owns the file list and makes every request about it.
//
// How data flows:
//   listAssets(collection) -> `assets` state -> <AssetTile asset> for each file
//     repeated every 2 s while any file is pending or processing
//   <UploadArea onFiles> -> handleUpload() -> uploadAsset() per file, in parallel
//     -> `notices` state -> <UploadNotices>   (refused files and duplicates)
//     -> listAssets() again, and onCollectionChanged() so the collection counts reload
//   <AssetTile onRetry> -> handleRetry() -> retryAsset() -> the returned asset replaces the old one
//   <AssetTile onOpen> -> onOpen(asset), passed up to CollectionView, which shows the detail dialog
import { useCallback, useEffect, useState } from 'react'
import { ApiError, listAssets, retryAsset, uploadAsset } from '../api/client'
import type { Asset } from '../api/types'
import AssetTile from './AssetTile'
import { ExclamationIcon, FolderIcon } from './icons'
import StatusMessage from './StatusMessage'
import UploadArea from './UploadArea'
import UploadNotices from './UploadNotices'
import type { UploadNotice } from './UploadNotices'

type CollectionFilesProps = {
  collection: string
  onCollectionChanged: () => void
  onOpen: (asset: Asset) => void
}

const POLL_INTERVAL_MS = 2000

export default function CollectionFiles({ collection, onCollectionChanged, onOpen }: CollectionFilesProps) {
  const [assets, setAssets] = useState<Asset[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [uploadingCount, setUploadingCount] = useState(0)
  const [notices, setNotices] = useState<UploadNotice[]>([])

  // ---- Talks to the API -------------------------------------------------------------------

  // A failed load keeps the files already on screen and only reports the error.
  // useCallback keeps the same function between renders until `collection` changes, so the effects
  // below can list it as a dependency without re-running on every render.
  const loadAssets = useCallback((): Promise<void> => {
    return listAssets(collection)
      .then((loaded) => {
        setAssets(loaded)
        setLoadError(null)
      })
      .catch((caught) => {
        setLoadError(caught instanceof ApiError ? caught.detail : 'Something went wrong.')
      })
  }, [collection])

  // Loads the files once, when the collection is opened.
  useEffect(() => {
    loadAssets()
  }, [loadAssets])

  // While any file is still being processed, loads the list again every 2 s. The timer repeats on its
  // own, so a failed load does not stop it: the list recovers as soon as the server answers again.
  // The effect re-runs only when `stillWorking` flips; the cleanup stops the timer once nothing is left.
  const stillWorking = assets?.some((asset) => asset.status === 'pending' || asset.status === 'processing') ?? false
  useEffect(() => {
    if (!stillWorking) {
      return
    }
    const timer = setInterval(loadAssets, POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [stillWorking, loadAssets])

  // Every file is its own request. allSettled waits for all of them, so one refused file does not
  // stop the others.
  async function handleUpload(files: File[]) {
    setUploadingCount(files.length)
    setNotices([])
    const outcomes = await Promise.allSettled(files.map((file) => uploadAsset(collection, file)))

    const newNotices: UploadNotice[] = []
    outcomes.forEach((outcome, index) => {
      const filename = files[index].name
      if (outcome.status === 'rejected') {
        const detail = outcome.reason instanceof ApiError ? outcome.reason.detail : 'Upload failed.'
        newNotices.push({ kind: 'error', text: `${filename}: ${detail}` })
      } else if (outcome.value.deduplicated) {
        const existing = outcome.value.asset.filename
        const text =
          existing === filename
            ? `${filename} is already in this collection.`
            : `${filename} is identical to ${existing}, which is already in this collection.`
        newNotices.push({ kind: 'duplicate', text })
      }
    })

    setNotices(newNotices)
    setUploadingCount(0)
    await loadAssets()
    onCollectionChanged()
  }

  // Errors are left to propagate so the tile can show them.
  async function handleRetry(id: string) {
    const updated = await retryAsset(id)
    setAssets((current) => (current ?? []).map((asset) => (asset.id === id ? updated : asset)))
  }

  function handleTryAgain() {
    setLoadError(null)
    loadAssets()
  }

  // ---- Display ------------------------------------------------------------------------------

  const tryAgainButton = (
    <button
      type="button"
      onClick={handleTryAgain}
      className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-xs hover:bg-indigo-500"
    >
      Try again
    </button>
  )

  function renderFiles() {
    if (assets === null) {
      if (loadError) {
        return (
          <StatusMessage
            icon={<ExclamationIcon className="size-12" />}
            title="Could not load files"
            text={loadError}
            action={tryAgainButton}
          />
        )
      }
      return null
    }
    if (assets.length === 0) {
      return (
        <StatusMessage
          icon={<FolderIcon className="size-12" />}
          title="No files yet"
          text="Drop files above to add the first ones."
        />
      )
    }

    // The same words as the status badges, so the summary and the tiles agree.
    const pendingCount = assets.filter((asset) => asset.status === 'pending').length
    const processingCount = assets.filter((asset) => asset.status === 'processing').length
    return (
      <>
        {loadError && (
          <div className="flex items-center justify-between gap-3 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">
            <span>Could not refresh the list: {loadError}</span>
            <button type="button" onClick={handleTryAgain} className="font-semibold hover:text-red-600">
              Try again
            </button>
          </div>
        )}
        <p className="text-sm text-gray-500">
          {assets.length === 1 ? '1 file' : `${assets.length} files`}
          {pendingCount > 0 && ` · ${pendingCount} pending`}
          {processingCount > 0 && ` · ${processingCount} processing`}
        </p>
        <ul className="space-y-3">
          {assets.map((asset) => (
            <AssetTile key={asset.id} asset={asset} onRetry={handleRetry} onOpen={onOpen} />
          ))}
        </ul>
      </>
    )
  }

  return (
    <div className="space-y-4">
      <UploadArea onFiles={handleUpload} uploadingCount={uploadingCount} />
      <UploadNotices notices={notices} onDismiss={() => setNotices([])} />
      {renderFiles()}
    </div>
  )
}
