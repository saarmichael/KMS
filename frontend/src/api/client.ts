// One function per endpoint of docs/api-contract.md. Every failure is thrown as ApiError, so a
// component only ever catches one type and shows its `detail`.
import type { Asset, Collection, SearchResponse, UploadResponse } from './types'

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
async function send(path: string, init?: RequestInit): Promise<Response> {
  let response: Response
  try {
    response = await fetch(path, init)
  } catch {
    throw new ApiError(0, 'Could not reach the server.')
  }
  if (response.ok) {
    return response
  }

  // Contract §4: errors are {"detail": string}, except a 500, whose body may be anything.
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

export function search(collection: string, query: string, page: number): Promise<SearchResponse> {
  const params = new URLSearchParams({ collection, q: query, page: String(page) })
  return request<SearchResponse>(`/api/search?${params}`)
}
