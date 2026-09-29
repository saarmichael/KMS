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
import { flushSync } from 'react-dom'
import type { Asset, SearchView, Snippet } from '../api/types'
import { DEFAULT_VIEW } from '../searchView'
import type { Theme } from '../theme'
import AssetDetailDialog from './AssetDetailDialog'
import CollectionFiles from './CollectionFiles'
import SearchBar from './SearchBar'
import SearchOptions from './SearchOptions'
import SearchResults from './SearchResults'
import { AdjustmentsIcon, ChevronDownIcon } from './icons'
// The Sift logo: the whole word on the home page; in the bar above results only the mark, the i on its own,
// which stays legible at that small height. Each in a light-background and a dark-background version, for
// the two themes.
import logoOnDark from '../assets/sift-logo-on-dark.svg'
import logoOnLight from '../assets/sift-logo-on-light.svg'
import markOnDark from '../assets/sift-mark-on-dark.svg'
import markOnLight from '../assets/sift-mark-on-light.svg'

type CollectionViewProps = {
  collection: string
  filesVersion: number
  theme: Theme
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

export default function CollectionView({ collection, filesVersion, theme }: CollectionViewProps) {
  const [activeSearch, setActiveSearch] = useState<ActiveSearch | null>(null)
  const [searching, setSearching] = useState(false)
  const [detail, setDetail] = useState<OpenDetail | null>(null)
  // Lives here, not in the results, so a new search keeps the order and filters the user set.
  const [view, setView] = useState<SearchView>(DEFAULT_VIEW)
  const [browsing, setBrowsing] = useState(false)
  const [filtersOpen, setFiltersOpen] = useState(false)

  // Switches between the home layout and the compact one with an animation: the browser snapshots the page,
  // `update` changes the state, and the logo and the search box (named in index.css) glide to their new
  // places. flushSync puts the new layout on the page before the browser takes its second snapshot. Without
  // the API, or when the user asked for less motion, the change is instant.
  function changeLayout(update: () => void) {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!document.startViewTransition || reduceMotion) {
      update()
      return
    }
    document.startViewTransition(() => flushSync(update))
  }

  // Every search gets a new id. Used as the results' key, it gives each search a fresh component:
  // page 1, nothing left over, and a late answer from an earlier search is dropped with the old one.
  function handleSearch(query: string) {
    changeLayout(() => {
      setActiveSearch((previous) => ({ query, id: (previous?.id ?? 0) + 1 }))
      setSearching(true)
    })
  }

  function handleCancel() {
    changeLayout(() => {
      setActiveSearch(null)
      setSearching(false)
    })
  }

  // Leaves the results for the full list of files, opened under the filters.
  function handleBackToFiles() {
    changeLayout(() => {
      setActiveSearch(null)
      setBrowsing(true)
    })
  }

  // The logo leads back to the empty home page, as a site's logo usually does.
  function handleHome() {
    changeLayout(() => {
      setActiveSearch(null)
      setSearching(false)
      setBrowsing(false)
    })
  }

  // SearchResults starts its request again whenever this function changes, so it must stay the same
  // function across renders; useCallback with no dependencies keeps it so.
  const handleFirstPageDone = useCallback(() => setSearching(false), [])

  function handleOpen(asset: Asset, snippet: Snippet | null, query: string | null) {
    setDetail({ asset, snippet, query })
  }

  const compact = activeSearch !== null || browsing
  const fullLogo = theme === 'dark' ? logoOnDark : logoOnLight
  const mark = theme === 'dark' ? markOnDark : markOnLight
  const showFilters = compact || filtersOpen
  const toggleClass =
    'flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium hover:bg-surface-hover hover:text-accent-text'

  return (
    <div className="space-y-6">
      {/* One set of elements for both layouts, only the classes change, so the search box keeps its text
          when the results appear. */}
      <div className={compact ? 'flex items-center gap-4' : 'flex flex-col items-center gap-5 pb-2'}>
        <button type="button" onClick={handleHome} aria-label="Home" className="shrink-0">
          <img
            src={compact ? mark : fullLogo}
            alt="Sift"
            className={`logo-moves ${compact ? 'h-12 w-auto' : 'h-36 w-auto'}`}
          />
        </button>
        <div className={`search-box-moves ${compact ? 'min-w-0 flex-1' : 'w-full max-w-3xl'}`}>
          <SearchBar
            compact={compact}
            searching={searching}
            onSearch={handleSearch}
            onCancel={handleCancel}
            onClear={() => changeLayout(() => setActiveSearch(null))}
          />
        </div>
        {!compact && (
          <div className="-mt-2 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setFiltersOpen(!filtersOpen)}
              aria-expanded={filtersOpen}
              className={`${toggleClass} ${filtersOpen ? 'bg-surface-hover text-accent-text' : 'text-text-muted'}`}
            >
              <AdjustmentsIcon className="size-4" />
              Filters
            </button>
            <button
              type="button"
              onClick={() => changeLayout(() => setBrowsing(true))}
              className={`${toggleClass} text-text-muted`}
            >
              Browse all
              <ChevronDownIcon className="size-4" />
            </button>
          </div>
        )}
      </div>
      {showFilters && (
        <div className={compact ? '' : 'mx-auto max-w-3xl'}>
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
          onHide={handleHome}
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
