# Sift — Test plan

Sep 24, 2026 · Michael

Companion to *Sift — System design*. The design says what the system is; this says how we know it works. Lives at `docs/TESTING.md` and is read by Claude Code alongside the design when producing the implementation plan.

## Audience and priorities

The interviewer will upload a photo and a text file, wait for `ready`, type the two example queries from the assignment plus a paraphrase or two, then read the code. So, in order:

1. The demo must not fail.
2. The automated tests must show which parts of *this* design are risky (queue, lease, dedup, hybrid merge) — not coverage for its own sake.
3. Everything else is optional.

Deliberately not automated: the React UI, vendor adapters beyond one skippable live test.

## Fake adapters

Both deterministic, selected with `AI_PROVIDER=fake`. The same switch is the local dev loop, so building the UI burns no quota.

| Adapter | Behaviour |
| --- | --- |
| `FakeVision` | Returns metadata keyed on filename from a fixture dict; unknown filename → generic valid metadata. Also has a mode that returns invalid JSON once, to exercise the repair retry. |
| `FakeEmbedder` | Hashed bag-of-words into 1024 dims, L2-normalised. Same text → same vector; "black hair" ≠ "brunette". Images embed from a hash of the bytes. |

Rationale: synonym recall ("brunette" for "black hair") is a property of Voyage, not of our code. Our code's claims are that both paths run, RRF fuses them, both-path hits outrank single-path hits, grouping picks the best unit, and the collection filter holds. All testable with a dumb-but-deterministic embedder.

## Automated tests

Runner: `pytest`. Integration tests use the compose Postgres (`docker compose up -d db` first; `make test` does this). No testcontainers.

**Unit — no DB, no network**

1. Chunker: offsets are correct, consecutive chunks overlap and cover the whole text, no chunk exceeds the size, no word is cut.
2. RRF merge + group-by-asset: a unit found on both paths outranks one found on either alone; best unit wins per asset; normalised score is 1.0 for the top asset.
3. Schema normalisation: tags lowercased and deduped, list lengths clamped, over-long text truncated, `image_type` null for text.
4. Error classification: 429 / 5xx / timeout → transient (retried with backoff); 400 / 413 / 401 / safety block → permanent (fails at once).

**Integration — real Postgres, fake adapters**

5. Upload → worker → ready, end to end; asset absent from search while `pending`, present once `ready`.
6. Dedup: same bytes twice → one row, second response `200 deduplicated: true`, new filename appended to `aliases`. Includes the race: two concurrent identical uploads → exactly one row, both responses succeed.
7. Lease reaper: a row stuck in `processing` with `started_at` older than the lease is reset to `pending`; a fresh one is not. Attempts cap: third failure → `failed` with message in `error`; retry endpoint resets it.
8. Hybrid search: a both-path hit ranks above single-path hits; results scoped to the collection; a text file's hit points at the right chunk offsets; pagination returns the next page without repeats.

**Live — skipped unless `GEMINI_API_KEY` and `VOYAGE_API_KEY` are set**

9. One image and one text file through real Gemini + Voyage: output validates against the schema, `visible_text` non-empty for the screenshot, and "black hair" finds the file that only says "brunette".

## Seed collection and query matrix

~30 files under `seed/demo/`, built backwards from the queries. `seed/demo/README.md` lists every file, its source and licence, and the queries it is meant to answer — that file doubles as the manual test matrix.

| Query | Must hit (literal) | Must also hit (paraphrase / vector-only) | Must not hit |
| --- | --- | --- | --- |
| black hair | 2–3 photos of dark-haired people; text file containing "black hair" | text file saying "brunette"; photo with no caption text | blond-hair photos ranked at the top |
| document | photo of paper on a desk; scanned form; screenshot of a PDF; text file containing "document" | text file that says "the report" but never "document" | — |
| receipt | one photo of a receipt | — | — |
| blond hair | 1–2 photos | — | dark-hair photos at the top |
| diagram | one hand-drawn diagram, photographed | — | — |
| screenshot text | screenshot with visible text; query is a phrase from it | — | — |

Sources: Unsplash / Pexels for people and scenes (free licence, credited in the README); 3–4 own screenshots; one own diagram; 8–10 short text files written by hand so literal vs. implied is controlled. Reseed cost is well under a minute of Gemini + Voyage spend; reseeding is a no-op after the first run thanks to hash dedup.

## Local run

```
docker compose up -d          # api + db (pgvector image)
make seed                     # ingests seed/demo/ through the upload path
make test                     # unit + integration (fake adapters)
make test-live                # adds the live test; needs API keys
AI_PROVIDER=fake make dev     # UI work without quota
```

## Manual checklist (the demo script)

Run before every deploy and once more before the interview. Ten minutes.

1. Create a new, empty collection.
2. Upload three files (photo, screenshot, text). Watch `pending → processing → ready` in the list.
3. Run the matrix queries above; check the paraphrase rows in particular.
4. Upload a duplicate under a different name; confirm `deduplicated` and the alias shown in results.
5. Upload a file with the worker stopped, then start the worker; confirm it picks the file up (LISTEN/NOTIFY or the 1 s poll).
6. Kill the worker mid-job; confirm the reaper returns the asset to `pending` and it completes on the next pass.
7. Force a permanent AI error (e.g. invalid key on one adapter); confirm `failed` with a readable message, and that Retry works after fixing it.
8. Open a file via `GET /api/assets/{id}/file`; confirm the ETag and cache headers.
9. Delete the collection; confirm search returns nothing for it.

## Open items

- Whether to gate CI on the integration tests (needs a Postgres service in the workflow) or unit-only. Default: both, GitHub Actions with a `pgvector/pgvector` service container.
- Rerank and pg_trgm, if built, each add one unit test and one matrix row; not planned otherwise.
