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
| D16 | Code lives in the phase of its first caller | Summary source with the worker (Phase 3, not the seed phase); the `Reranker` interface with search (Phase 5, not the adapters); structured logging built once in Phase 3, only verified in Phase 8 | decided (Sep 25) |
| D17 | Upload is a service function | `ingest.upload(collection, filename, bytes)` holds the upload logic; the `POST /api/assets` endpoint wraps it and the seeder calls it directly. Seeding at container start runs before the server accepts requests, so it cannot go over HTTP | decided (Sep 25) |
| D18 | Query matrix is data | `seed/demo/matrix.json` holds the matrix rows (query, must hit, must also hit, must not top); `make matrix` reads it; the seed README renders the same rows as prose | decided (Sep 25) |
| D19 | Worker runs standalone too | `uv run kms worker` runs the same thread pool as its own process. The API still starts the pool by default (`WORKER_ENABLED=true`); the command is for the manual checklist (stop the worker, kill it mid-job) and is the scale path the design names (a second container) | decided (Sep 25, Claude's pick) |
| D20 | One CLI entry point | Everything is a subcommand of `kms`: `describe`, `embed`, `worker`, `seed`, `matrix`. No separate console scripts | decided (Sep 25) |
| D21 | GitHub remote and deploy source | The interviewer reads the code on GitHub, and the design doc says Railway deploys from GitHub. Whether to add the remote now and switch Railway to it, or keep `railway up` until Phase 8 | **open — Michael's call, asked now rather than in Phase 8** |
| D22 | Recorded vendor responses | The real adapters are wrapped by a record/replay layer keyed on model, prompt version and input hash, one JSON file per call under `AI_CACHE_DIR`; fakes stay the test default. Michael's addition, see `docs/michael-additions.md` | decided (Sep 25) |
| D23 | Vision model fallback | `VISION_MODELS` is an ordered JSON list of Gemini model ids, older models only for price, default `["gemini-3-flash-preview", "gemini-3.1-flash-lite-preview", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]`. Every call starts at the first. Overloaded (503, or a 429 for that model's quota) → next model at once, no backoff; backoff only after the whole list answered overloaded. Any other error fails at once. The answering model is stored in the new `assets.vision_model` column (migration 0002, D11). No fallback for embeddings: vectors from two models are not comparable. Michael's addition | decided (Sep 25) |
| D24 | Retries on vendor errors | SDK retries off on both clients; `ai/errors.py` uses tenacity. It honours Gemini's `RetryInfo.retryDelay` when present, else backs off ~1 s, 4 s, 16 s with jitter. Chosen after the spike showed neither SDK waits as long as the server asks | decided (Sep 26) |
| D25 | Gemini thinking | Lowest thinking level on every describe call: the spike measured 554 thinking tokens against 140 answer tokens on a short note | decided (Sep 26) |
| D26 | Record the collection early | Michael designs `seed/demo/` during Phases 2–4. The last step of Phase 4 runs the real pipeline over it with recording on (D22): the DB is filled and every vendor response stored in one pass. Recordings are committed to git, so tests and demos on a fresh clone or on Railway replay them. Recording waits for the worker because a replay only hits when the request is byte-identical (preprocessed image, chunks, metadata unit). Michael's addition | decided (Sep 26; moved from Phase 3 to 4 by D27) |
| D27 | AI adapters get their own phase, after the worker | Phase 1 is the vendor spike only. The schema, the `Vision`/`Embedder` interfaces and the fakes move to Phase 3, where the worker is their first caller; the plumbing (upload, DB, worker) is built and demoed on hand-written fixture metadata. The real adapters, `ai/errors.py`, the record/replay layer, migration 0002, `kms describe`/`kms embed` and the D26 recording become Phase 4, built against a running worker. The former Phases 4–8 become 5–9. Michael's addition | decided (Sep 26) |
| D28 | Two tracks in parallel | A backend track (Phases 2–6, 8, 9) and a frontend track (Phase 7) run in two Claude sessions at once. Both build against the API contract (D29); the frontend uses mock responses until the backend's Phase 5 passes. Each track has its own gates. Michael's addition | decided (Sep 26) |
| D29 | API contract first | `docs/api-contract.md` fixes every endpoint's request and exact response JSON before Phase 2 or Phase 7 starts. Written in its own session and approved by Michael; a change to it needs his approval and lands on `main` | decided (Sep 26) |
| D30 | One worktree and branch per track | The backend session works in this checkout on `main`; the frontend session in a git worktree `../KMS-frontend` on branch `frontend`. Each session edits only its own files (see "Tracks" under How we work) | decided (Sep 26) |
| D31 | How a collection comes into existence | Implicitly: no collections table, no create endpoint; a collection exists while it has an asset. Name rule `^[a-z0-9_-]{1,64}$`, else `422` | decided (Sep 26) |
| D32 | Search paging | `page` (from 1) + `has_more`, page size 20, no total count; a page past the end is empty, not an error | decided (Sep 26) |
| D33 | Error body | Always `{"detail": string}`; one exception handler flattens FastAPI's 422 list into a string | decided (Sep 26) |
| D34 | Response models and TS types | Both hand-written from `docs/api-contract.md`; nothing generated | decided (Sep 26) |
| D35 | Duplicate of a `failed` asset | Returned as it is, still `failed`; the user clicks Retry. Upload never changes an existing asset's state | decided (Sep 26) |
| D36 | Accepted upload types | Images: JPEG, PNG, WebP, detected by Pillow reading the header. Text: strict UTF-8 (BOM allowed), no NUL bytes, no limit beyond the 10 MB cap. Empty file and anything else → `415` | decided (Sep 26) |
| D37 | Text files served with a charset | `Content-Type: text/plain; charset=utf-8`; contract §6.4 amended | decided (Sep 26) |
| D38 | `NOTIFY` on retry | Retry sends `NOTIFY asset_pending` in its transaction, like upload | decided (Sep 26) |
| D39 | Collection name validation | At the API only (query, form and path patterns); `upload()` trusts its caller | decided (Sep 26) |
| D40 | Dedup mechanism | `INSERT … ON CONFLICT (collection, sha256) DO NOTHING RETURNING *`; no row back = duplicate. Replaces lookup + catch `IntegrityError`; design doc amended | decided (Sep 26) |
| D41 | Chunker out of Phase 2 | Built at the end of Phase 3, its last step; its size units (chars or tokens) are decided in that step's plan. Michael's addition | decided (Sep 26; placed Sep 27) |

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

Only then does the next phase of the same track start (see Tracks below). If a phase reveals that the design
is wrong, the design doc is changed first, then the plan, then the code.

**Inside a phase.** Claude lists the steps, then does them one at a time. Each step ends with tests green
and the changes left unstaged; Michael reviews the diff and commits it himself (`phase-N: <what>`), see
"Stages and commits" in `CLAUDE.md`. A question that needs his call
is asked before the step that depends on it, never answered by assumption. Claude explains anything about
the stack that is new to Michael in the message that introduces it.

**Rules that keep the loop cheap.** `AI_PROVIDER=fake` is the local default; real vendors are used only in
the spike, the live test and seeding. Secrets live in `.env` (git-ignored); `.env.example` lists every
variable with a comment. No step reaches into a later phase's concern.

**Tracks (D28–D30).** Two Claude sessions work at once, one per track.

| | Backend track | Frontend track |
| --- | --- | --- |
| Phases | 2, 3, 4, 5, 6, 8, 9 | 7 |
| Where | this checkout, branch `main` | worktree `../KMS-frontend`, branch `frontend` |
| Edits | `backend/`, `docker/`, `seed/`, root files, `docs/`, all of `PLAN.md` except the Phase 7 section | `frontend/`, the Phase 7 section of `PLAN.md` |
| Decision numbers | D-numbers, in the decision log | F-numbers (F1, F2, …), in the Phase 7 section |
| Starts | after the API contract is approved | after the API contract is approved |

- Both tracks build against `docs/api-contract.md`. Neither changes it on its own: a change is a plan
  approved by Michael, committed on `main`, then merged into `frontend`.
- Both sessions append to `docs/michael-additions.md` and `docs/claude-recommendations.md`. Appends from the
  two branches can conflict at merge; the resolution is always to keep both entries.
- The frontend branch merges `main` whenever the contract changes, and merges into `main` at its gates.
- Setup, once the contract is committed: `git worktree add ../KMS-frontend -b frontend` from this checkout,
  then `npm install` in `../KMS-frontend/frontend`, then a Claude session opened in `../KMS-frontend`.
  `.env` files are git-ignored and do not follow into a worktree; the frontend needs none while it uses mocks.

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
│   ├── TESTING.md
│   ├── api-contract.md      every endpoint's request and response JSON (D29), shared by both tracks
│   ├── michael-additions.md
│   └── claude-recommendations.md
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
| 1 | Vendor unknowns (Gemini structured output, Voyage multimodal, limits, cost, SDK retries) | Findings in the Phase log; model list, retries and thinking decided (D23–D25) |
| contract | Two tracks building to different guesses of the API | `docs/api-contract.md` approved; frontend worktree set up (D28–D30) |
| 2 | Upload path: type sniffing, blob store, dedup race, the asset and collection API | Upload via curl → `pending` row, dedup returns the existing asset, files serve with cache headers |
| 3 | The queue design: claim, lease, reaper, retries, transactional commit; the adapter interfaces and fakes | Worker turns `pending` into `ready` with fixture metadata and units written; kill it and the reaper recovers |
| 4 | Our code around the vendors: validation and repair, model fallback, backoff, record/replay | An uploaded file gets real metadata through the worker; the demo collection is recorded and committed |
| 5 | Hybrid search: two paths, RRF, grouping, collection scope, paging | Search via curl returns ranked assets with snippets |
| 6 | Search quality with real models; seed collection proves the assignment's queries | `make seed` + `make matrix` passes on the demo collection |
| 7 (frontend track) | The interviewer's path through the UI | Full demo in the browser, locally; built on mocks from the contract on, switched to the real API after Phase 5 |
| 8 | Production shape: seed on start, volume, migrations at boot, README | Full manual checklist passes on the live URL |
| 9 (optional) | Reranker, typo correction | Each behind a flag with one test and one matrix row |

Test numbers below refer to the test plan's numbered list. Test 5 is split: its "upload → worker → ready"
half passes in Phase 3, its "absent from search while pending" half needs search and passes in Phase 5.
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

## Phase 1 — Vendor spike

**Risk retired.** Whether Gemini Flash honours `response_schema` for our schema through the current SDK,
whether Voyage multimodal-3.5 takes mixed text + image batches the way the design assumes, what the batch
limits and rate limits are, what one image costs, and whether the vendor SDKs retry transient errors on
their own. None of this can be learned from our own code, and the answers shape the adapters built in
Phase 4 (D27).

**Build.**

1. Throwaway scripts in `backend/spike/` (kept in git, not imported): describe one image and one text
   file with Gemini using the two prompts and the shared schema; embed a batch of text + image with Voyage;
   print raw responses, token counts, timings; provoke a 429 or a bad key and see what the SDK does with
   it. List the Flash models the key can see, and record which error a model under high demand returns
   (D23). Record findings in the Phase log. The spike's answer on retries decides how thin `ai/errors.py` is:
   if the SDKs already back off on transient errors, the module is classification only; if not, tenacity
   wraps the calls.

**Tests that pass here.** None new: nothing in `src/` changes, `make test` stays green.

**Demo.** Michael runs the three spike scripts (commands in `backend/spike/README.md`) and reads the
findings in the Phase log against their output.

**Decisions to take.** Exact Gemini model id (D23). SDK retries or tenacity (D24). Anything the spike
contradicts in the design.

---

## API contract — before Phases 2 and 7 (D29)

**Risk retired.** Two sessions building the two sides at once (D28) would each guess field names, status
codes and error shapes differently. Writing the contract first is the only coupling between the tracks.

**Build.** Done in its own session. The plan for it is written and approved like any part plan.

1. `docs/api-contract.md`: one entry per endpoint. Method and path; query parameters; request body (the
   multipart fields for upload); every status code it can return; the exact response JSON with field
   names, types and nullability; the error body shape. The endpoints already named in this plan and the
   design: `POST /api/assets`, `GET /api/assets?collection=`, `GET /api/assets/{id}`,
   `GET /api/assets/{id}/file`, `POST /api/assets/{id}/retry`, `GET /api/collections`,
   `DELETE /api/collections/{name}`, `GET /api/search`, `GET /api/health`.
2. Record the contract's decisions in the decision log and in Michael's two lists as usual.
3. Once approved and committed: set up the frontend worktree (Tracks, under How we work).

**Questions the contract session must put to Michael** (not answered here): how a collection comes into
existence, since the UI has "+ New collection" but no create endpoint is listed; the paging shape of
search (page number or offset, total count or not); the error body format; whether FastAPI response models
and the hand-written TypeScript types are both written from the contract, or one is generated.

**Tests that pass here.** None; no code changes.

**Demo.** Michael reads `docs/api-contract.md` and can say, for each screen of Phase 7, which call feeds it.

---

## Phase 2 — Upload, storage and the asset API

**Risk retired.** Everything the API does at upload time, where a bug is silent: type sniffing, the
content hash, the dedup lookup and its race against the unique index, the `NOTIFY` in the same
transaction as the insert. This phase also fixes the shape that both the endpoint and the seeder share
(D17), so the seed phase has nothing to reshape.

**Build.**

1. `blob/`: `BlobStore` interface, `LocalBlobStore` keyed by sha256 under `BLOB_DIR`.
2. `ingest/upload.py`: `upload(collection, filename, data) -> UploadResult` (D17): sniff type from bytes,
   sha256, store blob, insert `pending` with `ON CONFLICT DO NOTHING` (D40) + `NOTIFY asset_pending` in
   the same transaction; no row back → existing asset + alias append. Pure service function: no FastAPI
   types, so the seeder can call it.
3. `POST /api/assets` (multipart, collection name, 10 MB cap) wraps `upload()`: `200 deduplicated` or `202`.
4. `GET /api/assets?collection=` (status, filename, aliases, error, metadata), `GET /api/assets/{id}`,
   `GET /api/assets/{id}/file` with `ETag = sha256` and the immutable cache headers,
   `POST /api/assets/{id}/retry` (resets `attempts` and `status`; the worker that consumes it comes in
   Phase 3), `GET /api/collections` (names + counts), `DELETE /api/collections/{name}` (rows only, D13).
5. ~~`ingest/chunker.py`~~: moved to the end of Phase 3 by D41.

**Tests that pass here.** Integration 6 (dedup, alias, concurrent race → one row). (Unit 1, the chunker, moved out by D41.)
An integration test of the upload service function (row is `pending`, blob is on disk, a `NOTIFY` was
received on a listening connection) stands in for test 5 until the worker exists.

**Demo.** With `make dev`: `curl -F file=@a.txt -F collection=demo /api/assets` returns `202` and
`GET /api/assets` shows the row `pending`. Upload the same bytes as `b.txt`: `200 deduplicated`, alias
present. Manual checklist item 8: fetch the file and inspect headers. Redeploy; the same curl sequence
works on the live URL.

**Decisions taken.** D35–D41 (Sep 26), from the phase plan.

---

## Phase 3 — Worker and queue (fake adapters)

**Risk retired.** The parts of the design that are ours alone: the claim query, the lease and reaper, the
attempts cap, the transactional commit of results. This is the phase the test plan calls out as the one
that must show its work. The adapter interfaces are designed here, against the worker that calls them
(D27); the real adapters behind them come in Phase 4.

**Build.**

1. `ai/schema.py`: the Pydantic metadata model and the normalisation layer (lowercase/dedupe tags, clamp
   lengths, truncate, `image_type` null for text).
2. Interfaces: `Vision.describe(bytes | text, asset_type) -> Metadata`, `Embedder.embed(units) -> vectors`.
   The `Reranker` interface arrives with search in Phase 5 (D16).
3. Fake adapters exactly as the test plan describes: `FakeVision` (fixture dict by filename, generic
   fallback, invalid-JSON-once mode) and `FakeEmbedder` (hashed bag-of-words, L2-normalised, image from
   byte hash). Selected by `AI_PROVIDER`. The fixture dict holds hand-written metadata for the files the
   demo uploads, so the whole pipeline runs on static data until Phase 4.
4. `ingest/images.py`: EXIF rotation fix, downscale to ~1024 px, re-encode.
5. `ingest/summary_source.py` (D16): strategy with `WholeFile` (live), `Head` (live fallback, token
   budget), `MapReduce` (stub raising `NotImplementedError` with the README note). Decides which text the
   vision model sees; the chunker decides the content units independently.
6. `ingest/worker.py`: `claim_one()` (SKIP LOCKED, status/started_at/attempts), `process(asset)` (load,
   preprocess, describe via the summary source, build units, embed in one batch, commit metadata + units +
   `ready` in one transaction), `run_once()` and `run_forever()`; the outer retry loop (adapter gave up →
   back to `pending` via the lease; `attempts = 3` → `failed` with the message). `reaper()` on startup and
   every minute.
7. Listener: dedicated autocommit connection, `LISTEN asset_pending`, wait with a 1 s timeout, reconnect
   loop. Wake-up triggers a claim; the timeout is the poll guarantee.
8. Two ways to run the pool (D19): the app's startup hook starts `WORKER_THREADS` threads when
   `WORKER_ENABLED=true` (the default, and how the deployed container runs); `uv run kms worker` runs the
   same pool as its own process for the checklist and as the scale path. Tests and `make dev` with the
   worker off use the flag.
9. Structured logging of every state transition with asset id, attempt and duration: upload, claim,
   commit, failure, reaper reset. Built here once; Phase 8 only checks it reads well in Railway's log view.
10. `ingest/chunker.py` (D41), the last step: recursive paragraph → sentence → word split, configurable
    target/max/overlap, character offsets; unit test 1. Size units (chars or tokens) decided in its plan.

**Tests that pass here.** Unit 3 (schema normalisation). Integration 5a (upload → worker → `ready`, units written, one per chunk plus
metadata plus image unit). Integration 7 (reaper resets stale `processing`, leaves fresh; third failure →
`failed` with error; retry endpoint resets). Tests drive the worker with `run_once()` and set `started_at`
directly in SQL for the lease case, so nothing depends on timing.

**Demo.** With `AI_PROVIDER=fake`: upload, then `GET /api/assets` shows `pending` then `ready` within a
second; `psql` shows the units. Manual checklist items 5, 6, 7 with curl and psql: API with
`WORKER_ENABLED=false`, upload, start `kms worker` and watch it pick the file up; kill `kms worker`
mid-job and watch the reaper; force a permanent error with the fake adapter's invalid mode, see `failed`
with the message, retry. Redeploy; the live URL processes an upload end to end (fake adapters there too
until Phase 6).

**Decisions to take.** Whether the reaper interval and the lease length are settings or constants
(config already has `lease_minutes`). Whether `kms worker` also runs the reaper (suggest: yes, same code path).
How tags are normalised: the spike saw multi-word tags ("travel notes") and outside knowledge added by the
model. Whether `describe` already returns the answering model's id here (the fakes would name themselves),
so the interface does not change when D23 arrives in Phase 4.

---

## Phase 4 — AI adapters

**Risk retired.** Our own code around the vendors, which the spike could not test: validation and the
repair retry, the move to the next model on an overloaded answer, backoff that waits as long as the server
asks, and whether record/replay really hits on a second run. Built after the worker (D27), so every piece
is exercised by its real caller: upload a file and read Gemini's metadata back from the asset API.

**Build.**

1. `ai/errors.py` (D24): transient vs permanent classification; tenacity backoff with jitter, honouring
   Gemini's `RetryInfo.retryDelay`. SDK retries off on both clients.
2. Real adapters behind the Phase 3 interfaces: `GeminiVision` (response_schema → validate → normalise →
   one repair retry → permanent error; lowest thinking level, D25; on an overloaded answer it moves to the
   next id in `VISION_MODELS` and reports which model answered, D23), `VoyageEmbedder` (batched,
   `input_type` query/document). Prompts live in `ai/prompts/`. `VISION_MODELS` replaces the single
   `VISION_MODEL` setting.
3. Migration 0002 adds `assets.vision_model`; the worker writes the answering model with the metadata.
4. Recorded responses (D22): `ai/recorded.py` wraps the real adapters. Each call is keyed by a hash of
   model, prompt version and input; one JSON file per call under `AI_CACHE_DIR`. Hit → the stored
   response; miss → the vendor, then store. An empty setting turns it off. Fakes stay the test default;
   recording makes the live test, the matrix and the demo repeatable and free after the first run.
5. CLI subcommands (D20): `uv run kms describe <file>` and `uv run kms embed <file>...` print the result
   with either provider. A debugging tool next to the worker, not the adapters' only caller.
6. Record the collection (D26): with `AI_PROVIDER=real` and recording on, upload every file of
   `seed/demo/` (as designed by Michael so far) and let the worker process it. Commit the recordings.
   Until the collection exists, the spike's note and single screenshot are the only real files.

**Tests that pass here.** Unit 4 (error classification), plus an adapter-level live check (skipped without
keys): real output validates, `visible_text` non-empty for a screenshot, and the cosine between the
embeddings of "black hair" and "brunette" exceeds that of "black hair" and an unrelated sentence. The test
plan's full live test 9 completes in Phase 6 once search exists.

**Demo.** With `AI_PROVIDER=real` and recording on: upload the spike's screenshot with curl, and
`GET /api/assets` shows it `ready` with a real title, tags, the visible text and the model that answered.
Empty the tables and upload it again: the same metadata comes back from the recordings, with no vendor
call in the log. `uv run kms describe <file>` prints validated JSON; with `AI_PROVIDER=fake` it prints the
fixture. `kms embed` prints 1024-dim vectors and the batch timing. Redeploy so migration 0002 runs at
boot; the live URL stays on fake adapters until Phase 6.

**Decisions to take.** Output token limit for `visible_text`. Whether the repair retry re-sends the image
(cost) or only the text. Where `AI_CACHE_DIR` defaults to (recordings are committed, D26).

---

## Phase 5 — Search

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
4. `ai/`: the `Reranker` interface and its no-op implementation (D16); `VoyageReranker` stays in Phase 9.
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
Text search configuration (suggest `english`). RRF k (suggest 60). (The image unit's snippet is the
description, fixed by the API contract.)

---

## Phase 6 — Real pipeline, seed collection, query matrix

**Risk retired.** Everything so far proves the machinery; this phase proves the product claim, that the
assignment's queries and their paraphrases find the right files with real models. It also fixes the seed
that the interviewer will see.

**Build.**

1. Wire `AI_PROVIDER=real` end to end; run one image and one text file through; read the metadata and
   tune the two prompts until the fields are what search needs.
2. `seed/demo/` finalised (designed by Michael during Phases 2–4, recorded in Phase 4, D26): ~30 files built
   backwards from the query matrix (Unsplash/Pexels photos, own screenshots,
   one diagram, 8–10 hand-written text files that control literal vs implied). `seed/demo/README.md`
   lists each file, source, licence, and the queries it answers.
3. `seed/demo/matrix.json` (D18): one object per matrix row with `query`, `must_hit`, `must_also_hit`
   and `must_not_top` file lists. The README's table is written from it, so the two cannot drift.
4. `uv run kms seed [collection]` behind `make seed`: walks `seed/<collection>/` and calls the upload
   service function (D17) for each file; idempotent by dedup. The same function runs from the app's
   startup hook when `SEED_ON_START=true` (used in Phase 8).
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
changes and that is migration 0003 (D11 allows it).

---

## Phase 7 — Web UI (frontend track, D28)

**Risk retired.** The interviewer's path: create a collection, upload, watch statuses, search, read
results. Low technical risk, but it is the surface everything is judged through, so it gets its own gate.

**Runs in parallel** with the backend track, in the `frontend` worktree, from the moment the API contract is
approved. Until the backend's Phase 5 passes, every call is answered by mock responses that follow
`docs/api-contract.md` exactly. Items 1–6 below can all be built on mocks; the gate needs the real API.

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

**Decisions to take.** How the mocks are served (for example static JSON behind the API client, or a
request-intercepting library). When and how the client switches from mocks to the real API. Visual
direction (minimal, one accent colour is the suggestion). Whether the detail view is a route or a drawer.
Thumbnail sizing.

**Frontend decisions** (F-numbers, kept here by the frontend session):

| # | Decision | Value | Status |
| --- | --- | --- | --- |

---

## Phase 8 — Deployment hardening and demo readiness

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

## Phase 9 — Optional, in this order

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
| 1 Chunker | 3, last step (D41) |
| 6 Dedup + race | 2 |
| Upload service function → pending + NOTIFY (not in plan) | 2 |
| 3 Schema normalisation | 3 |
| 5a Upload → worker → ready | 3 |
| 7 Lease reaper + attempts cap + retry | 3 |
| 4 Error classification | 4 |
| Adapter-level live check (precursor to 9) | 4 |
| 2 RRF merge + group-by-asset | 5 |
| 5b Absent while pending, present when ready | 5 |
| 8 Hybrid search properties | 5 |
| 9 Live end to end | 6 |
| Reranker / pg_trgm unit tests | 9 |

| Manual checklist item | First run | Repeated on live |
| --- | --- | --- |
| 8 File headers | 2 (curl) | 8 |
| 5 Worker off then on, 6 Kill mid-job, 7 Permanent error + retry | 3 (curl/psql, `kms worker`) | 8 |
| 1 New collection, 2 Upload three, 3 Matrix queries, 4 Duplicate alias, 9 Delete collection | 7 (browser) | 8 |
| Query matrix (`make matrix`) | 6 | 6, 8 |

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

### Plan revision — Sep 26, 2026

D27: Phase 1 is the spike only. The adapter code it held moved out: the schema, interfaces and fakes to Phase 3
(the worker is their first caller), everything that talks to a real vendor to a new Phase 4, together with the
D26 recording. The former Phases 4–8 are now 5–9. No code changed except the comments that named phases.

### Phase 1 — Sep 26, 2026

- **Built.** The vendor spike in `backend/spike/` (describe, embed, errors), findings above. Nothing in `src/`.
- **Deviations.** The adapter code planned for this phase moved out by D27: schema, interfaces and fakes to
  Phase 3, real adapters, errors, record/replay and the collection recording to Phase 4. A Sep 24 `phase-1`
  branch that held early `ai/` code written before the working agreement was deleted unmerged.
- **Decisions taken.** D23 (model list), D24 (tenacity), D25 (lowest thinking), D26 (record the collection
  early and commit it), D27 (adapters after the worker).
- **Gate.** `make test` green (3 tests). Demo: `describe.py` and `embed.py` re-run by Claude, output shown to
  Michael, who accepted it as the demo. Gemini no longer answers `402`; billing works. Schema honoured on both
  files, Voyage cosines identical to the findings. The note spent ~709 thinking tokens against 114 answer
  tokens, which confirms D25. `errors.py` not re-run, to save quota. No deploy: nothing in the app changed.
  Merged to `main` and tagged `phase-1` on Sep 26, 2026.

### API contract — Sep 26, 2026

- **Built.** `docs/api-contract.md`: nine endpoints, one `Asset` shape shared by upload, list, detail, retry and
  search, the error shape, and a table of which call feeds each Phase 7 screen.
- **Decisions taken.** D31 (implicit collections), D32 (`page` + `has_more`), D33 (`{"detail": string}`),
  D34 (hand-written types), each chosen by Michael from presented options. Smaller choices proposed by Claude
  and accepted are in `docs/claude-recommendations.md`.
- **Deviations.** The Phase 5 question on the image unit's snippet is settled here (the description).
- **Gate.** Michael read the contract and approved it. Committed on `main`; frontend worktree set up.

### Phase 2 — Sep 27, 2026

- **Built.** `blob/` (`BlobStore` ABC, `LocalBlobStore` with atomic writes), `ingest/upload.py` (`sniff`, `upload()` with
  `ON CONFLICT` dedup, alias append in one `UPDATE`, `pg_notify` with the asset id), `db.notify_asset_pending`, the
  asset and collection API (`api/schemas.py`, `api/assets.py`, `api/collections.py`) and the 422 handler that
  flattens `detail` to one string. Worked on branch `phase-2`.
- **Deviations.** The chunker moved out of the phase (D41), together with unit test 1. Dedup uses
  `INSERT … ON CONFLICT DO NOTHING` instead of catching `IntegrityError` (D40; design doc amended). Added on the way:
  a decompression bomb is a `415`; any filename that is not header-safe (not only non-ASCII) uses
  `filename*=utf-8''…`; `.gitignore` ignores `data/` at any depth, since blobs land in `backend/data/blobs`. Doc
  references removed from code comments, including Phase 0's.
- **Decisions taken.** D35–D41. Working agreement changed in `CLAUDE.md`: Claude never commits (Michael reviews and
  commits), a big part is split into approved stages, and comments never refer to the docs.
- **Gate.** `make test` green (32 tests). Local demo run by Claude on a real uvicorn server against the dev database;
  live demo run by Michael on the Railway URL after `railway up`: `202` then `200 deduplicated` with the alias, the
  file served from the volume with `ETag` and `immutable` cache headers. Committed and pushed on branch `phase-2`;
  merge to `main` and the `phase-2` tag pending.
