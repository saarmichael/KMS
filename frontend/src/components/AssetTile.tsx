// One file of the collection as a full-width tile: thumbnail on the left, what is known about the
// file on the right, its status in the corner.
//
// How data reaches it:
//   CollectionFiles `assets` state -> <AssetTile asset> -> title, filename, aliases, description, tags, status
//   Retry button -> handleRetry() -> onRetry(id) (CollectionFiles.handleRetry -> retryAsset())
import { useState } from 'react'
import { ApiError, assetFileUrl } from '../api/client'
import type { Asset } from '../api/types'
import { formatAge, formatBytes } from '../format'
import { DocumentIcon, RetryIcon } from './icons'
import StatusBadge from './StatusBadge'

type AssetTileProps = {
  asset: Asset
  onRetry: (id: string) => Promise<void>
}

const TAGS_SHOWN = 4

export default function AssetTile({ asset, onRetry }: AssetTileProps) {
  const [retrying, setRetrying] = useState(false)
  const [retryError, setRetryError] = useState<string | null>(null)

  // ---- Talks to the API -------------------------------------------------------------------

  async function handleRetry() {
    setRetrying(true)
    setRetryError(null)
    try {
      await onRetry(asset.id)
    } catch (caught) {
      setRetryError(caught instanceof ApiError ? caught.detail : 'Something went wrong.')
    } finally {
      setRetrying(false)
    }
  }

  // ---- Display ------------------------------------------------------------------------------

  const metadata = asset.metadata
  const title = metadata ? metadata.title : asset.filename

  return (
    <li className="flex gap-4 rounded-xl bg-white p-3 shadow-xs ring-1 ring-gray-200">
      {asset.asset_type === 'image' ? (
        // The file endpoint serves the original; CSS scales it into the square.
        <img
          src={assetFileUrl(asset.id)}
          alt=""
          className="size-24 shrink-0 rounded-lg bg-gray-100 object-cover"
        />
      ) : (
        <div className="flex size-24 shrink-0 items-center justify-center rounded-lg bg-indigo-50">
          <DocumentIcon className="size-10 text-indigo-400" />
        </div>
      )}

      <div className="min-w-0 flex-1 py-1">
        <div className="flex items-start gap-3">
          <h3 className="min-w-0 flex-1 truncate text-sm font-semibold text-gray-900">{title}</h3>
          <StatusBadge status={asset.status} />
        </div>

        {metadata && <p className="truncate text-xs text-gray-500">{asset.filename}</p>}
        {asset.aliases.length > 0 && (
          <p className="truncate text-xs text-gray-500">also uploaded as {asset.aliases.join(', ')}</p>
        )}

        {metadata && <p className="mt-1.5 line-clamp-2 text-sm text-gray-600">{metadata.description}</p>}
        {metadata && metadata.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {metadata.tags.slice(0, TAGS_SHOWN).map((tag) => (
              <span key={tag} className="rounded-md bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">
                {tag}
              </span>
            ))}
          </div>
        )}

        {asset.status === 'failed' && (
          <div className="mt-2 flex items-start gap-3 rounded-lg bg-red-50 px-3 py-2">
            <p className="flex-1 text-sm text-red-700">{retryError ?? asset.error}</p>
            <button
              type="button"
              onClick={handleRetry}
              disabled={retrying}
              className="flex shrink-0 items-center gap-1.5 rounded-md bg-white px-2.5 py-1 text-xs font-semibold text-red-700 shadow-xs ring-1 ring-red-200 hover:bg-red-50 disabled:opacity-50"
            >
              <RetryIcon className="size-3.5" />
              {retrying ? 'Retrying…' : 'Retry'}
            </button>
          </div>
        )}

        <p className="mt-2 text-xs text-gray-400">
          {formatBytes(asset.size_bytes)} · {formatAge(asset.created_at)}
        </p>
      </div>
    </li>
  )
}
