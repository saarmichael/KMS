# UI checklist

Steps through every screen and error path of the web UI, each with what should be seen. Run against
the real API (`npm run dev`, API on :8000). Steps marked *(mocks)* need `npm run dev:mock` instead,
and steps marked *(Phase 5)* need the search endpoint.

To stop and start the API in the middle, stop `make api` (or `make dev`) with Ctrl-C and start it again.

## 1. Loading collections

- [ ] Open the page with the API running: the default collection is selected (`demo` if it exists,
      otherwise the first one) and its files are listed.
- [ ] Stop the API and reload: "Could not load collections" with the reason and **Try again**.
- [ ] Press **Try again** with the API still stopped: the same screen comes back.
- [ ] Start the API and press **Try again**: the collections load and the default one is selected.
- [ ] With no collections at all: "No collections yet", pointing at **+ New**.

## 2. New collection

- [ ] **+ New**, type a name with a capital letter or a space: the hint turns red and Create does nothing.
- [ ] Type a valid name and press Enter: it is selected, shows count 0, and "No files yet".
- [ ] Reload before uploading anything: the empty collection is gone (it exists only after a first upload).

## 3. Upload

- [ ] Drop, or pick with **browse**, a JPEG, a PNG and a text file at once: all three appear at the top,
      newest first, with a thumbnail or a text icon, and the count in the dropdown goes up.
- [ ] The summary above the list reads "N files · N pending" and matches the badges.
- [ ] Upload the same image again under another name: a grey notice says it is identical to the
      existing file, no new tile appears, and the tile shows "also uploaded as …".
- [ ] Upload a GIF: red notice, unsupported type. An empty file: red notice, the file is empty.
      A file over 10 MB: red notice, larger than the limit. None of them adds a tile.
- [ ] The × on the notices closes them.

## 4. Status updates

- [ ] With the worker running, a new file goes pending → processing → ready within a few seconds,
      without a reload. Once nothing is pending or processing, the list stops refreshing
      (no more `/api/assets` requests in the network tab).
- [ ] With a file still pending, stop the API: after about 2 s a red line says
      "Could not refresh the list", and the files stay on screen.
- [ ] Start the API again: within about 2 s the red line disappears by itself, without pressing Try again.

## 5. Failed file and Retry

- [ ] A failed file shows a red **Failed** badge, the error text and **Retry**
      (force one with the fake adapter's invalid mode, or in SQL:
      `UPDATE assets SET status='failed', error='test' WHERE filename='…'`).
- [ ] **Retry**: the tile turns **Pending** at once, and the error text disappears.
- [ ] *(mocks)* `will-fail.txt` in `demo` fails, and Retry brings it back.

## 6. Detail dialog

- [ ] Click a text file's tile: the dialog shows the whole text, Open in new tab, Download, and
      File and Uploaded details.
- [ ] Click a large image: it fits the dialog without scrolling sideways.
- [ ] Click a small image (e.g. 60×40 px): it is shown at its own size, centred, not stretched or blurred.
- [ ] A pending file: the heading is the filename, once (no repeated grey filename under it), and
      "The description and tags appear once processing finishes."
- [ ] A ready file: the heading is the AI title with the filename under it, and description, tags,
      visible text (images) and type are listed.
- [ ] The dialog closes with ×, with Esc and with a click on the dimmed area; the list is as it was.
- [ ] After closing with Esc, one click on another tile opens it straight away.

## 7. Open and download

- [ ] **Open in new tab** (in the dialog and on a tile) opens the file in a new tab: an image shows,
      a text file shows its text with accented characters intact.
- [ ] **Download** saves the file under its filename, including a name with spaces or accents.

## 8. Search

- [ ] Before Phase 5 (real API): a search shows "Search failed", "Search is not available on this
      server yet.", **Try again** and **Back to all files**. Back returns to the file list.
- [ ] *(Phase 5 or mocks)* A matching query: "N results for …", cards with a closeness bar, snippet
      and thumbnail. Clicking a card opens the dialog with the matched passage marked.
- [ ] *(Phase 5 or mocks)* More than 20 results: **Show more** adds the next page below.
- [ ] *(Phase 5 or mocks)* A query with no match: "No matches for …" and **Back to all files**.
- [ ] While a search runs, the box is greyed and **Cancel** replaces Search. Cancel (or Esc) returns
      to the file list with an empty box.
- [ ] After a search, the × in the box (or Esc) clears it and returns to the file list.
- [ ] A search containing only spaces sends nothing.

## 9. Switching collection

- [ ] Switch collection while search results are shown: the new collection opens on its file list,
      with no search and no old results.
- [ ] Switch while files are pending: the new collection's files show, and the old collection's list
      is no longer refreshed.

## 10. Delete collection

- [ ] **Delete**: the dialog names the collection and how many files go with it. Cancel changes nothing.
- [ ] Confirm: the collection disappears from the dropdown and another one is selected.
- [ ] *(Phase 5 or mocks)* A search in another collection never returns the deleted collection's files.
