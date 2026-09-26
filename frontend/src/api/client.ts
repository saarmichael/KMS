// Every request the app sends to the server goes through this file: one function per API endpoint.
// Each builds the URL (and body), sends it, and returns the parsed JSON typed as in types.ts.
// Every failure is thrown as ApiError, so a component only ever catches one type and shows its `detail`.
import type { Asset, Collection, SearchResponse, UploadResponse } from './types'

// `signal` lets the caller cancel the request: aborting it stops the fetch and rejects with an AbortError.
export function search(collection: string, query: string, page: number, signal?: AbortSignal): Promise<SearchResponse> {
  const params = new URLSearchParams({ collection, q: query, page: String(page) })
  return request<SearchResponse>(`/api/search?${params}`, { signal })
}

export function uploadAsset(collection: string, file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('collection', collection)
  return request<UploadResponse>('/api/assets', { method: 'POST', body: form })
}

export async function listAssets(collection: string): Promise<Asset[]> {
  const params = new URLSearchParams({ collection })
  const body = await request<{ assets: Asset[] }>(`/api/assets?${params}`)
  return body.assets
}

export function getAsset(id: string): Promise<Asset> {
  return request<Asset>(`/api/assets/${id}`)
}

export function assetFileUrl(id: string): string {
  return `/api/assets/${id}/file`
}

export async function getAssetText(id: string): Promise<string> {
  const response = await send(assetFileUrl(id))
  return response.text()
}

export function retryAsset(id: string): Promise<Asset> {
  return request<Asset>(`/api/assets/${id}/retry`, { method: 'POST' })
}

export async function listCollections(): Promise<Collection[]> {
  const body = await request<{ collections: Collection[] }>('/api/collections')
  return body.collections
}

export function deleteCollection(name: string): Promise<void> {
  return request<void>(`/api/collections/${name}`, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------------------------------
// Shared by the functions above: sending a request and turning a failed answer into an ApiError.

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
    this.detail = detail
  }
}

// Status 0 stands for "no HTTP answer at all" (server down, network gone).
// A request the caller cancelled is passed on as the browser's AbortError, so it is never shown as an error.
async function send(path: string, init?: RequestInit): Promise<Response> {
  let response: Response
  try {
    response = await fetch(path, init)
  } catch (caught) {
    if (caught instanceof DOMException && caught.name === 'AbortError') {
      throw caught
    }
    throw new ApiError(0, 'Could not reach the server.')
  }
  if (response.ok) {
    return response
  }

  // Errors arrive as {"detail": string}, except a server crash, whose body may be anything.
  let detail = `Something went wrong on the server (HTTP ${response.status}).`
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') {
      detail = body.detail
    }
  } catch {
    // Not JSON: keep the generic message.
  }
  throw new ApiError(response.status, detail)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await send(path, init)
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}
