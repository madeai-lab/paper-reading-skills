"""Section-ordered text projection and a separate physical-page coverage audit."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path

from reading_element_contracts import error_code, validated_pages
from reading_pdf_elements import MAX_READ_CHARS, ElementError, word_text
from reading_run_records import read

TEXT_KINDS = {'SECTION', 'APPENDIX', 'BIBLIOGRAPHY'}


def _native(root, packet, source_id):
    if not packet.get('content_acquisition'):
        raise ElementError('ELEMENTS_INVALID', 'No frozen native acquisition. Read the source by section; do not migrate this run.')
    try:
        pages = validated_pages(root, packet)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ElementError(error_code(exc), str(exc)) from exc
    selected = {p['page']: (ref, p) for ref, p in pages.items() if p['source_id'] == source_id}
    if any(s.get('source_id') == source_id and s.get('source_kind') == 'DATA_FILE' for s in packet.get('sources', [])):
        raise ElementError('INVALID_ARGUMENT', 'This is a DATA_FILE source; read it with read-data and file + row/field locators.')
    if not selected:
        raise ElementError('INVALID_ARGUMENT', 'Select a source_id in the frozen native manifest.')
    return selected


def _anchor(words, phrase):
    if not isinstance(phrase, str) or not phrase.strip():
        raise ValueError('A text boundary needs a nonempty exact native phrase.')
    tokens = phrase.split()
    matches = [i for i, w in enumerate(words) if w['text'] == tokens[0] and
               [s['text'] for s in words[i:i+len(tokens)]] == tokens]
    if len(matches) != 1:
        raise ValueError(f'Boundary {phrase!r} matched {len(matches)} times. Verify the source or narrow the bbox.')
    return matches[0]


def _span_words(page, body):
    if not isinstance(body, dict) or body.keys() - {'bbox', 'start_at', 'stop_before'}:
        raise ValueError('body must be an object with only bbox, start_at or stop_before.')
    words = page['words']
    if 'bbox' in body:
        box = body['bbox']
        if (not isinstance(box, list) or len(box) != 4 or
                any(type(x) not in (int,float) or not isfinite(x) for x in box) or
                not (0 <= box[0] < box[2] <= page['width'] and 0 <= box[1] < box[3] <= page['height'])):
            raise ValueError('Use a positive bbox inside the source page (PDF points, top-left origin).')
        words = [w for w in words if box[0] <= (w['bbox'][0]+w['bbox'][2])/2 < box[2]
                 and box[1] <= (w['bbox'][1]+w['bbox'][3])/2 < box[3]]
    start = _anchor(words, body['start_at']) if 'start_at' in body else 0
    stop = _anchor(words, body['stop_before']) if 'stop_before' in body else len(words)
    if start >= stop:
        raise ValueError('Empty or reversed body span. Resolve the boundary or inspect missing native text.')
    return words[start:stop]


@dataclass
class Span:
    locator_index: int
    ref: str
    page: dict
    words: list

    def chunk(self, lo, hi):
        words = self.words[lo:hi]
        return {'locator_index': self.locator_index, 'physical_page': self.page['page'], 'page_ref': self.ref,
                'text_id': self.page['text_id'], 'first_word_id': words[0]['id'], 'last_word_id': words[-1]['id'],
                'flags': self.page['flags'], 'text': word_text(words)}


def _spans(unit, pages):
    spans = []
    seen = defaultdict(set)
    locators = unit.get('locators', [])
    if not isinstance(locators, list):
        raise ValueError('Section locators must be an ordered list.')
    for i, loc in enumerate(locators):
        if not isinstance(loc, dict):
            raise ValueError(f'Locator {i} must be an object.')
        if 'body' not in loc:
            continue
        page_num = loc.get('physical_page')
        if type(page_num) is not int or page_num not in pages:
            raise ValueError(f'Locator {i} has no valid physical_page for its source.')
        ref, page = pages[page_num]
        words = _span_words(page, loc['body'])
        ids = {w['id'] for w in words}
        if not seen[page_num].isdisjoint(ids):
            raise ValueError(f'Overlapping body spans in locator {i} on page {page_num}.')
        seen[page_num].update(ids)
        spans.append(Span(i, ref, page, words))
    return spans


def _section_text(obj):
    lines = [f"{obj['unit_id']} — {obj['label']} [{obj['source_id']}]"]
    for seg in obj['segments']:
        flags = ','.join(seg['flags']) or 'none'
        lines.extend((f"[p{seg['physical_page']} {seg['page_ref']} {seg['text_id']} "
                      f"{seg['first_word_id']}..{seg['last_word_id']} flags={flags}]", seg['text']))
    lines.append('next_cursor: ' + (obj['next_cursor'] or 'END'))
    return '\n\n'.join(lines)


def read_section(root, unit_id, cursor=None, max_chars=MAX_READ_CHARS, *, output_format='json'):
    if output_format not in ('json','text'):
        raise ElementError('INVALID_ARGUMENT', 'Use --format text or json for a section.')
    root = Path(root).resolve(); packet = read(root/'paper_packet.json')
    unit = next((u for u in packet.get('units', []) if u['unit_id'] == unit_id), None)
    if not unit or unit.get('kind') not in TEXT_KINDS:
        raise ElementError('INVALID_SECTION', 'Use the ID of a synced SECTION, APPENDIX or BIBLIOGRAPHY unit.')
    if type(max_chars) is not int or not 0 < max_chars <= MAX_READ_CHARS:
        raise ElementError('ELEMENT_READ_LIMIT', f'Omit --max-chars (default {MAX_READ_CHARS}) or use 1–{MAX_READ_CHARS}; follow next_cursor for the rest of the section.')
    pages = _native(root, packet, unit['source_id'])
    try:
        spans = _spans(unit, pages)
    except ValueError as exc:
        raise ElementError('INVALID_SECTION_MAP', f'{unit_id}: {exc}') from exc
    if not spans:
        raise ElementError('SECTION_UNMAPPED', 'No verified body locators for this unit; a page reference alone is not a section boundary.')
    manifest = root/packet['content_acquisition']['manifest_ref']
    digest = sha256(manifest.read_bytes())
    digest.update(json.dumps([unit_id, unit['source_id'], unit['locators']], sort_keys=True).encode())
    tag = digest.hexdigest()[:20]
    total = sum(len(s.words) for s in spans)
    offset = 0
    if cursor is not None:
        prefix, _, index = cursor.partition(':') if isinstance(cursor,str) else ('','','')
        if prefix != tag or not index.isascii() or not index.isdecimal() or len(index)>10 or not 0 < int(index) < total:
            raise ElementError('INVALID_SECTION_CURSOR', 'Use the last next_cursor from this unchanged section, or restart it.')
        offset = int(index)

    def response(stop):
        segments = []; base = 0
        for span in spans:
            end = base+len(span.words)
            if end > offset and base < stop:
                segments.append(span.chunk(max(0,offset-base), min(stop-base,len(span.words))))
            base = end
            if base >= stop: break
        return {'unit_id': unit_id, 'label': unit.get('label'), 'source_id': unit['source_id'], 'segments': segments,
                'next_cursor': f'{tag}:{stop}' if stop < total else None, 'reading_state_changed': False}

    def fits(obj):
        display = _section_text(obj) if output_format == 'text' else json.dumps(obj,ensure_ascii=True,separators=(',',':'))
        return len(display) + 1 <= max_chars

    lo, hi = offset+1, min(total,offset+max_chars)
    best = response(hi)
    if fits(best):
        return _section_text(best) if output_format == 'text' else best
    best = None
    while lo <= hi:
        mid = (lo+hi)//2; part = response(mid)
        if fits(part):
            best = part; lo = mid+1
        else:
            hi = mid-1
    if best is None:
        raise ElementError('ELEMENT_READ_LIMIT', 'A single native word and provenance do not fit. Increase the budget or inspect the source conflict.')
    return _section_text(best) if output_format == 'text' else best


def _runs(page, mapped):
    """Consecutive unmapped native words in page order, with a short preview."""
    runs, cur = [], []
    for w in page['words']:
        if w['id'] in mapped:
            if cur:
                runs.append(cur)
            cur = []
        else:
            cur.append(w)
    if cur:
        runs.append(cur)
    out = []
    for r in runs:
        text = ' '.join(w['text'] for w in r)
        box = [min(w['bbox'][0] for w in r), min(w['bbox'][1] for w in r),
               max(w['bbox'][2] for w in r), max(w['bbox'][3] for w in r)]
        where = ('top margin' if box[3] <= page['height']*.09 else
                 'bottom margin' if box[1] >= page['height']*.91 else 'body')
        out.append({'first_word_id': r[0]['id'], 'last_word_id': r[-1]['id'], 'words': len(r),
                    'bbox': [round(v, 1) for v in box], 'position': where,
                    'text': text if len(text) <= 160 else text[:157] + '...'})
    return out


def section_coverage(root, source_id, details=False, pages_filter=None, limit=60, offset=0):
    """Account for native words page by page. Any unit kind may own body selectors (captions, table text)."""
    root = Path(root).resolve(); packet = read(root/'paper_packet.json')
    pages = _native(root,packet,source_id)
    counts = defaultdict(Counter)
    result = {'source_id': source_id, 'page_count': len(pages), 'unmapped_pages': [], 'partial_pages': [],
              'overlap_pages': [], 'no_native_text_pages': [], 'unbound_sections': [], 'invalid_sections': {},
              'reading_state_changed': False, 'purpose': 'MAPPING_AUDIT_ONLY'}
    for unit in packet.get('units', []):
        if unit.get('source_id') != source_id:
            continue
        try:
            spans = _spans(unit, pages)
        except ValueError as exc:
            result['invalid_sections'][unit['unit_id']] = str(exc)
            continue
        if not spans and unit.get('kind') in TEXT_KINDS:
            result['unbound_sections'].append(unit['unit_id'])
        for s in spans:
            counts[s.page['page']].update(w['id'] for w in s.words)
    for n, (_, p) in sorted(pages.items()):
        hits = counts[n]
        if not p['words']:
            result['no_native_text_pages'].append(n)
        elif not hits:
            result['unmapped_pages'].append(n)
        elif len(hits) < len(p['words']):
            result['partial_pages'].append(n)
        if any(v > 1 for v in hits.values()):
            result['overlap_pages'].append(n)
    if details:
        wanted = set(pages_filter or (result['unmapped_pages'] + result['partial_pages']))
        if any(type(n) is not int or n not in pages for n in wanted):
            raise ElementError('INVALID_ARGUMENT', 'Filter --details by physical pages of the selected source.')
        if type(offset) is not int or offset < 0 or type(limit) is not int or limit <= 0:
            raise ElementError('INVALID_ARGUMENT', 'Use a nonnegative details offset and a positive limit.')
        total, runs = 0, {}
        for n in sorted(wanted):
            for run in _runs(pages[n][1], counts[n]):
                if offset <= total < offset+limit:
                    runs.setdefault(n, []).append(run)
                total += 1
        result.update(unmapped_runs=runs, total_unmapped_runs=total,
                      next_offset=offset+limit if offset+limit < total else None)
    return result
