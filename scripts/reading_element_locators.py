"""Read-only navigation hints from a frozen native page; no PDF backend required."""
import re


_CAPTION = re.compile(r'^(?:fig(?:ure)?\.?|table|图|表)\s*(?:S?\d+[a-z]?|[IVXLCDM]+)(?=$|[\s.:：、)）-])', re.I)
_DRAWINGS = ('lines', 'rects', 'curves')


def _overlaps(a, b):
    # A horizontal/vertical path can have zero height/width.
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


def _extent(items):
    boxes = [item['bbox'] for item in items]
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def _bands(items, axis, gap):
    group = []
    end = float('-inf')
    for item in sorted(items, key=lambda e: e['bbox'][axis]):
        b = item['bbox']
        if group and b[axis] > end + gap:
            yield group
            group = []
            end = float('-inf')
        end = max(end, b[axis + 2])
        group.append(item)
    if group:
        yield group


def _drawing_regions(primitives, area):
    for band in _bands(primitives, 1, 6):
        for group in _bands(band, 0, 6):
            x0, y0, x1, y1 = _extent(group)
            bounds = [max(area[0], x0), max(area[1], y0), min(area[2], x1), min(area[3], y1)]
            if bounds[0] < bounds[2] and bounds[1] < bounds[3]:
                yield {'kind': 'drawing_region', 'bbox': bounds, 'primitive_count': len(group),
                       'anchor_element_id': group[0]['id']}


def _ruled_regions(lines, captions):
    # Parallel borders and a nearby table caption can survive a failed grid extraction.
    groups = {}
    for line in lines:
        x0, y0, x1, y1 = line['bbox']
        if y1 - y0 <= 1 and x1 - x0 >= 36:
            groups.setdefault((round(x0 / 2), round(x1 / 2)), []).append(line)
    for borders in groups.values():
        x0, _, x1, _ = _extent(borders)
        labels = [c for c in captions if c['text'].lower().startswith(('table', '表'))
                  and c['bbox'][0] < x1 and x0 < c['bbox'][2]]
        if not labels:
            continue
        # A caption between two borders separates tables with identical margins.
        for band in _bands(borders, 1, 144):
            partitions = {}
            for border in band:
                slot = sum(c['bbox'][3] < border['bbox'][1] for c in labels)
                partitions.setdefault(slot, []).append(border)
            for group in partitions.values():
                if len({round(b['bbox'][1]) for b in group}) < 3:
                    continue
                bounds = _extent(group)
                if any(0 <= max(bounds[1] - c['bbox'][3], c['bbox'][1] - bounds[3]) <= 48 for c in labels):
                    yield {'kind': 'drawing_region', 'basis': 'parallel_rules', 'bbox': bounds,
                           'primitive_count': len(group), 'anchor_element_id': group[0]['id']}


def _preview(words, limit):
    text = ' '.join(w['text'] for w in words)
    return text[:limit], len(text) > limit


def _caption_hints(words, area):
    # Numbered starts only. A nearby body reference can still look like a caption.
    local = [w for w in words if w['bbox'][1] <= area[3] + 48 and w['bbox'][3] >= area[1] - 48]
    line = []
    for w in sorted(local, key=lambda w: (w['bbox'][1], w['bbox'][0])):
        if line and w['bbox'][1] - line[0]['bbox'][1] > 2.5:
            yield from _caption_line(line, area)
            line = []
        line.append(w)
    if line:
        yield from _caption_line(line, area)


def _caption_line(line, area):
    for segment in _bands(line, 0, 16):
        if not _CAPTION.match(' '.join(w['text'] for w in segment[:3])):
            continue
        bounds = _extent(segment)
        if bounds[0] <= area[2] and area[0] <= bounds[2]:
            text, shortened = _preview(segment, 160)
            yield {'word_id': segment[0]['id'], 'bbox': bounds,
                   'text': text, 'preview_shortened': shortened}


def locator_page(page, page_ref, bbox=None):
    full = [0, 0, page['width'], page['height']]
    area = bbox if bbox is not None else full

    def selected(key):
        return [item for item in page[key] if _overlaps(item['bbox'], area)]

    graphics = {k: selected(k) for k in _DRAWINGS}
    objects = [{'kind': 'bitmap', 'element_id': i['id'], 'bbox': i['bbox'], 'srcsize': i['srcsize']}
               for i in selected('images')]
    for t in selected('tables'):
        objects.append({'kind': 'table', 'element_id': t['id'], 'bbox': t['bbox'],
                        'row_count': len(t['rows']), 'flags': t['flags']})
    captions = list(_caption_hints(page['words'], area))
    drawings = list(_drawing_regions([item for group in graphics.values() for item in group], area))
    objects.extend(drawings or _ruled_regions(graphics['lines'], captions))
    result = {'page': page['page'], 'page_ref': page_ref, 'bbox': area,
              'page_size': [page['width'], page['height']], 'flags': page['flags'],
              'objects': sorted(objects, key=lambda o: (o['bbox'][1], o['bbox'][0], o['kind'])),
              'graphics_counts': {k: len(v) for k, v in graphics.items()},
              'caption_hints': captions}
    if bbox is not None:
        text, shortened = _preview(selected('words'), 240)
        result.update(native_text_preview=text, preview_shortened=shortened)
    return result
