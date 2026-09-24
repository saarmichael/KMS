import { useEffect, useState } from 'react'

type Health = {
  status: string
  db?: string
  migrations?: { current: string | null; head: string | null; ok: boolean }
  notify?: { ok: boolean; ms: number | null; error?: string }
  ai_provider?: string
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setError(String(e)))
  }, [])

  return (
    <main className="mx-auto max-w-2xl p-8 font-sans">
      <h1 className="text-2xl font-semibold">KMS</h1>
      <p className="mt-1 text-gray-600">Phase 0: skeleton. The API answers below.</p>
      <pre className="mt-6 rounded-lg bg-gray-100 p-4 text-sm">
        {error ?? (health ? JSON.stringify(health, null, 2) : 'loading…')}
      </pre>
    </main>
  )
}
