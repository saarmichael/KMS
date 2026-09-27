// Everything under the top bar for one collection: the logo, the search box and the filters, and below
// them either the results of the current search or, after "Browse all", the collection's files. Before a
// search the logo and box are large and centred, like a search engine's home page, and no files are
// shown; with results showing they shrink into one row at the top. On the home page the filters open from
// a Filters button, so they can be set before searching; with results showing they are always open. They
// only shape searches, never the file list.
//
// How data flows:
//   <SearchBar onSearch> -> handleSearch(query) -> `activeSearch` state, `searching` = true
//     -> <SearchResults key={id} collection query>   (makes the search request itself)
//     -> page 1 arrives or fails -> onFirstPageDone -> `searching` = false (the box unlocks)
//   <SearchOptions onChange> -> `view` state (order and filters) -> <SearchResults view>, used by the
//     next search and reloading the results shown; kept across searches in this collection
//   Filters button -> `filtersOpen` state -> <SearchOptions> under the box on the home page
//   Browse all -> `browsing` state -> the file list shows under the filters while no search is active
//   <SearchBar onCancel> -> handleCancel() -> no active search: the files show again at once, and
//     SearchResults is removed, aborting its request in the background
//   <CollectionFiles collection filesVersion>   (files and retries) stays mounted the whole time and is
//     only hidden, so opening it or leaving a search needs no reload
//   a tile or a result card -> handleOpen(asset, snippet, query) -> `detail` state -> <AssetDetailDialog>
import { useCallback, useState } from 'react'
import type { Asset, SearchView, Snippet } from '../api/types'
import { DEFAULT_VIEW } from '../searchView'
import AssetDetailDialog from './AssetDetailDialog'
import CollectionFiles from './CollectionFiles'
import SearchBar from './SearchBar'
import SearchOptions from './SearchOptions'
import SearchResults from './SearchResults'
import { AdjustmentsIcon, ChevronDownIcon, StackIcon } from './icons'

type CollectionViewProps = {
  collection: string
  filesVersion: number
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

export default function CollectionView({ collection, filesVersion }: CollectionViewProps) {
  const [activeSearch, setActiveSearch] = useState<ActiveSearch | null>(null)
  const [searching, setSearching] = useState(false)
  const [detail, setDetail] = useState<OpenDetail | null>(null)
  // Lives here, not in the results, so a new search keeps the order and filters the user set.
  const [view, setView] = useState<SearchView>(DEFAULT_VIEW)
  const [browsing, setBrowsing] = useState(false)
  const [filtersOpen, setFiltersOpen] = useState(false)

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

  // Leaves the results for the full list of files, opened under the filters.
  function handleBackToFiles() {
    setActiveSearch(null)
    setBrowsing(true)
  }

  // SearchResults starts its request again whenever this function changes, so it must stay the same
  // function across renders; useCallback with no dependencies keeps it so.
  const handleFirstPageDone = useCallback(() => setSearching(false), [])

  function handleOpen(asset: Asset, snippet: Snippet | null, query: string | null) {
    setDetail({ asset, snippet, query })
  }

  const compact = activeSearch !== null
  const showFilters = compact || filtersOpen
  const toggleClass =
    'flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium hover:bg-gray-100 hover:text-indigo-600'

  return (
    <div className="space-y-6">
      {/* One set of elements for both layouts, only the classes change, so the search box keeps its text
          when the results appear. */}
      <div className={compact ? 'flex items-center gap-4' : 'flex flex-col items-center gap-8 pt-10 pb-6 sm:pt-16'}>
        <div className={`flex shrink-0 items-center ${compact ? 'gap-2' : 'gap-3'}`}>
          <div className={`flex items-center justify-center bg-indigo-600 ${compact ? 'size-9 rounded-lg' : 'size-14 rounded-2xl'}`}>
            <StackIcon className={compact ? 'size-5 text-white' : 'size-8 text-white'} />
          </div>
          <span
            className={`font-semibold tracking-tight text-gray-900 ${compact ? 'hidden text-xl sm:inline' : 'text-5xl'}`}
          >
            Sift
          </span>
        </div>
        <div className={compact ? 'min-w-0 flex-1' : 'w-full max-w-2xl'}>
          <SearchBar
            compact={compact}
            searching={searching}
            onSearch={handleSearch}
            onCancel={handleCancel}
            onClear={() => setActiveSearch(null)}
          />
        </div>
        {!compact && (
          <div className="-mt-4 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setFiltersOpen(!filtersOpen)}
              aria-expanded={filtersOpen}
              className={`${toggleClass} ${filtersOpen ? 'bg-gray-100 text-indigo-600' : 'text-gray-600'}`}
            >
              <AdjustmentsIcon className="size-4" />
              Filters
            </button>
            <button
              type="button"
              onClick={() => setBrowsing(!browsing)}
              aria-expanded={browsing}
              className={`${toggleClass} text-gray-600`}
            >
              {browsing ? 'Hide all' : 'Browse all'}
              <ChevronDownIcon className={`size-4 transition-transform ${browsing ? 'rotate-180' : ''}`} />
            </button>
          </div>
        )}
      </div>
      {showFilters && (
        <div className={compact ? '' : 'mx-auto max-w-2xl'}>
          <SearchOptions view={view} onChange={setView} />
        </div>
      )}
      {activeSearch && (
        <SearchResults
          key={activeSearch.id}
          collection={collection}
          query={activeSearch.query}
          view={view}
          onBack={handleBackToFiles}
          onFirstPageDone={handleFirstPageDone}
          onOpen={handleOpen}
        />
      )}
      {/* Hidden rather than removed: the list and its polling keep running, so the files show at once
          when opened or when a search ends. */}
      <div className={activeSearch === null && browsing ? '' : 'hidden'}>
        <CollectionFiles
          collection={collection}
          filesVersion={filesVersion}
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
