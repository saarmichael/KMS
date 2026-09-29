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
| D26 | Record the collection early | Michael designs `seed/demo/` during Phases 2–4. The last step of Phase 4 runs the real pipeline over it with recording on (D22): the DB is filled and every vendor response stored in one pass. Recordings stay local and git-ignored (amended Sep 27, Michael's call: they hold real model output about personal files); a fresh clone or Railway records again on first use. Recording waits for the worker because a replay only hits when the request is byte-identical (preprocessed image, chunks, metadata unit). Michael's addition | decided (Sep 26; moved from Phase 3 to 4 by D27) |
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
| D41 | Chunker out of Phase 2 | Built in Phase 3 (placed with the worker by D44); its size units (chars or tokens) are decided in that step's plan. Michael's addition | decided (Sep 26; placed Sep 27) |
| D42 | An asset is found by its kind | A query naming a kind of asset ("picture", "document") finds assets of that kind even when no content mentions it. Our code, not the model, adds fixed type tags to `assets.tags`, taken from `asset_type` and `image_type`: every image: `image`, `picture`; by `image_type`: photo → `photo`, `photograph`; screenshot → `screenshot`; document → `document`, `scan`; diagram → `diagram`, `drawing`; every text file: `text`, `text file`, `document`. Merged with the model's tags and deduped; visible in the API like any tag. Tested in Phase 5 (integration) and Phase 6 (two matrix rows). Michael's addition | decided (Sep 27) |
| D43 | Where the seed collection lives | Outside the repo, at `../seed` (the `SEED_DIR` default), never committed: the photos are personal. How `kms seed` and the matrix read it is settled in Phase 6. The `FakeVision` fixtures that describe its files (filenames plus short hand-written metadata) are committed | decided (Sep 27) |
| D44 | Chunker built with the worker | The chunker and unit test 1 move from the last step of Phase 3 into the worker part, so the worker builds real content units from the start instead of one placeholder chunk per file. Replaces D41's placement | decided (Sep 27) |
| D45 | Photo date and place to the vision model | EXIF date taken and GPS are read from the original bytes (`ingest/images.py`) and passed to `Vision.describe` as `PhotoDetails`; the Phase 4 prompt tells the model to use them only when they help, naming place and time in the description and tags. Date and GPS only; no new columns (a structured date-taken column is a later option). An image without them works as before. Michael's addition | decided (Sep 27) |
| D46 | A naive chunker | Fixed windows of `CHUNK_SIZE_CHARS` (1,600) with `CHUNK_OVERLAP_CHARS` (240) overlap, each ending at its last space; sizes in characters, not tokens. The chunker shows the structure (content units with offsets); the recursive paragraph → sentence → word split is noted in the design as the next step. Michael's addition | decided (Sep 27) |
| D47 | A failed attempt goes back to `pending` at once | The adapter's own backoff covers blips; the asset gets its next full pass right away, and after `MAX_ATTEMPTS` it is `failed`. An expired lease counts as an attempt: at the cap the reaper marks the asset `failed` instead of re-queueing it. Chosen for the simpler claim query over a delay of one lease length | decided (Sep 27) |
| D48 | An asset is found by its file name | Every asset gets one `filename` search unit, keyword-indexed and embedded like the others: the full name, then its words split on anything that is not a letter or digit (`notes-lisbon.txt notes lisbon txt`), because Postgres keeps a bare file name as one token and "lisbon" would not find it. Original filename only, not aliases (they arrive after processing). No migration. Search needs no new path, only a `"filename"` snippet kind whose text is the filename (contract change); the UI labels it and marks the query words. Kept small on purpose: a misleading filename snippet in the vector tail is a known limitation, checked in Phase 6, not fixed now. Michael's addition | decided (Sep 27) |
| D49 | One password in front of the deployed app | HTTP Basic Auth as middleware over every path except `/api/health`; one shared `APP_PASSWORD` (any username), compared in constant time; empty turns it off, so local dev and tests are open. The browser's own prompt, so the UI needs no change. Guards the vendor credit behind the public URL once live runs real providers; teardown is changing or emptying the password. Brought forward from Phase 8. Michael's addition | decided (Sep 27) |
| D50 | How a result matched, and the user's view of the results | Each unit is an `exact` match (the keyword search found every query word in it), `partial` (some words) or `semantic` (meaning only). A plain query now finds keyword matches on any word, all-words units first; a query with quotes, `-word` or `or` stays strict. An asset takes its strongest match and its snippet from the unit that shows it; its score stays its best unit's, against the top of the whole query. The API returns `match` per result and takes `order` (`exact_first` default, `tiered`, `blended`) and repeatable filters `match`, `asset_type`, `found_in`. Filters and order run in the backend over the fused list, then the cap and the page, so a change is a new request for page 1 (the query vector is cached). Filters narrow the best 100 units per path; they do not search deeper. A real reranker must keep each result in its tier. Michael's addition | decided (Sep 27) |
| D51 | The closest sentence of a match by meaning | For every result whose `match` is `semantic`, whatever its snippet (a passage, a description, a file name), the search finds the sentence of the snippet's text closest in meaning to the query: the text is split into sentences with `pysbd` (rule-based: abbreviations, numbered lists, one line per item; character offsets), all such sentences of the page are embedded in one call with the same embedder as `"document"`, and the closest by cosine to the cached query vector wins. The API returns it as `snippet.sentence_start`/`sentence_end`, counted in the snippet's `text`, so every kind goes through the same code; the card opens its preview on it and the dialog marks it where that text shows (the passage, scrolled to; the description; the file name). Our own embedder, not a second model (Jev was weighed), so the sentence comes from the same model that ranked the result. Computed during the search, after paging, so only shown results cost anything; not stored at ingest (a migration and about 12x the vector rows). A failed sentence embedding leaves the fields `null` and the search succeeds. Phase 9, item 3 | decided (Sep 27) |
| D52 | Text in an image is its own search unit | An image's `visible_text` becomes its own unit, kind `visible_text`, written only when the text is not empty; the `metadata` unit keeps title, description and tags. A word read from the image is then reported as `snippet.kind` `"visible_text"` (`text` is the asset's `visible_text`, no offsets), filtered by `found_in=visible_text` (its own "Text in image" chip), and embedded on its own. Alternative: one unit and the label worked out at snippet time, which leaves the filter wrong. No migration (`kind` is plain text); existing collections are wiped and uploaded again. Phase 9, item 4 | decided (Sep 27) |
| D53 | Cancel on the password prompt | The SPA's pages are sent with `Cache-Control: no-cache`, so the browser checks with the server, and so asks for the password, on every page load, instead of reusing a cached page whose API calls then all fail. Any `401` the UI still gets (Cancel pressed, or the password changed while a tab is open) replaces the app with a "Password needed" screen and a Reload button, which brings the browser's prompt back. `no-store` was weighed and gives nothing more; an inline error per component was the state that went unnoticed. Phase 9, item 6 | decided (Sep 28) |
| D54 | Voyage batches in parallel | `VoyageEmbedder.embed` sends its batches of 100 at the same time from a thread pool of its own, `min(batches, EMBED_PARALLEL_CALLS)` threads, default 20 (a 2.5 MB text file's 19 batches in one round). One pool per call, not one shared by the app, so search's embed calls never wait behind an upload. Each batch keeps its own retries; a batch that still fails fails the whole call after the calls in flight finish, and vectors come back in input order as before. Recordings are unaffected (one per `embed()` call). The cap guards Voyage's tokens-per-minute limit on large uploads; requests per minute (2,000) are far off. Phase 9, item 7. Michael's addition | decided (Sep 28) |
| D55 | Sift brand, palette and a light/dark theme | The Sift brand kit lives in `frontend/brand/` (logos, lockups, favicons, social image, the scripts that made them); the files the app serves are copied into `frontend/public/` (favicons, manifest, `og-image.png`) and `frontend/src/assets/` (the lockups). Two raw scales from the artwork, `sift` (orange) and `ink` (Bone to Night), and on top of them role colours (`page`, `surface`, `text`, `accent`, …) that components use; each role has a light value and a dark value under `[data-theme="dark"]` on `<html>`, so switching the attribute re-colours the page. Tailwind's `dark:` variant on every element and a flipped `ink` scale were weighed. Orange fills carry Ink text (about 5.4:1; white is about 2.9:1). Poppins, self-hosted through `@fontsource/poppins`. A toggle in the header's top corner switches the theme; the first visit follows the OS setting, a chosen theme is kept in `localStorage`, and an inline script in `index.html` sets it before the first paint. Link-preview tags point at the Railway URL; behind the password, previews show no image. Phase 9, item 8. Michael's addition (both themes and the toggle) | decided (Sep 28) |
| D56 | Relevance from the reranker | A Voyage reranker (`rerank-2.5`, behind `RERANK_ENABLED`) scores the first `RERANK_CANDIDATES` (20) results of the requested order, after the filters, reading each one's snippet text; the API returns it as `relevance` (0 to 1) next to `score`, which keeps its meaning. A new order, `relevance`, the API's and the UI's default, sorts those candidates by relevance whatever their match kind (this replaces D50's rule that a reranker keeps each result in its tier); the results after them follow in score order. The other orders keep their order and still get relevance on their candidates, so relevance is there whatever the order. Results past the candidates, and every result while reranking is off, have `relevance: null`. No cut-offs turn relevance into "good" or "bad" (amended Sep 29, Michael): the score is given as it is, and how the UI shows it is decided later. Each (model, query, text) pair's relevance is remembered (`RERANK_CACHE_SIZE` pairs, least recently used dropped), so a change of order or filter sends only texts not scored before. A failed rerank leaves `relevance` `null` and score order; the search succeeds. The `Reranker` interface returns relevances, and `NoOpReranker` returns none. Phase 9, item 1. Michael's addition (relevance over tiers by default, the 20 candidates) | decided (Sep 29) |
| D57 | Retry policy chosen by the caller | Every vendor call (`describe`, `embed`, `rerank`) takes a required `RetryPolicy` (attempts, first wait, the longest server-requested wait honoured, timeout per request), chosen at the call site: `BACKGROUND_POLICY` for the worker and the CLI, `INTERACTIVE_POLICY` for the search query's embedding, `OPTIONAL_POLICY` (one attempt) for the closest sentences and the rerank, whose failure only drops a hint. Each adapter reads its own vendor's errors (`classify_gemini_error`, `classify_voyage_error`); `errors.py` keeps only the vendor-neutral loop and imports no SDK; Gemini's model fallback reads `is_overloaded` in `gemini.py`. The timeout travels with the policy: per request for Gemini, one client per timeout for Voyage (`VoyageClients`). One adapter instance per context (worker, search) was weighed and rejected: it cannot tell the search query from the optional search calls. Phase 9, item 9. Michael's addition | decided (Sep 29) |
| D58 | Demo mode | `DEMO_MODE` (default off) is a runtime setting: `GET /api/config` returns `{demo_mode}`, the UI reads it once on load, shows a "Demo" label by the logo, and greys out Delete, with a hint bubble on hover, "Deleting collections is not allowed in demo mode", and `DELETE /api/collections/{name}` answers `403` while it is on, so the shared collection is safe from curl too. A failed config call leaves the button enabled; the server still refuses. A build-time `VITE_DEMO_MODE` was weighed (a rebuild per mode, a Dockerfile `ARG`). There is no per-asset delete, so nothing else is switched off. Phase 9, item 10 | decided (Sep 29) |
| D59 | Review fixes before hand-over | An external-review pass found: the SPA route served any file on disk (`%2e%2e` in the URL), so it now serves only files that resolve inside the build; `make test` read `DEMO_MODE` from `.env`; the built SPA was tracked because `.gitignore` named the wrong path; an oversized upload was received in full before its `413`; a vendor outage in search was a bare `500`; recordings grew with every query and could be left half-written; "Show more" could append a page of an old filter; `q` had no length limit; docs lagged the code. Fixes: resolve-and-check in `spa()`; `DEMO_MODE` pinned in the test conftest; the `.gitignore` path; a `Content-Length` middleware (`413` before the body is read); `503` via `QueryEmbeddingFailed`; `AI_CACHE_DIR` off by default and atomic `write_recording`; the view's `AbortController` cancels its later pages; `q` capped at 500 characters (`422`); README, system design, contract and the entrypoint comment brought in line, F13 retired. Left as is (Michael): seeding not built, local recordings and blobs in the Docker image, the Phase log. Phase 9, item 11 | decided (Sep 29) |
| D60 | Checklist follow-ups | Three checklist agents (browser demo script, backend ops and contract, a fresh reviewer following the README) ran against throwaway instances after D59. Small fixes: `spa()` answers an unknown `api/` path with a JSON `404` and treats a path it cannot resolve (a NUL byte) as unknown; the no-cache test builds its own UI folder, so a fresh clone passes; the search box stops at 500 characters; a model answer that fails validation is stored as a readable sentence, the raw error kept in the log; a `422` on a list filter names the parameter, not its index; docs (auth wording, reranker needs real adapters, TESTING.md run and open items, the unit kinds and deploy source in the design); the API title and the contract say Sift. Everything else found is listed, unfixed, in `Smart_Search/flaws.md` (Michael, Sep 29). Phase 9, item 12 | decided (Sep 29) |

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
   lengths, truncate, `image_type` null for text). Normalisation also adds the fixed type tags (D42) from
   `asset_type` and `image_type`; how they interact with the tag-count cap is settled in the part's plan.
2. Interfaces: `Vision.describe(bytes | text, asset_type) -> Metadata`, `Embedder.embed(units) -> vectors`.
   The `Reranker` interface arrives with search in Phase 5 (D16).
3. Fake adapters exactly as the test plan describes: `FakeVision` (fixture dict by filename, generic
   fallback, a filename containing `invalid` always fails validation; the "once" mode comes with the
   repair retry in Phase 4) and `FakeEmbedder` (hashed bag-of-words, L2-normalised, image from
   byte hash). Selected by `AI_PROVIDER`. The fixture dict holds hand-written metadata for the files the
   demo uploads, so the whole pipeline runs on static data until Phase 4.
4. `ingest/images.py`: EXIF rotation fix, downscale to ~1024 px, re-encode; read date taken and GPS
   from the original for the vision call (D45).
5. `ingest/summary_source.py` (D16): strategy with `WholeFile` (live), `Head` (live fallback, token
   budget), `MapReduce` (stub raising `NotImplementedError` with the README note). Decides which text the
   vision model sees; the chunker decides the content units independently.
6. `ingest/worker.py`: `claim_one()` (SKIP LOCKED, status/started_at/attempts), `process(asset)` (load,
   preprocess, describe via the summary source, build units, embed in one batch, commit metadata + units +
   `ready` in one transaction) and `run_once()`; the loop that repeats it is `WorkerPool._work_loop` in
   `ingest/pool.py`; the outer retry loop (adapter gave up →
   back to `pending` at once; `attempts = 3` → `failed` with the message; an expired lease at the cap →
   `failed`). `reaper()` on startup and
   every minute.
7. Listener (`ingest/pool.py`): dedicated autocommit connection, `LISTEN asset_pending`, wait with a 1 s
   timeout, reconnect loop. Wake-up triggers a claim; the timeout is the poll guarantee.
8. Two ways to run the pool (D19): the app's startup hook starts `WORKER_THREADS` threads when
   `WORKER_ENABLED=true` (the default, and how the deployed container runs); `uv run kms worker` runs the
   same pool as its own process for the checklist and as the scale path. Tests and `make dev` with the
   worker off use the flag.
9. Structured logging of every state transition with asset id, attempt and duration: upload, claim,
   commit, failure, reaper reset. Built here once; Phase 8 only checks it reads well in Railway's log view.
10. `ingest/chunker.py` (D41), built with the worker in step 6 (D44): fixed character windows ending at a space,
    configurable size and overlap, character offsets; unit test 1 (D46).
11. The filename unit (D48), its own small part after the pool: `filename_body(filename) -> str` in
    `ingest/worker.py` (full name, then its words), and `build_units` adds one `filename` unit after the
    metadata unit. One unit test of `filename_body`; integration 5a checks the unit is written.

**Tests that pass here.** Unit 3 (schema normalisation). Integration 5a (upload → worker → `ready`, units written, one per chunk plus
metadata plus image unit plus filename unit). Integration 7 (reaper resets stale `processing`, leaves fresh; third failure →
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
2. Real adapters behind the Phase 3 interfaces: `GeminiVision` (response_schema → validate →
   one repair retry → permanent error; lowest thinking level, D25; on an overloaded answer it moves to the
   next id in `VISION_MODELS` and reports which model answered, D23), `VoyageEmbedder` (batched,
   `input_type` query/document). Adapters return validated metadata; the worker normalises it. Prompts live in `ai/prompts/`; the image prompt uses the photo's date and place when given (D45). `VISION_MODELS` replaces the single
   `VISION_MODEL` setting.
3. Migration 0002 adds `assets.vision_model`; the worker writes the answering model with the metadata.
4. Recorded responses (D22): `ai/recorded.py` wraps the real adapters. Each call is keyed by a hash of
   model, prompt version and input; one JSON file per call under `AI_CACHE_DIR`. Hit → the stored
   response; miss → the vendor, then store. An empty setting turns it off. Fakes stay the test default;
   recording makes the live test, the matrix and the demo repeatable and free after the first run.
5. CLI subcommands (D20): `uv run kms describe <file>` and `uv run kms embed <file>...` print the result
   with either provider. A debugging tool next to the worker, not the adapters' only caller.
6. Record the collection (D26): with `AI_PROVIDER=real` and recording on, upload every file of
   `seed/demo/` (as designed by Michael so far) and let the worker process it. The recordings stay local, git-ignored (D26 as amended).
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
(cost) or only the text. Where `AI_CACHE_DIR` defaults to (recordings stay local, D26 as amended).

**Parts.** Agreed Sep 27. Work on branch `phase-4`. Each part gets its own plan, approved before its code;
the next part starts only when Michael says so. Vendor-free parts first, real vendor calls last.

| # | Part | Holds | Status |
| --- | --- | --- | --- |
| 1 | The answering model is stored | Migration 0002 adds `assets.vision_model`; the worker writes `description.model`; the API returns it | done |
| 2 | Vendor error handling | `ai/errors.py`: transient / overloaded (next model) / permanent (incl. 402); tenacity backoff honouring `RetryInfo.retryDelay`; unit test 4 | done |
| 3 | `GeminiVision` and prompts | `ai/prompts.py` (image, text, repair, prompt version; photo date and place, D45); `response_schema`, lowest thinking, validation + one repair retry; `VISION_MODELS` walk (D23) replacing `VISION_MODEL`; `get_vision()` builds it for `AI_PROVIDER=real` | done |
| 4 | `VoyageEmbedder` | Batched `multimodal_embed`, `input_type`, image bytes → PIL, SDK retries off; `get_embedder()` builds it for `AI_PROVIDER=real` | done |
| 5 | Record and replay | `ai/recorded.py` wraps the real adapters; key = hash of model, prompt version, input; one JSON file per call under `AI_CACHE_DIR` | done |
| 6 | CLI | `kms describe <file>`, `kms embed <file>...`, either provider | done |
| 7 | Live test | `tests/live/`: output validates, screenshot `visible_text` non-empty, "black hair" closer to "brunette" than to an unrelated sentence; every fallback model checked; the recorder replays real answers | done |
| 8 | Record the collection | Real pipeline over the seed with recording on; check in the UI; the recordings stay local, git-ignored (D26 as amended). An operational run, not new code | done |
| 9 | A password on the app | `api/auth.py` middleware, `APP_PASSWORD` setting, contract rule (D49); added Sep 27 before live runs real providers | done |

Open points, settled in the part named:

- Part 3: the `visible_text` output token limit; whether the repair retry re-sends the image. Where the
  repair retry lives: inside `GeminiVision` (tested with a stubbed client) or as a wrapper around any
  `Vision` (then `FakeVision` gets the "invalid once" mode the test plan names).
- Part 5: the `AI_CACHE_DIR` default. Settled: `./recordings` (`backend/recordings`).
- Part 8: committing recordings. Settled Sep 27: never committed; `recordings/` is git-ignored (D26 as amended).
- Parts 7 and 8 need Gemini credit: the last spike call answered `402` on every model.

**Part 1 plan (approved Sep 27).**

- *How the model reaches the row:* a new parameter on `commit_ready`. Not a field on `Metadata` (that is the
  schema Gemini fills, so the model would be asked for its own name); not the whole `Description` (it holds
  the raw answer, `commit_ready` the normalised one).
- *Column:* `assets.vision_model TEXT NULL`, no default, no backfill; rows described earlier stay `null`
  (unknown). Retry leaves it alone: a failed asset never had metadata written.
- *Files:* new `alembic/versions/0002_assets_vision_model.py` (`upgrade()` adds the column, `downgrade()`
  drops it); `models.py` gains the column after `image_type`, docstring "Mirrors the migrations exactly";
  `ingest/worker.py` `process()` passes `description.model`; `api/schemas.py` `Asset.from_row` reads the
  column. No new dependency or setting.
- *Function:* `commit_ready(asset, metadata, vision_model: str, units, vectors) -> bool`, writes
  `vision_model` in the same update that sets `ready`; return and lease behaviour unchanged.
- *Contract:* only the comment on `vision_model` changes, to "null for assets described before the column
  existed". Shape unchanged, no frontend change.
- *Tests:* `test_image_becomes_ready_with_metadata_image_and_filename_units` asserts `vision_model ==
  "fake-vision"`; `test_stale_worker_cannot_commit` passes the argument; new
  `test_ready_asset_reports_the_model_that_described_it` (upload, `run_once()`, `GET` shows `fake-vision`).
  The health test proves 0002 applies.
- *Demo:* `make migrate`; `/api/health` at `0002`; a new upload shows `"vision_model": "fake-vision"`; the
  stored seed assets show `null`.

**Part 2 plan (approved Sep 27).**

- *Kinds:* `classify(error: Exception) -> ErrorKind`, never raises. `ErrorKind` is a `StrEnum` (`TRANSIENT`,
  `OVERLOADED`, `PERMANENT`; prints as its value in logs); status codes are written as `http.HTTPStatus`
  members. Amended Sep 27 on Michael's request, replacing a `Literal` of strings and bare numbers.
  Overloaded: Gemini 503 and every Gemini 429 (all its quotas are per model). Transient: Gemini 500/502/504,
  `httpx.TransportError`; Voyage 429, 5xx, `Timeout`, `APIConnectionError`. Permanent: everything else (400,
  401/403, 402, 404, 413, 422, safety block raised by Part 3, validation errors, unknown errors).
- *Fallback and backoff together:* `call_with_retries` retries anything not permanent. Part 3 wraps the whole
  model walk in one call: overloaded → next model inside the walk; all overloaded, or a transient error →
  the walk raises, backoff, restart at the first model. D23's "any other error fails at once" read as "does
  not move to the next model".
- *Waits:* Gemini's `RetryInfo.retryDelay` when present, else 1, 4, 16 s plus 0–1 s jitter
  (`wait_exponential(exp_base=4)` + `wait_random(0, 1)`); at most `MAX_CALL_ATTEMPTS = 4`; a server wait over
  `MAX_SERVER_WAIT_SECONDS = 60` is raised at once. Constants, not settings.
- *Functions:* `server_retry_delay(error: Exception) -> float | None` (seconds from RetryInfo, `None` when
  absent or malformed, never raises); `call_with_retries(call: Callable[[], T], description: str) -> T`
  (tenacity `Retrying` with `reraise=True`; the original error is re-raised; each wait logged as
  `vendor_retry call= attempt= kind= wait_s= error=`).
- *Files:* new `ai/errors.py`, new `tests/unit/test_errors.py`; `httpx` becomes a direct dependency (already
  installed through google-genai). No settings.
- *Tests (unit 4):* `test_gemini_429_and_503_are_overloaded`, `test_gemini_500_502_504_are_transient`,
  `test_gemini_client_errors_are_permanent`, `test_voyage_rate_limit_server_and_network_errors_are_transient`,
  `test_voyage_auth_and_bad_request_are_permanent`, `test_network_errors_are_transient`,
  `test_unknown_error_is_permanent`, `test_server_retry_delay_is_read_from_retry_info`,
  `test_retries_a_transient_error_then_succeeds`, `test_permanent_error_is_raised_at_once`,
  `test_gives_up_after_four_attempts`, `test_waits_as_long_as_the_server_asks`,
  `test_server_wait_over_the_cap_is_raised_at_once`. Sleep patched with `monkeypatch`; errors built by hand.

**Part 3 plan (approved Sep 27).**

- *Walk inside one backoff (Part 2):* `describe` runs `call_with_retries` around the model walk. Overloaded →
  next model at once; any other error raised; all overloaded → the last error is raised, backoff (honouring
  `retryDelay`), restart at the first model.
- *Validation and repair per model, inside the walk:* generate → validate; invalid → one repair call to the same
  model → validate; still invalid → `ValidationError` (permanent). An overloaded answer to the repair call moves
  the walk on; the next model starts fresh. The repair re-sends the whole conversation: prompt and image, the bad
  answer, then `REPAIR_PROMPT` with the validation error. `FakeVision` gets no "invalid once" mode; the repair is
  tested with a stub client (`docs/TESTING.md` amended).
- *Safety block:* `prompt_feedback.block_reason`, or a candidate finishing for a safety or prohibited-content
  reason, raises `ContentBlockedError("Gemini blocked the answer: <reason>")`; permanent through `classify`'s
  unknown-error rule, `errors.py` unchanged.
- *Client passed in:* `GeminiVision(client, models)`; `get_vision()` builds `genai.Client(api_key=...,
  http_options=HttpOptions(timeout=REQUEST_TIMEOUT_SECONDS * 1000))`, SDK retries off (no `retry_options`).
  `REQUEST_TIMEOUT_SECONDS = 120`. A timeout arrives as an `httpx` error: transient.
- *Request:* `response_mime_type="application/json"`, `response_schema=Metadata`,
  `thinking_config=ThinkingConfig(thinking_level=MINIMAL)` (D25), `max_output_tokens=MAX_OUTPUT_TOKENS` (8,192,
  constant; covers thinking and the JSON). Default temperature. Amended Sep 27 after the Part 7 live run: `automatic_function_calling`
  disabled, since no tools are passed and the SDK warned on every call. An image is the prompt plus
  `Part.from_bytes(prepared JPEG, "image/jpeg")`; a text file is `TEXT_PROMPT` plus the summary text as its own
  part. The filename is never sent.
- *Prompts (`ai/prompts.py`, one module):* the spike's prompts; tags "lowercase words or short phrases"; the image
  prompt adds D45's date and position lines when present, used only when they help, naming place and time in the
  description and tags; the text prompt asks for `image_type` null. `PROMPT_VERSION = 1`, for Part 5's
  recording key; not written to `assets.metadata_version` (that column tracks the schema's shape).
- *Settings:* `vision_model: str` → `vision_models: list[str] = Field(min_length=1)`, D23's list as default,
  `VISION_MODELS` as a JSON list; `.env.example` gains a commented line. `AI_PROVIDER=real` without
  `GEMINI_API_KEY` → `get_vision()` raises `ValueError("GEMINI_API_KEY is not set")`, so the asset fails with it.
- *Files:* new `ai/prompts.py`, `ai/gemini.py`, `tests/unit/test_gemini_vision.py`, `tests/unit/test_prompts.py`;
  changed `ai/__init__.py`, `config.py`, `.env.example`, `tests/unit/test_fake_adapters.py`,
  `tests/unit/test_settings.py`. No new dependency.
- *Functions:* `build_image_prompt(photo_details: PhotoDetails | None) -> str` (never raises);
  `GeminiVision.describe(content, asset_type, filename, photo_details) -> Description` (validated, not
  normalised; raises `ValidationError`, `ContentBlockedError` or the vendor error unchanged);
  `_describe_with_fallback(contents) -> Description` (the walk; logs `vision_model_overloaded model= error=`);
  `_describe_with_model(model, contents) -> Metadata` (generate, validate, one repair; logs `vision_repair model=
  error=`); `_generate(model, contents) -> str` (one call, answer text or `""`; raises `ContentBlockedError`; logs
  `vision_call model= prompt_tokens= output_tokens= thinking_tokens= seconds=`).
- *Tests:* `test_first_model_answers`, `test_overloaded_model_moves_to_next_at_once`,
  `test_all_models_overloaded_backs_off_and_restarts_at_first`, `test_permanent_error_does_not_try_next_model`,
  `test_invalid_answer_is_repaired_once`, `test_invalid_twice_raises_validation_error`,
  `test_blocked_answer_raises_content_blocked`, `test_request_uses_schema_lowest_thinking_and_output_limit`,
  `test_text_file_is_sent_as_text_without_image`; `test_image_prompt_names_date_and_place_when_given`,
  `test_image_prompt_leaves_them_out_when_absent`; `test_real_provider_not_available_yet` becomes
  `test_real_provider_builds_gemini_vision` (dummy key, no call; the embedder still raises);
  `test_vision_models_read_from_json_list`.
- *Demo:* `make test` green; `AI_PROVIDER=real`, upload the spike screenshot → `ready` with real metadata and
  `vision_model`; on a `402` it fails with the message after one call per attempt, no walk.
- *Not verified:* `thinking_level=MINIMAL` on the flash-lite models; a `400` would fail the asset. Checked once per
  model before Part 8.

**Part 4 plan (approved Sep 27).** Planned as if Part 3 were done; touches only the embedding side.

- *Batching:* at most `MAX_INPUTS_PER_CALL = 100` inputs per `multimodal_embed` call (Voyage allows 1,000
  inputs and 320K tokens; 100 × the largest unit, ~2,800 tokens, stays under). Vectors joined in input order.
  Each batch goes through its own `call_with_retries`; if one still fails, `embed()` raises and the worker's
  next attempt re-embeds everything. No model fallback (D23).
- *Client passed in, as in Part 3:* `VoyageEmbedder(client, model, dims)`; `get_embedder()` builds
  `voyageai.Client(api_key=..., max_retries=0, timeout=REQUEST_TIMEOUT_SECONDS)` with `REQUEST_TIMEOUT_SECONDS =
  60` in `ai/voyage.py` (the SDK has no timeout by default). Tests pass a stub client to the constructor.
  Amended Sep 27 from "the adapter builds its own client", to match Part 3's injection. After implementation
  the timeout constants were named per vendor, `GEMINI_REQUEST_TIMEOUT_SECONDS` (in `ai/gemini.py`) and
  `VOYAGE_REQUEST_TIMEOUT_SECONDS`, so `ai/__init__.py` imports both without an alias; the `real_provider`
  test fixture moved to a new `tests/unit/conftest.py`, shared by both adapters' tests.
- *Dimensions:* `output_dimension=dims` on every call; a wrong vector count or length raises `ValueError`
  (permanent) instead of failing later at the `vector(1024)` insert.
- *Files:* new `ai/voyage.py`; `ai/__init__.py` `get_embedder()` builds the client and `VoyageEmbedder(client,
  embedding_model, embedding_dims)` for `"real"` and raises `ValueError("VOYAGE_API_KEY is not set")` without
  a key; `REAL_NOT_AVAILABLE` is removed (both adapters are real now). No new dependency or setting.
- *API:* `VoyageEmbedder(client: voyageai.Client, model: str, dims: int)`, no network call; `embed(inputs: list[str | bytes],
  input_type) -> list[list[float]]`: `str` as text, `bytes` opened with Pillow as an image; `[]` returns `[]`
  with no call; logs `voyage_embedded inputs= calls= duration_ms=`; raises the vendor error or `ValueError`.
- *Tests (`tests/unit/test_voyage_embedder.py`, stub client):* `test_texts_and_images_go_in_one_call_in_order`,
  `test_more_inputs_than_one_call_takes_are_split_in_order`, `test_query_input_type_is_passed_through`,
  `test_a_transient_error_is_retried`, `test_wrong_vector_length_is_an_error`,
  `test_empty_input_makes_no_call`, `test_real_provider_builds_the_voyage_embedder`,
  `test_real_provider_without_a_key_raises`. Part 3's `test_real_provider_builds_gemini_vision` drops its
  "the embedder still raises" check.

**Part 5 plan (approved Sep 27).** Planned as if Part 4 were done. Kept deliberately small: the recordings
are a development aid, not a production cache.

- *How it works:* a wrapper around each real adapter turns a fingerprint of the request into a file path. File
  exists → its answer is returned; otherwise the real adapter is called, its answer written, and returned. Only
  successful answers are written; an error passes through and the next attempt calls the vendor again.
- *Vision fingerprint:* the first model in `VISION_MODELS` (changing the primary model re-records; editing the
  fallbacks does not), `PROMPT_VERSION`, `asset_type`, the sha256 of the content, `photo_details`. Not the
  filename: Gemini never sees it.
- *Embed fingerprint:* model, dims, `input_type`, and each input's kind (`"text"` / `"image"`) with its sha256, in
  order. Every embed call is recorded, search queries included, so the query matrix replays after a restart.
- *Files:* `AI_CACHE_DIR/vision/<hash>.json` holds `{"model": <the model that answered>, "metadata": {...}}`;
  `AI_CACHE_DIR/embed/<hash>.json` holds `{"vectors": [...]}`. JSON files rather than a table: they survive an emptied
  database (not committed: D26 as amended).
- *Left out on purpose:* atomic writes (two threads writing one file needs the same file uploaded twice at once;
  the only cost is a second vendor call); custom handling of a damaged file (the JSON or validation error is
  raised; delete the file to re-record); a copy of the request in the file.
- *Setting:* `ai_cache_dir: str = "./recordings"`; a string so that empty means off. Only the real adapters are
  wrapped; the fakes never are.
- *Files:* new `ai/recorded.py`, `tests/unit/test_recorded.py`; changed `ai/__init__.py` (wraps the real adapters
  when the setting is non-empty), `config.py`, `.env.example`. No new dependency.
- *Code:* `recording_path(cache_dir: Path, kind: str, request: dict) -> Path` (`cache_dir/kind/<sha256 of the
  request as sorted JSON>.json`); `RecordedVision(Vision)` with `__init__(self, inner: GeminiVision, cache_dir:
  Path)` and `describe(...) -> Description`; `RecordedEmbedder(Embedder)` with `__init__(self, inner:
  VoyageEmbedder, cache_dir: Path)`, `model = inner.model`, and `embed(inputs, input_type) -> list[list[float]]`.
  One log line, `recording_hit kind= file=`; a miss shows in the adapter's own call logs.
- *Tests (stub `inner` that counts calls, `tmp_path`):* `test_vision_second_call_is_replayed` (one vendor call; the
  replay keeps the answering model), `test_vision_ignores_the_filename`,
  `test_vision_changed_request_is_not_replayed` (parametrized: model, prompt version, content, photo details),
  `test_embed_second_call_is_replayed`, `test_embed_changed_input_type_is_not_replayed`,
  `test_failed_call_is_not_recorded`, `test_real_provider_records_only_when_cache_dir_is_set`.
- *Demo:* `AI_PROVIDER=real`: upload the screenshot → `ready`, two files in `backend/recordings/`. Empty the tables,
  upload again → `ready`, same metadata, `recording_hit` twice, no `vision_call` in the log.

**Part 6 plan (approved Sep 27).** Planned as if Part 5 were done. Michael took Claude's proposal as written.

- *Same preparation as the worker:* `process()`'s inline preparation (image: `prepare_image`,
  `read_photo_details`; text: decode, `chunk_text`, summary source) moves into `prepare_file` in
  `ingest/worker.py`; the worker and the CLI both call it, so a CLI call is byte-identical to the worker's and
  hits its recordings. Chosen over a copy in `cli.py`, which could drift.
- *Type:* from the bytes via `upload.sniff()`; no size cap (local tool). The filename given to `describe` is
  `path.name`, so fake mode prints the fixture.
- *`embed` inputs:* what the worker embeds without metadata: an image's prepared JPEG, a text file's chunks. All
  files in one `embed()` call, `input_type="document"`. Query embeddings wait for Phase 5.
- *Output (stdout; logs stay on stderr):* `describe` prints JSON `{"model", "photo_details", "metadata"}`, metadata
  validated, not normalised. `embed` prints one line per input, `<file> <kind> <index> dims= norm= [first 4
  values]`, then `model= inputs= seconds=`. No full vectors.
- *Errors:* any exception → `error: <ErrorClass>: <message>` on stderr, exit 1. A missing file argument prints the
  usage, exit 2. Arguments still read from `sys.argv`, not `argparse`.
- *Recording:* through `get_vision()` / `get_embedder()`, so `AI_CACHE_DIR` applies as in the worker.
- *Files:* changed `cli.py`, `ingest/worker.py`; new `tests/unit/test_cli.py`. No new dependency or setting.
- *Code:* `PreparedFile` (frozen dataclass: `content: bytes | str`, `photo_details: PhotoDetails | None`,
  `prepared_image: bytes | None`, `chunks: list[Chunk]`); `prepare_file(data: bytes, asset_type: str) ->
  PreparedFile` (reads chunk and summary settings; raises what `prepare_image` or decoding raises). In `cli.py`:
  `load_file(path: Path) -> tuple[str, PreparedFile]` (read, sniff, prepare; raises `OSError`,
  `UnsupportedFileType`); `describe_command(path: Path) -> int`; `embed_command(paths: list[Path]) -> int`;
  `main()` gains both branches and exits with the code; usage `kms migrate | worker | describe <file> | embed
  <file>...`.
- *Tests (fake provider, `tmp_path`, `capsys`):* `test_describe_prints_the_fixture_for_a_known_file`,
  `test_describe_passes_photo_details_for_a_photo`, `test_embed_prints_one_line_per_input` (two-chunk text + an
  image → 3 lines + summary), `test_unsupported_file_is_an_error`, `test_missing_file_is_an_error`. The worker's
  integration tests cover the `process()` refactor.
- *Demo:* `uv run kms describe <spike screenshot>` with fake, then real; a second real run shows `recording_hit`
  and no `vision_call`. `uv run kms embed <note> <screenshot>` prints 1,024-dim lines and the timing.


**Part 7 plan (approved Sep 27).** Planned as if Part 6 were done. Two passes in one file: the first talks to
the vendors, the second proves the recorder replays what the first recorded. Michael's addition.

- *Adapters as the app builds them:* through `get_vision()` / `get_embedder()`, so the live run also checks the
  client setup (timeouts, SDK retries off, `VISION_MODELS` from settings). Not constructors in the test.
- *Recording on, into a fresh folder:* `recordings_dir` (one `tmp_path_factory` folder per run, never
  `backend/recordings/`); `live_provider` sets `AI_PROVIDER=real` and `AI_CACHE_DIR=<recordings_dir>` and resets
  the settings and adapter caches in and out. Every pass-1 call misses, so it is live; pass 2 expects hits at
  once. `real_provider` stays in `tests/unit/conftest.py`.
- *Skip:* every test marked `live`, `skipif` either key is missing; a key that is set but refused fails.
- *Inputs:* `spike/samples/screenshot.png` through `prepare_image()` and `note.txt`; the spike's sentences
  ("black hair" as `"query"`; the brunette and tax sentences as `"document"`); cosine computed in the test.
- *Files:* new `tests/live/test_live_adapters.py`. No new log line, dependency, setting or Makefile change
  (the existing `recording_hit kind= file=` proves a hit).
- *Pass 1 (vendors):* `test_screenshot_is_described_with_visible_text`, `test_text_file_is_described`,
  `test_every_vision_model_accepts_the_request` (parametrized over `VISION_MODELS`, `GeminiVision(client,
  [model])` on the note, never recorded; closes Part 3's "not verified"),
  `test_black_hair_is_closer_to_brunette_than_to_an_unrelated_sentence`,
  `test_image_and_text_embed_to_the_configured_dimensions`. Helper `cosine(first, second) -> float`.
- *Pass 2 (recorder), last in the file, relying on pass 1:*
  `test_screenshot_description_is_replayed_from_its_recording` and
  `test_embeddings_are_replayed_from_their_recording`: one `recording_hit` naming an existing file, no
  `vision_call` / `voyage_embedded`, the answer equal to the file's contents. Run alone they fail by design.
- *Cost per run:* 6 Gemini calls, 3 Voyage calls; pass 2 makes none.
- *Demo:* `make test` unchanged; `make test-live` skips without keys; with keys all pass, the log shows the
  vendor calls, then two `recording_hit` lines.

**Part 8 plan (approved Sep 27).** Planned as if Part 7 were done. An operational run: no new file, function,
dependency or setting.

- *Fresh start:* every collection deleted (`DELETE /api/collections/{name}` for each in `GET /api/collections`),
  which then answers `[]`; `backend/recordings/` absent or emptied. Blobs stay on disk (D13); dedup is by row.
- *No filename shortcut in the real path (checked while planning):* with `AI_PROVIDER=real`, `get_vision()` never
  builds `FakeVision`, so its filename-keyed fixtures are unreachable; `GeminiVision` sends only the prompt and
  the prepared image or text, and uses the filename in a log label only; the recording key leaves it out. The
  filename unit (D48) is embedded and indexed as a search unit, as designed; it produces no metadata. At run
  time the log must show a `vision_call` for every asset and no `fake_vision_*` line.
- *Recordings:* `AI_CACHE_DIR=./recordings`, git-ignored (D26 as amended); nothing is committed.
- *Left out:* `innocents_abroad.txt` (not built yet; its size and recording are decided in Phase 6).
- *Steps:* `.env` with `AI_PROVIDER=real`, both keys, `AI_CACHE_DIR=./recordings`; `make dev` (the UI against
  the real API, no mocks), API log kept to a file. Create collection `demo` in the UI and upload the 31 files
  of `../seed/demo` (21 images, 10 text files) through the upload area. All `ready`, each with a
  `vision_model`; 31 files each in `recordings/vision/` and `recordings/embed/`. Michael reads titles, tags,
  visible text (screenshot, receipt) and GPS/EXIF places and dates in the UI; quality notes go to Phase 6's
  prompt tuning, not fixed now. Then delete `demo` and upload the same files again: 62 `recording_hit`, no
  `vision_call` or `voyage_embedded`, the same metadata.
- *Cost:* about 31 Gemini describe calls (more if repairs run) and 31 Voyage calls; the replay pass none.
  Nothing deployed; the live URL stays on fake adapters until Phase 6.
- *Noted for Phase 6:* the `seed_dir` default `../seed` resolves from `backend/` to `KMS/seed`, not the folder
  beside the repo. A prompt change bumps `PROMPT_VERSION` and re-records the vision answers and the
  metadata-unit embeddings.

**Part 9 plan (approved Sep 27).** Added when the live test with real providers came up: the public URL would
spend the vendor credit for anyone who finds it. Option A of two; B (a login page with a signed session cookie)
was set aside as several times the work for the same protection. Michael's addition (D49).

- *Mechanism:* HTTP Basic Auth as HTTP middleware over the whole app, API and SPA, except `/api/health` (it shows
  only migration state, and a deployment check needs no password). Any username; only the password is checked,
  with `secrets.compare_digest`. The browser shows its own prompt on the `401` and resends the password on every
  same-origin request, so the UI is unchanged.
- *Off by default:* `app_password: str = ""`; empty lets every request through, so local dev and tests are open.
  `tests/conftest.py` pins `APP_PASSWORD=""`, as it pins `AI_PROVIDER=fake`.
- *Files:* new `api/auth.py`, `tests/integration/test_auth.py`; changed `main.py` (registers the middleware),
  `config.py`, `.env.example`, `tests/conftest.py`, `docs/api-contract.md` (one Conventions row). No new dependency.
- *Code:* `require_password(request, call_next) -> Response` (passes when the password is empty or the path is
  open; otherwise `401`, `{"detail": "Password required"}`, `WWW-Authenticate: Basic`); `basic_auth_password(header:
  str) -> str | None` (the password from a Basic header; `None` when missing, not Basic, or malformed);
  `OPEN_PATHS = {"/api/health"}`.
- *Tests:* `test_everything_is_open_when_no_password_is_set`, `test_request_without_password_gets_401_and_a_challenge`,
  `test_wrong_password_gets_401`, `test_right_password_passes`, `test_health_is_open_with_a_password_set`.
- *Teardown:* changing `APP_PASSWORD` on Railway redeploys the service and the old password stops working at once;
  emptying it opens the app again. Behind it: `AI_PROVIDER=fake`, revoking the Railway-only vendor keys, and the
  vendors' spend caps.

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
   one final fetch of asset rows by id. Snippet (contract §6.8): the best unit's kind; for `"content"` the
   chunk's text with `start_char`/`end_char`; for `"metadata"` and `"image"` the asset's description, no
   offsets. When the best unit is the filename unit (D48): kind `"filename"`, text the asset's filename,
   no offsets.
6. `GET /api/search?collection=&q=&page=`.

**Tests that pass here.** Unit 2 (RRF + grouping properties). Integration 5b (pending asset absent from
search, present once `ready`). Integration 8 (both-path hit outranks single-path hits; collection scope
holds; a text hit points at the right chunk offsets; page 2 has no repeats). Integration test of D42: in a
collection with no picture- or document-related content, "picture" ranks the images first and "document"
ranks the text files first. Integration test of D48: one word of a filename finds that asset, with a
`"filename"` snippet.

**Demo.** Seed a few hand-written text files and two images with the fake provider, then
`curl "/api/search?collection=demo&q=..."` shows ranked assets, snippets with offsets, normalised scores
and paging. Redeploy.

**Decisions to take.** `plainto` vs `websearch` tsquery (suggest `websearch`: quoted phrases and `-word`).
Text search configuration (suggest `english`). RRF k (suggest 60). (The image unit's snippet is the
description, fixed by the API contract.)

**Parts.** Agreed Sep 27. Work on branch `phase-5`, cut from `phase-4` once Phase 4 is tagged. Each part
gets its own plan, approved by Michael before its code; the next part starts only when Michael says so.
A session that picks up a part reads `CLAUDE.md`, this section, `docs/api-contract.md` §6.8 and the
design doc's "Search" section, writes the part's plan (the shape `CLAUDE.md` asks for) for approval, and
only then writes code. The approved plan goes below the table as **Part N plan (approved <date>)**.

| # | Part | Holds | Tests | Status |
| --- | --- | --- | --- | --- |
| 1 | The two search paths | `search/keyword.py`: full-text match on `tsv`, ranked by `ts_rank`, within the collection, top `UNITS_PER_PATH`. `search/vector.py`: cosine distance `<=>` to the query vector, `hnsw.ef_search` = `HNSW_EF_SEARCH` and `hnsw.iterative_scan = relaxed_order` set for the transaction only, filtered on collection and `embedding_model`, top `UNITS_PER_PATH`. Both return ranked unit hits `(unit_id, asset_id, rank)` in one shared shape, best first, with a fixed tie-break so the same query always gives the same order | Integration: each path ranks the matching unit first, stays inside the collection; the vector path skips units of another `embedding_model` | plan approved, in progress |
| 2 | Fusion and grouping | `search/fuse.py`, pure Python, no database: RRF over the two hit lists (score per unit = sum of `1 / (k + rank)` over the paths that found it), group by asset with the best unit winning (keeps its unit id, so the service can read its kind and offsets), normalised score = asset's best RRF / top RRF. Deterministic order on ties | Unit test 2: a unit on both paths outranks one on either alone; best unit wins per asset; top asset scores 1.0 | plan approved, in progress |
| 3 | Reranker interface and the search service | `Reranker` interface in `ai/interfaces.py`, a no-op implementation, `get_reranker()` in `ai/__init__.py` (always the no-op; `RERANK_ENABLED` stays unread until Phase 9, D16). `search/service.py`: the query-embedding cache (`functools.lru_cache`, `QUERY_CACHE_SIZE`, keyed on embedding model + normalised query), keyword path run at the same time as embed → vector path (thread pool of 2, one connection each), fuse, cap at `MAX_ASSETS_PER_QUERY`, slice the page, one fetch of the asset rows by id, snippets as in step 5 above, no-op rerank of the page | Unit: cache key normalisation; snippet per unit kind | plan approved, in progress |
| 4 | The endpoint | `api/search.py` with `GET /api/search?collection=&q=&page=`; `SearchResponse`, `SearchResult`, `Snippet` in `api/schemas.py` exactly as contract §6.8; router added in `main.py`. `422` for a bad collection name, an empty or blank `q`, `page` below 1; unknown collection or no match → `results: []`; a page past the end → `results: []`, `has_more: false` | Integration 5b, integration 8, the D42 test ("picture" ranks images first, "document" text files first), the D48 test (one word of a filename finds the asset, `"filename"` snippet) | plan approved, in progress |
| 5 | Demo and redeploy | The phase's **Demo** above: seed a few text files and two images with the fake provider, curl ranks, snippets with offsets, normalised scores and paging; `make deploy`; tell the frontend track (Phase 7) that the real search API is live. An operational run, no new code | the Demo | not started |

Facts already settled by the code, so no part re-decides them:

- The search settings exist in `config.py`: `UNITS_PER_PATH=100`, `HNSW_EF_SEARCH=100`, `PAGE_SIZE=20`,
  `MAX_ASSETS_PER_QUERY=100`, `QUERY_CACHE_SIZE=4096`. Phase 5 adds no setting.
- Text search configuration is `english`: migration 0001 builds `tsv` with it, and a query must use the
  same configuration to match its stems.
- Local pgvector is 0.8.6, so `hnsw.iterative_scan` is available. With `relaxed_order` the index may hand
  back rows slightly out of order, so the vector query orders by distance again after the scan.
- Search units exist only for `ready` assets: `commit_ready` writes them in the transaction that sets
  `ready`. Test 5b holds without an extra status filter.
- Unit kinds: `metadata` (title, description, tags, visible text; D42's type tags are in it through
  `assets.tags`), `filename` (D48), `image` (no body, vector only), `content` (one per chunk, with
  `start_char`/`end_char`).

Interfaces between parts: Part 1's hit shape is Part 2's input; Part 2's grouped, scored assets are Part
3's input; Part 3's service function is the only thing Part 4 calls. Each part's plan names the exact
types and signatures, and a later part's plan uses them as approved.

Open points, settled in the part named (a suggestion is not a decision until Michael takes it):

- Part 1: `websearch_to_tsquery` vs `plainto_tsquery`. Suggested: `websearch` (quoted phrases, `-word`,
  never raises on odd input). A query of stop words only gives an empty tsquery: the keyword path returns
  nothing and the vector path still answers.
- Part 2: RRF k. Settled Sep 27: 60 (the original paper's value and the common default).
- Part 3: how the query is normalised for the cache key. Suggested: trim and collapse whitespace, no
  lowercasing, so the text embedded is exactly what was typed. Tests that swap the embedder clear the cache.
- Part 3: the reranker's signature. Suggested: `rerank(query: str, documents: list[str]) -> list[int]`,
  the new order as indices, the shape of Voyage's rerank call, so the Phase 9 version drops in.
- Part 3: what the final fetch does with an id whose row is gone (collection deleted mid-query).
  Suggested: skip it.
- Part 4: integration 8 needs a unit found by one path only, which the bag-of-words `FakeEmbedder` cannot
  give (a shared word is also a close vector). Suggested: the test writes assets and units straight into
  the database with hand-picked vectors, and a stub embedder returns a chosen query vector. The D42 and
  D48 tests go through `upload` and the worker, as a real asset would.

**Part 1 plan (approved Sep 27).** Settled: `websearch_to_tsquery`; words are ANDed (websearch's default;
the user can type `or`, quotes and `-word`).

- `search/__init__.py`: `UnitHit(unit_id: int, asset_id: UUID, rank: int)`, a frozen dataclass; rank
  from 1, no gaps, the unit's place in its own path. Part 2's input is two `list[UnitHit]`, best first.
  (Alternatives: a plain tuple; carrying the raw score, which Part 2 does not use.)
- `search/keyword.py`: `keyword_search(collection: str, query: str, limit: int) -> list[UnitHit]`. The
  units of the collection matching `websearch_to_tsquery('english', query)` on `tsv`, ordered by
  `ts_rank` (default normalisation, no length adjustment; alternative: normalisation 1, which favours
  short units) descending, then unit id ascending, top `limit`. `[]` for no match, stop words only or an
  unknown collection; never raises on typed text; database errors propagate.
- `search/vector.py`: `vector_search(collection: str, query_vector: list[float], embedding_model: str,
  limit: int) -> list[UnitHit]`. One transaction: `set_config('hnsw.ef_search', HNSW_EF_SEARCH, true)`
  and `set_config('hnsw.iterative_scan', 'relaxed_order', true)`, local to the transaction so a pooled
  connection carries nothing over; a `MATERIALIZED` CTE selects the units of that collection and
  `embedding_model`, ordered by `embedding <=> query_vector` alone (so the HNSW index can serve it), top
  `limit`; the outer query re-orders by distance, then unit id. `[]` when nothing matches; database errors
  (a wrong vector length included) propagate.
- Both open their own connection through `get_engine()`, so Part 3's two threads get one each; the
  caller passes `limit` (`UNITS_PER_PATH`) and `embedding_model` (the embedder's model); `HNSW_EF_SEARCH`
  is read inside `vector_search`.
- Tests, `tests/integration/test_search_paths.py`, assets and units written straight into the database
  with hand-picked bodies and axis vectors: keyword ranks the best matching unit first; matches word
  forms; stays inside the collection; stop words only returns nothing; understands quotes and minus;
  odd input does not raise; ties break on unit id; returns at most `limit`. Vector ranks the nearest unit
  first; stays inside the collection; skips another `embedding_model`; ties break on unit id; returns at
  most `limit`; its index settings last only for the transaction. Not provable at test size: that the
  iterative scan refills a filtered result (the planner scans the small table without the index).

**Part 2 plan (approved Sep 27).** Settled: RRF k = 60.

- `search/fuse.py`, pure Python, no database, no setting: `RRF_K = 60` is a module constant (alternative: a
  smaller k such as 10, which weights top ranks more). Imports `UnitHit` from `kms.search`.
- *Rank from `hit.rank`:* Part 1 guarantees it is the place in the path, from 1 with no gaps, so a unit's
  score is the sum of `1 / (RRF_K + hit.rank)` over the paths that found it; a path that missed it adds
  nothing.
- *An asset scores by its best unit, not the sum of its units:* summing would lift long text files with many
  weak chunks over an image with one strong match.
- *One sort decides every order:* units by score descending, then unit id ascending (the tie-break both
  paths already use). Grouping walks that list and keeps each asset's first unit, so assets come out
  ordered by their best unit with no second sort.
- *Normalised score:* the asset's best-unit score over the top asset's; the top asset is exactly 1.0. No
  division by zero: a non-empty list has a top score above 0. No cut here; Part 3 caps and pages.
- *Types (frozen dataclasses):* `FusedUnit(unit_id: int, asset_id: UUID, score: float)`, one unit with its
  raw RRF score. `AssetMatch(asset_id: UUID, unit_id: int, score: float)`, one asset, its best unit's id
  (Part 3 reads the unit's kind and offsets for the snippet) and its normalised score.
- *Functions:* `fuse_units(keyword_hits: list[UnitHit], vector_hits: list[UnitHit]) -> list[FusedUnit]`,
  every unit found by either path once, best first, ties on unit id; `[]` when both are empty; never
  raises. `group_by_asset(units: list[FusedUnit]) -> list[AssetMatch]`, the first (best) unit of each asset,
  scores normalised to the first; expects `fuse_units`' order; `[]` for `[]`; never raises.
- *Interface to Part 3:* `group_by_asset(fuse_units(keyword_hits, vector_hits))`, then cap and slice.
- *Files:* new `search/fuse.py`, new `tests/unit/test_fuse.py`. No dependency, no setting.
- *Tests (unit 2), hits built with explicit ranks:* `test_unit_score_is_the_sum_of_reciprocal_ranks`
  (1st on keyword, 2nd on vector → `1/61 + 1/62`); `test_unit_on_both_paths_outranks_units_on_one_path`
  (3rd on both beats 1st on either alone); `test_one_path_alone_keeps_its_order` (an empty vector list);
  `test_equal_scores_are_ordered_by_unit_id`; `test_best_unit_wins_per_asset`;
  `test_asset_with_one_strong_unit_beats_asset_with_many_weak_units`;
  `test_top_asset_scores_one_and_the_rest_less`; `test_no_hits_give_no_assets`.

**Part 3 plan (approved Sep 27).** Settled: the cache key is the embedding model and the query trimmed with
whitespace collapsed, case kept; the reranker returns the new order as indices; an asset whose row is gone
by the final fetch is skipped; a failed query embedding fails the request (no keyword-only fallback); the
cache size is read once, when `search/service.py` is imported. The seam is kept though the no-op changes
nothing: the design names reranking as a pluggable stage, and Phase 9 then adds one class and one flag.

- *Reranker:* `ai/interfaces.py` gains `class Reranker(ABC)` with `rerank(query: str, documents: list[str])
  -> list[int]`, the new order as indices into `documents` (Voyage's rerank shape); vendor errors
  propagate. Alternative: `(index, score)` pairs; the no-op has no score and the API keeps the fused score.
  New `ai/noop.py`: `NoOpReranker(Reranker)`, returns `list(range(len(documents)))` (alternative: in
  `ai/fake.py`, but it is the production default, not a test double). `ai/__init__.py`: `get_reranker() ->
  Reranker`, a new `NoOpReranker()` each call; `RERANK_ENABLED` unread until Phase 9; no setter.
- *Types in new `search/service.py` (frozen dataclasses):* `MatchSnippet(kind: str, text: str, start_char:
  int | None, end_char: int | None)`; `FoundAsset(asset: RowMapping, score: float, snippet: MatchSnippet)`,
  the row goes to `Asset.from_row` in Part 4; `ResultPage(results: list[FoundAsset], has_more: bool)`.
- *`normalise_query(query: str) -> str`:* strip, collapse whitespace runs to one space, keep case. Never
  raises.
- *`embed_query(model: str, query: str) -> tuple[float, ...]`:* `lru_cache(maxsize=QUERY_CACHE_SIZE)`;
  `get_embedder().embed([query], "query")[0]`; `model` is an argument only to be part of the key. A tuple,
  since the cache hands the same object to every caller. Vendor errors propagate and are not cached. Tests
  that swap the embedder call `embed_query.cache_clear()`.
- *`build_snippet(row: RowMapping) -> MatchSnippet`:* from one fetched row, by the best unit's kind:
  `content` → the unit's body and offsets; `metadata`, `image` → the asset's description, no offsets;
  `filename` → the asset's filename, no offsets; any other kind raises `ValueError`.
- *`search(collection: str, query: str, page: int) -> ResultPage`, the only function Part 4 calls:*
  normalise; a `ThreadPoolExecutor(max_workers=2)` per call runs `keyword_search` in one thread and
  `embed_query` → `vector_search` (embedder's model, `UNITS_PER_PATH`) in the other; `group_by_asset(
  fuse_units(...))`; first `MAX_ASSETS_PER_QUERY`; slice `[(page-1)*PAGE_SIZE : page*PAGE_SIZE]`,
  `has_more` when assets follow the slice; one query fetches the page's assets joined to their best units
  by unit id (asset columns plus `unit_kind`, `unit_body`, `unit_start_char`, `unit_end_char`); skips a
  missing row; `get_reranker().rerank(query, [descriptions])` reorders the page, scores stay fused; logs
  `search_done collection= units_keyword= units_vector= assets= ms=`. Trusts its caller (blank query,
  `page < 1` are the API's 422). A page past the end → `ResultPage([], False)`. Database and vendor errors
  propagate. Alternatives: one shared pool of 2 (concurrent searches would queue behind each other); a
  second query for the units; the metadata unit's body for the reranker (another fetch; revisit in Phase 9).
- *Two steps of `search` as their own functions (amended Sep 27, Michael's call):* `run_both_paths(collection:
  str, query: str, model: str, limit: int) -> tuple[list[UnitHit], list[UnitHit]]`, the keyword path and
  embed → vector path at the same time on the per-call pool of 2, keyword hits first; errors propagate.
  `fetch_found_assets(page_matches: list[AssetMatch]) -> list[FoundAsset]`, the one query joining the
  page's assets to their best units, snippets built, a missing row skipped, in `page_matches`' order; `[]`
  for `[]`; database errors propagate. Paging and the rerank stay inline; each step of `search` opens with
  a comment.
- *Files:* new `ai/noop.py`, `search/service.py`, `tests/unit/test_search_service.py`; edits to
  `ai/interfaces.py`, `ai/__init__.py`. No dependency, no setting.
- *Tests (unit, no database):* `test_normalise_trims_and_collapses_whitespace`, `test_normalise_keeps_case`,
  `test_embed_query_calls_embedder_once_for_repeated_query` (a counting stub embedder),
  `test_embed_query_keys_on_model`, `test_snippet_content_has_chunk_text_and_offsets`,
  `test_snippet_metadata_and_image_use_description`, `test_snippet_filename_uses_filename`,
  `test_noop_reranker_keeps_order`. The service end to end is Part 4's integration tests.

**Part 4 plan (approved Sep 27).** Settled: a blank `q` is rejected by one check in the handler; the handler
is named `search_collection`, so it does not hide the service's `search`; `q` has no length cap (the
contract sets none). Embed errors give `500` and the service logs `search_done`, both settled in Part 3.

- *Blank `q`:* `q` is a required `str`; the handler raises `HTTPException(422, "q: must not be blank.")`
  when `q.strip()` is empty, covering `""` and spaces only; the `"field: message"` form of the existing 422
  handler. Alternative: `Query(pattern=r"\S")`, one mechanism but a message that shows the regex. A
  missing `q` is FastAPI's own 422. The query goes to the service as typed; the service normalises it.
- *Parameters:* `collection` is `Query(pattern=COLLECTION_NAME_PATTERN)` as in `list_assets`; `page` is
  `Query(ge=1)`, default 1. `page_size` in the response is `get_settings().page_size`, the setting the
  service pages by.
- *Files:* new `api/search.py`: `router = APIRouter()`; `search_collection(collection: str, q: str, page:
  int) -> SearchResponse` for `GET /api/search`: the blank check, `search(collection, q, page)`, each
  `FoundAsset` mapped to a `SearchResult` (`Asset.from_row(found.asset)`, `found.score`, a `Snippet` from
  `found.snippet`). Catches nothing; no log line (the service logs). `api/schemas.py` gains, exactly as
  contract §6.8: `Snippet(kind: Literal["metadata", "content", "image", "filename"], text: str,
  start_char: int | None, end_char: int | None)`, `SearchResult(asset: Asset, score: float, snippet:
  Snippet)`, `SearchResponse(results: list[SearchResult], page: int, page_size: int, has_more: bool)`.
  `main.py` includes `search.router`. No dependency, no setting, no contract change.
- *Tests, new `tests/integration/test_search_api.py`:* a `StubEmbedder` (model `"stub-embedder"`, returns
  the query vector a test picks) behind a fixture that calls `set_embedder` and `embed_query.cache_clear()`
  on the way in and out; `insert_asset`, `insert_unit`, `axis_vector` as in `test_search_paths.py`.
  `test_rejects_invalid_parameters` (bad collection name, missing, empty and spaces-only `q`, `page=0`:
  422 with a string `detail`); `test_unknown_collection_gives_no_results`. 5b:
  `test_pending_asset_is_absent_until_ready` (upload, not found; `run_once`, found). 8:
  `test_asset_on_both_paths_outranks_assets_on_one_path`, `test_top_result_scores_one`,
  `test_search_stays_inside_the_collection`, `test_text_hit_points_at_the_chunk_offsets`,
  `test_page_two_continues_without_repeats` (`page_size + 5` assets), `test_results_stop_at_the_cap`
  (`max_assets_per_query + 1` assets). D42: `test_picture_ranks_images_first_and_document_ranks_text_files_first`
  (photos `IMG_2101.jpg`, `IMG_2114.jpg` with different bytes, two text files with no picture or document
  words; photos because a document image also gets the `document` tag). D48:
  `test_filename_word_finds_the_asset` (`2101` puts `IMG_2101.jpg` first with a `"filename"` snippet; a
  fixture image, since an unknown text file's title is its filename and its metadata unit would match too).

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
   Two rows prove D42 with real models: "picture" tops with images, "document" tops with documents and
   text files.
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
   closeness shown by an accent bar on the card's edge (nothing dimmed, every result fully visible), image thumbnail via the file endpoint, "show more".
5. Asset detail view: metadata fields, visible text, the file. "Open in a new tab" and "Download" for the file,
   both in the detail view and on each file tile (Michael, Sep 27).
6. Empty states and the seed collection as the default selection.
7. A filename match (D48): the `"filename"` snippet kind in the TS types, a label for it on the result card,
   the filename as the snippet text with the query words marked, one mock result that shows it. The detail
   view needs no change.

**Tests that pass here.** None automated, by the test plan's choice. Manual checklist items 1, 2, 3, 4, 9
run locally.

**Demo.** The full assignment flow in the browser at `localhost:5173` with fake adapters, then once with
real adapters on the demo collection. Redeploy.

**Decisions to take.** How the mocks are served (for example static JSON behind the API client, or a
request-intercepting library). When and how the client switches from mocks to the real API. Visual
direction (minimal, one accent colour is the suggestion). Whether the detail view is a route or a drawer.
Thumbnail sizing.

**How the frontend code is written** (Michael, Sep 27, 2026). The code is simple to understand: plain React
(state in `App`, props and callbacks down, one component per file), no clever abstractions. The app itself
looks polished: styled components rather than bare browser controls. Comments only explain what the code
does; they never refer to this plan, decision numbers, parts or contract sections.
Code that sends or receives data comes first in its file: the endpoint functions at the top of the API
client and of the mock store, the functions that call the API right after the state in a component, under
a "Talks to the API" divider. A component that loads data starts with a short comment drawing the flow
(request → state → props → what draws it), so the path of a query and its results can be followed from the
top of each file.

**Frontend decisions** (F-numbers, kept here by the frontend session):

| # | Decision | Value | Status |
| --- | --- | --- | --- |
| F1 | How mocks are served | MSW (Mock Service Worker): handlers answer `/api/...` in the browser at the network level, so the real client code runs unchanged against them | decided (Sep 26) |
| F2 | Switching between mocks and the real API | `npm run dev` always uses the real API; `npm run dev:mock` sets `VITE_MOCK_API=true` and starts the mocks. Mocks never enter the production bundle and stay after Phase 5 | decided (Sep 26) |
| F3 | Visual direction | Minimal: neutral greys, one accent colour, Tailwind's indigo | decided (Sep 27) |
| F4 | Collection selector | Top bar with a dropdown (names and counts), "+ New" and "Delete" next to it | decided (Sep 27) |
| F5 | Where the selected collection lives | React state (`useState`) only; a reload goes back to the default, a new collection without uploads is lost on reload (contract §3) | decided (Sep 27) |
| F6 | Asset list layout | One column of full-width tiles: thumbnail on the left, details on the right, status in the corner; not a table of rows, not a multi-column grid | decided (Sep 27) |
| F7 | Where search lives | A wide search box at the top of the main area; submitting replaces the upload box and file tiles with the results, "Back to all files" returns | decided (Sep 27) |
| F8 | How closeness is shown | No dimming: every result, thumbnail and snippet stays fully visible. A coloured bar on each result card's left edge, strong indigo for close matches down to light grey for far ones. Replaced Sep 29 by D56 (amended): the bar is removed and the reranker's relevance is shown as a number | replaced (Sep 29) |
| F9 | Asset detail view | A large centred modal (`<dialog>`) over the page; closing returns to the list or results as they were | decided (Sep 27) |
| F10 | Open in a new tab and Download | Plain links to the file endpoint (`target="_blank"`, `download`). They do not work under the mocks (MSW never handles page navigations; the proxy answers 502) and work against the real API | decided (Sep 27) |
| F11 | Polling the file list | One repeating 2 s timer (`setInterval`) while any file is pending or processing, so a failed load does not stop it and the list recovers when the server answers again. Two slow loads may overlap; the next tick corrects any older answer | decided (Sep 27) |
| F12 | File count summary above the list | Uses the badge words: "3 files · 1 pending · 1 processing", a part left out when its count is 0 | decided (Sep 27) |
| F13 | Search before the backend has it | A 404 from the search endpoint is shown as "Search is not available on this server yet."; the error screen offers Try again and Back to all files. Retired Sep 29 by D59: the endpoint exists, so a 404 shows the server's own detail | replaced (Sep 29) |

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

1. **Reranker and relevance (D56)**: `VoyageReranker` (rerank-2.5) behind `RERANK_ENABLED` scores the first
   20 results against the query, so each card can show how close a match really is, not only where it ranks.
   Two parts, on branch `reranker`. Asked Sep 28: the top result always showed "Close match", because `score`
   is relative to the best result of the query.

| Part | What | Status |
| --- | --- | --- |
| 1 | Backend and contract: `VoyageReranker`, the relevance cache, the `relevance` order and field | done (723f1aa) |
| 2 | Frontend: the `relevance` field and order, relevance shown as a number, the closeness bar removed | done |

**Item 1 plan (approved Sep 29).** Settled: relevance is a new field, `score` unchanged; the candidates are
the first `RERANK_CANDIDATES` (20, one page) of the requested order after the filters; the reranker reads each
candidate's snippet text; every order gets relevance on its candidates, only `relevance` re-sorts by it; a
failed rerank degrades quietly; the existing code is expanded, no fake reranker (with `AI_PROVIDER=fake` the
reranker is the no-op and every `relevance` is `null`); no recording of rerank calls. Amended Sep 29 (Michael):
no cut-offs at all; relevance is shown as a score and the results are sorted by it, its visual form decided later.

- *`ai/interfaces.py`:* `Reranker.rerank(query: str, documents: list[str]) -> list[float] | None`: one
  relevance from 0 to 1 per document, in input order, or `None` when the reranker gives no relevance; vendor
  errors raised as they come.
- *`ai/noop.py`:* `NoOpReranker.rerank` returns `None`, never raises.
- *`ai/voyage.py`:* new `VoyageReranker(client: voyageai.Client, model: str)`. `rerank(query, documents) ->
  list[float]`: `[]` for no documents without a call; otherwise one `client.rerank(query, documents, model,
  truncation=True)` through `call_with_retries(..., "voyage_rerank")`, the results put back in input order by
  their `index`; `ValueError` when the count differs from the documents'. Logs `voyage_reranked documents=%d
  duration_ms=%d`.
- *`ai/__init__.py`:* `get_reranker() -> Reranker`, built once: `VoyageReranker` over `RERANK_MODEL` with its
  own Voyage client (same options as the embedder's) when `RERANK_ENABLED` is true and `AI_PROVIDER` is
  `real`; `NoOpReranker` otherwise. `ValueError` when the real one has no `VOYAGE_API_KEY`.
- *`config.py`:* `rerank_candidates: int = Field(default=20, ge=1)`, `rerank_cache_size: int =
  Field(default=2000, ge=1)` (pairs), in the search section; `rerank_enabled` stays `False` by default.
  `backend/.env.example`: `RERANK_ENABLED`, `RERANK_MODEL`, `RERANK_CANDIDATES`, `RERANK_CACHE_SIZE`.
- *`search/order.py`:* `SearchOrder.RELEVANCE = "relevance"`; `order_matches` leaves it in score order (the
  re-sort by relevance happens after the rerank).
- *`search/service.py`:* `FoundAsset` gains `relevance: float | None`, `None` from `fetch_found_assets`.
  New `rerank_with_cache(query: str, documents: list[str]) -> list[float] | None`: a module-level
  `OrderedDict` of `(rerank model, query, text) -> relevance`, at most `RERANK_CACHE_SIZE` pairs, the least
  recently used dropped; only unseen texts go to one `rerank` call; relevances in input order; `None` when the
  reranker gives `None`; vendor errors raised. New `score_relevance(query: str, found: list[FoundAsset],
  order: SearchOrder) -> list[FoundAsset]`: sets each `relevance` from the snippet texts; for `RELEVANCE`
  sorts by it, highest first (stable); unchanged when there is no relevance; on a vendor error logs
  `rerank_failed error=<type>` as a warning and returns `found` unchanged. `search()`: when the page starts
  inside the candidates, fetches the candidates and the rest of the page in one `fetch_found_assets`, scores
  the candidates, then slices the page; otherwise as before. The per-page rerank step is removed;
  `search_done` gains `reranked=`.
- *API:* `api/schemas.py` `SearchResult.relevance: float | None`; `api/search.py` default `order` is
  `relevance`, `relevance` returned. Contract: the `order` value and default, `relevance: number | null` and
  how to read it, D56.
- *Tests:* new `tests/unit/test_voyage_reranker.py`: `test_relevance_comes_back_in_input_order`,
  `test_no_documents_makes_no_call`, `test_wrong_count_raises`. `test_order.py`:
  `test_relevance_order_keeps_score_order`. `test_search_service.py` (stub reranker):
  `test_relevance_order_sorts_candidates_by_relevance`, `test_other_orders_keep_order_with_relevance`,
  `test_results_past_the_candidates_have_no_relevance`, `test_reranker_reads_snippet_text`,
  `test_rerank_error_leaves_score_order`, `test_noop_reranker_gives_no_relevance`,
  `test_switching_order_makes_no_second_rerank_call`, `test_only_unseen_texts_are_sent`,
  `test_cache_drops_least_recently_used_pair`. `test_search_api.py`: `test_default_order_is_relevance`,
  `test_page_two_has_no_relevance`. (As built: `test_results_past_the_candidates_have_no_relevance` sits in
  `test_search_api.py`, since it needs a whole search; the old `test_noop_reranker_keeps_order` is replaced.)
- *Part 2, frontend:* `api/types.ts`: `relevance: number | null`, `'relevance'` in `SearchOrder`.
  `searchView.ts`: default order `'relevance'`. `SearchOptions.tsx`: "Most relevant" first.
  `mocks/store.ts`: relevance on the first 20 mock results. Tests: none automated; checked in the browser
  (page 1, Show more, each order).

**Item 1, Part 2 plan (re-planned and approved Sep 29).** No cut-offs (Michael): the card shows `relevance` as a
plain number, two decimals, beside the match badge ("Relevance 0.69", titled "How well this result answers your
query, as judged by the reranker"); nothing when it is `null`. The closeness bar and its steps are removed (F8
replaced). A percentage was weighed; it reads as a probability, which the score is not.
- `api/types.ts`: `SearchResult.relevance: number | null`; `'relevance'` in `SearchOrder`. `searchView.ts`:
  `DEFAULT_VIEW.order` is `'relevance'`. `SearchOptions.tsx`: `{ value: 'relevance', label: 'Most relevant' }` first.
- `SearchResultCard.tsx`: the bar's `<span>` and the card's `title` removed, `pl-5` back to `p-3`; the number beside
  the badge; the header comment's data-flow line for relevance. `closeness.ts` deleted.
- `mocks/store.ts`: the first 20 results get `relevance` = the share of query words they hold; the rest `null`.
- Tests: none automated; `npm run build` and `npm run lint`; checked in the browser on the mocks and on the real
  API with the reranker on (numbers on page 1, none after Show more, each order, Most relevant the default).
2. **pg_trgm typo correction**: vocabulary table from `ts_stat`, trigram index, per-term correction before
   the keyword query. One migration, one unit test, one matrix row ("blak hair").
3. **Closest sentence of a match by meaning (D51)**: for every `semantic` result, the sentence of its
   snippet closest to the query is returned as offsets and marked in the card and the dialog. Three parts,
   on branch `ui-fixes`.

| Part | What | Status |
| --- | --- | --- |
| 1 | Backend and contract: splitter, the sentence step in the search, two snippet fields | done (20e5f2e) |
| 2 | Frontend: types, mock, card preview and dialog tint | done (5bc2032) |
| 3 | Every snippet kind: descriptions and file names too, offsets in `text`, one shared component | done (adda639) |

**Item 3, Part 1 plan (approved Sep 27).** Settled: our own embedder, not Jev; computed during the search,
only for the page; only for `semantic` results whose snippet kind is `content`; `pysbd` as the splitter (amended Sep 27:
the first regex cut `1.` off a numbered list; `nltk` Punkt kept a to-do file as one piece, `blingfire`
has no Apple Silicon build); no flag, no setting, no migration. A failed sentence embedding degrades quietly, unlike the query
embedding, which fails the request: the sentence is decoration on results the user already has.

- *New `search/sentences.py`:* `Sentence(start: int, end: int, text: str)`, a frozen dataclass, offsets
  relative to the text split, `text == source[start:end]`. `split_sentences(text: str) -> list[Sentence]`:
  one module-level `pysbd.Segmenter(language="en", clean=False, char_span=True)` finds the sentences and
  their offsets; edge whitespace (pysbd keeps it) is left out by moving the offsets; a piece with no letter or digit is dropped; `[]` for text with no words;
  never raises. The first and last piece of a passage may be half a sentence (chunks cut at a space).
  `cosine_similarity(first: Sequence[float], second: Sequence[float]) -> float`: dot product over the
  product of the lengths, plain Python; 0.0 when either has length zero; never raises. Alternative:
  `numpy`, installed through pgvector but not declared.
- *`search/service.py`:* `MatchSnippet` gains `sentence_start_char: int | None`, `sentence_end_char: int |
  None`, offsets in the file (the passage's `start_char` plus the sentence's own); `build_snippet` sets
  both `None`. New `mark_closest_sentences(query_vector: Sequence[float], found: list[FoundAsset]) ->
  list[FoundAsset]`: the results with `match` `SEMANTIC` and snippet kind `content` are split, every
  sentence embedded in one `embed(sentences, "document")` call, each such snippet replaced with its
  closest sentence's offsets; same order; no call when none qualifies; on a vendor error logs
  `sentence_match_failed error=<type>` as a warning and returns `found` unchanged, the only error caught.
  `search()` calls it after the rerank with `embed_query(model, query)` (a cache hit); `search_done` gains
  `sentences=`.
- *API:* `api/schemas.py` `Snippet` gains `sentence_start_char: int | None`, `sentence_end_char: int |
  None`; `api/search.py` maps them. Contract §6.8: the two fields, set only when `kind` is `"content"` and
  `match` is `"semantic"`, inside `start_char`–`end_char`, otherwise `null` (also when the sentence could
  not be found); D51 in the decision table.
- *Tests:* new `tests/unit/test_sentences.py`: `test_splits_after_sentence_punctuation`,
  `test_splits_at_line_breaks`, `test_numbered_list_item_stays_whole`,
  `test_abbreviation_does_not_end_a_sentence`, `test_offsets_point_back_into_the_text`, `test_edge_whitespace_is_left_out`,
  `test_pieces_without_words_are_dropped`, `test_text_without_words_gives_no_sentences`,
  `test_cosine_of_same_direction_is_one`, `test_cosine_of_zero_vector_is_zero`. `test_search_service.py`
  (stub embedder): `test_closest_sentence_marked_on_semantic_passage`,
  `test_exact_and_partial_results_get_no_sentence`, `test_non_content_snippet_gets_no_sentence`,
  `test_one_embed_call_for_the_whole_page`, `test_no_call_when_no_result_qualifies`,
  `test_embed_error_leaves_results_without_sentence`. `test_search_api.py`:
  `test_semantic_text_hit_points_at_closest_sentence`, `test_exact_hit_has_no_sentence`.

**Item 3, Part 2 plan (approved Sep 27).** `api/types.ts`: the two fields on `Snippet`; `mocks/store.ts`:
`null` for both. `SearchResultCard.tsx`: with a sentence, the preview starts at it ("…" before) instead of
at the first query word, and the sentence is tinted teal, the semantic badge's colour, titled "Closest in
meaning to your query". `AssetDetailDialog.tsx`: the passage split into before, sentence, after; the
sentence tinted the same way; the scroll target is the sentence, then the first marked word, then the
passage start. No new files; tested in the browser (a semantic text result, an exact one, an image, and
the dialog of each).

**Item 3, Part 3 plan (approved Sep 27).** Found in the browser: most semantic results show a description or
a file name, not a passage, so Parts 1–2 marked almost nothing. Every snippet kind now gets its sentence
through one path. Backend: `mark_closest_sentences` takes every `SEMANTIC` result, splits `snippet.text`,
and stores the closest sentence's offsets counted in `text` (no `start_char` added); a file name comes out
of `pysbd` as one piece, so the whole name is marked. The fields are renamed `sentence_start` /
`sentence_end` in `MatchSnippet`, `api/schemas.py`, `api/types.ts` and contract §6.8, since they are no
longer file offsets. Frontend: new `components/ClosestSentenceText.tsx`, `ClosestSentenceText({ text,
query, sentence, sentenceRef?, firstMarkRef? })` and `SentenceRange { start, end }`: slices `text` once,
marks the sentence in teal with the tooltip, the rest through `HighlightedText`; with `sentence` null it is
`HighlightedText`. `SearchResultCard`: one path for every kind, the preview starts at the sentence
("…" before it). `AssetDetailDialog`: the one place kinds differ, mapping the sentence to where the
snippet's text shows (the passage in the file text, scrolled to; the description; the file name line).
Tests: `test_non_content_snippet_gets_no_sentence` replaced by `test_description_snippet_gets_a_sentence`
and `test_filename_snippet_is_one_sentence`; offsets in the unit and integration tests are counted in
`text`.

4. **Text in an image as its own search unit (D52)**: a word read from an image is shown as "In the text
   in the image" and filtered by its own chip, not as part of the description. Two parts, on branch `ui-fixes`.

| Part | What | Status |
| --- | --- | --- |
| 1 | Backend and contract: the new unit, its snippet, the `found_in` value | done (adda639) |
| 2 | Frontend: type, card label, chip, dialog, mock; browser check | done (adda639) |

**Item 4, Part 1 plan (approved Sep 27).** Settled: the unit kind is `visible_text`, after the field it holds;
its own filter chip; no migration; existing collections are wiped and uploaded again, no reindex command.
- *`ingest/worker.py`:* `metadata_body(metadata) -> str` returns title, description and tags only.
  `build_units(...)`, same signature, adds `Unit("visible_text", 0, None, None, text, text)` after the `image`
  unit for an image whose `visible_text` is not empty; none for an image without text or for a text file.
- *`models.py`:* the `kind` column comment lists `visible_text`.
- *`search/__init__.py`:* the `UnitHit.unit_kind` docstring lists `visible_text`.
- *`search/service.py`:* `build_snippet` returns `MatchSnippet("visible_text", row["visible_text"], None, None,
  None, None)` for the new kind; the closest-sentence step takes it like any other text.
- *API:* `"visible_text"` added to the `Literal` of `Snippet.kind` in `api/schemas.py` and of `found_in` in
  `api/search.py`. Contract §6.8: the new `kind` and `found_in` value; D52 in the decision table.
- *Tests:* `test_worker.py`: `test_image_text_gets_its_own_unit`, `test_image_without_text_has_no_image_text_unit`,
  `test_metadata_unit_leaves_out_image_text`. `test_search_service.py`: `test_visible_text_snippet_is_the_image_text`.
  `test_search_api.py`: `test_word_only_in_image_text_is_found_in_visible_text`,
  `test_found_in_without_visible_text_drops_image_text_match`.

**Item 4, Part 2 plan (approved Sep 27).** `api/types.ts`: the new kind. `SearchResultCard.tsx`: label "In the
text in the image"; the extra "Text in the image" block is hidden when the snippet already is that text.
The preview of a `visible_text` snippet starts just before its first query word, as a passage does,
in the monospace style of the image-text block (amended Sep 28: the text is often long, and the matched word
fell below the card's three lines). `SearchOptions.tsx`: a "Text in image" chip, and the "Image" chip removed (amended Sep 28, Michael: a
pixel match is always searched and cannot be filtered out; the API keeps `found_in=image`); `searchView.ts`: `visible_text` in the default
`foundIn`, so the new part is searched unless the user turns it off. `AssetDetailDialog.tsx`: the closest sentence of a
`visible_text` snippet is marked in the image-text section. `mocks/store.ts`: one mock result of the new kind.
Tested in the browser: "Israeli" with every chip on and with "Text in image" off; the Bamba card keeps "In the
description".

5. **Upload and search layout**: uploads leave the page flow, as in Google Drive; the search box is the
   centre of the page, as on Google's home page. Frontend only, no contract change, on branch `ui-layout`.
   One part, Michael's ideas (Sep 28).

| Part | What | Status |
| --- | --- | --- |
| 1 | Upload window, drop anywhere, upload panel; Retry all; centred search; larger text | done (e3ec848) |
| 2 | Filters set before searching; an empty home page with "Browse all" | done (e3ec848) |

**Item 5 plan (approved Sep 28).**
- *Uploads in `App`:* state `uploads: UploadItem[]`, `uploadDialogOpen`, `filesVersion: number`, and
  `handleFiles(files: File[])`: every file to the collection selected when it arrived, in parallel, each
  updating its own item; when one ends, `filesVersion` + 1 and the collections reload. Kept in `App`, not
  in `CollectionFiles`, so an upload survives a switch of collection. An **Upload** button in the top bar.
- *`api/client.ts`:* `uploadAsset(collection, file, onProgress?)` on `XMLHttpRequest` (fetch cannot report
  bytes sent), same `ApiError`s; `errorDetail(status, bodyText)` shared with `send()`.
- *New components:* `UploadDialog({ open, collection, onFiles, onClose })`, the drop box in a `<dialog>`;
  `PageDropZone({ collection, onFiles })`, `window` drag listeners and a full-page overlay, skipping a drop
  the dialog's box took; `UploadPanel({ uploads, onClose })` with `UploadItem`, bottom-right, overall bar by
  bytes, a row per file (bar, tick, duplicate note, refusal), foldable, closable once nothing uploads.
  `UploadNotices.tsx` removed; `UploadArea` loses `uploadingCount`.
- *`CollectionFiles`:* no upload code; `filesVersion` prop reloads the list; " · N failed" in the summary and
  **Retry all failed (N)**, `handleRetryAll()` with `allSettled`, a red line naming how many could not be
  retried.
- *Search:* the logo leaves the top bar; on the home view a large logo and a large pill-shaped box are
  centred with the button below; with results showing both shrink into one row (`SearchBar` `compact`).
- *Text:* root font 16.5px (everything about 3% larger), and Tailwind's `text-xs`…`text-xl` one small step up.
- *Tests:* none automated; UI checklist section 3 rewritten; checked in the browser on the mocks.

**Item 5, Part 2 plan (approved Sep 28).** The filters (`SearchOptions`) move from `SearchResults` into
`CollectionView`, under the search box on every view; set before a search they send nothing and are used by
the next one, and they never touch the file list. The home page shows no files: a "Browse all ⌄" button under
Search (Michael) opens the list under the filters, "Hide all" closes it (`browsing` state); "Back to all files"
in the results opens it too. `CollectionFiles` stays mounted and hidden otherwise. `SearchResults` loses
`onViewChange`; its reloading spinner is derived from a `shownView` state (the view of the cards on screen)
instead of being set by the chip handler, and "Show more" waits while it differs.
Amended Sep 28 (Michael): on the home page the filters are behind a "Filters" button with the adjustments
(sliders) icon, beside "Browse all" (`filtersOpen` state, closed at first); with results showing they are
always open and the button is not shown. New icon: `AdjustmentsIcon` (Heroicons adjustments-horizontal).

6. **Cancel on the password prompt (D53)**: after Cancel on the browser's password prompt the UI could load
   from the browser cache while every request failed with a `401`, and nothing said so. On branch
   `password-cancel`. Found Sep 28.

| Part | What | Status |
| --- | --- | --- |
| 1 | Backend: the SPA's pages sent with `Cache-Control: no-cache` | done (faa69ff) |
| 2 | Frontend: a "Password needed" screen on any `401` | done (faa69ff) |

**Item 6, Part 1 plan (approved Sep 28).** `main.py`: the `spa()` route sends every file it serves
(`index.html` and the other files at the root of the build) with `Cache-Control: no-cache`. The hashed files
under `/assets` keep the default caching; they are only reached through `index.html`. No new setting, file
or dependency. Test in `tests/integration/test_auth.py`: `test_spa_index_is_sent_with_no_cache` (on `/` and
on a deep SPA path).

**Item 6, Part 2 plan (approved Sep 28).** `api/client.ts`: `onPasswordNeeded(listener: () => void): void`
registers one listener; `send()` and `uploadAsset()` call it on a `401` and still throw
`ApiError(401, "Password needed. Reload the page to enter it.")`. New `components/PasswordNeeded.tsx`:
`PasswordNeeded()`, a full-page `StatusMessage` with a **Reload** button (`window.location.reload()`, the one
way to bring the browser's prompt back). `App.tsx`: a `passwordNeeded` state, set by the listener it
registers on mount; while true, `<PasswordNeeded />` replaces the whole app. Thumbnails (`<img>`) never reach
the listener; the collections load on every page open does. Tests: none automated; checked in the browser
(login with the password; the password changed on a running server, a search, Cancel, the screen, Reload
brings the prompt back).

7. **Voyage batches in parallel (D54)**: a 2.5 MB text file (about 1,840 chunks, 19 Voyage calls) took
   one to two minutes, most of it the Voyage calls made one after another. On branch `parallel-embed`.
   Found Sep 28.

| Part | What | Status |
| --- | --- | --- |
| 1 | Backend: the batches of one `embed()` call run in parallel, capped by `EMBED_PARALLEL_CALLS` | done (2cf1ecc) |

**Item 7, Part 1 plan (approved Sep 28).** Not in scope: the Gemini call, describing and embedding at the
same time, batch sizes. No new file, no new dependency.

- *`ai/voyage.py`:* `VoyageEmbedder.__init__(self, client, model, dims, parallel_calls: int)` keeps the cap.
  `embed(inputs, input_type) -> list[list[float]]`: same signature, return and errors as before; the batches
  run in a `concurrent.futures.ThreadPoolExecutor` of `min(batches, parallel_calls)` threads, made per call;
  the vectors are joined in input order; if a batch still fails after its retries, the error of the first
  failed batch in input order is raised once the calls in flight have finished. The `voyage_embedded` log
  line gains `parallel=%d`.
- *`config.py`:* `embed_parallel_calls: int = 20`, at least 1 (`Field(ge=1)`), in the AI section.
- *`ai/__init__.py`:* passes `settings.embed_parallel_calls` to `VoyageEmbedder`.
- *`backend/.env.example`:* `EMBED_PARALLEL_CALLS=20` with a one-line comment.
- *Tests in `tests/unit/test_voyage_embedder.py`:* the fake client is made safe across threads, each vector
  filled from its own input rather than a shared counter; the existing tests are kept.
  `test_batches_run_at_the_same_time` (the fake's calls wait at a `threading.Barrier` for 3 batches, so
  they pass only together); `test_parallel_calls_never_exceed_the_setting` (cap 2, 5 batches, at most 2 in
  flight); `test_a_failed_batch_fails_the_whole_call` (a permanent error in one batch is raised).
- *Demo:* upload `pg1184.txt` (2.8 MB) again and compare `voyage_embedded … duration_ms` with the one-to-two
  minutes before. Its old asset row and recordings were deleted Sep 28 so that it runs for real.
  Measured Sep 28, real vendors, 20 calls, no retries: embedding 83.1 s one at a time, 25.9 s at 10,
  20.3 s at 20; whole file 93.6 s, 40.7 s, 31.4 s. Default kept at 20.

8. **Sift brand, palette and light/dark theme (D55)**: the Sift logos, favicons and colours in the UI, both
   themes with a toggle. On branch `sift-brand`. Asked Sep 28.

| Stage | What | Status |
| --- | --- | --- |
| 1 | Brand: assets in place, Poppins, `sift`/`ink` scales and role colours (light), components on roles, lockup logo | done |
| 2 | Dark theme: dark role values, the inline theme script, `theme.ts`, `ThemeToggle`, the logo per theme | done |

**Item 8 plan (approved Sep 28).**
- *Palette.* `sift`: 50 `#FEF3EC`, 100 `#FDE3D3`, 200 `#FAC6A7`, 300 `#F6A274`, 400 `#F7874A`, 500 `#F0763A`, 600
  `#D8602A`, 700 `#B34B20`, 800 `#8C3B1C`, 900 `#6B2F18`. `ink`: 50 `#F8F4EB`, 100 `#F6F1E7`, 200 `#ECE5D6`, 300
  `#D3CCBD`, 400 `#A9A294`, 500 `#5E6773`, 600 `#33414F`, 700 `#2B3845`, 800 `#1B2631`, 900 `#0E151C`. Picked from
  the artwork: sift 400/500, ink 50/100/200/400/600/700/800/900; the rest derived and checked in the browser.
- *Roles (light / dark):* `page` ink-50 / ink-900; `surface` white / ink-800; `surface-hover` ink-100 / ink-700;
  `border` ink-200 / ink-700; `border-strong` ink-300 / ink-600; `text` ink-900 / ink-100; `text-muted` ink-500 /
  ink-400; `text-subtle` ink-400 / ink-500; `accent` and `accent-hover` sift-500 and sift-400 in both; `on-accent`
  ink-800 in both; `accent-text` sift-700 / sift-400; `accent-muted` sift-300 in both; `accent-soft` and
  `accent-soft-text` sift-100 and sift-800 / sift-900 and sift-200; `danger` and `danger-soft` red-700 and red-50 /
  red-400 and red-950; `success` and `success-soft` green-700 and green-50 / green-400 and green-950; `meaning` and
  `meaning-soft` teal-900 and teal-100 / teal-100 and teal-900. Dark values are tuned in the browser.
- *Stage 1.* The kit moves from the repo root to `frontend/brand/`. Into `frontend/public/`: Sift's `favicon.svg`
  (replaces Vite's), `favicon.ico`, `favicon-16x16.png`, `favicon-32x32.png`, `apple-touch-icon.png`,
  `android-chrome-192x192.png`, `android-chrome-512x512.png`, `maskable-icon-512x512.png`, `site.webmanifest`,
  `og-image.png`. Into `frontend/src/assets/`: `sift-lockup-compact-on-light.svg`,
  `sift-lockup-compact-on-dark.svg` (and the full logos, see the amendment below). Deleted, unused: `public/icons.svg`,
  `src/assets/hero.png`, `src/assets/vite.svg`. `index.html`: icon, manifest, `theme-color`, og and twitter tags
  (`https://api-production-6776.up.railway.app/og-image.png`). New dependency `@fontsource/poppins`, weights
  400/500/600/700 imported in `main.tsx`; `--font-sans` is Poppins. `index.css`: the scales and the roles' light
  values. Every component moves from `gray-*`, `indigo-*`, `red-*`, `green-*`, `teal-*` classes to the roles;
  orange fills take `on-accent` text. `CollectionView.tsx`: the logo is an `<img alt="Sift">` of the full lockup on
  the home page and the compact lockup with results; `StackIcon` is removed from `icons.tsx`.
  Amended Sep 28 (Michael): the home page shows the full logo instead, the word under the sifter
  (`sift-logo-on-light-800.png` and `-on-dark-800.png` in `src/assets/`; the 744 KB SVG is too heavy), `h-64`; the
  compact lockup stays above results. The home search box and the filters under it widen from `max-w-2xl` to
  `max-w-3xl`, so the placeholder fits in Poppins. Phone width is not a concern. The home layout sits higher
  (no extra top padding, `gap-5`, `pb-2`) so the filters panel fits below it; nothing shrinks when it opens.
  Amended Sep 28 (Michael): Browse all uses the compact layout (`compact` is `activeSearch !== null ||
  browsing`), so the cards start near the top; the logo becomes a `<button aria-label="Home">` that clears the
  search and the list; Browse all no longer reads "Hide all", and a "Hide all" button right-aligned above the
  list does the same as the logo. Every switch between the layouts animates with the
  browser's View Transitions API: `changeLayout(update: () => void): void` in `CollectionView.tsx` runs the state
  change in `document.startViewTransition` with `flushSync`, or directly when the API is missing or reduced motion
  is set; never throws. `index.css` names the logo (`sift-logo`) and the search box (`search-box`), sets about
  400 ms, and keeps the logo's proportions while it cross-fades. `framer-motion` and hand-written FLIP were weighed.
- *Stage 2.* `index.css`: the dark values under `[data-theme="dark"]`. `index.html`: an inline script sets
  `data-theme` on `<html>` before the first paint, from `localStorage` key `sift-theme`, else the OS setting. New
  `src/theme.ts`: `type Theme = 'light' | 'dark'`; `currentTheme(): Theme` reads `data-theme` (never throws);
  `applyTheme(theme: Theme): void` sets `data-theme`, saves the choice (a storage error is ignored) and updates
  `theme-color`. New `components/ThemeToggle.tsx`: `ThemeToggle({ theme, onToggle })`, a round icon button, moon
  in light, sun in dark, labelled "Switch to dark theme" / "Switch to light theme". `icons.tsx`: `SunIcon`,
  `MoonIcon` (Heroicons). `App.tsx`: `theme` state from `currentTheme()`, the toggle at the header's far right,
  `theme` passed to `CollectionView`, which picks the on-light or on-dark lockup.
- *Stage 2, tuned in the browser (Sep 28):* dark `accent-soft` is the brand orange mixed 22% into the dark
  surface (solid `sift-900` read as brown); the dark block sets `color-scheme: dark` so scrollbars and form
  controls are dark too; the red Delete button's text is `text-surface` (white on red in light, Ink on the lighter
  red in dark, where white was too faint).
- *Tests:* none automated; checked in Chrome per stage (home and compact bar at desktop and phone widths, buttons,
  dialogs, uploads, chips, closeness bars, the favicon; in Stage 2 the same in dark, the toggle, the choice kept
  over a reload, the OS setting when nothing is saved, no light flash on a dark load, the password screen in both),
  plus `npm run build` and `npm run lint`.

9. **Retry policy chosen by the caller (D57)**: one retry policy served every vendor call, so a rate-limited
   Voyage call could hold a search for about 21 s (4 attempts, waits of about 1, 4 and 16 s, 60 s timeouts),
   and `errors.py` read every vendor's errors in one place. One part, on branch `retry-policy`, from
   `reranker` (it edits `VoyageReranker`). Found Sep 29, while planning item 1.

| Part | What | Status |
| --- | --- | --- |
| 1 | `RetryPolicy` and three named policies, a classifier per vendor, `policy` on every vendor call, the timeout with the policy | done (a4a3964) |

**Item 9 plan (approved Sep 29).** Settled: the policy is a required parameter of every vendor call, chosen at
the call site; constants in code, not settings; the worker's Voyage timeout goes from 60 to 120 s (one timeout
per policy for both vendors; a timeout per vendor in the policy was weighed); the jitter is up to one first
wait, not a fixed second. No new dependency, no migration, no contract change.

| Policy | Attempts | First wait | Longest server wait honoured | Timeout per request | Used by |
| --- | --- | --- | --- | --- | --- |
| `BACKGROUND_POLICY` | 4 | 1 s (then 4, 16) | 60 s | 120 s | worker, CLI |
| `INTERACTIVE_POLICY` | 2 | 0.5 s | 1 s | 5 s | search query embedding |
| `OPTIONAL_POLICY` | 1 | none | none | 3 s | closest-sentence embedding, rerank |

The worst case at search time is then about 11 s for the query (two 5 s attempts and the wait) and 3 s for
each optional call, against 21 s of waits alone and 60 s per hung call before. Voyage answers a query
embedding or a 20-text rerank in well under a second, so the timeouts only cut calls that are really lost.

- *`ai/errors.py`:* `RetryPolicy(max_attempts: int, first_wait_seconds: float, max_server_wait_seconds:
  float, timeout_seconds: float)`, frozen dataclass; `ErrorVerdict(retryable: bool, server_wait_seconds:
  float | None)`, frozen dataclass; the three policies. `call_with_retries(call, description, classify:
  Callable[[Exception], ErrorVerdict], policy: RetryPolicy) -> T`: waits `first_wait × 4^(n−1)` plus up to
  `first_wait` of jitter, or the server's wait when it gave one; raises at once when the error is not
  retryable or the server asks for more than `max_server_wait_seconds`; raises the last error when the
  attempts run out; logs `vendor_retry` as now. `ErrorKind`, `classify`, `server_retry_delay`,
  `MAX_CALL_ATTEMPTS` and `MAX_SERVER_WAIT_SECONDS` removed; no SDK imported.
- *`ai/gemini.py`:* `classify_gemini_error(error: Exception) -> ErrorVerdict`: Gemini 429, 500, 502, 503,
  504 and `httpx.TransportError` retryable, anything else not; the server wait read from `RetryInfo`.
  `is_overloaded(error: Exception) -> bool`: a Gemini 429 or 503, for the model fallback. `describe(...,
  policy)` sets the request's timeout from the policy (`GenerateContentConfig.http_options`).
  `GEMINI_REQUEST_TIMEOUT_SECONDS` removed.
- *`ai/voyage.py`:* `classify_voyage_error(error: Exception) -> ErrorVerdict`: today's Voyage rules, no
  server wait. `VoyageClients(api_key: str)`, `for_timeout(seconds: float) -> voyageai.Client`: one client
  per timeout, built on first use with the SDK's retries off, safe across threads. `VoyageEmbedder(clients:
  VoyageClients, model, dims, parallel_calls)` and `VoyageReranker(clients: VoyageClients, model)`;
  `embed(..., policy)` and `rerank(..., policy)` take the client for the policy's timeout.
  `VOYAGE_REQUEST_TIMEOUT_SECONDS` removed.
- *`ai/interfaces.py`:* `Vision.describe`, `Embedder.embed` and `Reranker.rerank` gain `policy: RetryPolicy`.
  `ai/fake.py` and `ai/noop.py` take and ignore it; `ai/recorded.py` passes it to the real adapter and leaves
  it out of the recording's key.
- *`ai/__init__.py`:* one `VoyageClients` shared by `get_embedder()` and `get_reranker()`; the Gemini client
  built without a fixed timeout.
- *Callers:* `ingest/worker.py` and `cli.py` pass `BACKGROUND_POLICY`; `search/service.py`: `embed_query`
  `INTERACTIVE_POLICY`, `mark_closest_sentences` and `rerank_with_cache` `OPTIONAL_POLICY`.
- *Tests:* `test_errors.py` rewritten over a stub classifier: `test_retries_a_retryable_error_then_succeeds`,
  `test_not_retryable_error_is_raised_at_once`, `test_gives_up_after_the_policy_attempts`,
  `test_waits_as_long_as_the_server_asks`, `test_server_wait_over_the_policy_cap_is_raised_at_once`,
  `test_one_attempt_policy_never_retries`. Today's classification tests move to `test_gemini_vision.py`
  (`classify_gemini_error`, `is_overloaded`) and `test_voyage_embedder.py` (`classify_voyage_error`). New:
  `test_request_timeout_follows_the_policy` (Gemini), `test_client_timeout_follows_the_policy` and
  `test_one_client_per_timeout` (Voyage), `test_query_embedding_uses_interactive_policy` and
  `test_sentences_and_rerank_use_optional_policy` (search service), `test_worker_calls_use_background_policy`.
  The test stubs of every adapter gain the `policy` parameter. (As built: the Gemini tests also check that a
  blocked answer is not retryable; the live tests pass `BACKGROUND_POLICY`.)

10. **Demo mode (D58)**: the demo is shared, so a visitor must not be able to delete its collection. On branch
    `demo-mode`, one part.

- *`config.py`:* `demo_mode: bool = False` (`DEMO_MODE`), in the serving section; documented in `.env.example`.
- *`api/schemas.py`:* `AppConfig(demo_mode: bool)`.
- *`api/app_config.py` (new):* `GET /api/config -> AppConfig`, the setting as it is. A new endpoint rather than a
  field in `/api/health`: health is not a product call and is open without the password.
- *`api/collections.py`:* `delete_collection` raises `HTTPException(403, "Deleting collections is not allowed in
  demo mode.")` before deleting anything while `demo_mode` is on. *`main.py`:* registers the router.
- *`docs/api-contract.md`:* §6.10 `GET /api/config`; `403` added to §6.7; §7 and §8 rows.
- *Frontend:* `AppConfig` type and `getAppConfig(): Promise<AppConfig>`; `App.tsx` reads it once on load into
  `demoMode` (a failed call leaves it `false`); the Delete button is `disabled` and greyed out. Amended Sep 29
  (Michael): the browser's `title` tooltip waited and went unnoticed, so hovering now shows a styled hint bubble
  at once, "Deleting collections is not allowed in demo mode", right-aligned under the button; CSS only
  (Tailwind `group-hover` on a wrapping `<span>`, which a disabled button lets the mouse through to), no touch
  support. Amended Sep 29 (Michael): a "Demo" pill on the logo's top-right corner on the home page, and smaller,
  centred above the mark beside results, so a visitor sees at once that this is a demo; `CollectionView` takes
  a new `demoMode: boolean` prop from `App.tsx`. It does not glide with the logo, and clicks pass through it.
  The mock handler for `GET /api/config` returns `demo_mode: false`.
- *Tests (`test_assets_api.py`):* `test_config_reports_demo_mode` (off and on), `test_delete_refused_in_demo_mode`
  (403, the detail, the collection still there), `test_delete_allowed_outside_demo_mode`. Browser check with
  `DEMO_MODE=true`.
- Per-asset delete does not exist and stays out (Michael, Sep 29).

11. **Review fixes before hand-over (D59)**: an external-review pass (code review, tests, a browser run) before the
    code is sent out. On branch `review-fixes`, five parts, approved together Sep 29.

| Part | What | Status |
| --- | --- | --- |
| 1 | The SPA route serves only files inside the build | done |
| 2 | `make test` independent of `DEMO_MODE` in `.env` | done |
| 3 | The built SPA untracked: `.gitignore` path fixed; Michael runs `git rm -r --cached backend/src/kms/static` | done |
| 4 | Docs in line with the code, smallest edits | done |
| 5 | Robustness: early `413`, `503` on a failed query embed, recordings, "Show more", `q` length | done |

- *Part 1, `main.py`:* `spa(path)` resolves `static / path` and serves it only when it is a file inside
  `static.resolve()`; anything else gets `index.html`, as an unknown path does. `StaticFiles(html=True)` was weighed:
  it drops the `no-cache` header the password prompt needs and answers unknown paths with 404. Tests
  (`tests/unit/test_spa.py`): `test_spa_serves_a_file_of_the_build`, `test_spa_never_serves_a_file_outside_the_build`.
- *Part 2, `tests/conftest.py`:* `DEMO_MODE=false` pinned beside `WORKER_ENABLED`, `AI_PROVIDER` and `APP_PASSWORD`.
- *Part 3, `.gitignore`:* `backend/kms/static/` becomes `backend/src/kms/static/`. The Dockerfile builds the SPA
  itself; a fresh clone has no UI on :8000 until `npm run build`.
- *Part 4:* README (settings line; the search units as built; the reranker as built, out of "left out for scope";
  "ice cream" finds the gelato photo and the note that only says "gelato", in place of the "black hair" photo the
  demo does not have); system design (reranker built, scores the snippet text); contract (`503`, `q` limit, the
  relevance row, no phase wording); `docker/entrypoint.sh` comment; `client.ts` no longer remaps a search `404`.
- *Part 5a, `api/assets.py`:* `reject_oversized_upload(request, call_next) -> Response`, registered in `create_app()`
  inside the password check: a `POST /api/assets` whose `Content-Length` is over `max_upload_bytes` plus
  `MULTIPART_OVERHEAD_BYTES` (64 KiB) gets the handler's `413` before the body is read; no or an unreadable header
  passes to the handler's own check. Test: `test_upload_over_the_limit_is_refused_before_it_is_read`.
- *Part 5b, `search/service.py`:* `QueryEmbeddingFailed(Exception)`, raised by `embed_query` from any embedder
  error (chained); `api/search.py` answers it with `503`, "Search is unavailable: the embedding service did not
  answer. Try again in a moment." A keyword-only fallback was weighed (friendlier, a larger change to the flow).
  Test: `test_search_answers_503_when_the_query_cannot_be_embedded`.
- *Part 5c, `config.py` and `ai/recorded.py`:* `ai_cache_dir` defaults to `""` (off); `.env.example` keeps
  `./recordings` for local work. `write_recording(path: Path, recording: dict) -> None` writes to a temporary file in
  the same folder and renames it into place; raises `OSError`. Test: `test_recording_is_written_whole`.
- *Part 5d, `SearchResults.tsx`:* the page-1 effect keeps its `AbortController` in a ref (`viewRequests`); "Show
  more" and "Try again" pass its signal, so a view change aborts them; an answer that lands as the request is
  aborted is dropped. Browser check.
- *Part 5e, `api/search.py`:* `q: Annotated[str, Query(max_length=MAX_QUERY_CHARS)]`, `MAX_QUERY_CHARS = 500`, a
  constant, not a setting. Test: a 501-character query added to `test_rejects_invalid_parameters`.

12. **Checklist follow-ups (D60)**: small fixes from the three checklist agents run after item 11. On branch
    `review-fixes`, one part; asked by Michael Sep 29 to plan and implement together. What is not fixed here is
    written to `Smart_Search/flaws.md`, so the state at hand-over is stated honestly.

- *`main.py`, `spa(path)`:* a path starting with `api/` gets `404 {"detail": "Not Found"}`, so a mistyped API URL
  never returns the page; a path that cannot be resolved (`ValueError`, e.g. a NUL byte) is treated as unknown and
  gets `index.html`. Tests (`test_spa.py`): `test_unknown_api_path_is_a_json_404`,
  `test_null_byte_path_gets_the_index`, and `test_spa_index_is_sent_with_no_cache` moved here from `test_auth.py`,
  on the temporary build, so a clone without a built UI passes.
- *`main.py`, `flatten_validation_error`:* the field is the last string in the error's location, so a repeated
  parameter reports `match: …`, not `0: …`. Test: `test_invalid_filter_value_names_the_parameter`.
- *`ingest/worker.py`, `record_failure`:* a `pydantic.ValidationError` is stored as "The AI model's answer did not
  match the expected format."; other errors keep `"<ErrorClass>: <message>"`; the log line carries the raw error.
  Tests: the two `test_worker.py` assertions on `error` follow the new text.
- *`frontend/src/components/SearchBar.tsx`:* the input takes `maxLength={500}`, the server's limit.
- *Docs:* README (authentication beyond one shared password is out of scope; `RERANK_ENABLED` acts only with
  `AI_PROVIDER=real`); TESTING.md (the compose profile, no CI yet, rerank built, the Claude Code sentence);
  system-design (the five unit kinds, dedup unique on `(collection, sha256)`, deploy by `railway up`); contract
  and FastAPI title "Sift"; `health.py` names; `Unit` docstring lists `visible_text`.

Each is its own gate; each can be skipped without touching anything else.

---

## Test-to-phase map

| Test (test plan) | Phase |
| --- | --- |
| Smoke: health through test client (not in plan) | 0 |
| 1 Chunker | 3, with the worker (D44) |
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
| Found by kind: "picture" → images, "document" → text files (D42, not in plan) | 5 |
| Found by file name: a filename word → that asset, `"filename"` snippet (D48, not in plan) | 5 |
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
  file served from the volume with `ETag` and `immutable` cache headers. Merged to `main` and tagged `phase-2` on
  Sep 27, 2026.

### Phase 3 — Sep 27, 2026

- **Built.** `ai/schema.py` (`Metadata`, `normalise` with the fixed type tags), `ai/interfaces.py` (`Vision`,
  `Embedder`), `ai/fake.py` with the seed fixtures, `ingest/images.py` (prepared JPEG, photo date and place),
  `ingest/summary_source.py`, `ingest/chunker.py`, `ingest/worker.py` (claim, process, commit guarded by the lease,
  failed attempts, reaper), `ingest/pool.py` (`WorkerPool`: worker threads, one listener, the reaper every minute),
  `kms worker`, `kms/logs.py`, and the filename unit. Worked on branch `phase-3`.
- **Deviations.** The chunker was built with the worker, not at the end (D44), and is naive (D46). `run_forever()`
  became `WorkerPool._work_loop` in `ingest/pool.py`, which also holds the listener. Added in the phase: photo date and
  place for the vision call (D45), the filename unit (D48, with the `"filename"` snippet kind in the contract for
  Phases 5 and 7), MPO phone photos accepted as `image/jpeg` (found in the UI run: most seed photos were rejected with
  a `415`). Ruff now treats `alembic` as third-party, and `make lint` runs each check in its own shell.
- **Decisions taken.** D43–D48. The section's open questions were settled in the part plans and are listed in
  `docs/claude-recommendations.md`.
- **Gate.** `make test` green (89 tests). Local demo run by Claude on a real uvicorn server against the dev database:
  upload → `ready` with units written; `kms worker` picking up a file uploaded with the worker off; a dead worker's
  claim (staged in SQL, since a fake job takes about 10 ms) released by the reaper and finished as attempt 2; the
  invalid mode failing three times, then Retry. UI checklist run by Michael locally. Gate cleared by Michael; merged
  to `main` and tagged `phase-3` on Sep 27, 2026.

### Phase 4 — Sep 27, 2026

- **Built.** Migration 0002 and `assets.vision_model`; `ai/errors.py` (error kinds, backoff honouring
  `retryDelay`); `ai/prompts.py` and `ai/gemini.py` (`GeminiVision`: schema, minimal thinking, one repair, the
  `VISION_MODELS` walk); `ai/voyage.py` (`VoyageEmbedder`, batched); `ai/recorded.py` (record and replay);
  `kms describe` and `kms embed` with `prepare_file` shared with the worker; `tests/live/` in two passes (vendors,
  then the recorder); `api/auth.py`, one password in front of the app (D49). Worked on branch `phase-4`.
- **Deviations.** Recordings stay local and git-ignored instead of committed (D26 amended). The long book
  (`innocents_abroad.txt`) was left out of the recording run; its size and recording are decided in Phase 6. A
  password on the app (Part 9, D49) was brought forward from Phase 8, so the live URL could run real providers. The
  live URL runs `AI_PROVIDER=real` from this phase on, instead of from Phase 6. Found and fixed in the phase: text
  files stored `visible_text` as `""` where the contract says `null` (now written as null by `commit_ready`);
  `make test` read `AI_PROVIDER=real` from `backend/.env` and called the vendors (the test conftest now pins the
  fake provider and an empty password).
- **Recording run (Part 8).** From an empty database, the 31 files of `../seed/demo` uploaded through the UI: 31
  `ready`, one Gemini call each (`gemini-3-flash-preview`, no repair, fallback or retry), 31 Voyage calls. Deleted and
  uploaded again: 62 recording hits, no vendor call, identical metadata.
- **Deployment.** Railway sealed variables did not reach the running service: `APP_PASSWORD`, `GEMINI_API_KEY` and
  `VOYAGE_API_KEY` arrived empty while sealed and worked once re-added unsealed. They stay unsealed; the Railway-only
  vendor keys, the spend caps and the password carry the protection. `AI_CACHE_DIR` is not set on Railway (an empty
  value is not kept), so the live service records into the container's `./recordings`, wiped at each deploy.
- **Noted for Phase 6.** The `seed_dir` default `../seed` resolves from `backend/` to `KMS/seed`, not the folder
  beside the repo. A prompt change bumps `PROMPT_VERSION` and re-records.
- **Decisions taken.** D26 amended, D49. The section's open questions were settled in the part plans.
- **Gate.** `make test` green (163 tests). Recording run and replay run by Claude against the local dev server and
  checked in the UI. Deployed: migration 0002 applied at boot, the password answering `401` without it, and real
  providers tested on the live URL by Michael. Gate cleared by Michael; merged to `main` and tagged `phase-4` on
  Sep 27, 2026.
