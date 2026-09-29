// The JSON shapes the API sends and receives.

export type AssetStatus = 'pending' | 'processing' | 'ready' | 'failed'

export type ImageType = 'photo' | 'screenshot' | 'document' | 'diagram' | 'other'

// The AI-written description of an asset. It is null on the asset until status is "ready".
export type AssetMetadata = {
  title: string
  description: string
  tags: string[]
  visible_text: string | null
  image_type: ImageType | null
  vision_model: string | null
}

// One uploaded file. Upload, list, detail, retry and search all return this same shape.
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

export type Collection = {
  name: string
  asset_count: number
}

// How the deployment is set up. In demo mode, deleting a collection is switched off.
export type AppConfig = {
  demo_mode: boolean
}

// deduplicated is true when the collection already held these exact bytes.
export type UploadResponse = {
  deduplicated: boolean
  asset: Asset
}

// Why a search result matched: a passage of a text file (with its position), the asset's description,
// or its file name. A result matched by meaning also says which sentence of `text` is closest to the query,
// counted in characters of `text`.
export type Snippet = {
  kind: 'metadata' | 'content' | 'image' | 'visible_text' | 'filename'
  text: string
  start_char: number | null
  end_char: number | null
  sentence_start: number | null
  sentence_end: number | null
}

// How a result matched: every query word in one part of it, some of the words, or by meaning only.
export type MatchKind = 'exact' | 'partial' | 'semantic'

export type SearchResult = {
  asset: Asset
  score: number
  // How well the result answers the query, 0 to 1, as the reranker judged it; null when it was not scored
  // (past the first 20 results, or with reranking off).
  relevance: number | null
  snippet: Snippet
  match: MatchKind
}

export type SearchOrder = 'relevance' | 'exact_first' | 'tiered' | 'blended'

// What the user chose to see: the order and three filters, each a list of the values to keep.
export type SearchView = {
  order: SearchOrder
  match: MatchKind[]
  assetType: Asset['asset_type'][]
  foundIn: Snippet['kind'][]
}

export type SearchResponse = {
  results: SearchResult[]
  page: number
  page_size: number
  has_more: boolean
}
