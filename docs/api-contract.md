# KMS — API contract

**Status: approved by Michael, Sep 26, 2026.**

This file fixes every endpoint's request and response (D29). It is the only coupling between the backend
track and the frontend track (D28): the backend's Pydantic response models and the frontend's TypeScript
types are both written by hand from it (D34), and the frontend's mocks return exactly what it shows. A
change to this file needs Michael's approval and lands on `main` first.

The API is deliberately small: nine endpoints, one asset shape. Endpoints can be added later; changing the
shape of an existing one is what this file exists to prevent.

---

## 1. How to read this file

Each endpoint has: what it is for and when the UI calls it, the request, every status code, and an example
response. Types are written TypeScript-style because that is how the frontend will write them:
`string | null` means the key is always present and its value may be `null`. No key is ever omitted.

## 2. Conventions (apply to every endpoint)

| Rule | Value | Why |
| --- | --- | --- |
| Base path | Every endpoint starts with `/api`. Everything else is the SPA | FastAPI serves both from one origin, so no CORS |
| Field names | `snake_case`, the same as the database columns | Nothing gets renamed between the DB and the UI |
| IDs | UUID strings, e.g. `"3f2b8c1e-…"` | The `assets.id` column is a UUID |
| Times | ISO 8601 strings in UTC, e.g. `"2026-09-26T14:03:11Z"` | The browser's `new Date()` parses them |
| Lists | Wrapped in an object: `{"assets": [...]}`, never a bare array | A field can be added next to the list later without breaking the UI |
| Errors | Always `{"detail": string}` with a human-readable message (D33) | The UI shows `detail` as-is; see section 4 |

## 3. Collections (D31)

A collection is just the value of the `collection` column; there is no collections table and no create
endpoint. A collection exists as long as it has at least one asset.

- **"+ New collection"** in the UI only picks a new name and selects it locally. The first upload into
  it makes it real. Until then it does not appear in `GET /api/collections`, so an empty new collection
  is lost on a page reload. That is accepted.
- **Name rule:** 1 to 64 characters, each a lowercase letter, a digit, `-` or `_`
  (regex `^[a-z0-9_-]{1,64}$`). The name appears in URL paths (`DELETE /api/collections/{name}`), so this
  keeps it safe without encoding. A name that breaks the rule gets `422`.
- Reading from a collection that has no assets is not an error: the list and search just come back empty.

## 4. Errors (D33)

Every error response has the same body:

```json
{ "detail": "File is larger than the 10 MB limit." }
```

| Status | Meaning in this API |
| --- | --- |
| `404` | The asset id does not exist |
| `409` | The action does not fit the asset's current state (only: retry of an asset that is not `failed`) |
| `413` | Upload larger than 10 MB |
| `415` | Upload is neither a supported image nor text |
| `422` | A parameter is missing or invalid (bad collection name, empty query, page below 1, id not a UUID) |
| `500` | A bug on our side. Body is FastAPI's default and may not be JSON; the UI shows a generic message |

Why the `422` note matters: FastAPI's own validation errors come back with `detail` as a *list* of
objects. The backend adds one exception handler that joins them into a single string, so the UI never
has to check which kind of `detail` it got.

---

## 5. The Asset object

Every endpoint that returns a file's information returns this one shape: upload, list, detail, retry and
search. The UI therefore needs one type for it.

```ts
type Asset = {
  id: string;                 // UUID
  collection: string;
  filename: string;           // the name it was first uploaded under
  aliases: string[];          // other names later uploaded with identical bytes; [] if none
  asset_type: "image" | "text";
  mime: string;               // detected from the bytes, e.g. "image/jpeg", "text/plain"
  size_bytes: number;
  status: "pending" | "processing" | "ready" | "failed";
  error: string | null;       // the reason, set only when status is "failed"
  created_at: string;         // ISO 8601, UTC
  metadata: AssetMetadata | null;  // null until status is "ready"
};

type AssetMetadata = {
  title: string;
  description: string;
  tags: string[];             // lowercase, may be multi-word ("travel notes")
  visible_text: string | null;   // images only: every readable word in the image; null for text files
  image_type: "photo" | "screenshot" | "document" | "diagram" | "other" | null;  // null for text files
  vision_model: string | null;   // which Gemini model wrote it; null until Phase 4 adds the column
};
```

**Status lifecycle.** `pending` (uploaded, waiting for a worker) → `processing` (a worker is on it) →
`ready` (metadata written, searchable) or `failed` (gave up after 3 attempts; `error` says why). Retry
moves `failed` back to `pending`. Only `ready` assets appear in search.

**Why `metadata` is nested.** Before processing there is no metadata at all. One `null` says that; the UI
checks `asset.metadata` once instead of six separate fields.

**What is left out on purpose.** `sha256` (it is the file's `ETag` header, the UI never needs it),
`attempts` and `started_at` (worker internals), `metadata_version` (an ingest concern). They can be added
later if a screen needs them.

**Example** (a ready image):

```json
{
  "id": "3f2b8c1e-5d6a-4c1b-9a0e-2e7f1d9c4b10",
  "collection": "demo",
  "filename": "office-desk.jpg",
  "aliases": ["IMG_2231.jpg"],
  "asset_type": "image",
  "mime": "image/jpeg",
  "size_bytes": 842113,
  "status": "ready",
  "error": null,
  "created_at": "2026-09-26T14:03:11Z",
  "metadata": {
    "title": "Receipt on an office desk",
    "description": "A printed store receipt lies next to a laptop and a coffee mug on a wooden desk.",
    "tags": ["receipt", "desk", "laptop", "coffee mug", "document", "photo"],
    "visible_text": "SYNKA CO. TOTAL 23.40",
    "image_type": "photo",
    "vision_model": "gemini-3-flash-preview"
  }
}
```

A pending text file looks the same with `"asset_type": "text"`, `"status": "pending"` and
`"metadata": null`.

---

## 6. Endpoints

| # | Method and path | What it does |
| --- | --- | --- |
| 6.1 | `POST /api/assets` | Upload one file into a collection |
| 6.2 | `GET /api/assets?collection=` | All assets of a collection, with their status |
| 6.3 | `GET /api/assets/{id}` | One asset |
| 6.4 | `GET /api/assets/{id}/file` | The file's bytes |
| 6.5 | `POST /api/assets/{id}/retry` | Put a failed asset back in the queue |
| 6.6 | `GET /api/collections` | Collection names with asset counts |
| 6.7 | `DELETE /api/collections/{name}` | Delete a collection and all its assets |
| 6.8 | `GET /api/search?collection=&q=&page=` | Hybrid search within a collection |
| 6.9 | `GET /api/health` | Deployment check |

### 6.1 `POST /api/assets` — upload one file

**When the UI calls it:** once per file the user drops or picks. Several files are several requests; the
UI can send them in parallel.

**Request:** `multipart/form-data` with two fields.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `file` | file | yes | One file, at most 10 MB. Its type is detected from the bytes, not from the name or the browser's content type |
| `collection` | string | yes | Must follow the name rule (section 3). A new name creates the collection |

**Responses:**

| Status | Body | When |
| --- | --- | --- |
| `202 Accepted` | `{"deduplicated": false, "asset": Asset}` | New file. `asset.status` is `"pending"`; the worker picks it up |
| `200 OK` | `{"deduplicated": true, "asset": Asset}` | The collection already holds these exact bytes. Nothing is processed again; `asset` is the existing one in whatever status it has, and if the filename is new it now appears in `asset.aliases` |
| `413` | error | Over 10 MB |
| `415` | error | Not a supported image and not text. Accepted: JPEG, PNG and WebP images (detected by reading the image header), and UTF-8 text (a BOM is allowed, NUL bytes are not). An empty file is `415` (D36) |
| `422` | error | `file` or `collection` missing, or the collection name breaks the rule |

**Why dedup is a `200` and not an error:** uploading the same file twice is harmless, and a client that
retries after a timeout must not get an error for its own retry (design doc, "Same file uploaded twice").
The UI can use `deduplicated` to say "already in this collection".

```json
{ "deduplicated": false, "asset": { "id": "…", "status": "pending", "metadata": null, "…": "…" } }
```

### 6.2 `GET /api/assets?collection=` — list a collection

**When the UI calls it:** when a collection is selected, and every 2 s while any listed asset is
`pending` or `processing` (that polling is how statuses update in the UI).

**Query parameters:** `collection` (required, name rule).

**Responses:**

| Status | Body | When |
| --- | --- | --- |
| `200` | `{"assets": Asset[]}` | Newest first (`created_at` descending). Every status is included. An unknown collection gives `[]` |
| `422` | error | `collection` missing or invalid |

No paging: a collection in this project holds tens of files. If that changes, `limit`/`offset` can be
added next to `assets` without breaking anything.

### 6.3 `GET /api/assets/{id}` — one asset

**When the UI calls it:** to open the asset detail view directly (for example from a search result or a
reloaded detail URL).

| Status | Body | When |
| --- | --- | --- |
| `200` | `Asset` | |
| `404` | error | No asset with that id |
| `422` | error | `id` is not a UUID |

### 6.4 `GET /api/assets/{id}/file` — the file itself

**When the UI calls it:** as the `src` of an `<img>` for thumbnails and the detail view, and with `fetch`
to show a text file's content in the detail view.

| Status | Body | When |
| --- | --- | --- |
| `200` | the raw bytes | |
| `404` | error | No asset with that id |
| `422` | error | `id` is not a UUID |

**Headers on `200`:**

| Header | Value | Why |
| --- | --- | --- |
| `Content-Type` | the asset's `mime`; for text files `text/plain; charset=utf-8` (D37) | The browser renders it correctly; upload guarantees UTF-8, so the charset is always true |
| `ETag` | `"<sha256>"` | The bytes of an asset never change, so the hash identifies them |
| `Cache-Control` | `public, max-age=31536000, immutable` | Same reason: the browser keeps it for a year and never asks again |
| `Content-Disposition` | `inline; filename="<filename>"`; a non-ASCII name as `inline; filename*=utf-8''<percent-encoded name>` | Shown in the browser; a "save as" gets the right name. An HTTP header carries only Latin-1, so other names use the RFC 5987 form |

There is no thumbnail endpoint: the UI scales the original with CSS. Images are at most 10 MB and the
cache headers mean each is downloaded once.

### 6.5 `POST /api/assets/{id}/retry` — retry a failed asset

**When the UI calls it:** the Retry button, shown only on `failed` assets.

**Request:** no body.

| Status | Body | When |
| --- | --- | --- |
| `200` | `Asset` | Status is now `"pending"`, `error` is `null`, the attempt counter is reset; the worker picks it up |
| `404` | error | No asset with that id |
| `409` | error | The asset is not `failed` (for example a double click after the first retry already worked) |
| `422` | error | `id` is not a UUID |

### 6.6 `GET /api/collections` — collection selector

**When the UI calls it:** on load, and after an upload into a new collection or a delete.

| Status | Body | When |
| --- | --- | --- |
| `200` | `{"collections": Collection[]}` | Sorted by name. Only collections with at least one asset (section 3) |

```ts
type Collection = {
  name: string;
  asset_count: number;   // all assets, whatever their status
};
```

```json
{ "collections": [ { "name": "demo", "asset_count": 31 }, { "name": "interview", "asset_count": 3 } ] }
```

### 6.7 `DELETE /api/collections/{name}` — delete a collection

**When the UI calls it:** "Delete collection", after the user confirms.

| Status | Body | When |
| --- | --- | --- |
| `204 No Content` | none | The collection's assets and search units are gone. Also `204` when the collection had no assets: deleting twice is not an error, and it lets the UI "delete" a new collection that was never uploaded to |
| `422` | error | Name breaks the rule |

Deletes database rows only; the files stay on disk (D13).

### 6.8 `GET /api/search` — search a collection

**When the UI calls it:** when the user submits a query (page 1), and on "show more" (page 2, 3, …).

**Query parameters:**

| Param | Type | Required | Notes |
| --- | --- | --- | --- |
| `collection` | string | yes | Name rule. Search never crosses collections |
| `q` | string | yes | The query as typed. Empty or only spaces → `422` |
| `page` | integer | no, default `1` | `1` or more. Pages hold 20 results (D32) |

**Responses:**

| Status | Body | When |
| --- | --- | --- |
| `200` | `SearchResponse` | An unknown collection or no match gives `results: []` |
| `422` | error | `collection` or `q` missing or invalid, `page` below 1 |

```ts
type SearchResponse = {
  results: SearchResult[];   // up to page_size, best first
  page: number;              // echoes the request
  page_size: number;         // 20
  has_more: boolean;         // true if "show more" would return more results
};

type SearchResult = {
  asset: Asset;              // always status "ready"
  score: number;             // 0 to 1; 1 is the best result of the whole query (not of the page)
  snippet: Snippet;          // why this asset matched
};

type Snippet = {
  kind: "metadata" | "content" | "image" | "filename";   // which part of the asset matched best
  text: string;
  start_char: number | null;  // only for "content": where the text sits in the file
  end_char: number | null;
};
```

**How to read a result.**
- `score` is for display only: the UI may dim results with a low score. Nothing is cut by score; every
  match is returned (design doc, "Where the cut between match and noise is drawn").
- `snippet.kind` says what matched best. `"content"`: a passage of a text file; `text` is that passage and
  `start_char`/`end_char` locate it in the file, so the detail view can highlight it. `"metadata"`: the
  AI description matched; `text` is the asset's description. `"image"`: the pixels matched; there is no
  text for that, so `text` is also the asset's description.
  `"filename"`: the file's name matched (the full name or a word of it); `text` is the asset's `filename`
  and there are no offsets.
- An asset appears at most once in a whole query, even across pages.

**Paging (D32).** `page` × 20 results, capped at 100 results per query (5 pages). `has_more` is `false` on
the last page. There is no total count: it would cost an extra query and the UI only needs "is there
more". A page past the end gives `200` with `results: []` and `has_more: false`, not an error.

```json
{
  "results": [
    {
      "asset": { "id": "…", "filename": "notes-lisbon.txt", "asset_type": "text", "status": "ready", "…": "…" },
      "score": 1.0,
      "snippet": { "kind": "content", "text": "…her black hair tied back against the wind…", "start_char": 1204, "end_char": 1731 }
    },
    {
      "asset": { "id": "…", "filename": "portrait-02.jpg", "asset_type": "image", "status": "ready", "…": "…" },
      "score": 0.83,
      "snippet": { "kind": "image", "text": "A woman with dark hair smiling in a park.", "start_char": null, "end_char": null }
    }
  ],
  "page": 1,
  "page_size": 20,
  "has_more": false
}
```

### 6.9 `GET /api/health` — deployment check

**When the UI calls it:** not in the product. The Phase 0 hello page shows it; Phase 8 adds status
counts. Documented as it is today (Phase 0):

```ts
type Health = {
  status: "ok" | "degraded";
  db: string;                // "ok", "bad", or "error: <message>"
  migrations: { current: string | null; head: string | null; ok: boolean };
  notify: { ok: boolean; ms: number | null; error?: string };  // error only when ok is false
  ai_provider: "fake" | "real";
};
```

When `db` is not reachable the response stops after `db`, so `migrations`, `notify` and `ai_provider` are
missing. This endpoint is the one exception to "no key is ever omitted"; it is kept as built because no
screen depends on it.

---

## 7. Which call feeds which screen

| Screen or action (Phase 7) | Calls |
| --- | --- |
| App load | `GET /api/collections`; select `demo` if present |
| Collection selector with counts | `GET /api/collections` |
| "+ New collection" | none until the first upload (section 3) |
| "Delete collection" | `DELETE /api/collections/{name}`, then `GET /api/collections` |
| Asset list with status badges | `GET /api/assets?collection=`, repeated every 2 s while any asset is `pending` or `processing` |
| Upload (drag and drop, multi-file) | `POST /api/assets` once per file, then refresh the list and the collections |
| "Already in this collection" / alias note | `deduplicated` in the upload response; `aliases` on the asset |
| Failed asset: error text + Retry | `asset.error`; `POST /api/assets/{id}/retry` |
| Search results | `GET /api/search?collection=&q=` |
| "Show more" | `GET /api/search?…&page=N+1` while `has_more` |
| Dimmed tail | `score` |
| "Found in: … / identical to: …" | `asset.filename` and `asset.aliases` |
| Thumbnails | `<img src="/api/assets/{id}/file">` |
| Asset detail view | the `Asset` already in hand, or `GET /api/assets/{id}`; the file via `/api/assets/{id}/file`; `snippet` offsets for highlighting |

## 8. Decisions in this contract

| # | Decision | Where |
| --- | --- | --- |
| D31 | Collections are implicit: no create endpoint, name rule `^[a-z0-9_-]{1,64}$` | section 3 |
| D32 | Search paging is `page` + `has_more`, page size 20, no total | 6.8 |
| D33 | Error body is always `{"detail": string}`; one handler flattens 422 | section 4 |
| D34 | Backend response models and frontend types are both hand-written from this file | top |
| D48 | A file is found by its name; `snippet.kind` `"filename"` says so | 6.8 |
