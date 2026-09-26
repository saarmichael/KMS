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
import { useCallback, useState } from 'react'
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

export default function CollectionView({ collection, onCollectionChanged }: CollectionViewProps) {
  const [activeSearch, setActiveSearch] = useState<ActiveSearch | null>(null)
  const [searching, setSearching] = useState(false)

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
        />
      )}
      {/* Hidden rather than removed during a search: the list and its polling keep running, so the
          files are back the moment the search ends. */}
      <div className={activeSearch ? 'hidden' : ''}>
        <CollectionFiles collection={collection} onCollectionChanged={onCollectionChanged} />
      </div>
    </div>
  )
}
