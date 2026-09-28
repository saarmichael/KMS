// Two plain links to the file itself: open it in a new browser tab, or save it under its original name.
// The server sends files "inline", so a new tab shows images and text directly.
import type { MouseEvent } from 'react'
import { assetFileUrl } from '../api/client'
import type { Asset } from '../api/types'
import { DownloadIcon, ExternalLinkIcon } from './icons'

type FileActionsProps = {
  asset: Asset
  compact?: boolean
}

// The links sit inside clickable tiles; stopping the click here keeps the tile from opening its dialog.
function stopClick(event: MouseEvent) {
  event.stopPropagation()
}

export default function FileActions({ asset, compact = false }: FileActionsProps) {
  const url = assetFileUrl(asset.id)

  if (compact) {
    const iconLink = 'rounded-md p-1.5 text-text-subtle hover:bg-surface-hover hover:text-text-muted'
    return (
      <div className="flex items-center gap-0.5">
        {/* noreferrer: the new tab gets no handle back to this page. */}
        <a href={url} target="_blank" rel="noreferrer" onClick={stopClick} title="Open in new tab" className={iconLink}>
          <ExternalLinkIcon className="size-4" />
        </a>
        <a href={url} download={asset.filename} onClick={stopClick} title="Download" className={iconLink}>
          <DownloadIcon className="size-4" />
        </a>
      </div>
    )
  }

  const buttonLink =
    'flex items-center gap-1.5 rounded-lg bg-surface px-3 py-2 text-sm font-semibold text-text shadow-xs ring-1 ring-border-strong hover:bg-surface-hover'
  return (
    <div className="flex flex-wrap items-center gap-2">
      <a href={url} target="_blank" rel="noreferrer" className={buttonLink}>
        <ExternalLinkIcon className="size-4" />
        Open in new tab
      </a>
      <a href={url} download={asset.filename} className={buttonLink}>
        <DownloadIcon className="size-4" />
        Download
      </a>
    </div>
  )
}
