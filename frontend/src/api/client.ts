// Every request the app sends to the server goes through this file: one function per API endpoint.
// Each builds the URL (and body), sends it, and returns the parsed JSON typed as in types.ts.
// Every failure is thrown as ApiError, so a component only ever catches one type and shows its `detail`.
import type { Asset, Collection, SearchResponse, SearchView, UploadResponse } from './types'

// `signal` lets the caller cancel the request: aborting it stops the fetch and rejects with an AbortError.
// Each filter value is its own parameter (match=exact&match=partial), the form the server reads as a list.
export async function search(
  collection: string,
  query: string,
  page: number,
  view: SearchView,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  const params = new URLSearchParams({ collection, q: query, page: String(page), order: view.order })
  for (const kind of view.match) {
    params.append('match', kind)
  }
  for (const assetType of view.assetType) {
    params.append('asset_type', assetType)
  }
  for (const part of view.foundIn) {
    params.append('found_in', part)
  }
  try {
    return await request<SearchResponse>(`/api/search?${params}`, { signal })
  } catch (caught) {
    // The search endpoint never answers 404 itself, so a 404 means this server has no search yet.
    if (caught instanceof ApiError && caught.status === 404) {
      throw new ApiError(404, 'Search is not available on this server yet.')
    }
    throw caught
  }
}

// fetch cannot report how much of a request body has been sent, so the upload uses XMLHttpRequest, whose
// `upload.onprogress` event can. `onProgress` gets the fraction sent so far, from 0 to 1.
// Failures are the same ApiErrors as every other request.
export function uploadAsset(
  collection: string,
  file: File,
  onProgress?: (fraction: number) => void,
): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('collection', collection)

  return new Promise((resolve, reject) => {
    const httpRequest = new XMLHttpRequest()
    httpRequest.open('POST', '/api/assets')
    httpRequest.upload.onprogress = (event) => {
      if (onProgress && event.lengthComputable) {
        onProgress(event.loaded / event.total)
      }
    }
    httpRequest.onload = () => {
      if (httpRequest.status >= 200 && httpRequest.status < 300) {
        resolve(JSON.parse(httpRequest.responseText) as UploadResponse)
      } else {
        reject(new ApiError(httpRequest.status, errorDetail(httpRequest.status, httpRequest.responseText)))
      }
    }
    httpRequest.onerror = () => reject(new ApiError(0, 'Could not reach the server.'))
    httpRequest.send(form)
  })
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
  const bodyText = await response.text()
  throw new ApiError(response.status, errorDetail(response.status, bodyText))
}

// Errors arrive as {"detail": string}, except a server crash, whose body may be anything.
function errorDetail(status: number, bodyText: string): string {
  try {
    const body = JSON.parse(bodyText)
    if (typeof body.detail === 'string') {
      return body.detail
    }
  } catch {
    // Not JSON: fall through to the generic message.
  }
  return `Something went wrong on the server (HTTP ${status}).`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await send(path, init)
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}
