// Hand-written from docs/api-contract.md (D34). Section numbers refer to that file.

export type AssetStatus = 'pending' | 'processing' | 'ready' | 'failed'

export type ImageType = 'photo' | 'screenshot' | 'document' | 'diagram' | 'other'

// §5: null on the asset until status is "ready".
export type AssetMetadata = {
  title: string
  description: string
  tags: string[]
  visible_text: string | null
  image_type: ImageType | null
  vision_model: string | null
}

// §5: the one shape returned by upload, list, detail, retry and search.
export type Asset = {
  id: string
  collection: string
  filename: string
  aliases: string[]
  asset_type: 'image' | 'text'
  mime: string
  size_bytes: number
  status: AssetStatus
  error: string | null
  created_at: string
  metadata: AssetMetadata | null
}

// §6.6
export type Collection = {
  name: string
  asset_count: number
}

// §6.1
export type UploadResponse = {
  deduplicated: boolean
  asset: Asset
}

// §6.8
export type Snippet = {
  kind: 'metadata' | 'content' | 'image'
  text: string
  start_char: number | null
  end_char: number | null
}

export type SearchResult = {
  asset: Asset
  score: number
  snippet: Snippet
}

export type SearchResponse = {
  results: SearchResult[]
  page: number
  page_size: number
  has_more: boolean
}
