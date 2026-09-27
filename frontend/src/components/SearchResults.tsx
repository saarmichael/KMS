// The results of one search in one collection. This component makes the search request, keeps the
// pages loaded so far, and shows them as cards.
//
// How data flows:
//   loadPage(1) -> search(collection, query, 1, view) -> GET /api/search?collection=&q=&page=1&order=&match=…
//     -> { results, page, has_more } -> `results` state (each page appended) and `hasMore`
//     -> <SearchResultCard result query> for each result
//   "Show more" -> loadPage(page + 1) -> the same request for the next page, appended below
//   the filters (in CollectionView) change the `view` prop -> a new loadPage -> the effect loads page 1
//     again; the cards shown stay, with a spinner, until the new ones arrive
//   Cancel (in the search box) removes this component; the effect cleanup aborts the running request
//   <SearchResultCard onOpen> -> onOpen(asset, snippet, query), passed up to CollectionView's detail dialog
import { useCallback, useEffect, useState } from 'react'
import { ApiError, search } from '../api/client'
import type { Asset, SearchResult, SearchView, Snippet } from '../api/types'
import { ArrowLeftIcon, ExclamationIcon, SearchIcon, SpinnerIcon } from './icons'
import SearchResultCard from './SearchResultCard'
import StatusMessage from './StatusMessage'

type SearchResultsProps = {
  collection: string
  query: string
  view: SearchView
  onBack: () => void
  onFirstPageDone: () => void
  onOpen: (asset: Asset, snippet: Snippet, query: string) => void
}

const PLACEHOLDER_CARDS = 3

export default function SearchResults({
  collection,
  query,
  view,
  onBack,
  onFirstPageDone,
  onOpen,
}: SearchResultsProps) {
  const [results, setResults] = useState<SearchResult[]>([])
  const [page, setPage] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(true)
  // The view the results on screen were loaded with. While it differs from `view`, the filters have
  // changed and page 1 is on its way; the cards shown until then are the old ones.
  const [shownView, setShownView] = useState(view)
  const [error, setError] = useState<string | null>(null)

  // ---- Talks to the API -------------------------------------------------------------------

  // Loads one page of results; later pages go below the ones already shown. A failure keeps what is shown.
  // `loading` starts as true; the buttons that load again set it back to true themselves.
  // A cancelled request changes nothing: the component is on its way out.
  const loadPage = useCallback(
    (pageNumber: number, signal?: AbortSignal): Promise<void> => {
      return search(collection, query, pageNumber, view, signal)
        .then((response) => {
          // Page 1 replaces the list, so loading it twice never shows a result twice.
          if (pageNumber === 1) {
            setResults(response.results)
            setShownView(view)
            setError(null)
          } else {
            setResults((shown) => [...shown, ...response.results])
          }
          setPage(response.page)
          setHasMore(response.has_more)
          setLoading(false)
        })
        .catch((caught) => {
          if (signal?.aborted) {
            return
          }
          setError(caught instanceof ApiError ? caught.detail : 'Something went wrong.')
          setLoading(false)
          if (pageNumber === 1) {
            setShownView(view)
          }
        })
        .then(() => {
          if (pageNumber === 1 && !signal?.aborted) {
            onFirstPageDone()
          }
        })
    },
    [collection, query, view, onFirstPageDone],
  )

  // Loads the first page when the search starts, and again when the view changes. Leaving (Cancel, Back,
  // a new search) or a newer view runs the cleanup, which aborts the request if it is still running.
  useEffect(() => {
    const controller = new AbortController()
    loadPage(1, controller.signal)
    return () => controller.abort()
  }, [loadPage])

  function handleShowMore() {
    setLoading(true)
    setError(null)
    loadPage(page + 1)
  }

  function handleTryAgain() {
    setLoading(true)
    setError(null)
    loadPage(1)
  }

  // ---- Display ------------------------------------------------------------------------------

  const reloading = shownView !== view

  const backLink = (
    <button
      type="button"
      onClick={onBack}
      className="flex items-center gap-1.5 text-sm font-medium text-indigo-600 hover:text-indigo-500"
    >
      <ArrowLeftIcon className="size-4" />
      Back to all files
    </button>
  )

  if (page === 0) {
    if (loading) {
      return (
        <ul className="space-y-3" aria-label="Searching">
          {Array.from({ length: PLACEHOLDER_CARDS }, (_, index) => (
            <li key={index} className="flex animate-pulse gap-4 rounded-xl bg-white p-3 shadow-xs ring-1 ring-gray-200">
              <div className="size-28 shrink-0 rounded-lg bg-gray-100" />
              <div className="flex-1 space-y-3 py-2">
                <div className="h-3 w-1/3 rounded bg-gray-200" />
                <div className="h-2.5 w-1/4 rounded bg-gray-100" />
                <div className="h-2.5 w-5/6 rounded bg-gray-100" />
                <div className="h-2.5 w-2/3 rounded bg-gray-100" />
              </div>
            </li>
          ))}
        </ul>
      )
    }
    if (error) {
      return (
        <StatusMessage
          icon={<ExclamationIcon className="size-12" />}
          title="Search failed"
          text={error}
          action={
            <div className="flex items-center gap-4">
              <button
                type="button"
                onClick={handleTryAgain}
                className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-xs hover:bg-indigo-500"
              >
                Try again
              </button>
              {backLink}
            </div>
          }
        />
      )
    }
  }

  if (results.length === 0) {
    return (
      <div className="space-y-3">
        <StatusMessage
          icon={reloading ? <SpinnerIcon className="size-8 text-indigo-600" /> : <SearchIcon className="size-12" />}
          title={`No matches for "${query}"`}
          text="Try other words, or turn on more filters; searches match by meaning as well as by the exact words."
          action={backLink}
        />
      </div>
    )
  }

  const count = hasMore ? `${results.length}+` : `${results.length}`
  const resultsWord = results.length === 1 && !hasMore ? 'result' : 'results'

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="flex items-center gap-2 text-sm text-gray-500">
          <span>
            {count} {resultsWord} for <span className="font-medium text-gray-900">"{query}"</span>
          </span>
          {reloading && <SpinnerIcon className="size-4 text-indigo-600" />}
        </p>
        {backLink}
      </div>

      <ul className="space-y-3">
        {results.map((result) => (
          <SearchResultCard key={result.asset.id} result={result} query={query} onOpen={onOpen} />
        ))}
      </ul>

      {error && <p className="text-center text-sm text-red-700">{error}</p>}
      {hasMore && (
        <div className="flex justify-center pt-2">
          <button
            type="button"
            onClick={handleShowMore}
            disabled={loading || reloading}
            className="flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-gray-900 shadow-xs ring-1 ring-gray-300 hover:bg-gray-50 disabled:opacity-50"
          >
            {loading && <SpinnerIcon className="size-4 text-indigo-600" />}
            Show more
          </button>
        </div>
      )}
    </div>
  )
}
