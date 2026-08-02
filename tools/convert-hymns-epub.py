#!/usr/bin/env python3
"""
Convert a Church of Jesus Christ Hymns EPUB into the JSON schema
this app's data/ files use.

WHY THIS IS A SCRIPT YOU RUN, NOT SOMETHING PRE-BUILT:
The hymn texts are Church-copyrighted. This tool only reformats a copy you
already legitimately have — run it yourself, on your own file, for personal use.

HOW TO GET THE EPUB:
  Option A — Gospel Library desktop app (Mac/Windows):
    File → Export → Hymns → EPUB
  Option B — Church website:
    churchofjesuschrist.org → Gospel Library → Hymns → download/share → EPUB

USAGE:
    pip install beautifulsoup4 lxml
    python3 convert-hymns-epub.py /path/to/hymns.epub --out ../data/hymns.json

Run with --probe first to inspect the epub structure if parsing fails.
"""
import argparse, json, os, re, sys, tempfile, warnings, zipfile

try:
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except ImportError:
    sys.exit("Missing dependency. Run: pip install beautifulsoup4 lxml")


def decode_xhtml(raw):
    try:
        return raw.decode("utf-16")
    except Exception:
        return raw.decode("utf-8", errors="replace")


def all_xhtml(zf):
    return sorted(n for n in zf.namelist() if n.endswith(".xhtml") or n.endswith(".html"))


def probe(epub_path):
    """Print epub structure and the first hymn-like file's raw content."""
    with zipfile.ZipFile(epub_path) as zf:
        files = all_xhtml(zf)
        print(f"Total xhtml files: {len(files)}")
        for f in files[:60]:
            print(" ", f)
        if len(files) > 60:
            print(f"  ... and {len(files)-60} more")
        # Print the second file (first is often a cover/toc)
        candidates = [f for f in files if re.search(r'\d', os.path.basename(f))]
        if candidates:
            sample = candidates[0]
            print(f"\n--- SAMPLE: {sample} ---")
            raw = zf.read(sample)
            print(decode_xhtml(raw)[:3000])


def parse_hymn_file(raw, filename):
    """
    Parse one xhtml file. Returns dict with keys:
      num, title, heading (optional), verses (list of strings with <br> line breaks)
    Returns None if no hymn content found.
    """
    soup = BeautifulSoup(decode_xhtml(raw), "lxml")

    # --- Hymn number: try headings first, then filename ---
    num = None
    title = None

    def clean(s):
        return re.sub(r"\s+", " ", s).strip()

    headings = []
    for tag in ("h1", "h2", "h3", "h4"):
        for el in soup.find_all(tag):
            t = clean(el.get_text(" "))
            if t:
                headings.append((tag, t))

    # Look for "N. Title" or "Hymn N" patterns in headings
    for tag, text in headings:
        m = re.match(r'^(\d+)\s*[.\-:]\s*(.+)$', text)
        if m:
            num = int(m.group(1))
            title = m.group(2).strip()
            break
        m2 = re.match(r'^Hymn\s+(\d+)\s*[.\-:]?\s*(.*)$', text, re.I)
        if m2:
            num = int(m2.group(1))
            title = m2.group(2).strip() or None
            break

    # Title from second heading if still missing
    if title is None and len(headings) >= 2:
        title = headings[1][1]
    elif title is None and headings:
        title = headings[0][1]

    # Number from filename if not found in content
    if num is None:
        m = re.search(r'(\d+)', os.path.basename(filename))
        if m:
            num = int(m.group(1))

    if num is None or num == 0:
        return None

    # --- Attribution: look for text containing "Words:" / "Music:" / "Text:" ---
    heading = None
    for p in soup.find_all("p"):
        t = clean(p.get_text(" "))
        if re.search(r'\b(words?|music|text|composer|arr\.)\b', t, re.I) and len(t) < 200:
            heading = t
            break
    # Also try italicised elements
    if heading is None:
        for el in soup.find_all(["em", "i"]):
            t = clean(el.get_text(" "))
            if len(t) > 10 and re.search(r'\b(words?|music|text)\b', t, re.I):
                heading = t
                break

    # --- Stanzas: collect paragraphs that look like verse lines ---
    # Strategy: group <p> tags; skip very short or heading-like ones.
    heading_texts = {t for _, t in headings}
    verses = []
    for p in soup.find_all("p"):
        lines = [ln.strip() for ln in p.get_text("\n").split("\n") if ln.strip()]
        if not lines:
            continue
        block = "\n".join(lines)
        block_clean = clean(block)

        # Skip if it's just a heading repeated, attribution, or very short
        if block_clean in heading_texts:
            continue
        if block_clean == heading:
            continue
        if len(block_clean) < 8:
            continue
        # Skip if it looks like a copyright line
        if re.search(r'(©|copyright|\(c\)|all rights reserved)', block_clean, re.I):
            continue

        # Convert newlines to <br> for HTML rendering
        html_verse = "<br>".join(lines)
        verses.append(html_verse)

    # If we found nothing with <p>, try <div> children
    if not verses:
        for div in soup.find_all("div"):
            lines = [ln.strip() for ln in div.get_text("\n").split("\n") if ln.strip()]
            if len(lines) >= 2:
                verses.append("<br>".join(lines))

    if not verses:
        return None

    result = {"num": num, "title": title or f"Hymn {num}", "verses": verses}
    if heading:
        result["heading"] = heading
    return result


def convert(epub_path, out_path, only_num=None):
    with zipfile.ZipFile(epub_path) as zf:
        files = all_xhtml(zf)

    # Narrow to files that likely contain individual hymns
    # (skip toc, cover, introduction — usually lack digits in name or are very small)
    hymn_files = []
    with zipfile.ZipFile(epub_path) as zf:
        for f in files:
            raw = zf.read(f)
            # Skip tiny files (< 300 bytes) — likely stubs
            if len(raw) < 300:
                continue
            hymn_files.append((f, raw))

    chapters = []
    skipped = 0
    with zipfile.ZipFile(epub_path) as zf:
        for fname, raw in hymn_files:
            hymn = parse_hymn_file(raw, fname)
            if hymn is None:
                skipped += 1
                continue
            if only_num is not None and hymn["num"] != only_num:
                continue
            chapters.append(hymn)

    chapters.sort(key=lambda c: c["num"])

    # Deduplicate by num (keep first occurrence)
    seen = set()
    deduped = []
    for c in chapters:
        if c["num"] not in seen:
            seen.add(c["num"])
            deduped.append(c)
    chapters = deduped

    volume = {
        "id": "hymns",
        "name": "Hymns",
        "books": [
            {"id": "hymns", "name": "Hymns", "chapters": chapters}
        ]
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(volume, f, ensure_ascii=False, indent=2)

    n_verses = sum(len(c["verses"]) for c in chapters)
    n_heading = sum(1 for c in chapters if c.get("heading"))
    print(f"Wrote {out_path}")
    print(f"  {len(chapters)} hymns, {n_verses} total stanzas")
    print(f"  {n_heading}/{len(chapters)} hymns have attribution headings")
    print(f"  {skipped} files skipped (no hymn content found)")
    if len(chapters) < 100:
        print(f"\nWarning: only {len(chapters)} hymns found — expected ~341.")
        print("Run with --probe to inspect the epub structure.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("epub", help="Path to your Hymns .epub file")
    ap.add_argument("--out", default="../data/hymns.json", help="Output JSON path")
    ap.add_argument("--probe", action="store_true",
                    help="Print epub file list and sample content, then exit")
    ap.add_argument("--only", type=int, metavar="N",
                    help="Extract only hymn N (for testing)")
    args = ap.parse_args()

    if args.probe:
        probe(args.epub)
        return

    convert(args.epub, args.out, only_num=args.only)


if __name__ == "__main__":
    main()
