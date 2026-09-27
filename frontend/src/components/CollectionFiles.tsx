// The files of one collection, one tile per file. This component owns the file list and makes every
// request about it; uploads are sent by App, which bumps `filesVersion` whenever one ends.
//
// How data flows:
//   listAssets(collection) -> `assets` state -> <AssetTile asset> for each file
//     again whenever `filesVersion` changes, and every 2 s while any file is pending or processing
//   <AssetTile onRetry> -> handleRetry() -> retryAsset() -> the returned asset replaces the old one
//   Retry all failed -> handleRetryAll() -> retryAsset() per failed file, in parallel
//     -> the returned assets replace the old ones; `retryAllError` if any could not be retried
//   <AssetTile onOpen> -> onOpen(asset), passed up to CollectionView, which shows the detail dialog
import { useCallback, useEffect, useState } from 'react'
import { ApiError, listAssets, retryAsset } from '../api/client'
import type { Asset } from '../api/types'
import AssetTile from './AssetTile'
import { ExclamationIcon, FolderIcon, RetryIcon } from './icons'
import StatusMessage from './StatusMessage'

type CollectionFilesProps = {
  collection: string
  filesVersion: number
  onOpen: (asset: Asset) => void
}

const POLL_INTERVAL_MS = 2000

export default function CollectionFiles({ collection, filesVersion, onOpen }: CollectionFilesProps) {
  const [assets, setAssets] = useState<Asset[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [retryingAll, setRetryingAll] = useState(false)
  const [retryAllError, setRetryAllError] = useState<string | null>(null)

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

  // Loads the files when the collection is opened, and again each time an upload ends.
  useEffect(() => {
    loadAssets()
  }, [loadAssets, filesVersion])

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

  // Errors are left to propagate so the tile can show them.
  async function handleRetry(id: string) {
    const updated = await retryAsset(id)
    setAssets((current) => (current ?? []).map((asset) => (asset.id === id ? updated : asset)))
  }

  // Every failed file is its own request. allSettled waits for all of them, so one refusal does not stop
  // the others; the files that went back to pending are shown as such either way.
  async function handleRetryAll() {
    const failedAssets = (assets ?? []).filter((asset) => asset.status === 'failed')
    setRetryingAll(true)
    setRetryAllError(null)
    const outcomes = await Promise.allSettled(failedAssets.map((asset) => retryAsset(asset.id)))

    const updatedById = new Map<string, Asset>()
    const reasons: string[] = []
    outcomes.forEach((outcome, index) => {
      if (outcome.status === 'fulfilled') {
        updatedById.set(failedAssets[index].id, outcome.value)
      } else {
        reasons.push(outcome.reason instanceof ApiError ? outcome.reason.detail : 'Something went wrong.')
      }
    })

    setAssets((current) => (current ?? []).map((asset) => updatedById.get(asset.id) ?? asset))
    if (reasons.length > 0) {
      const files = reasons.length === 1 ? '1 file' : `${reasons.length} files`
      setRetryAllError(`${files} could not be retried: ${reasons[0]}`)
    }
    setRetryingAll(false)
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
          text="Drop files anywhere on the page, or press Upload, to add the first ones."
        />
      )
    }

    // The same words as the status badges, so the summary and the tiles agree.
    const pendingCount = assets.filter((asset) => asset.status === 'pending').length
    const processingCount = assets.filter((asset) => asset.status === 'processing').length
    const failedCount = assets.filter((asset) => asset.status === 'failed').length
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
        <div className="flex min-h-9 flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-gray-500">
            {assets.length === 1 ? '1 file' : `${assets.length} files`}
            {pendingCount > 0 && ` · ${pendingCount} pending`}
            {processingCount > 0 && ` · ${processingCount} processing`}
            {failedCount > 0 && ` · ${failedCount} failed`}
          </p>
          {failedCount > 0 && (
            <button
              type="button"
              onClick={handleRetryAll}
              disabled={retryingAll}
              className="flex items-center gap-1.5 rounded-lg bg-white px-3 py-1.5 text-sm font-semibold text-gray-900 shadow-xs ring-1 ring-gray-300 hover:bg-gray-50 disabled:opacity-50"
            >
              <RetryIcon className={`size-4 ${retryingAll ? 'animate-spin' : ''}`} />
              {retryingAll ? 'Retrying…' : `Retry all failed (${failedCount})`}
            </button>
          )}
        </div>
        {retryAllError && (
          <div className="flex items-center justify-between gap-3 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">
            <span>{retryAllError}</span>
            <button type="button" onClick={() => setRetryAllError(null)} className="font-semibold hover:text-red-600">
              Dismiss
            </button>
          </div>
        )}
        <ul className="space-y-3">
          {assets.map((asset) => (
            <AssetTile key={asset.id} asset={asset} onRetry={handleRetry} onOpen={onOpen} />
          ))}
        </ul>
      </>
    )
  }

  return (
    <div className="space-y-4">{renderFiles()}</div>
  )
}
