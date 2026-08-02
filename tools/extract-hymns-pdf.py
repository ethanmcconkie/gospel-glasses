#!/usr/bin/env python3
"""
Extract hymn lyrics from the Church's Hymns PDF.

Lyrics are in Palatino-Roman 9pt; music notation is in Interlude 18pt.
Within each music system, all verses appear simultaneously — verse 1 on
one y-row, verse 2 on the next, etc.  We recover each verse by grouping
spans into bands (one per music system) and reading rows in order.

USAGE:
    pip install pymupdf
    python3 extract-hymns-pdf.py /path/to/Hymns.pdf --out ../data/hymns.json
"""
import fitz, json, re, sys, argparse


# ── helpers ────────────────────────────────────────────────────────────────

def group_by_y(spans, tol=3):
    """Cluster spans into rows that share the same y coordinate (±tol px)."""
    if not spans:
        return []
    rows, current = [], [spans[0]]
    for s in spans[1:]:
        if abs(s['y'] - current[-1]['y']) <= tol:
            current.append(s)
        else:
            rows.append(current)
            current = [s]
    rows.append(current)
    return rows


def row_text(row):
    return ' '.join(s['text'] for s in sorted(row, key=lambda s: s['x']))


def clean_verse_tokens(tokens):
    """Join raw token list into clean stanza text."""
    text = ' '.join(t.strip() for t in tokens if t.strip())
    # Remove verse-number prefix:  "1. " or "2. " etc.
    text = re.sub(r'^\d+\.\s*', '', text)
    # Remove em-dash continuation marker at start
    text = re.sub(r'^[—–]\s*', '', text)
    # Collapse syllable hyphens:  "morn - ing" → "morning"
    text = re.sub(r'(\w)\s*-\s*(\w)', r'\1\2', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ── per-page span collection ─────────────────────────────────────────────

def page_spans(page):
    """Return all Palatino spans with x, y, size, text."""
    spans = []
    for block in page.get_text('dict')['blocks']:
        if 'lines' not in block:
            continue
        for line in block['lines']:
            for span in line['spans']:
                txt = span['text']
                if not txt.strip():
                    continue
                if 'Palatino' not in span['font']:
                    continue
                spans.append({
                    'text': txt,
                    'x':    round(span['bbox'][0], 1),
                    'y':    round(span['bbox'][1], 1),
                    'size': span['size'],
                })
    return spans


# ── lyrics band processor ─────────────────────────────────────────────────

def process_lyrics(sz9_spans, cur_data, cur_count_ref):
    """
    Group sz9 spans into bands and add tokens to cur_data.
    cur_count_ref is a list holding [cur_count] so we can mutate it.
    """
    if not sz9_spans:
        return

    rows = [sorted(g, key=lambda s: s['x'])
            for g in group_by_y(sz9_spans, tol=2)]
    rows.sort(key=lambda r: r[0]['y'])

    # Split rows into bands: gap > 18 px between consecutive rows
    bands, cur_band = [], [rows[0]]
    for i in range(1, len(rows)):
        gap = rows[i][0]['y'] - rows[i-1][0]['y']
        if gap > 18:
            bands.append(cur_band)
            cur_band = [rows[i]]
        else:
            cur_band.append(rows[i])
    bands.append(cur_band)

    for band in bands:
        verse_map = {}
        for ri, row in enumerate(band):
            rt = row_text(row).strip()
            m = re.match(r'^(\d+)\.\s', rt)
            if m:
                verse_map[ri] = int(m.group(1))

        if verse_map:
            cur_count_ref[0] = len(band)
            marked = sorted(verse_map)
            for ri in range(len(band)):
                if ri not in verse_map:
                    prev = max((k for k in marked if k < ri), default=None)
                    if prev is not None:
                        verse_map[ri] = verse_map[prev] + (ri - prev)
                    else:
                        verse_map[ri] = ri + 1
        elif cur_count_ref[0]:
            verse_map = {ri: ri + 1 for ri in range(len(band))}
        else:
            # No verse markers and no prior count (first band of hymn).
            # Treat rows as sequential verse lines; set cur_count from band size.
            verse_map = {ri: ri + 1 for ri in range(len(band))}
            cur_count_ref[0] = len(band)

        for ri, row in enumerate(band):
            vn = verse_map.get(ri, ri + 1)
            tokens = [s['text'] for s in row]
            cur_data.setdefault(vn, []).extend(tokens)


# ── main extraction ───────────────────────────────────────────────────────

def extract(pdf_path):
    doc   = fitz.open(pdf_path)
    hymns = {}

    cur_num       = None
    cur_data      = {}
    cur_count_ref = [None]   # mutable wrapper so process_lyrics can update it

    def flush():
        nonlocal cur_num, cur_data
        if cur_num and cur_data:
            verses = []
            for vn in sorted(cur_data):
                v = clean_verse_tokens(cur_data[vn])
                if v:
                    verses.append(v)
            hymns.setdefault(cur_num, {}).update({'num': cur_num, 'verses': verses})
        cur_data          = {}
        cur_count_ref[0]  = None

    def start_hymn(new_num, title=None):
        nonlocal cur_num
        flush()
        cur_num = new_num
        hymns.setdefault(cur_num, {})
        hymns[cur_num]['num'] = cur_num
        if title:
            hymns[cur_num]['title'] = title

    for page in doc:
        spans = page_spans(page)

        sz16 = sorted([s for s in spans if 14 < s['size'] < 18], key=lambda s: (s['y'], s['x']))
        sz9  = sorted([s for s in spans if 8.5 < s['size'] < 10], key=lambda s: (s['y'], s['x']))
        sz8  = sorted([s for s in spans if s['size'] <= 8.5],     key=lambda s: (s['y'], s['x']))

        # ── hymn headers: find all on this page, sorted by y ───────────────
        # Each entry: (y, num, title_or_None)
        header_events = []
        for group in group_by_y(sz16, tol=5):
            texts = [s['text'].strip() for s in sorted(group, key=lambda s: s['x'])]
            full  = ' '.join(texts)

            nums   = [t for t in texts if re.match(r'^\d+$', t)]
            titles = [t for t in texts if t and not re.match(r'^\d+$', t)]

            # Fallback: number embedded at end of title span ("Title Text 242")
            if not nums:
                m = re.match(r'^(.+?)\s+(\d+)$', full)
                if m and 1 <= int(m.group(2)) <= 400:
                    nums   = [m.group(2)]
                    titles = [m.group(1).strip()]

            if nums:
                new_num = int(nums[0])
                row_y   = min(s['y'] for s in group)
                title   = ' '.join(titles) if titles else None
                header_events.append((row_y, new_num, title))

        header_events.sort(key=lambda e: e[0])

        # ── split lyrics by header y-positions and process each segment ────
        if not header_events:
            # No new hymns start on this page; all lyrics belong to cur_num
            process_lyrics(sz9, cur_data, cur_count_ref)
        else:
            # Lyrics before the first header belong to the previous hymn
            first_y = header_events[0][0]
            pre = [s for s in sz9 if s['y'] < first_y]
            process_lyrics(pre, cur_data, cur_count_ref)

            for i, (hy, new_num, title) in enumerate(header_events):
                start_hymn(new_num, title)
                next_y = header_events[i + 1][0] if i + 1 < len(header_events) else float('inf')
                seg = [s for s in sz9 if hy <= s['y'] < next_y]
                process_lyrics(seg, cur_data, cur_count_ref)

        # ── attribution (sz ≈ 8) ────────────────────────────────────────────
        if cur_num and sz8:
            attrib_parts = []
            for group in group_by_y(sz8, tol=3):
                line = ' '.join(s['text'].strip() for s in sorted(group, key=lambda s: s['x']))
                if re.search(r'\b(text|music|words?|arr\.|adapt\.)\b', line, re.I):
                    part = re.split(r'\s{2,}', line)[0].strip()
                    attrib_parts.append(part)
            if attrib_parts:
                hymns[cur_num]['heading'] = ' '.join(attrib_parts)

    flush()
    return hymns


# ── output ────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pdf',   help='Path to Hymns PDF')
    ap.add_argument('--out', default='../data/hymns.json', help='Output JSON path')
    ap.add_argument('--only', type=int, metavar='N', help='Extract only hymn N (testing)')
    args = ap.parse_args()

    print(f'Reading {args.pdf} …', flush=True)
    hymns = extract(args.pdf)

    if args.only:
        h = hymns.get(args.only)
        if h:
            print(json.dumps(h, ensure_ascii=False, indent=2))
        else:
            print(f'Hymn {args.only} not found. Available: {sorted(hymns)[:20]}')
        return

    chapters = []
    for num in sorted(hymns):
        h = hymns[num]
        if not h.get('verses'):
            continue
        entry = {'num': num, 'title': h.get('title', f'Hymn {num}'), 'verses': h['verses']}
        if h.get('heading'):
            entry['heading'] = h['heading']
        chapters.append(entry)

    volume = {
        'id': 'hymns',
        'name': 'Hymns',
        'books': [{'id': 'hymns', 'name': 'Hymns', 'chapters': chapters}],
    }

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(volume, f, ensure_ascii=False, indent=2)

    n_v = sum(len(c['verses']) for c in chapters)
    n_h = sum(1 for c in chapters if c.get('heading'))
    print(f'Wrote {args.out}')
    print(f'  {len(chapters)} hymns · {n_v} total stanzas · {n_h} with attribution')

if __name__ == '__main__':
    main()
