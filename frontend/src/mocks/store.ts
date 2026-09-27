// The in-memory fake backend behind the MSW handlers. It answers with the same shapes and status codes
// as the real API; its search is a deliberately naive word match, not the real ranking.
import type { Asset, AssetMetadata, AssetStatus, SearchResult } from '../api/types'
import { seedAssets } from './seed'

// What the fake backend keeps per asset. The API's Asset is derived from it on every read.
export type StoredAsset = {
  id: string
  collection: string
  filename: string
  aliases: string[]
  asset_type: 'image' | 'text'
  body: Blob
  created_at: string
  metadata: AssetMetadata   // what the asset shows once "ready"
  queuedAt: number          // ms timestamp the status clock counts from; 0 means long ago
  retried: boolean          // the `fail` rule only fails the first pass
}

export type MockResponse = { status: number; body: object | null }

// Every asset the fake backend holds. Starts from the seed; a page reload starts over.
let assets: StoredAsset[] = seedAssets()

export async function search(collection: string | null, query: string | null, pageParam: string | null): Promise<MockResponse> {
  if (collection === null || !NAME_RULE.test(collection)) {
    return error(422, 'collection must be 1-64 characters of a-z, 0-9, - or _.')
  }
  if (query === null || query.trim() === '') {
    return error(422, 'q must not be empty.')
  }
  const page = pageParam === null ? 1 : Number(pageParam)
  if (!Number.isInteger(page) || page < 1) {
    return error(422, 'page must be 1 or more.')
  }

  const words = query.toLowerCase().split(/\s+/).filter((word) => word !== '')
  const matches: { stored: StoredAsset; matchCount: number }[] = []
  for (const stored of assets) {
    if (stored.collection !== collection || currentStatus(stored) !== 'ready') {
      continue
    }
    const metadata = stored.metadata
    const haystack = [stored.filename, metadata.title, metadata.description, metadata.tags.join(' '), metadata.visible_text ?? '']
      .join(' ')
      .toLowerCase()
    const matchCount = words.filter((word) => haystack.includes(word)).length
    if (matchCount > 0) {
      matches.push({ stored, matchCount })
    }
  }
  matches.sort((first, second) => second.matchCount - first.matchCount || second.stored.created_at.localeCompare(first.stored.created_at))

  const capped = matches.slice(0, MAX_RESULTS)
  const pageMatches = capped.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const topCount = capped.length > 0 ? capped[0].matchCount : 1
  const results: SearchResult[] = []
  for (const { stored, matchCount } of pageMatches) {
    let snippet
    if (stored.asset_type === 'text') {
      snippet = contentSnippet(await stored.body.text(), words)
    } else if (inImageTextOnly(stored.metadata, words)) {
      snippet = {
        kind: 'visible_text' as const,
        text: stored.metadata.visible_text ?? '',
        start_char: null,
        end_char: null,
        sentence_start: null,
        sentence_end: null,
      }
    } else {
      snippet = {
        kind: 'image' as const,
        text: stored.metadata.description,
        start_char: null,
        end_char: null,
        sentence_start: null,
        sentence_end: null,
      }
    }
    // The mock matches words only, so a result is exact when it holds every word; it ignores the filters.
    const match = matchCount === words.length ? ('exact' as const) : ('partial' as const)
    results.push({ asset: toAsset(stored), score: matchCount / topCount, snippet, match })
  }

  const hasMore = capped.length > page * PAGE_SIZE
  return { status: 200, body: { results, page, page_size: PAGE_SIZE, has_more: hasMore } }
}

export async function uploadAsset(collection: FormDataEntryValue | null, file: FormDataEntryValue | null): Promise<MockResponse> {
  if (typeof collection !== 'string' || !(file instanceof File)) {
    return error(422, 'Both file and collection are required.')
  }
  if (!NAME_RULE.test(collection)) {
    return error(422, 'collection must be 1-64 characters of a-z, 0-9, - or _.')
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return error(413, 'File is larger than the 10 MB limit.')
  }
  // Simplification: the real backend sniffs the type from the bytes; the mock trusts the browser.
  const isImage = file.type.startsWith('image/')
  const isText = file.type.startsWith('text/')
  if (!isImage && !isText) {
    return error(415, 'Only images and text files are supported.')
  }

  const hash = await sha256(file)
  for (const stored of assets) {
    if (stored.collection !== collection) {
      continue
    }
    if ((await sha256(stored.body)) !== hash) {
      continue
    }
    if (stored.filename !== file.name && !stored.aliases.includes(file.name)) {
      stored.aliases.push(file.name)
    }
    return { status: 200, body: { deduplicated: true, asset: toAsset(stored) } }
  }

  const baseName = file.name.replace(/\.[^.]*$/, '')
  const stored: StoredAsset = {
    id: crypto.randomUUID(),
    collection,
    filename: file.name,
    aliases: [],
    asset_type: isImage ? 'image' : 'text',
    body: file,
    created_at: new Date().toISOString(),
    metadata: {
      title: baseName,
      description: `Mock description of ${file.name}.`,
      tags: ['uploaded'],
      visible_text: isImage ? '' : null,
      image_type: isImage ? 'other' : null,
      vision_model: 'mock',
    },
    queuedAt: Date.now(),
    retried: false,
  }
  assets.push(stored)
  return { status: 202, body: { deduplicated: false, asset: toAsset(stored) } }
}

export function listAssets(collection: string | null): MockResponse {
  if (collection === null || !NAME_RULE.test(collection)) {
    return error(422, 'collection must be 1-64 characters of a-z, 0-9, - or _.')
  }
  const inCollection = assets.filter((stored) => stored.collection === collection)
  inCollection.sort((first, second) => second.created_at.localeCompare(first.created_at))
  return { status: 200, body: { assets: inCollection.map(toAsset) } }
}

export function getAsset(id: string): MockResponse {
  const found = findAsset(id)
  if ('status' in found) {
    return found
  }
  return { status: 200, body: toAsset(found) }
}

export function getFile(id: string): MockResponse {
  const found = findAsset(id)
  if ('status' in found) {
    return found
  }
  return { status: 200, body: found.body }
}

export function retryAsset(id: string): MockResponse {
  const found = findAsset(id)
  if ('status' in found) {
    return found
  }
  if (currentStatus(found) !== 'failed') {
    return error(409, 'Only a failed asset can be retried.')
  }
  found.retried = true
  found.queuedAt = Date.now()
  return { status: 200, body: toAsset(found) }
}

export function listCollections(): MockResponse {
  const counts = new Map<string, number>()
  for (const stored of assets) {
    counts.set(stored.collection, (counts.get(stored.collection) ?? 0) + 1)
  }
  const names = [...counts.keys()].sort()
  const collections = names.map((name) => ({ name, asset_count: counts.get(name) }))
  return { status: 200, body: { collections } }
}

export function deleteCollection(name: string): MockResponse {
  if (!NAME_RULE.test(name)) {
    return error(422, 'collection must be 1-64 characters of a-z, 0-9, - or _.')
  }
  assets = assets.filter((stored) => stored.collection !== name)
  return { status: 204, body: null }
}

// ---------------------------------------------------------------------------------------------------
// Limits and helpers used by the endpoint functions above.

const PENDING_MS = 2_000
const READY_MS = 5_000
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024
const PAGE_SIZE = 20
const MAX_RESULTS = 100
const NAME_RULE = /^[a-z0-9_-]{1,64}$/
const UUID_RULE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const FAIL_MESSAGE = 'Mock failure: the vision model returned invalid output three times.'

function error(status: number, detail: string): MockResponse {
  return { status, body: { detail } }
}

// The mock worker: no timers, the status follows from the time since the asset was queued.
function currentStatus(stored: StoredAsset): AssetStatus {
  const elapsed = Date.now() - stored.queuedAt
  if (elapsed < PENDING_MS) {
    return 'pending'
  }
  if (elapsed < READY_MS) {
    return 'processing'
  }
  if (stored.filename.includes('fail') && !stored.retried) {
    return 'failed'
  }
  return 'ready'
}

function toAsset(stored: StoredAsset): Asset {
  const status = currentStatus(stored)
  return {
    id: stored.id,
    collection: stored.collection,
    filename: stored.filename,
    aliases: stored.aliases,
    asset_type: stored.asset_type,
    mime: stored.body.type,
    size_bytes: stored.body.size,
    status,
    error: status === 'failed' ? FAIL_MESSAGE : null,
    created_at: stored.created_at,
    metadata: status === 'ready' ? stored.metadata : null,
  }
}

async function sha256(blob: Blob): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
}

function findAsset(id: string): StoredAsset | MockResponse {
  if (!UUID_RULE.test(id)) {
    return error(422, 'id is not a valid UUID.')
  }
  const stored = assets.find((candidate) => candidate.id === id)
  if (!stored) {
    return error(404, 'No asset with that id.')
  }
  return stored
}

// True when a query word is in the image's text but in none of the description, title or tags, so the
// match came from the text read from the image.
function inImageTextOnly(metadata: AssetMetadata, words: string[]) {
  const imageText = (metadata.visible_text ?? '').toLowerCase()
  const described = [metadata.title, metadata.description, metadata.tags.join(' ')].join(' ').toLowerCase()
  return words.some((word) => imageText.includes(word)) && !words.some((word) => described.includes(word))
}

// A content snippet: about 200 characters around the first query word found in the text.
function contentSnippet(text: string, words: string[]) {
  const lowered = text.toLowerCase()
  let position = -1
  for (const word of words) {
    position = lowered.indexOf(word)
    if (position !== -1) {
      break
    }
  }
  const start = Math.max(0, position - 100)
  const end = Math.min(text.length, start + 200)
  // The mock matches words only, so it never has a sentence matched by meaning.
  return {
    kind: 'content' as const,
    text: text.slice(start, end),
    start_char: start,
    end_char: end,
    sentence_start: null,
    sentence_end: null,
  }
}
