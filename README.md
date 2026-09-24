# KMS — Knowledge Management System

A small system for collecting text files and images and finding them again by
what they contain: literal words, described content, and — for images — what
they look like.

- **Live demo:** _TODO: Railway URL_
- **System design:** [`docs/system-design.md`](docs/system-design.md) — every
  design choice, the alternatives weighed, and what was deliberately left out.
  This README summarises it; the doc is the source of truth.

## What it does

- Upload a text file or an image into a **collection**. The upload returns at
  once; a background worker enriches the file (description, tags, visible
  text, embeddings) and it becomes searchable the moment its own processing
  finishes, independent of any other upload.
- **Search** runs two paths concurrently — keyword (Postgres full-text) and
  meaning (vector similarity) — and merges them with reciprocal rank fusion.
  Images are searchable through both their AI-written description and a
  vector computed directly from the pixels, so "black hair" and "brunette"
  both find the same photo, and "document" finds photos that contain one.
- **Collections** keep datasets apart. The demo ships with a seeded collection
  built to answer the assignment's example queries; create a new collection to
  start from scratch.

## How it works in one paragraph

Every asset becomes one or more **search units**: a metadata unit (title,
description, tags, visible text), one content unit per text chunk, and — for
images — an image unit embedded straight from the pixels. All vectors come from
one multimodal embedding model, so text, descriptions, images and the query
share a single vector space and one HNSW index. Search pulls the top 100 units
from each path, fuses the rankings in Python, groups by asset (best unit wins),
and returns pages of 20 with a "show more". No score threshold is applied:
recall is preferred over precision, so a weak match costs a glance and a real
match is never dropped.

## Stack

| Part | Choice |
|---|---|
| API + worker | Python (sync), one container, thread-pool worker |
| Web UI | React SPA served by the API |
| Database | Postgres + pgvector (HNSW, cosine) — also the job queue (`SKIP LOCKED` + `LISTEN/NOTIFY`) |
| Blob store | Local volume behind a `BlobStore` interface, files keyed by sha256 |
| Vision / summaries | Gemini Flash, structured JSON output |
| Embeddings | voyage-multimodal-3.5, 1024 dims |
| Migrations | Alembic, run at container start |
| Hosting | Railway (app + Postgres + volume) |

## Running locally

_TODO: `docker compose up`, env vars (`GEMINI_API_KEY`, `VOYAGE_API_KEY`,
`DATABASE_URL`, `WORKER_THREADS`, `SEED_ON_START`), `make seed`._

## Deliberately out of scope

The assignment asks for engineering approach, not production readiness. The
items below are things I would build into a production-grade, large-scale
version of this system as a matter of course — not as nice-to-haves. They are
left out here because of the time budget, and the code keeps the seam (an
interface, a flag, a stub, a column) where each one plugs in.

### Would be built in, left out for scope

- **Object storage for blobs.** The volume ties the system to one API
  instance. An S3-compatible `BlobStore` implementation is what allows
  horizontal scaling; the interface is already there.
- **Per-collection isolation at scale.** Collections are a partition key on
  shared tables — the standard multi-tenant pattern. At scale the next steps
  are `PARTITION BY LIST (collection)` on `search_units` (its own HNSW and GIN
  index per collection, partition pruning, detachable partitions) and, for
  tenants whose size or sensitivity demands it, a dedicated deployment of the
  same container with its own database.
- **Managed Postgres and, beyond tens of millions of vectors, a dedicated
  vector store.** The Railway-provisioned Postgres has no point-in-time
  recovery or failover. The listener needs a direct connection, not a
  transaction-mode pooler.
- **Worker scale-out.** The queue design (`FOR UPDATE SKIP LOCKED`) already
  supports many workers on many machines; scaling is `WORKER_THREADS` or more
  containers. An external broker only becomes necessary when the queue has to
  cross services.
- **Embedding-model migration.** Every vector records the model that made it
  and search filters on the current model, so a model switch degrades
  gracefully (old rows fall back to keyword search). The backfill job that
  re-embeds old rows is not written; in development, delete the collection
  and reseed.
- **Text-heavy images.** Images that are mostly text (dense document scans)
  lose small text at the ~1024 px the vision model receives. Production would
  branch on the `image_type` the model already returns and send document-like
  images through a full-resolution extraction pass or a dedicated OCR step
  behind the same adapter.
- **Large text files.** Files above the summary token budget are summarised
  from their head only. The `SummarySource` strategy has a `MapReduce`
  implementation as a stub; chunk units still carry full recall for the
  literal content, so only the topic-level summary degrades.
- **Typo tolerance on the keyword path.** The vector path absorbs common
  slips; the keyword path is exact after stemming. `pg_trgm` correction
  against a vocabulary table (built from `ts_stat`) is the planned addition.
- **Query expansion.** None at query time, by design: the vector path is the
  expansion, and rewrites cost 300–800 ms. For a domain-specific deployment,
  where every query maps onto a known set of questions, thesaurus
  dictionaries, multi-query/HyDE rewrites or ingest-time doc2query would be
  worth their cost.
- **Reranking.** A cross-encoder reranker (Voyage rerank-2.5) improves
  ordering but not recall and costs ~100–300 ms. The stage is pluggable with
  a no-op default; the implementation is behind a flag and is the last thing
  built, if time allows.

### Out of scope by the assignment

Authentication and authorisation, redundancy, rate limiting, production-grade
security, backups.

## Design decisions in short

Each line: what was chosen, and what it was chosen over. The rationale is in
the design doc.

**AI**
1. Two vendors behind adapters — Google (vision) + Voyage (embeddings) — over
   all-Google or self-hosted open weights.
2. Gemini Flash for descriptions and summaries, over Claude Haiku 4.5 /
   GPT-5.4 Mini (comparable) and Qwen3-VL (needs a GPU).
3. voyage-multimodal-3.5 embeddings, over Cohere Embed v4, Gemini Embedding 2,
   and Jina v5-omni / SigLIP 2.
4. Images get both a described text unit and a native pixel-embedded unit in
   one vector space, over describe-then-embed only or CLIP-only.
5. Two prompts, one output schema, over one branching prompt.
6. Text inside images is read by the vision model in the same call, over a
   separate OCR step.
7. Structured output → Pydantic validation → normalise → one repair retry →
   failed, over regex extraction or storing partial fields.
8. Chunks of ~400 tokens (max 512, ~60 overlap, recursive split),
   configurable, over fixed windows or semantic chunking.
9. Whole-file summary up to a token budget, else head only; map-reduce as a
   stub.

**Search**
10. 100 units per path (`ef_search` ≥ that), over page-size-per-path.
11. Fusion, grouping and reranking in Python; the two paths as concurrent SQL
    queries — over a single-statement SQL merge.
12. Pages of 20 with "show more", cap 100.
13. No score cut; structural limits only — over a cosine threshold.
14. Reranker off by default, pluggable — over always-rerank.
15. No query-time typo correction or expansion in v1 — over LLM rewrites.

**Storage**
16. HNSW with cosine ops (m 16 / ef_construction 64 / ef_search 100), over
    exact scan or IVFFlat.
17. `embedding_model` recorded per vector; search filters on it.
18. Alembic migrations at container start, over `create_all` or plain SQL
    files.
19. Collections as a partition key on shared tables, over a database per
    collection.

**Processing**
20. Postgres as the queue (`FOR UPDATE SKIP LOCKED`, `LISTEN/NOTIFY` wake-up,
    1 s poll fallback), over Celery/Redis or an in-process queue.
21. Lease + reaper for crashed workers, over holding the row lock through the
    job.
22. Errors classified: transient → backoff with jitter; permanent → fail
    fast; `attempts = 3` then `failed` with a retry button.
23. Configurable thread pool (default 4); each asset independent.
24. Idempotent uploads by content hash; other filenames kept as aliases and
    shown in the UI — over allowing duplicates or returning 409.

**Deployment**
25. Railway, over Render, a VPS with compose, or Cloud Run/ECS.
26. Platform Postgres with pgvector; the pgvector image in compose for dev.
27. Railway volume behind `BlobStore`; S3-compatible store as the next step.
28. Seeded collections ingested through the normal upload path (idempotent);
    a new collection for a clean start.

## AI tools used during development

_TODO: which tools, for what (design brainstorming, code generation, review),
and what was verified by hand._

## Exploration notes

- **Calibrated-decision models as the reranker.** TypeSafe's Jev
  (released Sept 2026) gives up text generation and returns typed decisions
  with *calibrated* probabilities in ~100 ms. Two things make it interesting
  here. First, the rerank stage takes (query, unit) pairs and returns an
  ordering — exactly a "score / judge" call, and Jev answers a whole page of
  units in one parallel query. Second, a calibrated relevance probability is
  the one thing this design lacks: cosine and RRF scores aren't calibrated,
  which is why I refused to draw a match/noise threshold. A number that
  actually means "70% relevant" would make that threshold honest.
  Text-only for now; early access; one vendor's benchmarks. Slot: the
  `Reranker` interface, behind the existing flag.
