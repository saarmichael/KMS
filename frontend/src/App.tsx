// Part 1 demo only: shows that the client reaches the API (or the mocks). Part 2 replaces it.
import { useEffect, useState } from 'react'
import { ApiError, listAssets, listCollections } from './api/client'
import type { Asset, Collection } from './api/types'

export default function App() {
  const [collections, setCollections] = useState<Collection[] | null>(null)
  const [demoAssets, setDemoAssets] = useState<Asset[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([listCollections(), listAssets('demo')])
      .then(([loadedCollections, loadedAssets]) => {
        setCollections(loadedCollections)
        setDemoAssets(loadedAssets)
      })
      .catch((caught) => setError(caught instanceof ApiError ? caught.detail : String(caught)))
  }, [])

  return (
    <main className="mx-auto max-w-2xl p-8 font-sans">
      <h1 className="text-2xl font-semibold">KMS</h1>
      <p className="mt-1 text-gray-600">Phase 7, part 1: the API client. Collections and the demo assets below.</p>
      <pre className="mt-6 overflow-x-auto rounded-lg bg-gray-100 p-4 text-sm">
        {error ?? (collections ? JSON.stringify({ collections, demo_assets: demoAssets }, null, 2) : 'loading…')}
      </pre>
    </main>
  )
}
