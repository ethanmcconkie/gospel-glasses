#!/usr/bin/env python3
"""
Convert the Book of Mormon, Doctrine and Covenants, and Pearl of Great Price
from a "Standard Works" EPUB (the official Church edition) into the JSON
schema this app's data/ files use.

WHY THIS IS A SCRIPT YOU RUN, NOT SOMETHING PRE-BUILT FOR YOU:
Unlike the Bible (public domain, already included in data/), this content is
Church-copyrighted. This tool only reformats a copy you already legitimately
have — run it yourself, on your own file, for your own personal use.

USAGE:
    pip install beautifulsoup4 lxml
    python3 convert-epub.py /path/to/standard-works.epub --collection bofm --out ../data/book-of-mormon.json
    python3 convert-epub.py /path/to/standard-works.epub --collection dc   --out ../data/doctrine-and-covenants.json
    python3 convert-epub.py /path/to/standard-works.epub --collection pgp --out ../data/pearl-of-great-price.json

Run all three, then reload the app — no other code changes needed since
data/manifest.json already lists these filenames.
"""
import argparse, glob, json, os, re, shutil, sys, tempfile, warnings, zipfile

try:
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except ImportError:
    sys.exit("Missing dependency. Run: pip install beautifulsoup4 lxml")

COLLECTIONS = {
    "ot": {
        "dir": "bible",
        "vol_id": "ot",
        "vol_name": "Old Testament",
        "books": [
            ("gen", "Genesis"), ("ex", "Exodus"), ("lev", "Leviticus"), ("num", "Numbers"),
            ("deut", "Deuteronomy"), ("josh", "Joshua"), ("judg", "Judges"), ("ruth", "Ruth"),
            ("1-sam", "1 Samuel"), ("2-sam", "2 Samuel"), ("1-kgs", "1 Kings"), ("2-kgs", "2 Kings"),
            ("1-chr", "1 Chronicles"), ("2-chr", "2 Chronicles"), ("ezra", "Ezra"), ("neh", "Nehemiah"),
            ("esth", "Esther"), ("job", "Job"), ("ps", "Psalms"), ("prov", "Proverbs"),
            ("eccl", "Ecclesiastes"), ("song", "Song of Solomon"), ("isa", "Isaiah"), ("jer", "Jeremiah"),
            ("lam", "Lamentations"), ("ezek", "Ezekiel"), ("dan", "Daniel"), ("hosea", "Hosea"),
            ("joel", "Joel"), ("amos", "Amos"), ("obad", "Obadiah"), ("jonah", "Jonah"),
            ("micah", "Micah"), ("nahum", "Nahum"), ("hab", "Habakkuk"), ("zeph", "Zephaniah"),
            ("hag", "Haggai"), ("zech", "Zechariah"), ("mal", "Malachi"),
        ],
    },
    "nt": {
        "dir": "bible",
        "vol_id": "nt",
        "vol_name": "New Testament",
        "books": [
            ("matt", "Matthew"), ("mark", "Mark"), ("luke", "Luke"), ("john", "John"),
            ("acts", "Acts"), ("rom", "Romans"), ("1-cor", "1 Corinthians"), ("2-cor", "2 Corinthians"),
            ("gal", "Galatians"), ("eph", "Ephesians"), ("philip", "Philippians"), ("col", "Colossians"),
            ("1-thes", "1 Thessalonians"), ("2-thes", "2 Thessalonians"), ("1-tim", "1 Timothy"),
            ("2-tim", "2 Timothy"), ("titus", "Titus"), ("philem", "Philemon"), ("heb", "Hebrews"),
            ("james", "James"), ("1-pet", "1 Peter"), ("2-pet", "2 Peter"), ("1-jn", "1 John"),
            ("2-jn", "2 John"), ("3-jn", "3 John"), ("jude", "Jude"), ("rev", "Revelation"),
        ],
    },
    "bofm": {
        "dir": "bofm",
        "vol_id": "bom",
        "vol_name": "Book of Mormon",
        "books": [
            ("1-ne", "1 Nephi"), ("2-ne", "2 Nephi"), ("jacob", "Jacob"),
            ("enos", "Enos"), ("jarom", "Jarom"), ("omni", "Omni"),
            ("w-of-m", "Words of Mormon"), ("mosiah", "Mosiah"), ("alma", "Alma"),
            ("hel", "Helaman"), ("3-ne", "3 Nephi"), ("4-ne", "4 Nephi"),
            ("morm", "Mormon"), ("ether", "Ether"), ("moro", "Moroni"),
        ],
    },
    "dc": {
        "dir": "dc-testament",
        "vol_id": "dc",
        "vol_name": "Doctrine and Covenants",
        "books": [
            ("dc", "Sections"),
        ],
    },
    "pgp": {
        "dir": "pgp",
        "vol_id": "pgp",
        "vol_name": "Pearl of Great Price",
        "books": [
            ("moses", "Moses"), ("abr", "Abraham"), ("js-m", "Joseph Smith—Matthew"),
            ("a-of-f", "Articles of Faith"),
        ],
    },
}


def load_xhtml(path):
    with open(path, "rb") as f:
        raw = f.read()
    try:
        return raw.decode("utf-16")
    except Exception:
        return raw.decode("utf-8", errors="replace")


def parse_chapter_verses(path):
    """Returns (heading, verses) for one chapter file.
    heading = the italic chapter summary paragraph(s) that precede verse 1
    (present in the official Standard Works epub), or None."""
    soup = BeautifulSoup(load_xhtml(path), "lxml")
    verses = []
    # In the official Standard Works epub each chapter file is:
    #   <h1>book name</h1> <h2>Chapter N</h2> <h3>italic chapter summary</h3> <p>verses...</p>
    h3 = soup.find("h3")
    heading = re.sub(r"\s+", " ", h3.get_text(" ", strip=True)) if h3 else None
    for p in soup.find_all("p"):
        spans = p.find_all("span", recursive=False)
        if (
            spans
            and "font-size" in spans[0].get("style", "")
            and spans[0].get_text(strip=True).isdigit()
        ):
            num = int(spans[0].get_text(strip=True))
            spans[0].extract()
            text = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
            verses.append((num, text))
    verses.sort(key=lambda x: x[0])
    return heading or None, [t for _, t in verses]


def slug(name):
    return name.lower().replace(" ", "-").replace("—", "-")


def build_volume(text_dir, book_list, vol_id, vol_name):
    books = []
    for prefix, name in book_list:
        pattern = os.path.join(text_dir, f"06897_000_{prefix}_*.xhtml")
        files = sorted(glob.glob(pattern))
        if not files:
            print(f"  (skipping {name}: no files matching {prefix}_*)", file=sys.stderr)
            continue
        chapters = []
        for fpath in files:
            m = re.search(r"_(\d+)\.xhtml$", fpath)
            if not m:
                continue  # e.g. introduction/toc files without a chapter number
            chap_num = int(m.group(1))
            heading, verses = parse_chapter_verses(fpath)
            if verses:
                entry = {"num": chap_num, "verses": verses}
                if heading:
                    entry["heading"] = heading
                chapters.append(entry)
        chapters.sort(key=lambda c: c["num"])
        if chapters:
            books.append({"id": slug(name), "name": name, "chapters": chapters})
    return {"id": vol_id, "name": vol_name, "books": books}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("epub", help="Path to your Standard Works .epub")
    ap.add_argument("--collection", required=True, choices=COLLECTIONS.keys())
    ap.add_argument("--out", required=True, help="Output JSON path")
    ap.add_argument("--only-book", help="Optional: only convert one book prefix (e.g. 'dc' section testing)")
    args = ap.parse_args()

    cfg = COLLECTIONS[args.collection]
    book_list = cfg["books"]
    if args.only_book:
        book_list = [b for b in book_list if b[0] == args.only_book]
        if not book_list:
            sys.exit(f"No book with prefix '{args.only_book}' in {args.collection}")

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(args.epub) as z:
            z.extractall(tmp)
        text_dir = os.path.join(tmp, "OEBPS", "Text", cfg["dir"])
        if not os.path.isdir(text_dir):
            sys.exit(f"Expected directory not found: {text_dir}\n"
                     f"Your epub's internal layout may differ — check OEBPS/Text/ manually.")
        volume = build_volume(text_dir, book_list, cfg["vol_id"], cfg["vol_name"])

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(volume, f, ensure_ascii=False, indent=2)

    n_chapters = sum(len(b["chapters"]) for b in volume["books"])
    n_verses = sum(len(c["verses"]) for b in volume["books"] for c in b["chapters"])
    print(f"Wrote {args.out}: {len(volume['books'])} books, {n_chapters} chapters, {n_verses} verses")


if __name__ == "__main__":
    main()
