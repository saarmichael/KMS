// Everything under the top bar for one collection: the search box, and below it either the collection's
// files or the results of the current search.
//
// How data flows:
//   <SearchBar onSearch> -> handleSearch(query) -> `activeSearch` state, `searching` = true
//     -> <SearchResults key={id} collection query>   (makes the search request itself)
//     -> page 1 arrives or fails -> onFirstPageDone -> `searching` = false (the box unlocks)
//   <SearchBar onCancel> -> handleCancel() -> no active search: the files show again at once, and
//     SearchResults is removed, aborting its request in the background
//   <CollectionFiles collection onCollectionChanged>   (files, uploads, retries) stays mounted the whole
//     time and is only hidden during a search, so leaving a search needs no reload
//   a tile or a result card -> handleOpen(asset, snippet, query) -> `detail` state -> <AssetDetailDialog>
import { useCallback, useState } from 'react'
import type { Asset, Snippet } from '../api/types'
import AssetDetailDialog from './AssetDetailDialog'
import CollectionFiles from './CollectionFiles'
import SearchBar from './SearchBar'
import SearchResults from './SearchResults'

type CollectionViewProps = {
  collection: string
  onCollectionChanged: () => void
}

type ActiveSearch = {
  query: string
  id: number
}

// The file shown in the detail dialog; `snippet` and `query` are set when it was opened from a search
// result, so the dialog can mark what matched.
type OpenDetail = {
  asset: Asset
  snippet: Snippet | null
  query: string | null
}

export default function CollectionView({ collection, onCollectionChanged }: CollectionViewProps) {
  const [activeSearch, setActiveSearch] = useState<ActiveSearch | null>(null)
  const [searching, setSearching] = useState(false)
  const [detail, setDetail] = useState<OpenDetail | null>(null)

  // Every search gets a new id. Used as the results' key, it gives each search a fresh component:
  // page 1, nothing left over, and a late answer from an earlier search is dropped with the old one.
  function handleSearch(query: string) {
    setActiveSearch((previous) => ({ query, id: (previous?.id ?? 0) + 1 }))
    setSearching(true)
  }

  function handleCancel() {
    setActiveSearch(null)
    setSearching(false)
  }

  // SearchResults starts its request again whenever this function changes, so it must stay the same
  // function across renders; useCallback with no dependencies keeps it so.
  const handleFirstPageDone = useCallback(() => setSearching(false), [])

  function handleOpen(asset: Asset, snippet: Snippet | null, query: string | null) {
    setDetail({ asset, snippet, query })
  }

  return (
    <div className="space-y-6">
      <SearchBar
        searching={searching}
        onSearch={handleSearch}
        onCancel={handleCancel}
        onClear={() => setActiveSearch(null)}
      />
      {activeSearch && (
        <SearchResults
          key={activeSearch.id}
          collection={collection}
          query={activeSearch.query}
          onBack={() => setActiveSearch(null)}
          onFirstPageDone={handleFirstPageDone}
          onOpen={handleOpen}
        />
      )}
      {/* Hidden rather than removed during a search: the list and its polling keep running, so the
          files are back the moment the search ends. */}
      <div className={activeSearch ? 'hidden' : ''}>
        <CollectionFiles
          collection={collection}
          onCollectionChanged={onCollectionChanged}
          onOpen={(asset) => handleOpen(asset, null, null)}
        />
      </div>
      {detail && (
        <AssetDetailDialog
          asset={detail.asset}
          snippet={detail.snippet}
          query={detail.query}
          onClose={() => setDetail(null)}
        />
      )}
    </div>
  )
}
