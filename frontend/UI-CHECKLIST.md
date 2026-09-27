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

## 2b. Home page and filters

- [ ] The home page shows the logo, the search box, Search, "Filters" and "Browse all", and no files.
- [ ] "Filters" (sliders icon) opens the filters under the box and closes them again. With results showing
      they are always open and the button is gone; back on the home page they are as you left them.
- [ ] Change the order and turn a match kind off before searching: no request is sent; the next search uses
      them (check `order` and `match` in the network tab).
- [ ] "Browse all" opens the file list under the filters, "Hide all" closes it; the filters never change it.
- [ ] Change a filter while results show: they reload with a spinner, and "Show more" waits until they are back.
- [ ] "Back to all files" in the results opens the file list.

## 3. Upload

- [ ] **Upload** in the top bar opens a window with the drop box; drop, or pick with **browse**, a JPEG,
      a PNG and a text file at once: the window closes, the upload panel opens in the bottom-right corner,
      and all three appear at the top of the list, newest first, with a thumbnail or a text icon; the count
      in the dropdown goes up.
- [ ] Drag files from the desktop anywhere onto the page: an overlay says "Drop files to upload" and names
      the collection; dropping uploads them without opening the window. It works during a search too.
- [ ] Several files at once, one of them large: the panel's overall bar and each file's own bar fill as
      the bytes go out, "N of M done" counts up, and each file ends with a tick.
- [ ] The panel's × is greyed out while anything is uploading; the arrow folds the panel to its header.
- [ ] Switch collection while a file is uploading: its row keeps going and names the collection it went to.
- [ ] The summary above the list reads "N files · N pending" and matches the badges.
- [ ] Upload the same image again under another name: its row says it is identical to the existing file,
      no new tile appears, and the tile shows "also uploaded as …".
- [ ] Upload a GIF: red row, unsupported type. An empty file: red row, the file is empty.
      A file over 10 MB: red row, larger than the limit. None of them adds a tile.

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
