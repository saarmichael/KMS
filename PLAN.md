# KMS — Working plan

Sep 24, 2026 · Michael, with Claude Code · phases revised Sep 25, 2026

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
| D9 | Deploy mechanism | Railway CLI `railway up` from the local directory for now. GitHub will be added later (not yet); switching Railway to deploy from it is a one-time dashboard change | decided, revisited by D21 |
| D10 | Vendor spike before the queue | Phase 1 talks to Gemini and Voyage before any pipeline code exists, because the SDK shapes and limits are the largest unknown that is outside our control | decided |
| D11 | Schema migrations | Migration 0001 in Phase 0 creates the extension and both tables exactly as designed; later phases add migrations only if the design changes | decided |
| D12 | Doc file names | Rename to `docs/system-design.md`, `docs/TESTING.md` (the test plan's own stated target) and move `docs/README.md` to the repo root, so the README's links resolve | decided |
| D13 | Blob deletion | Out of scope. Deleting a collection deletes its DB rows only; blobs stay on the volume (immutable by hash, harmless). Noted in README | decided |
| D14 | Phase gate | Defined in "How we work" below | decided |
| D15 | Phase split | The former Phase 2 (upload + queue) is two phases: Phase 2 is everything the API does at upload time, Phase 3 is everything the worker does. Every phase after that is renumbered by one | decided (Sep 25) |
| D16 | Code lives in the phase of its first caller | Summary source with the worker (Phase 3, not the seed phase); the `Reranker` interface with search (Phase 4, not the adapters); structured logging built once in Phase 3, only verified in Phase 7 | decided (Sep 25) |
| D17 | Upload is a service function | `ingest.upload(collection, filename, bytes)` holds the upload logic; the `POST /api/assets` endpoint wraps it and the seeder calls it directly. Seeding at container start runs before the server accepts requests, so it cannot go over HTTP | decided (Sep 25) |
| D18 | Query matrix is data | `seed/demo/matrix.json` holds the matrix rows (query, must hit, must also hit, must not top); `make matrix` reads it; the seed README renders the same rows as prose | decided (Sep 25) |
| D19 | Worker runs standalone too | `uv run kms worker` runs the same thread pool as its own process. The API still starts the pool by default (`WORKER_ENABLED=true`); the command is for the manual checklist (stop the worker, kill it mid-job) and is the scale path the design names (a second container) | decided (Sep 25, Claude's pick) |
| D20 | One CLI entry point | Everything is a subcommand of `kms`: `describe`, `embed`, `worker`, `seed`, `matrix`. No separate console scripts | decided (Sep 25) |
| D21 | GitHub remote and deploy source | The interviewer reads the code on GitHub, and the design doc says Railway deploys from GitHub. Whether to add the remote now and switch Railway to it, or keep `railway up` until Phase 7 | **open — Michael's call, asked now rather than in Phase 7** |
| D22 | Recorded vendor responses | The real adapters are wrapped by a record/replay layer keyed on model, prompt version and input hash, one JSON file per call under `AI_CACHE_DIR`; fakes stay the test default. Michael's addition, see `docs/michael-additions.md` | decided (Sep 25) |
| D23 | Vision model fallback | `VISION_MODELS` is an ordered JSON list of Gemini model ids, older models only for price, default `["gemini-3-flash-preview", "gemini-3.1-flash-lite-preview", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]`. Every call starts at the first. Overloaded (503, or a 429 for that model's quota) → next model at once, no backoff; backoff only after the whole list answered overloaded. Any other error fails at once. The answering model is stored in the new `assets.vision_model` column (migration 0002, D11). No fallback for embeddings: vectors from two models are not comparable. Michael's addition | decided (Sep 25) |
| D24 | Retries on vendor errors | SDK retries off on both clients; `ai/errors.py` uses tenacity. It honours Gemini's `RetryInfo.retryDelay` when present, else backs off ~1 s, 4 s, 16 s with jitter. Chosen after the spike showed neither SDK waits as long as the server asks | decided (Sep 26) |
| D25 | Gemini thinking | Lowest thinking level on every describe call: the spike measured 554 thinking tokens against 140 answer tokens on a short note | decided (Sep 26) |
| D26 | Record the collection early | Michael designs `seed/demo/` during Phases 2–3. The last step of Phase 3 runs the real pipeline over it with recording on (D22): the DB is filled and every vendor response stored in one pass. Recordings are committed to git, so tests and demos on a fresh clone or on Railway replay them. Recording waits for the worker because a replay only hits when the request is byte-identical (preprocessed image, chunks, metadata unit). Michael's addition | decided (Sep 26) |

Open readiness items (none exist yet, all are Phase 0 steps): Docker Desktop, `uv`, Railway CLI, Gemini API
key, Voyage API key, Railway account. GitHub repo: D21.

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
make seed        # uv run kms seed: ingests seed/demo/ through the upload service function
make matrix      # uv run kms matrix: runs seed/demo/matrix.json against an API URL
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
│   ├── pyproject.toml       uv-managed; ruff + pytest config; one console script: kms
│   ├── .env.example         every env var, commented; copy to .env (git-ignored)
│   ├── alembic/             migrations (0001 = full schema)
│   ├── spike/               Phase 1 throwaway scripts, kept in git, never imported
│   ├── src/kms/             src layout (uv's default; keeps tests from importing uninstalled code)
│   │   ├── config.py        pydantic-settings, every env var in one place
│   │   ├── db.py            engine, LISTEN connection, notify self-test
│   │   ├── models.py        SQLAlchemy Core tables (assets, search_units)
│   │   ├── migrations.py    run/inspect Alembic from Python
│   │   ├── cli.py           `uv run kms <command>`: describe, embed, worker, seed, matrix
│   │   ├── blob/            BlobStore interface + LocalBlobStore
│   │   ├── ai/              Vision / Embedder / Reranker interfaces, real + recorded + fake adapters, schema, prompts
│   │   ├── ingest/          upload service function, chunker, images, summary source, worker, listener
│   │   ├── search/          keyword path, vector path, fusion + grouping, service (query-embed cache lives here)
│   │   ├── api/             FastAPI routers: assets, collections, search, health
│   │   ├── static/          built SPA (git-ignored, produced by `npm run build`)
│   │   └── main.py          app factory, startup (worker threads, static SPA)
│   └── tests/
│       ├── conftest.py      kms_test database fixture (migrated once, truncated per test)
│       ├── unit/
│       ├── integration/
│       └── live/
├── frontend/                Vite + React + TS + Tailwind; `npm run build` → backend/src/kms/static/
├── seed/
│   └── demo/                ~30 files + README.md (file list, licences) + matrix.json (query matrix)
├── docker/                  initdb SQL (creates kms_test) + container entrypoint
├── docker-compose.yml       db (pgvector image); api behind `--profile full`
├── Dockerfile               multi-stage: node build → python runtime; entrypoint runs migrations
└── Makefile
```

---

## Phases at a glance

| Phase | Risk retired | Ends with |
| --- | --- | --- |
| 0 | Environment, toolchain, platform (can Railway run our container, Postgres, volume, LISTEN/NOTIFY?) | Hello-world app on a live URL, `make test` green |
| 1 | Vendor unknowns (Gemini structured output, Voyage multimodal, limits, cost) | CLI that describes and embeds a file for real; fake adapters for everything after |
| 2 | Upload path: type sniffing, blob store, dedup race, the asset and collection API | Upload via curl → `pending` row, dedup returns the existing asset, files serve with cache headers |
| 3 | The queue design: claim, lease, reaper, retries, transactional commit | Worker turns `pending` into `ready` with units written; kill it and the reaper recovers |
| 4 | Hybrid search: two paths, RRF, grouping, collection scope, paging | Search via curl returns ranked assets with snippets |
| 5 | Search quality with real models; seed collection proves the assignment's queries | `make seed` + `make matrix` passes on the demo collection |
| 6 | The interviewer's path through the UI | Full demo in the browser, locally |
| 7 | Production shape: seed on start, volume, migrations at boot, README | Full manual checklist passes on the live URL |
| 8 (optional) | Reranker, typo correction | Each behind a flag with one test and one matrix row |

Test numbers below refer to the test plan's numbered list. Test 5 is split: its "upload → worker → ready"
half passes in Phase 3, its "absent from search while pending" half needs search and passes in Phase 4.
Test 6 (dedup) needs no worker and passes in Phase 2.

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
limits and rate limits are, what one image costs, and whether the vendor SDKs retry transient errors on
their own. None of this can be learned from our own code, and the answers shape the adapter interfaces
everything else calls.

**Build.**

1. Throwaway scripts in `backend/spike/` (kept in git, not imported): describe one image and one text
   file with Gemini using the two prompts and the shared schema; embed a batch of text + image with Voyage;
   print raw responses, token counts, timings; provoke a 429 or a bad key and see what the SDK does with
   it. List the Flash models the key can see, and record which error a model under high demand returns
   (D23). Record findings in the Phase log. The spike's answer on retries decides how thin `ai/errors.py` is:
   if the SDKs already back off on transient errors, the module is classification only; if not, tenacity
   wraps the calls. The plan for step 3 is written after this step.
2. `ai/schema.py`: the Pydantic metadata model and the normalisation layer (lowercase/dedupe tags, clamp
   lengths, truncate, `image_type` null for text).
3. `ai/errors.py`: transient vs permanent classification; backoff with jitter (SDK or tenacity, per the
   spike), honouring `Retry-After`.
4. Interfaces: `Vision.describe(bytes | text, asset_type) -> Metadata`, `Embedder.embed(units) -> vectors`.
   The `Reranker` interface arrives with search in Phase 4 (D16).
5. Real adapters: `GeminiVision` (response_schema → validate → normalise → one repair retry → permanent
   error; on an overloaded answer it moves to the next id in `VISION_MODELS` and reports which model
   answered, D23; migration 0002 adds `assets.vision_model`), `VoyageEmbedder` (batched, `input_type` query/document). Prompts live in `ai/prompts/`.
6. Recorded responses (D22): `ai/recorded.py` wraps the real adapters. Each call is keyed by a hash of
   model, prompt version and input; one JSON file per call under `AI_CACHE_DIR`. Hit → the stored
   response; miss → the vendor, then store. An empty setting turns it off. Fakes stay the test default;
   recording makes the live test, the matrix and the demo repeatable and free after the first run.
7. Fake adapters exactly as the test plan describes: `FakeVision` (fixture dict by filename, generic
   fallback, invalid-JSON-once mode) and `FakeEmbedder` (hashed bag-of-words, L2-normalised, image from
   byte hash). Selected by `AI_PROVIDER`.
8. CLI subcommands (D20): `uv run kms describe <file>` and `uv run kms embed <file>...` print the result
   with either provider.

**Tests that pass here.** Unit 3 (schema normalisation), unit 4 (error classification), plus an
adapter-level live check (skipped without keys): real output validates, `visible_text` non-empty for a
screenshot, and the cosine between the embeddings of "black hair" and "brunette" exceeds that of "black
hair" and an unrelated sentence. The test plan's full live test 9 completes in Phase 5 once search exists.

**Demo.** `uv run kms describe seed-candidate.jpg` prints validated JSON with a title, tags and the
visible text. The same with `AI_PROVIDER=fake` prints the fixture. `kms embed` prints 1024-dim vectors and
the batch timing.

**Decisions to take.** Exact Gemini model id (current Flash). Output token limit for `visible_text`.
Whether the repair retry re-sends the image (cost) or only the text. SDK retries or tenacity (after
step 1). Anything the spike contradicts in the design. Where `AI_CACHE_DIR` defaults to (recordings are
committed, D26).

---

## Phase 2 — Upload, storage and the asset API

**Risk retired.** Everything the API does at upload time, where a bug is silent: type sniffing, the
content hash, the dedup lookup and its race against the unique index, the `NOTIFY` in the same
transaction as the insert. This phase also fixes the shape that both the endpoint and the seeder share
(D17), so the seed phase has nothing to reshape.

**Build.**

1. `blob/`: `BlobStore` interface, `LocalBlobStore` keyed by sha256 under `BLOB_DIR`.
2. `ingest/upload.py`: `upload(collection, filename, data) -> UploadResult` (D17): sniff type from bytes,
   sha256, store blob, dedup lookup → existing asset + alias append, else insert `pending` +
   `NOTIFY asset_pending` in the same transaction. IntegrityError on the unique index is caught and
   treated as the dedup path. Pure service function: no FastAPI types, so the seeder can call it.
3. `POST /api/assets` (multipart, collection name, 10 MB cap) wraps `upload()`: `200 deduplicated` or `202`.
4. `GET /api/assets?collection=` (status, filename, aliases, error, metadata), `GET /api/assets/{id}`,
   `GET /api/assets/{id}/file` with `ETag = sha256` and the immutable cache headers,
   `POST /api/assets/{id}/retry` (resets `attempts` and `status`; the worker that consumes it comes in
   Phase 3), `GET /api/collections` (names + counts), `DELETE /api/collections/{name}` (rows only, D13).
5. `ingest/chunker.py`: recursive paragraph → sentence → word split, configurable target/max/overlap,
   character offsets. A pure function with its own unit test; the worker in Phase 3 calls it.

**Tests that pass here.** Unit 1 (chunker). Integration 6 (dedup, alias, concurrent race → one row).
An integration test of the upload service function (row is `pending`, blob is on disk, a `NOTIFY` was
received on a listening connection) stands in for test 5 until the worker exists.

**Demo.** With `make dev`: `curl -F file=@a.txt -F collection=demo /api/assets` returns `202` and
`GET /api/assets` shows the row `pending`. Upload the same bytes as `b.txt`: `200 deduplicated`, alias
present. Manual checklist item 8: fetch the file and inspect headers. Redeploy; the same curl sequence
works on the live URL.

**Decisions to take.** Whether a duplicate arriving while the first is `failed` should re-queue it
(design says it returns the existing asset; suggest: yes, return it, user clicks retry). Maximum text file
size to accept as "text" and how binary sniffing decides.

---

## Phase 3 — Worker and queue (fake adapters)

**Risk retired.** The parts of the design that are ours alone: the claim query, the lease and reaper, the
attempts cap, the transactional commit of results. This is the phase the test plan calls out as the one
that must show its work.

**Build.**

1. `ingest/images.py`: EXIF rotation fix, downscale to ~1024 px, re-encode.
2. `ingest/summary_source.py` (D16): strategy with `WholeFile` (live), `Head` (live fallback, token
   budget), `MapReduce` (stub raising `NotImplementedError` with the README note). Decides which text the
   vision model sees; the chunker decides the content units independently.
3. `ingest/worker.py`: `claim_one()` (SKIP LOCKED, status/started_at/attempts), `process(asset)` (load,
   preprocess, describe via the summary source, build units, embed in one batch, commit metadata + units +
   `ready` in one transaction), `run_once()` and `run_forever()`; the outer retry loop (adapter gave up →
   back to `pending` via the lease; `attempts = 3` → `failed` with the message). `reaper()` on startup and
   every minute.
4. Listener: dedicated autocommit connection, `LISTEN asset_pending`, wait with a 1 s timeout, reconnect
   loop. Wake-up triggers a claim; the timeout is the poll guarantee.
5. Two ways to run the pool (D19): the app's startup hook starts `WORKER_THREADS` threads when
   `WORKER_ENABLED=true` (the default, and how the deployed container runs); `uv run kms worker` runs the
   same pool as its own process for the checklist and as the scale path. Tests and `make dev` with the
   worker off use the flag.
6. Structured logging of every state transition with asset id, attempt and duration: upload, claim,
   commit, failure, reaper reset. Built here once; Phase 7 only checks it reads well in Railway's log view.
7. Record the collection (D26): with `AI_PROVIDER=real` and recording on, upload every file of
   `seed/demo/` (as designed by Michael so far) and let the worker process it. Commit the recordings.
   Until the collection exists, the spike's note and single screenshot are the only real files.

**Tests that pass here.** Integration 5a (upload → worker → `ready`, units written, one per chunk plus
metadata plus image unit). Integration 7 (reaper resets stale `processing`, leaves fresh; third failure →
`failed` with error; retry endpoint resets). Tests drive the worker with `run_once()` and set `started_at`
directly in SQL for the lease case, so nothing depends on timing.

**Demo.** With `AI_PROVIDER=fake`: upload, then `GET /api/assets` shows `pending` then `ready` within a
second; `psql` shows the units. Manual checklist items 5, 6, 7 with curl and psql: API with
`WORKER_ENABLED=false`, upload, start `kms worker` and watch it pick the file up; kill `kms worker`
mid-job and watch the reaper; force a permanent error with the fake adapter's invalid mode, see `failed`
with the message, retry. Redeploy; the live URL processes an upload end to end (fake adapters there too
until Phase 5).

**Decisions to take.** Whether the reaper interval and the lease length are settings or constants
(config already has `lease_minutes`). Whether `kms worker` also runs the reaper (suggest: yes, same code path).

---

## Phase 4 — Search

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
4. `ai/`: the `Reranker` interface and its no-op implementation (D16); `VoyageReranker` stays in Phase 8.
5. `search/service.py`: embed the query through a cached function (`functools.lru_cache`, size
   `QUERY_CACHE_SIZE`, keyed on model + normalised query; no separate cache module) and run keyword
   concurrently with it (thread pool of 2), fuse, group, no-op rerank, page `(offset, limit)` with cap 100,
   one final fetch of asset rows by id. Snippet: the metadata unit's text for images, the best chunk's
   text for text files, with `start_char`/`end_char`.
6. `GET /api/search?collection=&q=&page=`.

**Tests that pass here.** Unit 2 (RRF + grouping properties). Integration 5b (pending asset absent from
search, present once `ready`). Integration 8 (both-path hit outranks single-path hits; collection scope
holds; a text hit points at the right chunk offsets; page 2 has no repeats).

**Demo.** Seed a few hand-written text files and two images with the fake provider, then
`curl "/api/search?collection=demo&q=..."` shows ranked assets, snippets with offsets, normalised scores
and paging. Redeploy.

**Decisions to take.** `plainto` vs `websearch` tsquery (suggest `websearch`: quoted phrases and `-word`).
Text search configuration (suggest `english`). RRF k (suggest 60). Whether the image unit's hit shows the
description as its snippet.

---

## Phase 5 — Real pipeline, seed collection, query matrix

**Risk retired.** Everything so far proves the machinery; this phase proves the product claim, that the
assignment's queries and their paraphrases find the right files with real models. It also fixes the seed
that the interviewer will see.

**Build.**

1. Wire `AI_PROVIDER=real` end to end; run one image and one text file through; read the metadata and
   tune the two prompts until the fields are what search needs.
2. `seed/demo/` finalised (designed by Michael during Phases 2–3, recorded in Phase 3, D26): ~30 files built
   backwards from the query matrix (Unsplash/Pexels photos, own screenshots,
   one diagram, 8–10 hand-written text files that control literal vs implied). `seed/demo/README.md`
   lists each file, source, licence, and the queries it answers.
3. `seed/demo/matrix.json` (D18): one object per matrix row with `query`, `must_hit`, `must_also_hit`
   and `must_not_top` file lists. The README's table is written from it, so the two cannot drift.
4. `uv run kms seed [collection]` behind `make seed`: walks `seed/<collection>/` and calls the upload
   service function (D17) for each file; idempotent by dedup. The same function runs from the app's
   startup hook when `SEED_ON_START=true` (used in Phase 7).
5. `uv run kms matrix --url <api>` behind `make matrix`: runs every row of `matrix.json` against the API
   and prints, per row, which must-hit files appeared and at what rank, and whether any must-not-top file
   is on top. This is the manual matrix made repeatable, not a pytest test, because its truth depends on
   the vendors.

**Tests that pass here.** Live 9 in full (skipped without keys): one image and one text file through real
Gemini + Voyage, schema validates, `visible_text` non-empty for the screenshot, "black hair" finds the
file that only says "brunette".

**Demo.** `make seed` with real keys ingests the demo collection in under a minute; `make matrix` shows
every row passing. Redeploy with real keys in Railway's env; `make matrix --url` against the live URL
passes.

**Decisions to take.** Which photos (licence and credit lines). Token budget default. Whether tags are
also written into the tsvector with a higher weight than description. If yes, the generated column
changes and that is migration 0002 (D11 allows it).

---

## Phase 6 — Web UI

**Risk retired.** The interviewer's path: create a collection, upload, watch statuses, search, read
results. Low technical risk, but it is the surface everything is judged through, so it gets its own gate.

**Build.**

1. Hand-written API client with typed responses, one function per endpoint (eight endpoints; a generator
   would be more to explain than it saves).
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

## Phase 7 — Deployment hardening and demo readiness

**Risk retired.** The demo must not fail. Everything that only matters on the live instance: seed on first
start, blobs on the volume across restarts, migrations at boot, logs you can read, README complete.

**Build.**

1. `SEED_ON_START=true` on Railway; confirm reseed is a no-op on restart.
2. Restart the service and confirm blobs survive on the volume and files still serve.
3. Read the Phase 3 log lines in Railway's log view for an upload, a search and a failure; fix wording
   only if something does not read well.
4. Health endpoint extended with pending/processing/failed counts.
5. README: fill the TODOs (live URL, running locally, env vars, AI tools used), point to
   `docs/TESTING.md` for the checklist, and state the deploy source that D21 settled on.
6. Run the full manual checklist (items 1–9) on the live URL and record it in the Phase log.

**Tests that pass here.** All of 1–9 remain green; nothing new.

**Demo.** The live URL, cold: open it, pick the demo collection, run the matrix queries, create a new
collection, upload, search. Ten minutes, the interviewer's script.

**Decisions to take.** Whether to add CI (the test plan's open item) if D21 gave us a remote.

---

## Phase 8 — Optional, in this order

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
| 6 Dedup + race | 2 |
| Upload service function → pending + NOTIFY (not in plan) | 2 |
| 5a Upload → worker → ready | 3 |
| 7 Lease reaper + attempts cap + retry | 3 |
| 2 RRF merge + group-by-asset | 4 |
| 5b Absent while pending, present when ready | 4 |
| 8 Hybrid search properties | 4 |
| 9 Live end to end | 5 |
| Reranker / pg_trgm unit tests | 8 |

| Manual checklist item | First run | Repeated on live |
| --- | --- | --- |
| 8 File headers | 2 (curl) | 7 |
| 5 Worker off then on, 6 Kill mid-job, 7 Permanent error + retry | 3 (curl/psql, `kms worker`) | 7 |
| 1 New collection, 2 Upload three, 3 Matrix queries, 4 Duplicate alias, 9 Delete collection | 6 (browser) | 7 |
| Query matrix (`make matrix`) | 5 | 5, 7 |

---

## Phase log

_Appended at each gate: date, deviations from the plan, decisions taken._

### Phase 0 — Sep 24, 2026

- **Built.** Toolchain (uv, Python 3.13, Docker Desktop, Railway CLI), git with repo-local identity, docs renamed
  (D12), backend skeleton with settings, Core tables, Alembic migration 0001 (full schema), health endpoint with
  LISTEN/NOTIFY self-test, test fixtures on `kms_test`, Vite + React + TS + Tailwind hello page, compose,
  Dockerfile with migrations at boot, Makefile. Railway project `kms`: Postgres, `api` service with a volume at
  `/data`, variables, public domain. Deployed with `railway up`.
- **Live URL:** https://api-production-6776.up.railway.app — `/api/health` reports db ok, migrations 0001,
  notify ok (~15 ms). Railway's Postgres ships pgvector; the platform risk is retired.
- **Deviations.** `src/kms/` layout instead of `backend/kms/` (uv default, updated in the layout tree). The
  Dockerfile overrides Vite's output directory, since Vite writes into the backend for local dev. Settings
  accept plain `postgresql://` URLs and add the psycopg driver, because that is what Railway hands out.
- **Decisions taken.** The `api` compose service is kept behind `--profile full` for a local container check.
  Railway region: default (not chosen explicitly). No GitHub remote yet (D9).
- **Gate.** `make test` green (2 tests). Container verified locally and on Railway. Demo run by Michael, tagged
  `phase-0` on Sep 24, 2026.

### Plan revision — Sep 25, 2026

Phases 1–7 reviewed against the design and the Phase 0 skeleton before Phase 1 started. Decisions D15–D20
taken, D21 opened. The former Phase 2 became Phases 2 and 3; everything after is renumbered by one. No code
changed except the Makefile comments that named the seed phase.

### Phase 1 spike findings — Sep 26, 2026

Scripts in `backend/spike/`; raw responses in `backend/spike/out/` (git-ignored).

- **Model ids.** `gemini-3-flash` does not exist. The 2.5 Flash models are listed but refused to new keys
  (404 "no longer available to new users"). D23 list chosen by Michael: older models for price,
  `gemini-3-flash-preview`, `gemini-3.1-flash-lite-preview`, `gemini-3.1-flash-lite`, `gemini-3.5-flash-lite`.
  `voyage-multimodal-3.5` works, 1024 dims, vectors come back L2-normalised (norm 0.999).
- **Structured output.** `response_schema` with a Pydantic class is honoured: both outputs parsed into the draft
  model with no repair. Screenshot OCR read the game HUD and "SYNKA CO."; `image_type` screenshot, correct.
- **Tags.** The text prompt returns multi-word tags ("travel notes") and adds outside knowledge ("jerónimos
  monastery" for "the monastery"). Normalisation question for part 2.
- **Cost per call.** Image at 1024x576: 1,266 prompt tokens, 230 output, 12 s. Text note: 311 prompt, 140 output,
  and 554 hidden thinking tokens billed as output (Gemini 3 thinks by default). Voyage: the same image is 589,824
  pixels, counted as ~1,050 tokens; a batch of three texts plus the image took 3.5 s, a one-word query 0.3 s.
- **Mixed batch.** Voyage takes one `multimodal_embed` call mixing text inputs and a PIL image input.
- **Synonyms.** cosine("black hair", brunette sentence) 0.276 > note 0.228 > screenshot 0.167 > unrelated 0.134.
  The design's claim holds on raw vectors.
- **Overload.** Gemini answers `503 UNAVAILABLE` "This model is currently experiencing high demand"; four models
  returned it during the spike, once mid-run. This is the D23 trigger.
- **Rate limits (free tiers).** Gemini: 20 requests per day per model (`GenerateRequestsPerDayPerProjectPerModel-
  FreeTier`), 429 with a `RetryInfo.retryDelay` in the body and no `Retry-After` header. Voyage without a payment
  method: 3 requests per minute, 10K tokens per minute, 429 with no retry header. Neither is enough for seeding.
- **Errors.** Bad key: Gemini 400 `API_KEY_INVALID` (`ClientError`), Voyage 401 `AuthenticationError`. Both are
  permanent; note Gemini's is a 400, not a 401.
- **SDK retries.** Both SDKs retry when asked (Gemini `HttpRetryOptions`, off by default; Voyage `max_retries`,
  0 by default). Neither honours the server's wait: Gemini gave up after ~8.6 s against a 33 s `retryDelay`;
  Voyage after ~4.5 s against a one-minute window.
- **Billing (Sep 26).** Voyage with a payment method: six back-to-back calls all succeed, the 3-per-minute limit
  is gone. Gemini with billing but no prepaid credit answers `402` "Your prepayment credits are depleted" on
  every model. A 402 is permanent and applies to the whole project, so D23 must not fall over on it.
