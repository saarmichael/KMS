# KMS — Working plan

Sep 24, 2026 · Michael, with Claude Code

This is the working plan, not the implementation spec. The design (`docs/system-design.md`) says what
the system is; the test plan (`docs/TESTING.md`) says how we know it works; this file says in what
order we build it so that each phase retires one risk, ends in something you can run and see, and leaves a
clear gate to pass before the next phase starts.

Rule of the plan: **every decision is Michael's.** Decisions already taken are in the log below. Decisions
that a phase will surface are listed inside that phase under "Decisions to take", and are asked before the
step that needs them. Anything marked *proposed* is Claude's suggestion, waiting for a yes.

---

## Decision log

| # | Decision | Value | Status |
| --- | --- | --- | --- |
| D1 | Backend framework | FastAPI, sync `def` endpoints (as designed) | decided |
| D2 | Database | Postgres + pgvector | decided (design) |
| D3 | DB driver / query layer / migrations | psycopg3 / SQLAlchemy Core / Alembic | decided |
| D4 | Frontend | Vite + React + TypeScript + Tailwind | decided |
| D5 | First Railway deploy | End of Phase 0, hello-world container; every later phase redeploys | decided |
| D6 | Git | Local git only for now, no CI. Identity set **in this repo only**: `Michael Saar <saarmichael@gmail.com>` | decided |
| D7 | Local Postgres | Docker Desktop, compose runs the `pgvector/pgvector` image | decided |
| D8 | Python version and package manager | Python 3.13 pinned via `uv` (`.python-version`), not the machine's 3.14: the AI vendor SDKs and pgvector wheels are safest one minor version behind | decided |
| D9 | Deploy mechanism | Railway CLI `railway up` from the local directory for now. GitHub will be added later (not yet); switching Railway to deploy from it is a one-time dashboard change | decided |
| D10 | Vendor spike before the queue | Phase 1 talks to Gemini and Voyage before any pipeline code exists, because the SDK shapes and limits are the largest unknown that is outside our control | decided |
| D11 | Schema migrations | Migration 0001 in Phase 0 creates the extension and both tables exactly as designed; later phases add migrations only if the design changes | decided |
| D12 | Doc file names | Rename to `docs/system-design.md`, `docs/TESTING.md` (the test plan's own stated target) and move `docs/README.md` to the repo root, so the README's links resolve | decided |
| D13 | Blob deletion | Out of scope. Deleting a collection deletes its DB rows only; blobs stay on the volume (immutable by hash, harmless). Noted in README | decided |
| D14 | Phase gate | Defined in "How we work" below | decided |

Open readiness items (none exist yet, all are Phase 0 steps): Docker Desktop, `uv`, Railway CLI, Gemini API
key, Voyage API key, Railway account. GitHub repo: later, by Michael's call (D9).

---

## How we work

**A phase is done when all of these hold, in order:**

1. `make test` is green on Michael's machine (unit + integration, fake adapters).
2. Michael runs the phase's **Demo** section by hand and sees what it says he will see.
3. Where the phase touches the deployed app, `make deploy` runs and the demo is repeated on the live URL.
4. The work is committed and tagged `phase-N`.
5. A short entry is appended to the **Phase log** at the bottom of this file: date, what deviated from the
   plan, decisions taken in the phase.

Only then does the next phase start. If a phase reveals that the design is wrong, the design doc is changed
first, then the plan, then the code.

**Inside a phase.** Claude lists the steps, then does them one at a time. Each step ends in a small commit
(`phase-N: <what>`) with tests green. Michael reviews diffs at his own pace; a question that needs his call
is asked before the step that depends on it, never answered by assumption. Claude explains anything about
the stack that is new to Michael in the message that introduces it.

**Rules that keep the loop cheap.** `AI_PROVIDER=fake` is the local default; real vendors are used only in
the spike, the live test and seeding. Secrets live in `.env` (git-ignored); `.env.example` lists every
variable with a comment. No step reaches into a later phase's concern.

**Running things** (targets exist from Phase 0; each phase fills them in):

```
make db          # docker compose up -d db
make dev         # API with reload + Vite dev server, fake adapters
make test        # unit + integration (starts db if needed)
make test-live   # adds the live vendor test; needs API keys
make seed        # ingests seed/demo/ through the upload path
make build       # builds the SPA and the container image
make deploy      # railway up
```

---

## Repository layout

```
KMS/
├── PLAN.md                  this file
├── README.md                project README (moved from docs/)
├── docs/
│   ├── system-design.md
│   └── TESTING.md
├── backend/
│   ├── pyproject.toml       uv-managed; ruff + pytest config
│   ├── alembic/             migrations
│   ├── kms/
│   │   ├── config.py        pydantic-settings, every env var in one place
│   │   ├── db.py            engine, sessions, LISTEN connection
│   │   ├── models.py        SQLAlchemy Core tables (assets, search_units)
│   │   ├── blob/            BlobStore interface + LocalBlobStore
│   │   ├── ai/              Vision / Embedder / Reranker interfaces, real + fake adapters, schema
│   │   ├── ingest/          chunker, image preprocessing, summary source, worker
│   │   ├── search/          keyword path, vector path, rrf, grouping, cache
│   │   ├── api/             FastAPI routers: assets, collections, search, health
│   │   └── main.py          app factory, startup (migrations check, worker threads, static SPA)
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── live/
├── frontend/                Vite + React + TS + Tailwind; `npm run build` → backend/kms/static/
├── seed/
│   └── demo/                ~30 files + README.md (file list, licences, query matrix)
├── docker-compose.yml       db (pgvector image) + api (built from Dockerfile)
├── Dockerfile               multi-stage: node build → python runtime; entrypoint runs migrations
├── Makefile
└── .env.example
```

---

## Phases at a glance

| Phase | Risk retired | Ends with |
| --- | --- | --- |
| 0 | Environment, toolchain, platform (can Railway run our container, Postgres, volume, LISTEN/NOTIFY?) | Hello-world app on a live URL, `make test` green |
| 1 | Vendor unknowns (Gemini structured output, Voyage multimodal, limits, cost) | CLI that describes and embeds a file for real; fake adapters for everything after |
| 2 | The queue design: claim, lease, reaper, retries, dedup race | Upload via curl → row goes pending → ready with units written |
| 3 | Hybrid search: two paths, RRF, grouping, collection scope, paging | Search via curl returns ranked assets with snippets |
| 4 | Search quality with real models; seed collection proves the assignment's queries | `make seed` + query matrix passes on the demo collection |
| 5 | The interviewer's path through the UI | Full demo in the browser, locally |
| 6 | Production shape: seed on start, volume, migrations at boot, README | Full manual checklist passes on the live URL |
| 7 (optional) | Reranker, typo correction | Each behind a flag with one test and one matrix row |

Test numbers below refer to the test plan's numbered list. Test 5 is split: its "upload → worker → ready"
half passes in Phase 2, its "absent from search while pending" half needs search and passes in Phase 3.

---

## Phase 0 — Environment and skeleton

**Risk retired.** Nothing in the stack has been run on this machine or on Railway. The costliest surprise
in this project would be discovering late that the Railway Postgres does not deliver notifications, that the
volume does not mount, or that the container will not build. Phase 0 makes all of that boring.

**Build.**

1. Machine: install Docker Desktop, `uv`, Railway CLI (`brew install railway`). `uv python install 3.13`.
2. Accounts: Google AI Studio key, Voyage key, Railway account. Keys go in `backend/.env` (never committed).
3. Git: `git init`, repo-local identity (D6), `.gitignore` (Python, node, `.env`, `/data`), first commit.
4. Docs (D12): rename and move as decided; fix the README links.
5. Repo layout as above. `uv init` in `backend/` with the dependency set: fastapi, uvicorn, sqlalchemy,
   psycopg[binary], alembic, pgvector, pydantic, pydantic-settings, pillow, google-genai, voyageai,
   tenacity; dev: pytest, httpx, ruff.
6. `config.py`: every env var from the design (`DATABASE_URL`, `AI_PROVIDER`, `GEMINI_API_KEY`,
   `VOYAGE_API_KEY`, `WORKER_THREADS`, `SEED_ON_START`, `BLOB_DIR`, chunk and search knobs) with defaults.
7. `docker-compose.yml`: `db` on the `pgvector/pgvector:pg17` image with a named volume; `api` built from
   the Dockerfile, mounting `./data` at `/data`.
8. Alembic + migration 0001 (D11): `CREATE EXTENSION vector`, `assets`, `search_units` with the generated
   `tsv` column, all five indexes from the design. `models.py` mirrors it in SQLAlchemy Core.
9. `GET /api/health`: runs `SELECT 1`, reports the Alembic head, and does a LISTEN/NOTIFY self-test on a
   dedicated connection (send a NOTIFY, receive it, time it). This single endpoint answers the Phase 0
   platform question on Railway.
10. pytest with a DB fixture (truncates both tables between tests) and one smoke test that calls the health
    endpoint through the FastAPI test client.
11. Frontend: `npm create vite@latest` with React + TS, Tailwind, one page that fetches `/api/health` and shows
    it. `npm run build` outputs into the backend static dir; FastAPI serves it at `/`.
12. Dockerfile: stage 1 builds the SPA, stage 2 is `python:3.13-slim` with `uv sync --frozen`; entrypoint runs
    `alembic upgrade head` then uvicorn. `docker compose up` runs the full thing locally.
13. Makefile with the targets above (`seed` and `test-live` are placeholders that print "not yet").
14. Railway: project, Postgres (pgvector template), volume at `/data`, env vars, `railway up`.

**Tests that pass here.** Smoke test (health through the test client). Not in the test plan; it exists so
`make test` is green from day one and the DB fixture is proven.

**Demo.** `make dev` shows the hello page at `localhost:5173` with the health JSON. `make test` is green.
The live Railway URL shows the same page, and `/api/health` on it reports `db: ok`, `migrations: <head>`,
`notify: ok` with a round-trip time.

**Decisions to take.** Railway region. Whether the `api` compose service
is kept (useful to test the container locally) or only `db` (lighter).

---

## Phase 1 — Vendor spike and adapters

**Risk retired.** Whether Gemini Flash honours `response_schema` for our schema through the current SDK,
whether Voyage multimodal-3.5 takes mixed text + image batches the way the design assumes, what the batch
limits and rate limits are, what one image costs. None of this can be learned from our own code, and the
answers shape the adapter interfaces everything else calls.

**Build.**

1. Throwaway scripts in `backend/spike/` (kept in git, not imported): describe one image and one text
   file with Gemini using the two prompts and the shared schema; embed a batch of text + image with Voyage;
   print raw responses, token counts, timings. Record findings in the Phase log.
2. `ai/schema.py`: the Pydantic metadata model and the normalisation layer (lowercase/dedupe tags, clamp
   lengths, truncate, `image_type` null for text).
3. `ai/errors.py`: transient vs permanent classification; backoff with jitter via tenacity, honouring
   `Retry-After`.
4. Interfaces: `Vision.describe(bytes | text, asset_type) -> Metadata`, `Embedder.embed(units) -> vectors`,
   `Reranker.rerank(query, candidates)` (no-op only for now).
5. Real adapters: `GeminiVision` (response_schema → validate → normalise → one repair retry → permanent
   error), `VoyageEmbedder` (batched, `input_type` query/document). Prompts live in `ai/prompts/`.
6. Fake adapters exactly as the test plan describes: `FakeVision` (fixture dict by filename, generic
   fallback, invalid-JSON-once mode) and `FakeEmbedder` (hashed bag-of-words, L2-normalised, image from
   byte hash). Selected by `AI_PROVIDER`.
7. A small CLI: `uv run kms-describe <file>` and `uv run kms-embed <file>...` print the result with either
   provider.

**Tests that pass here.** Unit 3 (schema normalisation), unit 4 (error classification), plus an
adapter-level live check (skipped without keys): real output validates, `visible_text` non-empty for a
screenshot, and the cosine between the embeddings of "black hair" and "brunette" exceeds that of "black
hair" and an unrelated sentence. The test plan's full live test 9 completes in Phase 4 once search exists.

**Demo.** `uv run kms-describe seed-candidate.jpg` prints validated JSON with a title, tags and the
visible text. The same with `AI_PROVIDER=fake` prints the fixture. `kms-embed` prints 1024-dim vectors and
the batch timing.

**Decisions to take.** Exact Gemini model id (current Flash). Output token limit for `visible_text`.
Whether the repair retry re-sends the image (cost) or only the text. Anything the spike contradicts in the
design.

---

## Phase 2 — Upload, storage, queue, worker (fake adapters)

**Risk retired.** The parts of the design that are ours alone and where a bug is silent: the claim query,
the lease and reaper, the attempts cap, the dedup race, transactional commit of results. This is the phase
the test plan calls out as the one that must show its work.

**Build.**

1. `blob/`: `BlobStore` interface, `LocalBlobStore` keyed by sha256 under `BLOB_DIR`.
2. `POST /api/assets` (multipart, collection name, 10 MB cap): sniff type from bytes, sha256, store blob,
   dedup lookup → `200 deduplicated` + alias append, else insert `pending` + `NOTIFY asset_pending` in the
   same transaction → `202`. IntegrityError on the unique index is caught and treated as the dedup path.
3. `GET /api/assets?collection=` (status, filename, aliases, error, metadata), `GET /api/assets/{id}`,
   `GET /api/assets/{id}/file` with `ETag = sha256` and the immutable cache headers,
   `POST /api/assets/{id}/retry`, `GET /api/collections` (names + counts), `DELETE /api/collections/{name}`
   (rows only, D13).
4. `ingest/chunker.py`: recursive paragraph → sentence → word split, configurable target/max/overlap,
   character offsets.
5. `ingest/images.py`: EXIF rotation fix, downscale to ~1024 px, re-encode.
6. `ingest/worker.py`: `claim_one()` (SKIP LOCKED, status/started_at/attempts), `process(asset)` (load,
   preprocess, describe, build units, embed in one batch, commit metadata + units + `ready` in one
   transaction), `run_once()` and `run_forever()`; the outer retry loop (adapter gave up → back to
   `pending` via the lease; `attempts = 3` → `failed` with the message). `reaper()` on startup and every
   minute. Thread pool of `WORKER_THREADS` started from the app's startup hook; a `WORKER_ENABLED` flag so
   tests and the demo can run the API with the worker off.
7. Listener: dedicated autocommit connection, `LISTEN asset_pending`, wait with a 1 s timeout, reconnect
   loop. Wake-up triggers a claim; the timeout is the poll guarantee.
8. Structured logging of every state transition with asset id, attempt and duration.

**Tests that pass here.** Unit 1 (chunker). Integration 5a (upload → worker → `ready`, units written, one
per chunk plus metadata plus image unit). Integration 6 (dedup, alias, concurrent race → one row).
Integration 7 (reaper resets stale `processing`, leaves fresh; third failure → `failed` with error; retry
endpoint resets). Tests drive the worker with `run_once()` and set `started_at` directly in SQL for the
lease case, so nothing depends on timing.

**Demo.** With `AI_PROVIDER=fake` and `make dev`: `curl -F file=@a.txt -F collection=demo /api/assets`
returns `202`; `GET /api/assets` shows `pending` then `ready` within a second; `psql` shows the units.
Upload the same bytes as `b.txt`: `200 deduplicated`, alias present. Manual checklist items 5, 6, 7, 8
run with curl and psql: worker off then on, kill mid-job then watch the reaper, force a permanent error
with the fake adapter's invalid mode, fetch the file and inspect headers. Redeploy; the same curl sequence
works on the live URL (fake adapters there too until Phase 4).

**Decisions to take.** Whether a duplicate arriving while the first is `failed` should re-queue it
(design says it returns the existing asset; suggest: yes, return it, user clicks retry). Maximum text file
size to accept as "text" and how binary sniffing decides.

---

## Phase 3 — Search

**Risk retired.** The hybrid merge is the second design-specific piece: two SQL paths run concurrently,
RRF in Python, group by asset with best unit wins, collection scope, normalised score, paging without
repeats. With the fake embedder every ranking claim is deterministic and testable.

**Build.**

1. `search/keyword.py`: `plainto_tsquery` (or `websearch_to_tsquery`) over `tsv`, `ts_rank`, within
   collection, top `UNITS_PER_PATH`; returns `(unit_id, asset_id, rank)`.
2. `search/vector.py`: `embedding <=> :q` with `hnsw.ef_search` set per transaction, filter on collection
   and `embedding_model`, `hnsw.iterative_scan = relaxed_order`; same return shape.
3. `search/fuse.py`: RRF (k = 60), group by asset (best unit wins, keep the unit's kind and offsets for
   the snippet), normalised score = best RRF / top RRF.
4. `search/cache.py`: LRU keyed on `(embedding_model, normalised query)`.
5. `search/service.py`: embed the query (cached) and run keyword concurrently with it (thread pool of 2),
   fuse, group, no-op rerank, page `(offset, limit)` with cap 100, one final fetch of asset rows by id.
   Snippet: the metadata unit's text for images, the best chunk's text for text files, with
   `start_char`/`end_char`.
6. `GET /api/search?collection=&q=&page=`.

**Tests that pass here.** Unit 2 (RRF + grouping properties). Integration 5b (pending asset absent from
search, present once `ready`). Integration 8 (both-path hit outranks single-path hits; collection scope
holds; a text hit points at the right chunk offsets; page 2 has no repeats).

**Demo.** Seed a few hand-written text files and two images with the fake provider, then
`curl "/api/search?collection=demo&q=..."` shows ranked assets, snippets with offsets, normalised scores
and paging. Redeploy.

**Decisions to take.** `plainto` vs `websearch` tsquery (the latter supports quoted phrases and `-word`).
Text search configuration (`english`). RRF k. Whether the image unit's hit shows the description as its
snippet.

---

## Phase 4 — Real pipeline, seed collection, query matrix

**Risk retired.** Everything so far proves the machinery; this phase proves the product claim, that the
assignment's queries and their paraphrases find the right files with real models. It also fixes the seed
that the interviewer will see.

**Build.**

1. `ingest/summary_source.py`: strategy with `WholeFile` (live), `Head` (live fallback, token budget),
   `MapReduce` (stub raising `NotImplementedError` with the README note).
2. Wire `AI_PROVIDER=real` end to end; run one image and one text file through; read the metadata and
   tune the two prompts until the fields are what search needs.
3. `seed/demo/`: ~30 files built backwards from the query matrix (Unsplash/Pexels photos, own screenshots,
   one diagram, 8–10 hand-written text files that control literal vs implied). `seed/demo/README.md`
   lists each file, source, licence, and the queries it answers.
4. `make seed`: walks `seed/<collection>/` and posts each file through the upload endpoint; idempotent by
   dedup. The same code runs at container start when `SEED_ON_START=true` (used in Phase 6).
5. `make matrix`: a script that runs every row of the query matrix against the API and prints, per row,
   which must-hit files appeared and at what rank, and whether any must-not-hit file is on top. This is the
   manual matrix made repeatable, not a pytest test, because its truth depends on the vendors.

**Tests that pass here.** Live 9 in full (skipped without keys): one image and one text file through real
Gemini + Voyage, schema validates, `visible_text` non-empty for the screenshot, "black hair" finds the
file that only says "brunette".

**Demo.** `make seed` with real keys ingests the demo collection in under a minute; `make matrix` shows
every row passing. Redeploy with real keys in Railway's env; `make matrix` against the live URL passes.

**Decisions to take.** Which photos (licence and credit lines). Token budget default. Whether tags are
also written into the tsvector with a higher weight than description.

---

## Phase 5 — Web UI

**Risk retired.** The interviewer's path: create a collection, upload, watch statuses, search, read
results. Low technical risk, but it is the surface everything is judged through, so it gets its own gate.

**Build.**

1. API client with typed responses (generated from FastAPI's OpenAPI or hand-written).
2. Collection selector with counts, "+ New collection", "Delete collection" with confirm.
3. Upload area (multi-file, drag and drop), list with status badges, 2 s polling while anything is
   `pending`/`processing`, error text and Retry on `failed`.
4. Search box, results as cards: title, filename with the "Found in / identical to" alias note, snippet,
   dimmed tail by normalised score, image thumbnail via the file endpoint, "show more".
5. Asset detail view: metadata fields, visible text, the file.
6. Empty states and the seed collection as the default selection.

**Tests that pass here.** None automated, by the test plan's choice. Manual checklist items 1, 2, 3, 4, 9
run locally.

**Demo.** The full assignment flow in the browser at `localhost:5173` with fake adapters, then once with
real adapters on the demo collection. Redeploy.

**Decisions to take.** Visual direction (minimal, one accent colour is the suggestion). Whether the
detail view is a route or a drawer. Thumbnail sizing.

---

## Phase 6 — Deployment hardening and demo readiness

**Risk retired.** The demo must not fail. Everything that only matters on the live instance: seed on first
start, blobs on the volume across restarts, migrations at boot, logs you can read, README complete.

**Build.**

1. `SEED_ON_START=true` on Railway; confirm reseed is a no-op on restart.
2. Restart the service and confirm blobs survive on the volume and files still serve.
3. Log lines for uploads, claims, commits, failures, searches with timings; confirm they read well in
   Railway's log view.
4. Health endpoint extended with pending/processing/failed counts.
5. README: fill the TODOs (live URL, running locally, env vars, AI tools used), point to
   `docs/TESTING.md` for the checklist.
6. Run the full manual checklist (items 1–9) on the live URL and record it in the Phase log.

**Tests that pass here.** All of 1–9 remain green; nothing new.

**Demo.** The live URL, cold: open it, pick the demo collection, run the matrix queries, create a new
collection, upload, search. Ten minutes, the interviewer's script.

**Decisions to take.** Whether to add a GitHub remote now and switch Railway to deploy from it (revisits
D6/D9). Whether to add CI (the test plan's open item) once a remote exists.

---

## Phase 7 — Optional, in this order

1. **Reranker**: `VoyageReranker` (rerank-2.5) behind `RERANK_ENABLED`, rescoring the first page by
   metadata-unit text. One unit test (order changes, candidate set does not) and one matrix row.
2. **pg_trgm typo correction**: vocabulary table from `ts_stat`, trigram index, per-term correction before
   the keyword query. One migration, one unit test, one matrix row ("blak hair").

Each is its own gate; each can be skipped without touching anything else.

---

## Test-to-phase map

| Test (test plan) | Phase |
| --- | --- |
| Smoke: health through test client (not in plan) | 0 |
| 3 Schema normalisation | 1 |
| 4 Error classification | 1 |
| Adapter-level live check (precursor to 9) | 1 |
| 1 Chunker | 2 |
| 5a Upload → worker → ready | 2 |
| 6 Dedup + race | 2 |
| 7 Lease reaper + attempts cap + retry | 2 |
| 2 RRF merge + group-by-asset | 3 |
| 5b Absent while pending, present when ready | 3 |
| 8 Hybrid search properties | 3 |
| 9 Live end to end | 4 |
| Reranker / pg_trgm unit tests | 7 |

| Manual checklist item | First run | Repeated on live |
| --- | --- | --- |
| 5 Worker off then on, 6 Kill mid-job, 7 Permanent error + retry, 8 File headers | 2 (curl/psql) | 6 |
| 1 New collection, 2 Upload three, 3 Matrix queries, 4 Duplicate alias, 9 Delete collection | 5 (browser) | 6 |
| Query matrix (`make matrix`) | 4 | 4, 6 |

---

## Phase log

_Appended at each gate: date, deviations from the plan, decisions taken._
