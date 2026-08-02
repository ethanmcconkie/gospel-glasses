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


# ── main extraction ───────────────────────────────────────────────────────

def extract(pdf_path):
    doc   = fitz.open(pdf_path)
    hymns = {}          # num → {num, title, heading, verses: {n: [tokens]}}

    cur_num   = None    # current hymn number
    cur_data  = {}      # verse_num → [tokens]
    cur_count = None    # number of verses in current hymn

    def flush():
        nonlocal cur_num, cur_data, cur_count
        if cur_num and cur_data:
            verses = []
            for vn in sorted(cur_data):
                v = clean_verse_tokens(cur_data[vn])
                if v:
                    verses.append(v)
            hymns.setdefault(cur_num, {}).update({'num': cur_num, 'verses': verses})
        cur_data  = {}
        cur_count = None

    for page in doc:
        spans = page_spans(page)

        # Separate by size bucket
        sz16 = sorted([s for s in spans if 14 < s['size'] < 18], key=lambda s: (s['y'], s['x']))
        sz9  = sorted([s for s in spans if 8.5 < s['size'] < 10], key=lambda s: (s['y'], s['x']))
        sz8  = sorted([s for s in spans if s['size'] <= 8.5],     key=lambda s: (s['y'], s['x']))

        # ── hymn header (sz ≈ 16): number + title ──────────────────────
        for group in group_by_y(sz16, tol=5):
            texts = [s['text'].strip() for s in sorted(group, key=lambda s: s['x'])]
            nums   = [t for t in texts if re.match(r'^\d+$', t)]
            titles = [t for t in texts if t and not re.match(r'^\d+$', t)]
            if nums:
                new_num = int(nums[0])
                if new_num != cur_num:
                    flush()
                    cur_num = new_num
                    hymns.setdefault(cur_num, {})
                if titles:
                    hymns[cur_num]['title'] = ' '.join(titles)
                hymns[cur_num]['num'] = cur_num

        # ── attribution (sz ≈ 8) ────────────────────────────────────────
        if cur_num and sz8:
            attrib_parts = []
            for group in group_by_y(sz8, tol=3):
                line = ' '.join(s['text'].strip() for s in sorted(group, key=lambda s: s['x']))
                if re.search(r'\b(text|music|words?|arr\.|adapt\.)\b', line, re.I):
                    # Split off scripture references (separated by two or more spaces)
                    part = re.split(r'\s{2,}', line)[0].strip()
                    attrib_parts.append(part)
            if attrib_parts:
                hymns[cur_num]['heading'] = ' '.join(attrib_parts)

        # ── lyrics (sz ≈ 9) ─────────────────────────────────────────────
        if not sz9 or cur_num is None:
            continue

        rows = [sorted(g, key=lambda s: s['x'])
                for g in group_by_y(sz9, tol=2)]
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
            # Detect verse markers in this band
            verse_map = {}      # row_index → verse_number
            for ri, row in enumerate(band):
                rt = row_text(row).strip()
                m = re.match(r'^(\d+)\.\s', rt)
                if m:
                    verse_map[ri] = int(m.group(1))

            if verse_map:
                cur_count = len(band)
                # Fill in any unmarked rows sequentially
                marked = sorted(verse_map)
                for ri in range(len(band)):
                    if ri not in verse_map:
                        # find nearest preceding marked row
                        prev = max((k for k in marked if k < ri), default=None)
                        if prev is not None:
                            verse_map[ri] = verse_map[prev] + (ri - prev)
                        else:
                            verse_map[ri] = ri + 1
            elif cur_count:
                verse_map = {ri: ri + 1 for ri in range(len(band))}
            else:
                # No clue about verse structure — skip
                continue

            for ri, row in enumerate(band):
                vn = verse_map.get(ri, ri + 1)
                tokens = [s['text'] for s in row]
                cur_data.setdefault(vn, []).extend(tokens)

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
