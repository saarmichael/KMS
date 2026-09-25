# Michael's additions

Design-level ideas that Michael brought and that were kept, on top of or against Claude's proposal.
Kept by Claude as the working agreement in `CLAUDE.md` says. Newest last.

| Date | Phase | Michael proposed | Claude had proposed | Why Michael's version was kept |
| --- | --- | --- | --- | --- |
| Sep 25, 2026 | 1 | Record real Gemini and Voyage responses from the first real call on, and replay them in later tests and demos, so the app is mostly exercised against recorded vendor output rather than live calls | Fake adapters only for tests (deterministic, no vendor), an in-memory cache for query embeddings in Phase 4; no record/replay of real responses | Live output is the ground truth for search quality; recording it makes the live test and the query matrix repeatable and free after the first run, and the spike's raw responses become fixtures instead of being thrown away |
