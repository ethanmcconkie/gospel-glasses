# Bookshelf — a scripture browser for Meta Ray-Ban Display

A standalone Web App (not a Gospel Library extension — see chat history for
why that isn't possible today) built for the glasses' 600×600 additive
display and D-pad/Neural Band input.

## Project structure

```
index.html            — the whole app: layout, styles, navigation logic
data/manifest.json     — ordered list of which volume files to load
data/old-testament.json
data/new-testament.json
data/book-of-mormon.json
data/doctrine-and-covenants.json
data/pearl-of-great-price.json
data/bible-dictionary.json
data/guide-to-scriptures.json
data/family-library.json
```

**This is the plug-and-play part:** `index.html` never hard-codes any book
or volume. On launch it fetches `manifest.json`, then fetches every file it
lists, and builds the whole Library screen from whatever comes back — in
the order the manifest lists them. Adding a new volume is two steps, no
code changes:

1. Create a new file in `data/` shaped like the others (see schema below).
2. Add its filename to `data/manifest.json`.

Reordering the Library screen is just reordering `manifest.json`.

## Data schema

Each volume file looks like:

```json
{
  "id": "unique-id",
  "name": "Displayed Volume Name",
  "books": [
    { "id": "book-id", "name": "Book Name", "chapters": [
      { "num": 1, "verses": [ "First verse text.", "Second verse text." ] }
    ]}
  ]
}
```

- An empty `"verses": []` shows a friendly "no text loaded yet" state in
  the reader, and the chapter is skipped in the progress dots.
- A chapter can carry an optional `"title"` (e.g. `"title": "Atonement"`)
  instead of relying on a bare number — used for dictionary entries and
  named chapters. When present, the chapters screen shows it as a list of
  titles rather than numbered chips.
- A verse entry can be a plain string, or an object `{ "text": "..." }` —
  the object form is kept available for any future per-verse metadata you
  might want to add later, but there's no special rendering tied to it
  right now.

## Reader navigation, confirmed

- Up / Down — previous / next verse within the current chapter, with a
  soft page-turn transition
- Left / Right — previous / next **chapter**, jumping straight there
  without passing back through the chapter list
- Enter — open the menu (bookmark, jump to chapter list, home). The
  bookmark option is hidden automatically on chapters with no text loaded,
  so you can't bookmark a placeholder.
- Verse numbers render inline as small superscript markers, the way
  printed scripture and Gospel Library both do it, rather than as a
  separate header line.

## Bible Dictionary & Guide to the Scriptures

Their own Library entries, structurally complete but empty — same
reasoning as the Book of Mormon/D&C/PGP: these are Church publications, so
I'm not shipping their text. Entries use the `title` field (e.g.
"Atonement") rather than chapter numbers.

## Family Library — your own family's writing

Different case from the Church content above: it's your own family's work,
and you already have legitimate copies. `data/family-library.json` ships
with `"books": []` — add your own books directly into that file:

```json
{
  "id": "family",
  "name": "Family Library",
  "books": [
    { "id": "grandpa-memoir", "name": "Grandpa's Memoir", "chapters": [
      { "num": 1, "title": "Chapter One: Leaving Home", "verses": [
        "First paragraph or page of text goes here.",
        "Second paragraph or page goes here."
      ]}
    ]}
  ]
}
```

Each entry in `"verses"` is one "page" shown at a time in the reader
(Up/Down moves between them) — for prose, a paragraph or a few sentences
per entry reads better on the small display than one giant block of text.

## Content status

- **Old Testament** — all 39 books, sourced from your uploaded epub (public
  domain KJV text)
- **New Testament** — all 27 books, same source
- **Book of Mormon, Doctrine and Covenants, Pearl of Great Price** —
  structure only, still empty in `data/`. See `tools/convert-epub.py` below.
- **Bible Dictionary, Guide to the Scriptures** — empty topic-entry
  placeholders, no public-domain fallback exists for these
- **Family Library** — empty, yours to fill in

## Converting your own epub for the Church-copyrighted volumes

`tools/convert-epub.py` is a script I wrote and tested against your actual
file's structure (confirmed it parses all 138 D&C sections correctly), but
you run it yourself — this reformats a copy you already legitimately have,
same as everything else Church-copyrighted in this project. I'm not
generating or shipping the Book of Mormon/D&C/PGP text myself.

```bash
cd tools
pip install beautifulsoup4 lxml
python3 convert-epub.py /path/to/your-standard-works.epub --collection bofm --out ../data/book-of-mormon.json
python3 convert-epub.py /path/to/your-standard-works.epub --collection dc   --out ../data/doctrine-and-covenants.json
python3 convert-epub.py /path/to/your-standard-works.epub --collection pgp --out ../data/pearl-of-great-price.json
```

Filenames match what `data/manifest.json` already expects, so no other
changes are needed — just reload the app after running these.

If your epub has a different internal folder layout than the standard
Church edition, the script will tell you exactly which directory it
expected and couldn't find, rather than failing silently.


Meta's Web Apps spec for MRBD explicitly does not support text input,
camera, or microphone. There's no keyboard to type with, so a "notes"
feature would have nowhere to receive typed text. Bookmarking works fine
because it's a single toggle, not typed input.

## Deploying to your glasses

Web Apps load from a URL, so this needs to be hosted somewhere with HTTPS.
Easiest free options:
1. **GitHub Pages** — push this whole folder (including `data/`) to a repo,
   enable Pages, done.
2. **Netlify Drop** (netlify.com/drop) — drag the whole folder in.
3. **Vercel** — `vercel` CLI from this folder, or drag-and-drop on vercel.com.

Once you have a URL, open it from developer mode on your glasses (via the
Meta AI companion app) the same way you would any other Web App.

**If you're testing locally:** don't just double-click `index.html` —
the browser blocks `fetch()` on `file://` URLs, so the data files won't
load. Run a quick local server from this folder instead, e.g.
`python3 -m http.server 8080`, then open `http://localhost:8080`.

## Known constraints from the platform (not this build)

- Fixed 600×600 viewport, no scrolling of the page itself (internal lists
  scroll via focus movement, which is supported)
- No offline support yet — the app needs to load over network each time
- No back-gesture your app can hook into — every screen has explicit
  Back rows instead. There is a system-level middle-pinch gesture, but
  it's owned entirely by the OS overlay (Restart/Resume/Permissions), not
  delivered to the app's code.
- Exactly five input signals total: swipe up/down/left/right and one
  select (pinch or tap). No custom gestures, no hold-duration, no
  swipe-velocity — confirmed directly from Meta's own developer docs and
  a developer/Meta engineer exchange on GitHub.
