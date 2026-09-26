// One MSW handler per API endpoint. Each one waits, reads its inputs, and hands them to the fake
// backend in store.ts.
import { delay, http, HttpResponse } from 'msw'
import * as store from './store'
import type { MockResponse } from './store'

// Makes loading states visible, as a real network would.
const LATENCY_MS = 300
// Search is slower on the real server (the query is embedded first), long enough here to try Cancel.
const SEARCH_LATENCY_MS = 1500

function toHttpResponse(response: MockResponse) {
  if (response.status === 204) {
    return new HttpResponse(null, { status: 204 })
  }
  return HttpResponse.json(response.body, { status: response.status })
}

export const handlers = [
  http.get('/api/search', async ({ request }) => {
    await delay(SEARCH_LATENCY_MS)
    const params = new URL(request.url).searchParams
    return toHttpResponse(await store.search(params.get('collection'), params.get('q'), params.get('page')))
  }),

  http.post('/api/assets', async ({ request }) => {
    await delay(LATENCY_MS)
    const form = await request.formData()
    return toHttpResponse(await store.uploadAsset(form.get('collection'), form.get('file')))
  }),

  http.get('/api/assets', async ({ request }) => {
    await delay(LATENCY_MS)
    const params = new URL(request.url).searchParams
    return toHttpResponse(store.listAssets(params.get('collection')))
  }),

  http.get('/api/assets/:id', async ({ params }) => {
    await delay(LATENCY_MS)
    return toHttpResponse(store.getAsset(String(params.id)))
  }),

  // The file answers with raw bytes and caching headers, not JSON.
  http.get('/api/assets/:id/file', async ({ params }) => {
    await delay(LATENCY_MS)
    const response = store.getFile(String(params.id))
    if (response.status !== 200) {
      return toHttpResponse(response)
    }
    const body = response.body as Blob
    return new HttpResponse(body, {
      status: 200,
      headers: {
        'Content-Type': body.type,
        'Cache-Control': 'public, max-age=31536000, immutable',
      },
    })
  }),

  http.post('/api/assets/:id/retry', async ({ params }) => {
    await delay(LATENCY_MS)
    return toHttpResponse(store.retryAsset(String(params.id)))
  }),

  http.get('/api/collections', async () => {
    await delay(LATENCY_MS)
    return toHttpResponse(store.listCollections())
  }),

  http.delete('/api/collections/:name', async ({ params }) => {
    await delay(LATENCY_MS)
    return toHttpResponse(store.deleteCollection(String(params.name)))
  }),

]
