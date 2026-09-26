# Phase 1 spike

Throwaway scripts that ask the vendors the questions the design could only assume. Kept in git as
evidence; nothing in `src/` imports them. Findings are in `PLAN.md` under the Phase log. Each script
writes the raw responses it received to `spike/out/` (git-ignored).

Run from `backend/` with keys in `.env`:

```
uv run python spike/describe.py spike/samples/screenshot.png spike/samples/note.txt
uv run python spike/embed.py
uv run python spike/errors.py [burst size, default 15]
```

- `describe.py`: does Gemini honour `response_schema` for our metadata model? Token counts, timing.
- `embed.py`: does Voyage take one batch mixing text and an image? Dims, tokens, timing, and the
  cosine of "black hair" against a sentence that only says "brunette".
- `errors.py`: what a bad key and a burst of requests look like from each SDK, with and without the
  SDK's own retries.
