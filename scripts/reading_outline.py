"""Draft a source outline and inventory from frozen native pages.

Everything here is a heuristic candidate for navigation. Headings, columns, captions
and object regions must be verified against the source before an inventory is synced.
"""
import json
import ntpath
import os
import re
import stat
import statistics
from collections import Counter, defaultdict
from contextlib import ExitStack
from math import ceil, floor
from pathlib import Path, PureWindowsPath

from reading_element_locators import _drawing_regions, _extent
from reading_pdf_elements import ElementError
from reading_sections import _native

BOLD = re.compile(r'bold|black|heavy|semibold|demi|medi(?!um)|cmbx|cmb\d|(?:^|[-,+_])bd(?:$|[-,+_])', re.I)
SMALLCAPS = re.compile(r'csc\d|smallcap|[-+]sc(?:$|[-,])|caps', re.I)
NUMBER = re.compile(r'^((?:\d{1,2}|[A-H](?=\.\d))(?:\.\d{1,2}){0,3})\.?$')
ROMAN = re.compile(r'^([IVX]{1,5})\.$')
LETTER = re.compile(r'^([A-H])\.$')
APPENDIX = re.compile(r'^(appendix|appendices|annex)\b', re.I)
CAPTION = re.compile(r'^(fig(?:ure)?s?\.?|table|tab\.)\s*(S?\d{1,3}[a-z]?|[IVXL]{1,6})(?=$|[\s.:|—–\-)])', re.I)
REFERENCES = {'references', 'reference', 'bibliography', 'literature cited', 'works cited'}
KEYWORDS = REFERENCES | {
    'abstract', 'introduction', 'background', 'related work', 'related works', 'literature review',
    'method', 'methods', 'methodology', 'materials and methods', 'research methodology', 'research method',
    'results', 'discussion', 'results and discussion', 'discussion and conclusions', 'evaluation',
    'experiments', 'experimental setup', 'case study', 'implementation', 'preliminaries',
    'problem formulation', 'conclusion', 'conclusions', 'conclusion and future work',
    'conclusions and future work', 'summary', 'limitations', 'future work', 'future directions',
    'threats to validity', 'challenges', 'open challenges', 'research questions',
    'acknowledgments', 'acknowledgements', 'acknowledgment', 'acknowledgement', 'appendix', 'appendices',
    'supplementary materials', 'supplementary material', 'data availability statement', 'data availability',
    'author contributions', 'funding', 'conflicts of interest', 'conflict of interest',
    'declaration of competing interest', 'abbreviations', 'nomenclature',
    'institutional review board statement', 'informed consent statement'}
MARGIN = 0.09          # running headers/footers live in the top/bottom 9% of a page
MAX_ANCHOR = 16        # longest boundary phrase tried before asking for review


def _center(b):
    return (b[0]+b[2])/2, (b[1]+b[3])/2


def _inside(b, box):
    cx, cy = _center(b)
    return box[0] <= cx < box[2] and box[1] <= cy < box[3]


def _union(a, b):
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def _rows(words):
    """Group words into horizontal rows across the whole page width."""
    rows = []
    for w in sorted(words, key=lambda w: (_center(w['bbox'])[1], w['bbox'][0])):
        cy = _center(w['bbox'])[1]
        h = max(1.0, w['bbox'][3]-w['bbox'][1])
        if rows and abs(cy-rows[-1]['cy']) <= max(1.5, 0.35*rows[-1]['h']):
            rows[-1]['words'].append(w)
        else:
            rows.append({'cy': cy, 'h': h, 'words': [w]})
    for r in rows:
        r['words'].sort(key=lambda w: w['bbox'][0])
        r['top'], r['bottom'] = min(w['bbox'][1] for w in r['words']), max(w['bbox'][3] for w in r['words'])
    return rows


def _fonts(page):
    """Median size and bold flag per word, from the glyph records inside it."""
    buckets, styles = defaultdict(list), {}
    for c in page['chars']:
        cx, cy = _center(c['bbox'])
        font = c.get('fontname') or ''
        if font not in styles:
            styles[font] = bool(BOLD.search(font) or SMALLCAPS.search(font))
        buckets[floor(cx/32), floor(cy/8)].append((cx, cy, c.get('size'), styles[font]))
    out = {}
    for w in page['words']:
        x0, top, x1, bottom = w['bbox']
        sizes, styled, n = [], 0, 0
        for y in range(floor((top-.5)/8), floor((bottom+.5)/8)+1):
            for x in range(floor((x0-.5)/32), floor((x1+.5)/32)+1):
                for cx, cy, size, emphasis in buckets.get((x, y), ()):
                    if x0-.5 <= cx <= x1+.5 and top-.5 <= cy <= bottom+.5:
                        n += 1
                        styled += emphasis
                        if size:
                            sizes.append(float(size))
        out[w['id']] = (statistics.median(sizes) if sizes else None, styled*2 > n)
    return out


def _furniture(pages):
    """Rows repeated near the top or bottom margin of several pages (running titles, page numbers)."""
    seen, where = defaultdict(set), defaultdict(list)
    for n, (_, p) in pages.items():
        for row in _rows(p['words']):
            if row['bottom'] <= p['height']*MARGIN or row['top'] >= p['height']*(1-MARGIN):
                key = re.sub(r'\s+', ' ', re.sub(r'\d+', '#', ' '.join(w['text'] for w in row['words']).lower())).strip()
                seen[key].add(n)
                where[(n, key)].append(row)
    need = max(3, -(-3*len(pages)//10)) if len(pages) >= 3 else len(pages)+1
    keys = {k for k, ps in seen.items() if len(ps) >= need or re.fullmatch(r'[#\W]+', k)}
    per_page = defaultdict(list)
    for (n, key), rows in where.items():
        if key in keys:
            per_page[n].extend(rows)
    return per_page, sorted((len(seen[k]), k) for k in keys)


def _crosses(row, x, gap):
    for w in row['words']:
        if w['bbox'][0] < x < w['bbox'][2]:
            return True
    left = [w['bbox'][2] for w in row['words'] if w['bbox'][2] <= x]
    right = [w['bbox'][0] for w in row['words'] if w['bbox'][0] >= x]
    return bool(left and right) and min(right)-max(left) < gap


def _gutter(rows, width):
    """x of a two-column gutter, or None for a single-column page."""
    if len(rows) < 8:
        return None
    gap = max(6.0, statistics.median(r['h'] for r in rows))
    low, high = int(width*.3), int(width*.7)
    # Each row votes on entire whitespace intervals at once, rather than
    # rescanning every word at every x coordinate (especially costly for surveys).
    events = defaultdict(lambda: [0, 0, 0, 0])
    for row in rows:
        boxes = [w['bbox'] for w in row['words']]  # already sorted left to right
        total = sum(b[2]-b[0] for b in boxes)
        left_width, last = 0., None
        for box in [*boxes, None]:
            if last is None or box is None or box[0]-last >= gap:
                lo = max(low, ceil(last)) if last is not None else low
                hi = min(high, floor(box[0])) if box is not None else high
                if lo <= hi:
                    lt, rt = left_width >= .1*width, total-left_width >= .1*width
                    for i, vote in enumerate((1, lt, rt, lt and rt)):
                        events[lo][i] += vote
                        events[hi+1][i] -= vote
            if box is not None:
                left_width += box[2]-box[0]
                last = box[2] if last is None else max(last, box[2])
    counts, best = [0]*4, None
    edges = sorted(events)
    for x, end in zip(edges, edges[1:]):
        counts = [a+b for a, b in zip(counts, events[x])]
        clear, left, right, both = counts
        cross = len(rows)-clear
        aligned = cross <= .6*len(rows) and both >= max(3, .15*len(rows))
        unaligned = cross <= .15*len(rows) and left-both >= 5 and right-both >= 5
        if left >= 5 and right >= 5 and (aligned or unaligned):
            mid = (x+end-1)/2
            candidate = (clear, both, end-x, -abs(mid-width/2), mid)
            if best is None or candidate > best:
                best = candidate
    return best[-1] if best else None


def _lines(rows, gutter, width):
    """Split rows into column lines, then at wide horizontal gaps (side-by-side text, table cells)."""
    gap = max(6.0, statistics.median(r['h'] for r in rows)) if rows else 6.0
    out = []
    for r in rows:
        if gutter is None:
            parts = [('F', r['words'])]
        elif _crosses(r, gutter, gap):
            parts = [('S', r['words'])]
        else:
            parts = [('L', [w for w in r['words'] if _center(w['bbox'])[0] < gutter]),
                     ('R', [w for w in r['words'] if _center(w['bbox'])[0] >= gutter])]
        for col, ws in parts:
            segments, wide = [], max(15.0, 1.5*r['h'])
            for w in ws:
                if segments and w['bbox'][0]-segments[-1][-1]['bbox'][2] > wide:
                    segments.append([w])
                elif segments:
                    segments[-1].append(w)
                else:
                    segments.append([w])
            for seg in segments:
                b = _extent(seg)
                out.append({'col': col, 'words': seg, 'bbox': b, 'h': max(1.0, b[3]-b[1]),
                            'text': ' '.join(w['text'] for w in seg)})
    return out


def _col_of(box, gutter):
    if gutter is None:
        return 'F'
    if box[0] < gutter-3 and box[2] > gutter+3:
        return 'S'
    return 'L' if _center(box)[0] < gutter else 'R'


def _caption_label(line, fonts, body=None):
    """(kind, number, strong) for a caption start; weak starts need an adjacent object."""
    m = CAPTION.match(line['text'])
    if not m:
        return None
    info = [fonts.get(w['id'], (None, False)) for w in line['words']]
    tail = line['text'][m.end():m.end()+2]
    bold_label = info[0][1] and not all(b for _, b in info)
    caps_alone = line['text'].isupper() and len(line['words']) <= 3
    sizes = [s for s, _ in info if s]
    smaller = bool(body and sizes and statistics.median(sizes) <= body*.97)
    punctuated = tail[:1] in {'.', ':', '|', '—', '–', '-'}
    if not (punctuated or bold_label or caps_alone):
        return None
    kind = 'TABLE' if m.group(1).lower().startswith('tab') else 'FIGURE'
    return kind, m.group(2).upper() if m.group(2).isalpha() else m.group(2), bold_label or caps_alone or smaller


def _heading(line, fonts, body):
    tokens = [w['text'] for w in line['words']]
    text = line['text']
    if CAPTION.match(text) or re.fullmatch(r'[\(\[]?[\d.]+[\)\]]?', text):
        return None
    spaced = sum(len(t) <= 2 for t in tokens[1:]) >= max(3, .6*len(tokens[1:]))
    if spaced:  # "1 I N T RO D U C T I O N" is one heading word set in tracked capitals
        tokens = tokens[:1] + [''.join(tokens[1:])] if NUMBER.match(tokens[0]) else [''.join(tokens)]
    info = [fonts.get(w['id'], (None, False)) for w in line['words']]
    sizes = [s for s, _ in info if s]
    size = statistics.median(sizes) if sizes else body
    bolds = [b for _, b in info]
    score, level, number = 0.0, None, None
    first, rest = tokens[0], tokens[1:]
    m, r, l = NUMBER.match(first), ROMAN.match(first), LETTER.match(first)
    starts_word = bool(rest) and rest[0][:1].isupper()
    if m and starts_word:
        score, level, number = score+2, m.group(1).count('.')+1, m.group(1)
    elif r and starts_word:
        score, level, number = score+2, 1, r.group(1)
    elif l and starts_word and len(tokens) <= 10:
        score, level, number = score+1, 2, l.group(1)
    core = re.sub(r'\s+', ' ', ' '.join(rest if number else tokens)).strip(' .:—–-').lower()
    keyword = core in KEYWORDS or bool(APPENDIX.match(core))
    if keyword:
        score += 2
        level = level or 1
    if body and size and size >= body*1.08:
        score += 2
    if body and size and size >= body*1.25:
        score += 1
    if bolds and all(bolds):
        score += 1.5
    letters = re.sub(r'[^A-Za-z]', '', text)
    if len(letters) >= 4 and letters.isupper() and (len(tokens) <= 8 or spaced):
        score += 1
    if len(tokens) > 14 and not spaced:
        score -= 3
    if text.endswith('.') and len(tokens) > 8:
        score -= 1
    run_in = None
    if bolds and bolds[0] and not all(bolds):
        k = next(i for i, b in enumerate(bolds) if not b)
        if 1 <= k <= 8:
            run_in = ' '.join(tokens[:k])
    return {'score': score, 'level': level, 'number': number, 'core': core, 'keyword': keyword,
            'size': size, 'text': text, 'run_in': None if spaced else run_in, 'structural': bool(number) or keyword}


def _divided_heading(stream, i, fonts, body):
    """A separately typeset divider is not the start of regular-weight prose."""
    if not _divided_number(stream, i):
        return None
    num, bar, first = stream[i:i+3]
    box = num['bbox']
    height = box[3]-box[1]
    def aligned(w, top):
        return abs(w['bbox'][1]-top) <= .35*height
    if (not fonts[num['id']][1] or not fonts[first['id']][1] or
            not all(aligned(w, box[1]) for w in (bar, first)) or
            not (box[2] <= bar['bbox'][0] < bar['bbox'][2] <= first['bbox'][0]) or
            first['bbox'][0]-box[2] > 4*height or
            (i and aligned(stream[i-1], box[1]) and stream[i-1]['bbox'][2] <= box[0])):
        return None
    title = [first]
    for w in stream[i+3:]:
        prev = title[-1]['bbox']
        same_line = aligned(w, prev[1]) and -.5 <= w['bbox'][0]-prev[2] <= 2*height
        wrapped = (prev[1]+.65*height <= w['bbox'][1] <= prev[3]+.6*height and
                   abs(w['bbox'][0]-box[0]) < height and not NUMBER.fullmatch(w['text']))
        if not same_line and not wrapped:
            break
        if not fonts[w['id']][1]:
            if same_line:
                return None  # genuine mixed-style run-in; leave it for verification
            break
        title.append(w)
    words = [num, *title]
    text = ' '.join(w['text'] for w in words)
    h = _heading({'text': text, 'words': words}, fonts, body)
    if h and h['number']:
        return dict(h, tokens=len(words)+1, bbox=_extent(words))
    return None


def _objects(page, area):
    objs = [{'kind': 'table', 'element_id': t['id'], 'bbox': t['bbox']} for t in page['tables']]
    page_area = page['width']*page['height']
    for i in page['images']:
        b = i['bbox']
        if (b[2]-b[0])*(b[3]-b[1]) >= .005*page_area:
            objs.append({'kind': 'bitmap', 'element_id': i['id'], 'bbox': b})
    prims = [g for k in ('lines', 'rects', 'curves') for g in page[k]
             if g['bbox'][1] >= area[1] and g['bbox'][3] <= area[3]]
    for d in _drawing_regions(prims, [0, area[1], page['width'], area[3]]):
        b = d['bbox']
        if (b[2]-b[0]) >= 30 and (b[3]-b[1]) >= 20:
            objs.append({'kind': 'drawing_region', 'element_id': d['anchor_element_id'], 'bbox': b})
    return objs


def _table_rules(page, cap, area, lines, other_caps):
    """Rules of a booktabs-style table under (caption above) or over (caption below) its caption."""
    rules = sorted((g['bbox'] for g in page['lines'] if g['bbox'][3]-g['bbox'][1] <= 1.5
                    and g['bbox'][2]-g['bbox'][0] >= 40 and g['bbox'][0] < cap[2] and cap[0] < g['bbox'][2]
                    and area[1] <= g['bbox'][1] <= area[3]), key=lambda b: b[1])

    def separated(y0, y1):
        # Another caption, or a run of sentence text between two rules, means two different tables.
        lo, hi = min(y0, y1), max(y0, y1)
        if any(lo < (b[1]+b[3])/2 < hi for b in other_caps):
            return True
        prose = [ln for ln in lines if lo < _center(ln['bbox'])[1] < hi and len(ln['words']) >= 10
                 and (ln['bbox'][2]-ln['bbox'][0]) >= .8*(cap[2]-cap[0])]
        return len(prose) >= 2

    for side in (sorted((b for b in rules if 0 <= b[1]-cap[3] <= 400), key=lambda b: b[1]),
                 sorted((b for b in rules if 0 <= cap[1]-b[3] <= 400), key=lambda b: -b[1])):
        if len(side) < 2:
            continue
        near = side[0][1]-cap[3] if side[0][1] >= cap[3] else cap[1]-side[0][3]
        if near > 30:
            continue
        group = [side[0]]
        for b in side[1:]:
            if abs(b[1]-group[-1][1]) > 160 or separated(group[-1][1], b[1]):
                break
            group.append(b)
        if len(group) >= 2:
            return {'kind': 'ruled_lines', 'element_id': None, 'bbox': _extent([{'bbox': b} for b in group])}
    return None


def _captions(lines, fonts, page, area, objects, body):
    """Caption blocks, each paired with at most one object (nearest first)."""
    blocks, used = [], set()
    for i, line in enumerate(lines):
        if i in used or not (label := _caption_label(line, fonts, body)):
            continue
        block = [line]
        for j in range(i+1, len(lines)):
            nxt = lines[j]
            if nxt['col'] != line['col']:
                continue
            if abs(nxt['bbox'][0]-line['bbox'][0]) > 40 or CAPTION.match(nxt['text']):
                break
            # Tight leading alone does not distinguish caption continuation from
            # the next body paragraph. Leave uncertain words in the prose stream.
            if not body or any((fonts[w['id']][0] or body) > .97*body for w in nxt['words']):
                break
            gap = nxt['bbox'][1]-block[-1]['bbox'][3]
            if gap < -1:
                continue
            if gap > max(2.5, .45*block[-1]['h']):
                break
            block.append(nxt)
            used.add(j)
        kind, number, strong = label
        blocks.append({'kind': kind, 'number': number, 'strong': strong, 'label': line['text'][:160],
                       'caption_box': _extent(block), 'word_ids': {w['id'] for ln in block for w in ln['words']},
                       'object': None})
    pairs = []
    for bi, cap in enumerate(blocks):
        box = cap['caption_box']
        for oi, o in enumerate(objects):
            ob = o['bbox']
            overlap = min(box[2], ob[2])-max(box[0], ob[0])
            if overlap < .3*min(box[2]-box[0], ob[2]-ob[0]):
                continue
            dist = 0 if (ob[1] < box[3] and box[1] < ob[3]) else min(abs(box[1]-ob[3]), abs(ob[1]-box[3]))
            if dist <= 40:
                fits = o['kind'] in ({'table', 'drawing_region'} if cap['kind'] == 'TABLE'
                                     else {'bitmap', 'drawing_region', 'table'})
                if fits:
                    pairs.append((dist, bi, oi))
    taken = set()
    for _, bi, oi in sorted(pairs):
        if blocks[bi]['object'] is None and oi not in taken:
            blocks[bi]['object'] = objects[oi]
            taken.add(oi)
    caps = []
    for cap in blocks:
        if cap['object'] is None and cap['kind'] == 'TABLE':
            others = [b['caption_box'] for b in blocks if b is not cap]
            cap['object'] = _table_rules(page, cap['caption_box'], area, lines, others)
        if cap['strong'] or cap['object'] is not None:
            caps.append(cap)  # same-size text merely starting with "Fig. 4." is a body reference
    return caps


def _divided_number(words, i):
    return (i+2 < len(words) and NUMBER.fullmatch(words[i]['text']) and
            words[i+1]['text'] == '|' and words[i+2]['text'][:1].isalpha())


def _mixed_columns(rows, words, width):
    """Recover a locally two-column band around a numbered heading on a mixed page."""
    ys = [_center(w['bbox'])[1] for i, w in enumerate(words) if _divided_number(words, i)]
    if not ys:
        return None
    gap = max(6., statistics.median(r['h'] for r in rows))
    for y in ys:
        i = min(range(len(rows)), key=lambda j: abs(rows[j]['cy']-y))
        local = rows[max(0, i-5):i+16]
        gutter = _gutter(local, width)
        if gutter is None or _crosses(rows[i], gutter, gap):
            continue
        lo = hi = i
        while lo and not _crosses(rows[lo-1], gutter, gap):
            lo -= 1
        while hi+1 < len(rows) and not _crosses(rows[hi+1], gutter, gap):
            hi += 1
        if _gutter(rows[lo:hi+1], width) is not None:
            return gutter, lo, hi
    return None


def _layout(n, ref, page, furniture_rows):
    W, H = page['width'], page['height']
    furn_ids = {w['id'] for r in furniture_rows for w in r['words']}
    top = max([r['bottom'] for r in furniture_rows if r['bottom'] <= H*MARGIN] + [0.0])
    bottom = min([r['top'] for r in furniture_rows if r['top'] >= H*(1-MARGIN)] + [H])
    top = top+.5 if top else 0.0
    bottom = bottom-.5 if bottom < H else H
    # Only strip contiguous margin material; a repeated row below a title,
    # or above a footnote, must not take that other text with it.
    kept = [w for w in page['words'] if w['id'] not in furn_ids]
    if kept:
        top = max(0., min(top, min(w['bbox'][1] for w in kept)))
        bottom = min(H, max(bottom, max(w['bbox'][3] for w in kept)))
    words = [w for w in page['words'] if top <= _center(w['bbox'])[1] < bottom]
    rows = _rows(words)
    gutter = _gutter(rows, W)
    mixed = _mixed_columns(rows, words, W) if gutter is None and rows else None
    if mixed:
        gutter, lo, hi = mixed
        def spanning(part):
            return [dict(ln, col='S') for ln in _lines(part, None, W)]
        lines = spanning(rows[:lo]) + _lines(rows[lo:hi+1], gutter, W) + spanning(rows[hi+1:])
    else:
        lines = _lines(rows, gutter, W)
    return {'page': n, 'ref': ref, 'width': W, 'height': H, 'area': [0.0, top, W, bottom],
            'gutter': gutter, 'rows': rows, 'lines': lines, 'flags': page['flags']}


def _carves(lay, page, fonts, body):
    """Figure/table regions removed from the prose flow, as full column-width cells."""
    objects = _objects(page, lay['area'])
    caps = _captions(lay['lines'], fonts, page, lay['area'], objects, body)
    W, g = lay['width'], lay['gutter']
    out = []
    for cap in caps:
        box = _union(cap['caption_box'], cap['object']['bbox']) if cap['object'] else cap['caption_box']
        cb = cap['caption_box']
        for other in caps:
            ob = other['caption_box']
            if other is cap or not (ob[0] < box[2] and box[0] < ob[2]):
                continue
            # An object region never reaches past the next caption (stacked tables, adjacent figures).
            if ob[1] >= cb[3] and ob[1] < box[3]:
                box = [box[0], box[1], box[2], max(cb[3], ob[1]-1)]
            elif ob[3] <= cb[1] and ob[3] > box[1]:
                box = [box[0], min(cb[1], ob[3]+1), box[2], box[3]]
        col = _col_of(box, g)
        x0, x1 = {'F': (0, W), 'S': (0, W), 'L': (0, g), 'R': (g, W)}[col]
        cell = [x0, max(lay['area'][1], box[1]-1), x1, min(lay['area'][3], box[3]+1)]
        # Do not give a full column-width band to an unpaired label, a
        # figure beside prose, or a region spanning a paragraph of body text.
        obj = cap['object']
        safe = obj is not None
        if safe:
            for ln in lay['lines']:
                extra = [w for w in ln['words'] if w['id'] not in cap['word_ids'] and _inside(w['bbox'], cell)]
                if len(extra) >= 10 or any(not _inside(w['bbox'], obj['bbox']) for w in extra):
                    safe = False
                    break
        cap.update(col=col, cell=cell, carved=safe)
        out.append(cap)
    # Competing ownership is not evidence for either object. Keep both in
    # prose rather than allowing the partitioner to merge their regions.
    for i, first in enumerate(out):
        a = first['cell']
        for second in out[i+1:]:
            b = second['cell']
            if a[0] < b[2] and b[0] < a[2] and a[1] <= b[3] and b[1] <= a[3]:
                first['carved'] = second['carved'] = False
    return out


def _cells(lay, carves):
    """Partition the body area into ordered prose cells and carve cells (no overlaps)."""
    W, g, (_, top, _, bottom) = lay['width'], lay['gutter'], lay['area']
    carved = [c for c in carves if c['carved']]
    in_carve = lambda b: any(_inside(b, c['cell']) for c in carved)
    spans = [(c['cell'][1], c['cell'][3], 'carve', c) for c in carved if c['col'] in {'S', 'F'}]
    for ln in lay['lines']:
        if ln['col'] == 'S' and not in_carve(ln['bbox']):
            spans.append((ln['bbox'][1], ln['bbox'][3], 'prose', None))
    spans.sort(key=lambda s: s[0])
    merged = []
    for s in spans:
        if merged and s[0] <= merged[-1][1] and (s[2] == merged[-1][2] == 'prose' or 'carve' in (s[2], merged[-1][2])):
            a = merged[-1]
            keep = a if a[2] == 'carve' else s if s[2] == 'carve' else a
            merged[-1] = (a[0], max(a[1], s[1]), keep[2], keep[3])
            carve = keep[3]
            if isinstance(carve, dict):
                carve['cell'] = [carve['cell'][0], a[0], carve['cell'][2], max(a[1], s[1])]
        elif merged and s[2] == 'prose' == merged[-1][2] and not any(
                ln['col'] in {'L', 'R'} and merged[-1][1] <= _center(ln['bbox'])[1] < s[0] for ln in lay['lines']):
            merged[-1] = (merged[-1][0], s[1], 'prose', None)
        else:
            merged.append(s)
    edges, bands = [top], []
    for i, s in enumerate(merged):
        prev_end = merged[i-1][1] if i else None
        lo = top if i == 0 and s[0] <= top+1 else (s[0]+prev_end)/2 if prev_end is not None and s[0]-prev_end < 2 else s[0]-.5
        bands.append(('column', edges[-1], max(edges[-1], lo)))
        nxt = merged[i+1][0] if i+1 < len(merged) else None
        hi = min(bottom, s[1]+.5 if nxt is None or nxt-s[1] >= 2 else (s[1]+nxt)/2)
        bands.append((s[2], max(edges[-1], lo), hi, s[3]))
        edges.append(hi)
    bands.append(('column', edges[-1], bottom))
    cells = []
    for band in bands:
        role, a, b = band[0], band[1], band[2]
        if b-a <= .5:
            continue
        if role == 'carve':
            cells.append({'role': 'carve', 'bbox': [0.0, a, W, b], 'carve': band[3]})
        elif role == 'prose':
            cells.append({'role': 'prose', 'bbox': [0.0, a, W, b]})
        elif g is None:
            cells.append({'role': 'prose', 'bbox': [0.0, a, W, b]})
        else:
            for col, x0, x1 in (('L', 0.0, g), ('R', g, W)):
                pieces, cursor = [], a
                for c in sorted((c for c in carved if c['col'] == col and c['cell'][1] < b and c['cell'][3] > a),
                                key=lambda c: c['cell'][1]):
                    ca, cb = max(a, cursor, c['cell'][1]), min(b, c['cell'][3])
                    if cb - ca <= .5:
                        continue
                    if ca > cursor:
                        pieces.append({'role': 'prose', 'bbox': [x0, cursor, x1, ca]})
                    pieces.append({'role': 'carve', 'bbox': [x0, ca, x1, cb], 'carve': c})
                    cursor = max(cursor, cb)
                if b > cursor:
                    pieces.append({'role': 'prose', 'bbox': [x0, cursor, x1, b]})
                cells.extend(p for p in pieces if p['bbox'][3]-p['bbox'][1] > .5)
    return cells


def _stream(page, cell):
    return [w for w in page['words'] if _inside(w['bbox'], cell['bbox'])]


def _phrase(stream, index, minimum):
    """Shortest token sequence from index that occurs once in this stream."""
    texts = [w['text'] for w in stream]
    matches = [i for i, t in enumerate(texts) if t == texts[index]]
    parts = []
    for k, token in enumerate(texts[index:index+MAX_ANCHOR], 1):
        if not token or re.search(r'\s', token):
            break  # the reader uses phrase.split(); this token cannot round trip
        parts.append(token)
        if k > 1 and len(matches) > 1:
            matches = [i for i in matches if i+k <= len(texts) and texts[i+k-1] == token]
        if len(matches) == 1 and (k >= minimum or index+k == len(texts)):
            return ' '.join(parts)
    return None


def _box_out(b, width, height):
    # This is a selector, not a display bbox. Rounding a half-open edge can
    # move a word to another unit and invalidate a previously unique anchor.
    return [max(0., b[0]), max(0., b[1]), min(b[2], width), min(b[3], height)]


def _slug(text):
    return re.sub(r'[^A-Za-z0-9]+', '-', text).strip('-')[:24] or 'X'


def analyze(root, source_id=None, packet=None):
    root = Path(root).resolve()
    if packet is None:
        packet = json.loads((root/'paper_packet.json').read_text(encoding='utf-8-sig'))
    sources = [s['source_id'] for s in packet.get('sources', []) if s.get('access_state') == 'AVAILABLE']
    sid = source_id or (sources[0] if sources else None)
    pages = _native(root, packet, sid)
    furniture, repeated = _furniture(pages)
    layouts, fonts_by_page, all_sizes = [], {}, Counter()
    for n, (ref, page) in sorted(pages.items()):
        fonts = _fonts(page)
        fonts_by_page[n] = fonts
        for c in page['chars']:
            if c.get('size') and str(c.get('text', '')).strip():
                all_sizes[round(float(c['size'])*2)/2] += 1
        layouts.append(_layout(n, ref, page, furniture.get(n, [])))
    body = all_sizes.most_common(1)[0][0] if all_sizes else None
    cells, carves, headings, notes, bitmaps = [], [], [], [], []
    for lay in layouts:
        page = pages[lay['page']][1]
        fonts = fonts_by_page[lay['page']]
        page_carves = _carves(lay, page, fonts, body) if page['words'] else []
        paired = {c['object']['element_id'] for c in page_carves if c['object'] and c['object']['kind'] == 'bitmap'}
        bitmaps.extend({'page': lay['page'], 'element_id': img['id'], 'bbox': img['bbox']}
                       for img in page['images'] if img['id'] not in paired)
        if not page['words']:
            notes.append(f"p{lay['page']}: no native text — inspect the original page; unreadable content stays a READING_GAP.")
            continue
        if set(page['flags']) & {'GLYPH_MAPPING_CONFLICT', 'NO_NATIVE_TEXT'}:
            notes.append(f"p{lay['page']}: {', '.join(page['flags'])} — verify glyphs against the original before relying on this text.")
        for c in page_carves:
            c['page'] = lay['page']
        carves.extend(page_carves)
        home = {}
        accounted = set()
        for cell in _cells(lay, page_carves):
            cell.update(page=lay['page'], ref=lay['ref'], width=lay['width'], height=lay['height'])
            cell['bbox'] = _box_out(cell['bbox'], cell['width'], cell['height'])
            cell['stream'] = _stream(page, cell)
            if not cell['stream']:
                continue
            cells.append(cell)
            accounted.update(w['id'] for w in cell['stream'])
            if cell['role'] == 'carve':
                c = cell['carve']
                # A spanning row can enlarge a band in _cells. Never give its
                # unrelated words to a caption instead of their prose section.
                if any(w['id'] not in c['word_ids'] and not _inside(w['bbox'], c['object']['bbox'])
                       for w in cell['stream']):
                    cell['role'] = 'prose'
            if cell['role'] == 'prose':
                home.update((w['id'], (cell, i)) for i, w in enumerate(cell['stream']))
        furniture_ids = {w['id'] for row in furniture.get(lay['page'], ()) for w in row['words']}
        unmapped = [w for w in page['words'] if w['id'] not in accounted and w['id'] not in furniture_ids]
        if unmapped:
            notes.append(f"p{lay['page']}: {len(unmapped)} non-margin words outside draft cells, starting at "
                         f"{unmapped[0]['id']}; inspect this page before using its draft.")
        caption_words = {wid for c in page_carves for wid in c['word_ids']}
        divided = set()
        for wid, (cell, i) in home.items():
            if wid in caption_words:
                continue
            if h := _divided_heading(cell['stream'], i, fonts, body):
                inside = any(c['object'] and _inside(h['bbox'], c['object']['bbox']) for c in page_carves)
                headings.append(dict(h, page=lay['page'], cell=cell, index=i, inside_object=inside))
                divided.add(wid)
        for ln in lay['lines']:
            first = ln['words'][0]['id']
            if first not in home or first in caption_words or first in divided:
                continue
            h = _heading(ln, fonts, body)
            if h and h['score'] >= 2:
                cell, index = home[first]
                inside_object = any(c['object'] and _inside(ln['bbox'], c['object']['bbox']) for c in page_carves)
                headings.append(dict(h, page=lay['page'], cell=cell, index=index, inside_object=inside_object,
                                     tokens=len(ln['words']), bbox=ln['bbox']))
    order = {id(c): i for i, c in enumerate(cells)}
    headings.sort(key=lambda h: (order[id(h['cell'])], h['index']))
    repeats = Counter(h['text'].casefold() for h in headings)
    active = {}
    for h in headings:
        num = h['number'] or ''
        parent, _, _ = num.rpartition('.')
        # Plain-font '2.1 …' under the current section 2 is stronger evidence
        # than an isolated number in a table. Bold text alone is not a section.
        nested = parent and active.get(h['level']-1) == parent and h['tokens'] <= 12 and not h['text'].endswith('.')
        integer_jump = (num.isdecimal() and len(num) > 1 and not h['keyword'] and
                        active.get(1) != str(int(num)-1))
        h['accepted'] = bool(h['structural'] and not h['run_in'] and not h['inside_object'] and not integer_jump and
                             repeats[h['text'].casefold()] == 1 and (h['score'] >= 3 or nested))
        if h['accepted']:
            level = h['level'] or 1
            active = {lv: n for lv, n in active.items() if lv < level}
            active[level] = num
    accepted = [h for h in headings if h['accepted']]
    for i, h in enumerate(accepted):
        if h['core'] != 'abstract':
            continue
        tail = accepted[i+1] if i+1 < len(accepted) else None
        last = order[id(tail['cell'])] + bool(tail['index']) if tail else len(cells)
        mapped = {c['page'] for c in cells[order[id(h['cell'])]:last] if c['role'] == 'prose'}
        if len(mapped) > 2:
            h['mapping_warning'] = (f"p{h['page']}: abstract would cover {len(mapped)} pages; "
                                    'verify the first body heading before mapping it.')
            notes.append(h['mapping_warning'])
    actual_carves = {id(c['carve']) for c in cells if c['role'] == 'carve'}
    for cap in carves:
        cap['carved'] = id(cap) in actual_carves
    return {'source_id': sid, 'id_prefix': sid+'__' if len(packet['sources']) > 1 else '',
            'pages': pages, 'layouts': layouts, 'body_size': body, 'cells': cells,
            'carves': carves, 'headings': headings, 'unpaired_bitmaps': bitmaps, 'repeated': repeated, 'notes': notes}


def _section_ids(heads):
    ids, used, parents = [], set(), {}
    last_top = None
    active = {}
    for h in heads:
        if h['number'] and NUMBER.match(h['number']):
            base = 'S' + h['number']
        elif h['number'] and ROMAN.match(h['number'] + '.'):
            base = 'S' + h['number']
        elif h['number'] and LETTER.match(h['number'] + '.'):
            base = (last_top or 'S') + '-' + h['number']
        elif h['core'] in REFERENCES:
            base = 'REF'
        else:
            base = 'S-' + _slug(h['core'] or h['text']).upper()
        uid, k = base, 2
        while uid in used:
            uid, k = f'{base}-{k}', k+1
        used.add(uid)
        ids.append(uid)
        level = h['level'] or 1
        active = {k: v for k, v in active.items() if k < level}
        if level == 1:
            last_top = uid
        elif level-1 in active:
            parent_number, parent_id = active[level-1]
            if (h['number'] or '').rpartition('.')[0] == parent_number or LETTER.match((h['number'] or '')+'.'):
                parents[uid] = parent_id
        active[level] = (h['number'], uid)
    return ids, parents


def draft_inventory(result):
    sid, cells = result['source_id'], result['cells']
    prose = [c for c in cells if c['role'] == 'prose']
    heads = [h for h in result['headings'] if h['accepted']]
    review = []
    namespace = result['id_prefix']
    local_ids, local_parents = _section_ids(heads)
    ids = [namespace+i for i in local_ids]
    parents = {namespace+c: namespace+p for c, p in local_parents.items()}
    indices = {id(cell): i for i, cell in enumerate(prose)}
    starts = [(indices[id(h['cell'])], h['index'], h) for h in heads]
    # A boundary is shared by the units on each side. Compute it only once.
    anchors = {(ci, wi): _phrase(prose[ci]['stream'], wi, min(h['tokens'], 10))
               for ci, wi, h in starts if wi}
    blocks = []
    if prose and (not starts or starts[0][:2] != (0, 0)):
        blocks.append((namespace+'FRONT', 'SECTION', 'Front matter / text before the first proposed section', None, (0, 0)))
    for uid, (ci, wi, h) in zip(ids, starts):
        kind = 'BIBLIOGRAPHY' if h['core'] in REFERENCES else 'APPENDIX' if APPENDIX.match(h['core']) else 'SECTION'
        blocks.append((uid, kind, h['text'][:160], h, (ci, wi)))
    in_appendix = False
    units = []
    for b, (uid, kind, label, h, (ci, wi)) in enumerate(blocks):
        if kind == 'APPENDIX':
            in_appendix = True
        elif in_appendix and kind == 'SECTION':
            kind = 'APPENDIX'
        end = blocks[b+1][4] if b+1 < len(blocks) else (len(prose), 0)
        locators, unresolved = [], False
        for k in range(ci, min(end[0], len(prose)-1)+1):
            cell = prose[k]
            stream = cell['stream']
            lo = wi if k == ci else 0
            hi = end[1] if k == end[0] else len(stream)
            if lo >= hi:
                continue
            loc = {'physical_page': cell['page'], 'section': label, 'body': {'bbox': cell['bbox']}}
            for key, at in (('start_at', lo), ('stop_before', hi)):
                if 0 < at < len(stream):
                    phrase = anchors[k, at]
                    if phrase is None:
                        unresolved = True
                        loc['paragraph_or_cell'] = f'Unresolved {key} before {stream[at]["id"]} in {cell["bbox"]}.'
                        review.append(f'{uid}: no unique {key} phrase on p{cell["page"]}; '
                                      f'unit unmapped. Verify the boundary at {stream[at]["id"]} by hand.')
                    else:
                        loc['body'][key] = phrase
            locators.append(loc)
        if h and h.get('mapping_warning') and locators:
            review.append(f"{uid}: {h['mapping_warning']}")
            locators[0]['paragraph_or_cell'] = h['mapping_warning']
            unresolved = True
        if unresolved:
            # A partly mapped section also reads as though it were complete.
            # Keep the page hints, but let read-section fail SECTION_UNMAPPED.
            for loc in locators:
                del loc['body']
        if not locators:
            review.append(f'{uid}: heading found but no text before the next heading; check whether it is a running title or merge it.')
        units.append({'unit_id': uid, 'kind': kind, 'label': label, 'parent_id': parents.get(uid),
                      'children': [], 'source_id': sid, 'locators': locators})
    by_id = {u['unit_id']: u for u in units}
    for u in units:
        if u['parent_id'] in by_id:
            by_id[u['parent_id']]['children'].append(u['unit_id'])
    objects, seen = [], Counter()
    carved_cells = defaultdict(list)
    for cell in cells:
        if cell['role'] == 'carve':
            carved_cells[id(cell['carve'])].append(cell['bbox'])
    for c in result['carves']:
        prefix = 'T' if c['kind'] == 'TABLE' else 'F'
        base = namespace + prefix + c['number'].replace('.', '')
        seen[base] += 1
        uid = base if seen[base] == 1 else f'{base}-{seen[base]}'
        if seen[base] > 1:
            review.append(f'{uid}: caption number repeats ({base}); merge as a continuation or correct the label.')
        loc = {'physical_page': c['page'], 'object_label': f"{'Table' if prefix == 'T' else 'Figure'} {c['number']}",
               'paragraph_or_cell': None}
        boxes = carved_cells[id(c)]
        locs = [dict(loc, body={'bbox': b}) for b in boxes] or [loc]
        if not c['object']:
            review.append(f'{uid}: caption on p{c["page"]} but no object region found; locate it with read-elements --view locator.')
        elif not c['carved']:
            review.append(f'{uid}: object region on p{c["page"]} overlaps running text; its words stay in the section text.')
        objects.append({'unit_id': uid, 'kind': c['kind'], 'label': c['label'], 'parent_id': None,
                        'children': [], 'source_id': sid, 'locators': locs})
    for page, count in sorted(Counter(b['page'] for b in result['unpaired_bitmaps']).items()):
        review.append(f'p{page}: {count} bitmap(s) without a matched caption. Inspect their positions with '
                      'read-elements --view locator; add informative objects/panels before G0.')
    return units + objects, review


def _heading_ids(result):
    heads = [h for h in result['headings'] if h['accepted']]
    return {id(h): result['id_prefix'] + uid for h, uid in zip(heads, _section_ids(heads)[0])}


def _listing(lines, items, hint='outline --format json', limit=60):
    shown = 0
    for shown, item in enumerate(items, 1):
        if shown <= limit:
            lines.append(item)
    if shown > limit:
        lines.append(f'  … {shown-limit} omitted; see {hint} for the full list.')


def outline_text(result, draft=None, review=None, out=None):
    lines = [f"OUTLINE {result['source_id']} · {len(result['pages'])} pages · body text {result['body_size']}pt",
             'Navigation candidates only; G0 is not assessed. Verify headings, columns and objects on the source.']
    two = [str(l['page']) for l in result['layouts'] if l['gutter'] is not None]
    lines.append('Two-column pages: ' + (', '.join(two) if two else 'none'))
    if result['repeated']:
        lines.append('Repeated margin text: ' + '; '.join(f'"{k[:60]}" ×{n}' for n, k in result['repeated'][:6]))
    lines.append('Headings (unit_id = proposed draft split; ? = candidate only):')
    ids = _heading_ids(result)
    front_id = result['id_prefix'] + 'FRONT'
    if draft and draft[0]['unit_id'] == front_id:
        lines.append(f'  {front_id} p{draft[0]["locators"][0]["physical_page"]} text before the first proposed section')
    _listing(lines, (f"  {ids.get(id(h), '?')} p{h['page']} L{h['level'] or '-'} {h['text'][:90]}"
                     + (' [run-in]' if h['run_in'] else '') for h in result['headings']))
    lines.append('Caption / object candidates (PDF points, top-left origin):')
    def captions():
        for c in result['carves']:
            obj = c['object']
            where = f"{obj['kind']} {obj['element_id'] or ''} bbox={obj['bbox']}" if obj else f"object not found; caption bbox={c['caption_box']}"
            yield f"  p{c['page']} {c['kind']} {c['number']}: {where}" + (' (left in prose)' if not c['carved'] else '')
    _listing(lines, captions())
    bitmaps = result['unpaired_bitmaps']
    if bitmaps:
        lines.append(f'{len(bitmaps)} unpaired bitmap(s); inspect for unnumbered figures/panels:')
        _listing(lines, (f"  p{b['page']} {b['element_id']} bbox={b['bbox']}" for b in bitmaps))
    _listing(lines, ('Note: ' + note for note in result['notes']))
    if draft is not None:
        kinds = Counter(u['kind'] for u in draft)
        lines.append(f"Draft inventory written to {out}: " + ', '.join(f'{k} {n}' for k, n in sorted(kinds.items())))
        lines.append('Next: verify, merge/split, add missed objects; only then sync 01_inventory.json, check '
                     'section-coverage --details and use read-section --id UNIT_ID. No gate or reading state changed.')
        _listing(lines, ('Review: ' + r for r in review or []), 'outline --format json --out tools/NEW.json')
    return '\n'.join(lines)


def outline_json(result):
    ids = _heading_ids(result)
    return {'source_id': result['source_id'], 'page_count': len(result['pages']), 'body_size': result['body_size'],
            'two_column_pages': [l['page'] for l in result['layouts'] if l['gutter'] is not None],
            'repeated_margin_text': [{'pages': n, 'text': k} for n, k in result['repeated']],
            'headings': [{'page': h['page'], 'level': h['level'], 'text': h['text'], 'accepted': h['accepted'],
                          'draft_unit_id': ids.get(id(h)), 'run_in': h['run_in'], 'bbox': h['bbox']} for h in result['headings']],
            'captions': [{'page': c['page'], 'kind': c['kind'], 'number': c['number'], 'label': c['label'],
                          'caption_bbox': c['caption_box'], 'object': c['object'], 'carved': c['carved']} for c in result['carves']],
            'unpaired_bitmap_count': len(result['unpaired_bitmaps']), 'unpaired_bitmaps': result['unpaired_bitmaps'],
            'notes': result['notes'], 'reading_state_changed': False, 'purpose': 'NAVIGATION_ONLY', 'g0_assessed': False}


def _draft_path(root, out):
    target = root / Path(out)
    try:
        rel = target.relative_to(root/'tools')
    except ValueError:
        rel = None
    reserved = getattr(ntpath, 'isreserved', lambda p: PureWindowsPath(p).is_reserved())
    if (not rel or not rel.parts or rel.suffix.lower() != '.json' or '..' in Path(out).parts or
            any(p.endswith(('.', ' ')) or ':' in p or '\x00' in p or reserved(p) for p in rel.parts)):
        raise ElementError('INVALID_PATH', 'Choose a new JSON path under the run, e.g. tools/inventory.draft.json.')
    return target.relative_to(root)


def _pin_windows_directory(path, stack):
    # Win32 has no os.open(dir_fd=...). Open the directory *itself* and
    # deny write/delete sharing until the child has been exclusively created.
    import _winapi
    flags = 0x02000000 | 0x00200000  # FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT
    handle = _winapi.CreateFile(str(path), _winapi.GENERIC_READ, 1, 0, _winapi.OPEN_EXISTING, flags, 0)
    stack.callback(_winapi.CloseHandle, handle)
    s = path.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ElementError('INVALID_PATH', f'Draft directory must not be a link or reparse point: {path}')


def _write_draft(root, rel, data):
    # No resolve/check-then-write: an existing/dangling leaf must lose the
    # exclusive create, and a swapped parent must never redirect the write.
    try:
        with ExitStack() as stack:
            if os.name == 'nt':
                current = root
                _pin_windows_directory(current, stack)
                for part in rel.parts[:-1]:
                    current /= part
                    current.mkdir(exist_ok=True)
                    _pin_windows_directory(current, stack)
                # Python's Windows open('x') can follow a *dangling* final
                # symlink. CREATE_NEW must address the reparse point itself.
                import _winapi
                import msvcrt
                handle = _winapi.CreateFile(str(current/rel.name), _winapi.GENERIC_WRITE, 0, 0,
                                            1, 0x00200000, 0)  # CREATE_NEW, FILE_FLAG_OPEN_REPARSE_POINT
                try:
                    fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
                except OSError:
                    _winapi.CloseHandle(handle)
                    raise
                file = os.fdopen(fd, 'wb')
            else:
                flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                fd = os.open(root, flags)
                stack.callback(os.close, fd)
                for part in rel.parts[:-1]:
                    try:
                        os.mkdir(part, 0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                    fd = os.open(part, flags, dir_fd=fd)
                    stack.callback(os.close, fd)
                file = os.fdopen(os.open(rel.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                         0o600, dir_fd=fd), 'wb')
            with file:
                file.write(data)
    except FileExistsError as exc:
        raise ElementError('DRAFT_EXISTS', 'Choose a new path; a draft never overwrites an existing file.') from exc
    except OSError as exc:
        raise ElementError('INVALID_PATH', f'Cannot safely create the draft under tools/: {exc}') from exc


def run_outline(root, source_id=None, out=None, packet=None):
    root = Path(root).absolute()
    rel = _draft_path(root, out) if out is not None else None
    result = analyze(root, source_id, packet)
    if rel is None:
        return result, None, None
    units, review = draft_inventory(result)
    _write_draft(root, rel, (json.dumps(units, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8'))
    return result, units, review
