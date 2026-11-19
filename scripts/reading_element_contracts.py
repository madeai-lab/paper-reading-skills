"""Standard-library validation of native PDF evidence; not proof of understanding."""
import hashlib
import json
import math
from pathlib import Path


def enabled(packet):
    try:
        revision = tuple(int(x) for x in packet.get('skill_revision', '0').split('.'))
    except (ValueError, AttributeError):
        revision = (0,)
    return 'content_acquisition' in packet or revision >= (2, 7)


def _load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def _sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _file(root, ref):
    if not isinstance(ref, str) or not ref:
        raise ValueError('Use a nonempty native artifact reference.')
    path = (root/ref).resolve()
    directory = (root/'source_elements').resolve()
    if not directory.is_relative_to(root) or not path.is_relative_to(directory) or not path.is_file():
        raise ValueError('Native element evidence must exist inside source_elements/.')
    return path


def _box(values):
    if (not isinstance(values, list) or len(values) != 4
            or any(type(x) not in {int, float} or not math.isfinite(x) for x in values)
            or values[0] > values[2] or values[1] > values[3]):
        raise ValueError('Invalid native element coordinates.')


def validated_pages(root, packet):
    """Return verified native page records keyed by manifest reference."""
    acquisition = packet.get('content_acquisition')
    if acquisition != {'method': 'PDFPLUMBER_NATIVE', 'manifest_ref': 'source_elements/manifest.json'}:
        raise ValueError('New runs require the canonical PDFPLUMBER_NATIVE manifest contract.')
    manifest = _load(_file(root, acquisition['manifest_ref']))
    if (manifest.get('schema_version') != 1 or manifest.get('ocr_used') is not False
            or manifest.get('parser', {}).get('name') != 'pdfplumber'
            or not manifest.get('parser', {}).get('version')):
        raise ValueError('Use a native-only, versioned pdfplumber manifest.')
    current = {s['source_id']: s for s in packet.get('sources', []) if s.get('access_state') == 'AVAILABLE'}
    sources = manifest.get('sources', [])
    if (not isinstance(sources, list) or len({s['source_id'] for s in sources}) != len(sources)
            or {s['source_id'] for s in sources} != set(current)):
        raise ValueError('Manifest must cover every current available source exactly once.')
    result = {}
    for source in sources:
        original = current[source['source_id']]
        path = root/original['local_path']
        if (source.get('sha256') != original.get('sha256') or source.get('local_path') != original['local_path']
                or not path.is_file() or _sha(path) != original.get('sha256')):
            raise ValueError('ELEMENT_SOURCE_CHANGED: regenerate in a fresh run for the actual source bytes.')
        rows = source.get('pages', [])
        count = source.get('page_count')
        if (type(count) is not int or count < 1 or not isinstance(rows, list) or len(rows) != count
                or sorted(row['page'] for row in rows) != list(range(1, count+1))
                or (original.get('page_count') is not None and original['page_count'] != count)):
            raise ValueError('Missing/duplicate source pages or page-count disagreement.')
        for row in rows:
            path = _file(root, row['ref'])
            if _sha(path) != row.get('sha256'):
                raise ValueError('Native page evidence changed: '+row['ref'])
            data = _load(path)
            if (data.get('source_id') != source['source_id'] or data.get('page') != row['page']
                    or data.get('ocr_used') is not False or not isinstance(data.get('text'), str)
                    or not isinstance(data.get('flags'), list)
                    or any(type(data.get(k)) not in {int, float} or data[k] <= 0 for k in ['width', 'height'])):
                raise ValueError('Native page identity, dimensions or text contract is invalid.')
            ids = [data.get('text_id')]
            for key in ['chars', 'words', 'tables', 'images', 'lines', 'rects', 'curves']:
                if not isinstance(data.get(key), list):
                    raise ValueError('Native page collection must be an array: '+key)
                for item in data[key]:
                    ids.append(item.get('id'))
                    _box(item.get('bbox'))
            if any(not isinstance(uid, str) or not uid for uid in ids) or len(set(ids)) != len(ids):
                raise ValueError('Native element IDs must be present and unique on their page.')
            if row['ref'] in result:
                raise ValueError('Sources must not alias the same page artifact.')
            result[row['ref']] = data
    return result


def element_errors(root, packet):
    if not enabled(packet):
        return []
    try:
        validated_pages(Path(root).resolve(), packet)
        return []
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        code = 'ELEMENT_SOURCE_CHANGED' if 'ELEMENT_SOURCE_CHANGED' in str(exc) else 'ELEMENTS_INVALID'
        return [{'code': code, 'item': 'content_acquisition', 'next_action': str(exc)}]


def _reading(root, packet, unit, pages):
    record = unit.get('content_reading', {})
    if (not isinstance(record, dict) or record.get('mode') not in {'NATIVE_ELEMENTS', 'VISUAL', 'MIXED'}
            or not isinstance(record.get('page_refs'), list) or not record['page_refs']
            or not isinstance(record.get('element_ids'), list) or not record['element_ids']
            or record.get('unresolved_conflicts')):
        raise ValueError('Record native-first page references, element IDs, actual reading mode and resolved conflicts.')
    locators = {x.get('physical_page') for x in unit.get('locators', [])}
    selected = []
    known = set()
    for ref in record['page_refs']:
        if ref not in pages:
            raise ValueError('Unit references an unknown native page.')
        page = pages[ref]
        if page['source_id'] != unit.get('source_id') or page['page'] not in locators:
            raise ValueError('Native evidence must match this unit source and physical-page locators.')
        selected.append(page)
        known.add(page['text_id'])
        for key in ['chars', 'words', 'tables', 'images', 'lines', 'rects', 'curves']:
            known.update(x['id'] for x in page[key])
    if any(not isinstance(uid, str) or uid not in known for uid in record['element_ids']):
        raise ValueError('Unit references an unknown native element ID.')
    refs = record.get('conflict_resolution_refs', [])
    if not isinstance(refs, list) or any(not isinstance(ref, str) or not (root/ref.split('#', 1)[0]).is_file() for ref in refs):
        raise ValueError('Conflict resolutions require existing local evidence.')
    if any(set(p['flags']) & {'GLYPH_MAPPING_CONFLICT', 'NO_NATIVE_TEXT'} for p in selected):
        visual = unit.get('visual_review', {})
        artifacts = visual.get('artifact_refs', [])
        if (not refs or record['mode'] == 'NATIVE_ELEMENTS' or visual.get('actually_viewed') is not True
                or not isinstance(artifacts, list) or not artifacts
                or any(not isinstance(ref, str) or not (root/ref.split('#', 1)[0]).is_file() for ref in artifacts)):
            raise ValueError('Unreadable native text/glyphs require actual pixel inspection and conflict-resolution evidence.')
    return record, selected


def native_unit_errors(root, packet):
    if not enabled(packet):
        return []
    root = Path(root).resolve()
    if element_errors(root, packet):
        return []
    pages = validated_pages(root, packet)
    errors = []
    for unit in packet.get('units', []):
        if unit.get('read_state') not in {'CHECKED', 'NON_INFORMATIVE'}:
            continue
        try:
            _reading(root, packet, unit, pages)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            errors.append({'code': 'UNIT_NATIVE_EVIDENCE_MISSING', 'item': unit.get('unit_id'), 'next_action': str(exc)})
    return errors


def native_table_ready(root, packet, unit):
    if not enabled(packet) or unit.get('kind') != 'TABLE':
        return False
    root = Path(root).resolve()
    try:
        pages = validated_pages(root, packet)
        record, selected = _reading(root, packet, unit, pages)
        if record['mode'] != 'NATIVE_ELEMENTS':
            return False
        if {page['page'] for page in selected} != {x.get('physical_page') for x in unit.get('locators', [])}:
            return False
        if any(not any(t['id'] in record['element_ids'] for t in page['tables']) for page in selected):
            return False
        tables = [t for page in selected for t in page['tables'] if t['id'] in record['element_ids']]
        if not tables or any(page['flags'] for page in selected):
            return False
        for table in tables:
            rows, cells = table.get('rows', []), table.get('cells', [])
            if (table.get('flags') or not rows or not cells or not all(isinstance(row, list) and row for row in rows)
                    or len({len(row) for row in rows}) != 1
                    or any(value is None or value == '' for row in rows for value in row)
                    or any(cell.get('bbox') is None for cell in cells)
                    or len(cells) != sum(len(row) for row in rows)
                    or {(c.get('row'), c.get('column')) for c in cells} !=
                       {(ri, ci) for ri, row in enumerate(rows) for ci in range(len(row))}):
                return False
            for page in selected:
                if table not in page['tables']:
                    continue
                a = table['bbox']
                for image in page['images']:
                    b = image['bbox']
                    if a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]:
                        return False
        return True
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def structured_review_errors(root, packet, review):
    if not enabled(packet):
        return []
    from reading_review_modes import review_plan
    root = Path(root).resolve()
    required = set(review_plan(packet)['required_unit_ids']) | set(review.get('checked_unit_ids', []))
    tables = {u['unit_id'] for u in packet.get('units', [])
              if u['unit_id'] in required and native_table_ready(root, packet, u)}
    if not tables:
        return []
    record = review.get('structured_inspection', {})
    refs = record.get('evidence_refs', []) if isinstance(record, dict) else []
    ids = record.get('unit_ids', []) if isinstance(record, dict) else []
    if (not isinstance(ids, list) or set(ids) != tables or len(ids) != len(tables)
            or not isinstance(refs, list) or not refs
            or any(not isinstance(ref, str) or not (root/ref.split('#', 1)[0]).is_file() for ref in refs)):
        return [{'code': 'REVIEW_NATIVE_INCOMPLETE', 'item': 'G3',
                 'next_action': 'Independently inspect every required native table and save reviewer-owned structured_inspection evidence.'}]
    return []
