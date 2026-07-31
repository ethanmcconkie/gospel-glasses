# Gospel Glasses — Complete Design Brief
> Paste this entire document into your AI to get a world-class UI overhaul.

---

## What this app is

A scripture reading app built specifically for **Meta Ray-Ban Display glasses**. It runs as a Progressive Web App hosted at `https://ethanmcconkie.github.io/gospel-glasses/`. The entire app is a **single file**: `index.html` with all HTML, CSS, and JavaScript inline — no build system, no frameworks.

---

## Platform constraints (non-negotiable)

| Constraint | Detail |
|---|---|
| Viewport | Fixed **600 × 600 px**. No scrolling of the page itself. |
| Display type | **Additive** — black (`#000`) is fully transparent glass. Colors appear as light on top of the real world. |
| Input | Exactly **5 signals**: swipe up, swipe down, swipe left, swipe right, pinch/select. No keyboard, no touch, no hover. |
| Navigation | Implemented via `tabIndex=0` + `.focusable` class. The D-pad moves focus between `.focusable` elements. |
| Font | **Noto Serif** loaded from Google Fonts (already in `<head>`). All text should use this. |
| Background | Must stay `#000` — it's the transparent baseline on the additive display. |

---

## App screens and flow

```
BOOT → HOME → LIBRARY → BOOKS → CHAPTERS → READER
                      ↘ RECENTS
                                         ↑
                                      MENU (overlay, appears over READER on select)
```

### Screen: BOOT (`#boot`)
- Shows while data files load
- Has a **3D CSS book animation**: open book with pages flipping from right side to left, viewed at a slight rotated angle
- Has a **"Library" wordmark** that fades in below the book, with a thin gold rule above it and "Scripture Study" in tiny uppercase below
- `#bootStatus` exists for error messages (hidden normally)
- No other content

### Screen: HOME (`#home`)
- First screen after boot
- Small gold uppercase label: "Scripture Library"
- Large serif heading: "Library"  
- Two navigation rows: "Library" and "Recents"

### Screen: LIBRARY (`#library`)
- Back button → Home
- Title: "Library"
- A **4-column grid** (`#volGrid`) of portrait book cover cards
- Cards are 2:3 aspect ratio (like physical books)
- Each card tries to load `covers/{volumeId}.jpg` — if image exists it fills the card. If not, shows a CSS fallback: dark background + gold uppercase title + thin gold rules above/below title
- Volume IDs: `ot`, `nt`, `bom`, `dc`, `pgp`, `bd`, `gts`, `family`
- Focused card lifts with scale + warm gold glow shadow
- Short label below each card (volume name, 9px dim)

### Screen: BOOKS (`#books`)
- Back button → Library
- Title = volume name (set by JS)
- Scrollable list of book rows (e.g. "Genesis", "Exodus", etc.)

### Screen: CHAPTERS (`#chapters`)
- Back button → Books
- Title = book name
- If chapters have numbers: shows a **grid of number chips** (62×62px square tokens)
- If chapters have titles (Bible Dictionary, Guide to Scriptures): shows a list of title rows

### Screen: READER (`#reader`)
- **Header bar**: `ref-tag` (e.g. "GENESIS · 1") | verse counter ("3 / 31") | bookmark diamond (◇ or ◆)
- Thin divider below header with a 48px gold accent on the left
- Scrollable chapter content (`#chapterScroll`):
  - Chapter opening: book name in tiny spaced uppercase gold, chapter number in 24px serif, thin gold rule
  - Verses flow continuously — all verses visible, user navigates with up/down to move the "current" highlight
  - Current verse: subtle gold left-bar highlight + barely-there gold background tint
  - Verse numbers: tiny gold superscript (10px, not bold) before each verse

### Overlay: MENU (`#menu`)
- Opens on select while in reader
- Full-screen dark frosted overlay (blur + near-black)
- Card inside with:
  - Header: current chapter name (large, serif) + "READING" in tiny gold uppercase
  - Thin gold gradient divider
  - 4 action buttons: Continue reading / Bookmark verse / Chapter list / Home
  - Focused button: inset gold left bar + subtle gold tint

---

## Current design tokens

```css
:root {
  --bg:        #000;
  --card:      rgba(255,255,255,0.052);
  --card-hi:   rgba(201,168,76,0.11);
  --ink:       #F0EBE0;          /* warm off-white, primary text */
  --ink-dim:   rgba(240,235,224,0.38);  /* secondary/metadata */
  --ink-mid:   rgba(240,235,224,0.62);  /* medium emphasis */
  --gold:      #C9A84C;          /* primary accent */
  --gold-b:    rgba(201,168,76,0.45);
  --gold-glow: rgba(201,168,76,0.18);
  --divider:   rgba(255,255,255,0.06);
  --scrim:     rgba(0,0,0,0.92);
  --font:      'Noto Serif', Georgia, serif;
  --ease:      cubic-bezier(0.4,0,0.2,1);
  --ease-out:  cubic-bezier(0,0,0.2,1);
}
```

---

## The visual goal

**Think: the official Gospel Library app (Church of Jesus Christ of Latter-day Saints) meets Apple Books on iOS in dark mode.**

Specific qualities to nail:
- **Premium, sacred, calm** — not techy, not developer-ish, not generic
- **Gold is sacred, not decorative** — use it for active states, hierarchy markers, fine rules. Not splashed everywhere.
- **Typography does the heavy lifting** — Noto Serif at the right sizes/weights/spacing should feel like holding a real book
- **Generous breathing room** — 600×600 is small but the content should feel uncluttered
- **Every interaction state is considered** — focused elements should feel warm and intentional, not like a browser default

---

## What the inspiration images show (Gospel Library)

The official Gospel Library app uses:
- Near-black backgrounds in dark mode
- Clean list rows with very subtle dividers — no card backgrounds, just lines
- Chapter headings: book name in tiny dim uppercase above, chapter number clean and medium-large below
- Verse text flows continuously, verse numbers are tiny inline superscripts (not bold, barely visible)
- Gold/orange accent color for active states and navigation elements
- Portrait book covers with actual cover photography — books in a clean grid
- Navigation is minimal — back labels just say the previous screen name

---

## JavaScript — DO NOT CHANGE ANY OF THIS

All JS must remain character-for-character identical. The only JS-adjacent things you can change are:
1. HTML string templates inside `renderLibrary()` for the card fallback content (cosmetic HTML only)
2. HTML string inside `makeRow()` (cosmetic HTML only)

**Element IDs that MUST exist and be preserved:**
- `#boot`, `#bootStatus` (boot)
- `#home`, `#homeLibrary`, `#homeRecents` (home)
- `#library`, `#volGrid` (library)
- `#recents`, `#recentsList` (recents)
- `#books`, `#booksTitle`, `#booksBackLabel`, `#booksList` (books)
- `#chapters`, `#chaptersTitle`, `#chaptersBackLabel`, `#chaptersGrid` (chapters)
- `#reader`, `#refTag`, `#verseCounter`, `#bookmarkFlag`, `#chapterScroll` (reader)
- `#menu`, `#menuRef`, `#bookmarkLabel` (menu)

**CSS classes that MUST exist (used by JS):**
- `.focusable` — D-pad navigation target
- `.screen`, `.screen.active` — screen visibility
- `.card-row`, `.card-row.empty`, `.label`, `.sub`, `.chev` — list rows
- `.vol-wrap`, `.vol-wrap.empty`, `.vol-card`, `.vol-card-img`, `.vol-card-fallback`, `.vol-card-name`, `.vol-label` — book cards
- `.chip`, `.chip.empty`, `.chip-grid`, `.chip-grid.list-mode` — chapter chips
- `.verse-row`, `.verse-row.current`, `.verse-body`, `.verse-num` — reader
- `.chapter-header`, `.chapter-book-name`, `.chapter-number-large`, `.chapter-heading`, `.chapter-intro` — chapter header
- `.menu-btn`, `.menu-icon`, `.menu-inner`, `.menu-header`, `.menu-header-ref`, `.menu-header-sub`, `.menu-divider` — menu
- `.section-label`, `.recents-note`, `.empty-state`, `.back-btn`, `.back-chev`, `.screen-title` — misc
- `.boot-error` — error display
- `data-action` attributes on menu buttons: `resume`, `bookmark`, `chapters`, `home`

---

## Book animation (keep concept, can redesign execution)

The boot screen has a **3D CSS book with flipping pages**. Keep this concept — an open book viewed at a slight angle, pages turning continuously from right to left. Current implementation uses `rotateX(32deg) rotateY(-6deg)` perspective tilt on a 240×158px book. Pages use `transform-style: preserve-3d` with front (cream) and back (navy) faces using `backface-visibility: hidden`.

Feel free to make this more cinematic, more detailed, or more beautiful — just keep it a recognizable flipping book.

---

## Cover images

Drop JPG files into `covers/` to get real book covers:
- `covers/ot.jpg` — Old Testament  
- `covers/nt.jpg` — New Testament
- `covers/bom.jpg` — Book of Mormon
- `covers/dc.jpg` — Doctrine & Covenants
- `covers/pgp.jpg` — Pearl of Great Price
- `covers/bd.jpg` — Bible Dictionary
- `covers/gts.jpg` — Guide to the Scriptures
- `covers/family.jpg` — Family Library

The JS already handles the `onerror` fallback. When a cover image loads successfully, it fills the card with `object-fit: cover`. The fallback CSS cover must look premium on its own.

**Recommended cover colors per volume (for CSS fallbacks):**
- OT: deep burgundy/oxblood
- NT: deep forest green  
- BOM: navy blue (#152448 — the real BofM cover color)
- DC: deep charcoal/slate
- PGP: deep purple/midnight
- BD: warm brown/leather
- GTS: dark teal
- Family: warm dark brown

---

## Specific things to nail

1. **Boot animation** — the book should feel cinematic. Consider adding a subtle ambient glow behind it, or a slow breathing animation on the whole scene. The wordmark reveal should feel like a luxury app splash screen.

2. **Library grid** — 4 columns of portrait book covers. The fallback covers (no image) must look like REAL premium book covers — proper typography, gold embossed feel, unique colors per volume. Not generic placeholders.

3. **Reader** — this is where the app is used most. Make it feel like reading a beautiful printed book. The typography, spacing, and current-verse highlight should be perfect. Verse text at 17px Noto Serif, 1.78 line-height.

4. **Menu** — the popup that appears while reading. It should feel like a polished iOS action sheet — dark, blurred background, elegant card, smooth transitions.

5. **Focus states everywhere** — on a D-pad interface, focus IS the hover state. Every `.focusable` element needs a beautiful focused appearance: warm gold glow, lift, or accent bar. Never just a browser default outline.

6. **Transitions** — all state changes at 180–220ms with refined cubic-bezier. Screen transitions already slide+fade at 240ms.

---

## Deploy after changes

```bash
git add index.html
git commit -m "UI: complete overhaul"
git push
```

The app is live at `https://ethanmcconkie.github.io/gospel-glasses/` — GitHub Pages auto-deploys on push (takes ~60 seconds).

---

## What NOT to do

- Do not add new screens, features, or JS logic
- Do not change any element IDs or class names used by JS
- Do not use bright/neon colors, gradients that look "web 2.0", or anything generic
- Do not add emoji to the UI
- Do not change `#000` background — it's transparent on the glasses
- Do not add scrollbars (already hidden)
- Do not use any external CSS frameworks or libraries
- Do not split into multiple files — keep everything in `index.html`
