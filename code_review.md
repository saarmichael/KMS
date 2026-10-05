# Code review

## bad_practice

- **`backend/src/kms/ingest/chunker.py` (`chunk_text`) and `backend/src/kms/search/sentences.py`
  (`split_sentences`), duplicated code:**
  - **Problem:** the same four-line loop trims the whitespace at a span's edges in both places
    (`chunker.py:49-54`, `sentences.py:51-56`), only the variable names differ. Each moves the start forward
    and the end back one character at a time with `isspace()`, without editing the text.
  - **Why:** bad practice.
  - **Fix:** one shared function that takes the text and a span's start and end and returns the trimmed start
    and end, using `str.lstrip()` and `str.rstrip()` on the slice; both callers use it.
- **`backend/src/kms/search/keyword.py` and `models.py`:**
  - **Problem:** the `"english"` config that builds `tsv` is repeated as a literal.
  - **Why:** bad practice.
  - **Fix:** share it instead.
- **`backend/src/kms/ingest/worker.py` (`Unit.kind`) and `search/`:**
  - **Problem:** a unit's kind is a plain `str`, though there is a fixed set of kinds (`metadata`, `content`,
    `image`, `visible_text`, `filename`). The set is only listed in docstrings and the `models.py` column
    comment, and as a `Literal` twice at the API edge (`api/schemas.py`, `api/search.py`).
  - **Why:** bad practice.
  - **Fix:** an enum for the unit kinds.
- **`backend/src/kms/search/service.py` (`search`, `run_both_paths`):**
  - **Problem:** `embed_query` is called twice per search: once on the vector thread in `run_both_paths`
    (`:231`), and again in `search` for `mark_closest_sentences` (`:458`).
  - **Why:** the second call is free only because `embed_query` is wrapped in `@lru_cache` (`:99`), which the
    call site does not show, and it reads the vector back from the cache instead of using the one already
    computed.
  - **Fix:** the vector thread returns the vector with its hits, `run_both_paths` returns it as a third value,
    and `search` passes it to `mark_closest_sentences`; the keyword search still runs while the query is
    embedded.
- **`backend/src/kms/api/assets.py` (`list_assets`):**
  - **Problem:** `GET /api/assets` returns every asset of a collection in one response, newest first, with no
    limit: the query has no `LIMIT`, `.mappings().all()` loads every row, and each becomes an `Asset` in the one
    JSON body.
  - **Why:** it does not hold if the system scales.
  - **Fix:** paging with an offset plus a cursor.
- **`backend/src/kms/main.py` (SPA catch-all):**
  - **Problem:** `path.startswith("api/")` relies on every router writing `/api` by hand (also `OPEN_PATHS` in
    `api/auth.py`).
  - **Why:** if the prefix changes, mistyped API URLs silently get the page instead of a JSON 404.
  - **Fix:** one `API_PREFIX` constant passed to `include_router(prefix=...)` and reused in the check.

## design

- **`backend/src/kms/blob/__init__.py` (`get_blob_store`):**
  - **Problem:** the blob store is built as an adapter (the `BlobStore` base class, callers that never name an
    implementation), but `get_blob_store()` always builds `LocalBlobStore` and no setting picks the backend.
  - **Why:** adding the S3-compatible store means editing the function.
  - **Fix:** a `BLOB_BACKEND` setting that `get_blob_store()` reads to choose the implementation.

- **`backend/src/kms/ingest/upload.py` (whole module), speculative:**
  - **Problem:** uploads are handled by hand from the raw bytes: type sniffing, sha256, the blob write and the
    row insert.
  - **Why:** bad practice; libraries exist that do this end to end.
  - **Fix:** use one (Rails Active Storage; in Python `sqlalchemy-file` or `fastapi-storages`: a file column
    type that records the metadata and stores the bytes on local disk or S3).
- **`backend/src/kms/ai/prompts.py` and `ai/gemini.py` (`GeminiVision`):**
  - **Problem:** the prompt text is fixed: module constants, with `PREAMBLE` joined into `IMAGE_PROMPT` and
    `TEXT_PROMPT` at import time, which `gemini.py` imports directly. The recording cache (`ai/recorded.py`)
    keys on `PROMPT_VERSION`, a number raised by hand.
  - **Why:** the prompts cannot be adapted, and a prompt test cannot swap one part on its own. Once prompts can
    be swapped, two variants share a key and replay each other's answers.
  - **Fix:** the prompts become a dependency of the vision model, passed in when it is constructed; the cache
    keys on a hash of the prompt text itself.
- **`backend/src/kms/search/service.py:100` (`embed_query`):**
  - **Problem:** `model` is an argument only so that it is part of the cache key; the body never uses it. The
    embedder that makes the vector is fetched inside, with `get_embedder()` (`:121`).
  - **Why:** the key and the embedder that answers are tied only by the caller reading `get_embedder().model`
    first (`:418`).
  - **Fix:** the embedder is passed in as the argument (dependency injection), so the cache key is the embedder
    that makes the vector.

## style

- **`backend/src/kms/ingest/upload.py` (`upload`):**
  - **Problem:** the duplicate branch (append the filename to `aliases`, load the existing row, return it as
    deduplicated) runs inline after the insert, so `upload` handles both the new-file and the duplicate case.
  - **Why:** style only; bad practice.
  - **Fix:** a helper for the duplicate case, called when the insert returns no row.
- **`backend/src/kms/api/assets.py` (`get_asset_file`):**
  - **Problem:** one handler works out the three parts of the `Response` inline: the bytes (loaded from the blob
    store, a missing blob logged), the content type (forced to UTF-8 for text) and the `Content-Disposition`
    header (plain or percent-encoded filename).
  - **Why:** bad practice.
  - **Fix:** a helper for each, so the handler only loads the row and assembles the response.
