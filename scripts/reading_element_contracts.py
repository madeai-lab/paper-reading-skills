"""Standard-library validation of native PDF evidence; not proof of understanding."""
import hashlib
import json
import math
from pathlib import Path
import re

from reading_data_sources import (DATA_KIND, DATA_UNIT_KINDS, ENCODINGS, TABULAR, check_record, check_registry,
                                  extensions_enabled, is_data_source, parse, resolve, sha256_file, summary)

CODES = {'ELEMENT_SOURCE_CHANGED', 'ELEMENTS_APPEND_REQUIRED', 'DATA_SOURCE_INVALID', 'DATA_SOURCE_UNSUPPORTED',
         'DATA_LIMIT', 'DATA_LOCATOR_INVALID', 'DATA_PARSE_CONFLICT'}


def error_code(exc, default='ELEMENTS_INVALID'):
    code = getattr(exc, 'code', None)
    if code:
        return code
    match = re.match(r'([A-Z_]+):', str(exc))
    return match[1] if match and match[1] in CODES else default


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


def _parser_ok(parser):
    return isinstance(parser, dict) and parser.get('name') == 'pdfplumber' and bool(parser.get('version'))


def _history(root, manifest):
    """Prove every append kept earlier manifest entries, and so their page files, unchanged."""
    history = manifest.get('history')
    if not isinstance(history, list) or not history:
        raise ValueError('Schema-2 manifests record their extraction history.')
    directory = root/'source_elements/history'
    if directory.exists():
        expected = {f'manifest-{i:04}.json' for i in range(1, len(history))}
        for snapshot in directory.glob('manifest-*.json'):
            if snapshot.name in expected:
                continue
            # A failed atomic swap can leave an exact copy of the still-current manifest.
            if (snapshot.name == f'manifest-{len(history):04}.json'
                    and _sha(snapshot) == _sha(root/'source_elements/manifest.json')):
                continue
            raise ValueError('Unexpected manifest history snapshot; do not truncate a committed chain.')
    seen_pdf, seen_data = [], []
    for i, row in enumerate(history):
        new_pdf = row.get('source_ids') if isinstance(row, dict) else None
        new_data = row.get('data_source_ids') if isinstance(row, dict) else None
        if (not isinstance(row, dict) or row.get('sequence') != i + 1
                or row.get('operation') != ('INITIAL' if i == 0 else 'APPEND')
                or not isinstance(new_pdf, list) or not isinstance(new_data, list) or not new_pdf + new_data
                or any(not isinstance(x, str) for x in new_pdf + new_data) or (i == 0 and not new_pdf)
                or not (_parser_ok(row.get('parser')) if new_pdf else row.get('parser') is None)):
            raise ValueError('Manifest history entries must be sequential INITIAL/APPEND steps with their own sources and parser.')
        if i == 0:
            if row.get('parser') != manifest['parser'] or row.get('previous_manifest_ref') is not None \
                    or row.get('previous_manifest_sha256') is not None:
                raise ValueError('The initial history entry must match the manifest parser and have no predecessor.')
        else:
            ref = f'source_elements/history/manifest-{i:04}.json'
            path = _file(root, row.get('previous_manifest_ref'))
            if row['previous_manifest_ref'] != ref or _sha(path) != row.get('previous_manifest_sha256'):
                raise ValueError('ELEMENTS_INVALID: preserved manifest history changed or is missing: ' + ref)
            old = _load(path)
            if (old.get('schema_version') != 2 or old.get('ocr_used') is not False
                    or old.get('parser') != manifest['parser'] or old.get('history') != history[:i]
                    or old.get('sources') != manifest['sources'][:len(seen_pdf)]
                    or old.get('data_sources') != manifest['data_sources'][:len(seen_data)]):
                raise ValueError('An append changed earlier manifest evidence; existing pages are never rewritten. Use a fresh run.')
        seen_pdf += new_pdf
        seen_data += new_data
    if (seen_pdf != [s['source_id'] for s in manifest['sources']]
            or seen_data != [s['source_id'] for s in manifest['data_sources']]):
        raise ValueError('Manifest history must account for every bound source in extraction order.')


def _data_entries(root, manifest, current):
    rows = manifest.get('data_sources')
    if (not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows)
            or len({r.get('source_id') for r in rows}) != len(rows)):
        raise ValueError('Schema-2 manifests list data_sources once each.')
    ids = {r['source_id'] for r in rows}
    if not ids <= set(current):
        raise ValueError('ELEMENT_SOURCE_CHANGED: a bound data source is no longer an available DATA_FILE; use a fresh run.')
    result = {}
    archive_hashes = {}
    declarations = None  # Only needed when applying a synced decoding correction.
    for row in rows:
        source = current[row['source_id']]
        container = (source.get('provenance') or {}).get('container')
        if (row.get('local_path') != source.get('local_path') or row.get('sha256') != source.get('sha256')
                or row.get('format') != source.get('format')
                or row.get('container') != container or row.get('supplement_of') != source.get('supplement_of')
                or row.get('origin') != source['provenance']['origin']
                or row.get('acquisition_ref') != source['provenance']['acquisition_ref']
                or row.get('acquisition_sha256') != sha256_file(root/source['provenance']['acquisition_ref'])):
            raise ValueError('ELEMENT_SOURCE_CHANGED: data source identity changed after binding: ' + row['source_id'])
        path = root/source['local_path']
        if sha256_file(path) != source['sha256']:
            raise ValueError('ELEMENT_SOURCE_CHANGED: data file bytes changed: ' + row['source_id'])
        if container:
            archive = root/container['local_path']
            if archive not in archive_hashes:
                archive_hashes[archive] = sha256_file(archive)
            if archive_hashes[archive] != container['sha256']:
                raise ValueError('ELEMENT_SOURCE_CHANGED: container archive changed: ' + row['source_id'])
        encoding = row['encoding']
        if encoding is not None and (encoding not in ENCODINGS or source['format'] == 'XLSX'):
            raise ValueError('Invalid originally bound encoding: ' + row['source_id'])
        original = summary(parse(path, row, row['sha256']))
        # Exact JSON types matter: True, 1 and 1.0 are equal in Python, not in a frozen record.
        if json.dumps(row.get('structure'), sort_keys=True) != json.dumps(original, sort_keys=True):
            raise ValueError('Recorded data structure differs from the bound bytes and encoding: ' + row['source_id'])
        entry = row
        if source.get('encoding') != encoding:
            if original.get('conflict') != 'TEXT_DECODING_CONFLICT' or not source.get('encoding'):
                raise ValueError('ELEMENT_SOURCE_CHANGED: only an original text decoding conflict permits '
                                 'an explicit encoding correction: ' + row['source_id'])
            if declarations is None:
                registry = root/'01_sources.json'
                declarations = _load(registry) if registry.is_file() else []
                check_registry(declarations)
            if source not in declarations:
                raise ValueError('ELEMENT_SOURCE_CHANGED: declare the correction in 01_sources.json and sync: ' + row['source_id'])
            effective = summary(parse(path, source, row['sha256']))
            if effective['parse_state'] != 'PARSED':
                raise ValueError('DATA_PARSE_CONFLICT: corrected encoding does not resolve ' + row['source_id']
                                 + ': ' + effective['conflict'])
            # Only the read interface uses this overlay. manifest and its history retain the original conflict.
            entry = dict(row, encoding=source['encoding'], structure=effective)
        result[row['source_id']] = (source, entry)
    return result


def validate_acquisition(root, packet, allow_pending=False):
    """Verify the frozen acquisition record and return pages, data bindings and unbound sources.

    allow_pending is used only by append extraction: newly registered AVAILABLE sources may
    still be unbound, but every bound source and page must remain exactly as recorded.
    """
    root = Path(root).resolve()
    acquisition = packet.get('content_acquisition')
    if acquisition != {'method': 'PDFPLUMBER_NATIVE', 'manifest_ref': 'source_elements/manifest.json'}:
        raise ValueError('New runs require the canonical PDFPLUMBER_NATIVE manifest contract.')
    extended = extensions_enabled(packet)
    if extended:
        check_registry(packet.get('sources', []))
    elif any(is_data_source(s) for s in packet.get('sources', [])):
        raise ValueError('DATA_SOURCE_UNSUPPORTED: data-file sources need a run initialized at 2.10 or later.')
    manifest = _load(_file(root, acquisition['manifest_ref']))
    if (manifest.get('schema_version') != (2 if extended else 1) or manifest.get('ocr_used') is not False
            or not _parser_ok(manifest.get('parser'))):
        raise ValueError('Use a native-only, versioned pdfplumber manifest' + (' (schema 2 for 2.10+ runs).' if extended else '.'))
    available = [s for s in packet.get('sources', []) if s.get('access_state') == 'AVAILABLE']
    current = {s['source_id']: s for s in available if not (extended and is_data_source(s))}
    data_current = {s['source_id']: s for s in available if extended and is_data_source(s)}
    for source in data_current.values():
        check_record(root, packet, source)
    sources = manifest.get('sources', [])
    bound = [s['source_id'] for s in sources] if isinstance(sources, list) else None
    if bound is None or len(set(bound)) != len(bound) or (not extended and set(bound) != set(current)):
        raise ValueError('Manifest must cover every current available source exactly once.')
    if not set(bound) <= set(current):
        raise ValueError('ELEMENT_SOURCE_CHANGED: a bound PDF source is no longer available or became a data file; use a fresh run.')
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
            page = _load(path)
            if (page.get('source_id') != source['source_id'] or page.get('page') != row['page']
                    or page.get('ocr_used') is not False or not isinstance(page.get('text'), str)
                    or not isinstance(page.get('flags'), list)
                    or any(type(page.get(k)) not in {int, float} or page[k] <= 0 for k in ['width', 'height'])):
                raise ValueError('Native page identity, dimensions or text contract is invalid.')
            ids = [page.get('text_id')]
            for key in ['chars', 'words', 'tables', 'images', 'lines', 'rects', 'curves']:
                if not isinstance(page.get(key), list):
                    raise ValueError('Native page collection must be an array: '+key)
                for item in page[key]:
                    ids.append(item.get('id'))
                    _box(item.get('bbox'))
            if any(not isinstance(uid, str) or not uid for uid in ids) or len(set(ids)) != len(ids):
                raise ValueError('Native element IDs must be present and unique on their page.')
            if row['ref'] in result:
                raise ValueError('Sources must not alias the same page artifact.')
            result[row['ref']] = page
    data = {}
    if extended:
        data = _data_entries(root, manifest, data_current)
        _history(root, manifest)
    pending_pdf = [s for s in available if s['source_id'] in current and s['source_id'] not in bound]
    pending_data = [s for s in available if s['source_id'] in data_current and s['source_id'] not in data]
    if (pending_pdf or pending_data) and not allow_pending:
        raise ValueError('ELEMENTS_APPEND_REQUIRED: newly available sources are not yet bound ('
                         + ', '.join(s['source_id'] for s in pending_pdf + pending_data)
                         + '). Run extract-elements --append; existing evidence stays unchanged.')
    return {'manifest': manifest, 'pages': result, 'data': data,
            'pending_pdf': pending_pdf, 'pending_data': pending_data}


def validated_pages(root, packet):
    """Verify the whole acquisition, including any container bindings, before exposing a page."""
    return validate_acquisition(root, packet)['pages']


def checked_acquisition(root, packet):
    """Share one read-only validation (including failure) within a check; never cache it across checks."""
    errors = []
    if enabled(packet):
        try:
            return validate_acquisition(root, packet)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            errors.append({'code': error_code(exc), 'item': 'content_acquisition', 'next_action': str(exc)})
    return {'pages': {}, 'data': {}, 'errors': errors}


def element_errors(root, packet, acquisition=None):
    if acquisition is None:
        acquisition = checked_acquisition(root, packet)
    return acquisition.get('errors', [])


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


def _data_reading(root, unit, data):
    """Validate locator evidence; return whether it represents actual table cells without missing graphics."""
    source, entry = data[unit['source_id']]
    if unit.get('kind') not in DATA_UNIT_KINDS:
        raise ValueError('Data-file sources hold TABLE, SECTION, APPENDIX or BIBLIOGRAPHY units; register image or PDF '
                         'material as its own source instead of describing pixels from a data file.')
    record = unit.get('content_reading', {})
    if (not isinstance(record, dict) or record.get('mode') != DATA_KIND or record.get('unresolved_conflicts')
            or record.get('page_refs') or record.get('element_ids')):
        raise ValueError('Record content_reading.mode=DATA_FILE with resolved conflicts; pages and native element IDs do not apply.')
    refs = record.get('conflict_resolution_refs', [])
    if not isinstance(refs, list) or any(not isinstance(ref, str) or not (root/ref.split('#', 1)[0]).is_file() for ref in refs):
        raise ValueError('Conflict resolutions require existing local evidence.')
    locators = unit.get('locators')
    if not isinstance(locators, list) or not locators:
        raise ValueError('Data units need file + sheet/row/field, JSON-pointer or line locators.')
    doc = parse(root/source['local_path'], source, entry['sha256'])
    has_cells = False
    for locator in locators:
        selected = resolve(doc, locator)
        if selected.get('flags') and not refs:
            raise ValueError('Inspect flagged structure or cached values and link a resolution note: ' + ', '.join(selected['flags']))
        if doc['format'] in TABULAR and not has_cells:
            has_cells = any(value is not None and str(value).strip()
                            for row in selected['rows'] if row['row'] != selected['header_row']
                            for value in row['values'])
    # Notes can explain cached numeric values/headers, but cannot supply omitted graphics.
    return has_cells and 'EMBEDDED_GRAPHICS_NOT_REPRESENTED' not in doc.get('flags', [])


def native_unit_errors(root, packet, acquisition=None):
    if not enabled(packet):
        return []
    root = Path(root).resolve()
    if acquisition is None:
        acquisition = checked_acquisition(root, packet)
    if acquisition.get('errors'):
        return []  # element_errors reports the acquisition failure itself.
    errors = []
    for unit in packet.get('units', []):
        if unit.get('read_state') not in {'CHECKED', 'NON_INFORMATIVE'}:
            continue
        on_data = unit.get('source_id') in acquisition['data']
        try:
            if on_data:
                cells = _data_reading(root, unit, acquisition['data'])
                visual = unit.get('visual_review', {})
                if (unit.get('kind') == 'TABLE' and not cells
                        and (visual.get('actually_viewed') is not True or not has_rendered_artifact(root, visual.get('artifact_refs')))):
                    raise ValueError('Link the inspected rendering; a data locator or resolution note is not pixels.')
            else:
                _reading(root, packet, unit, acquisition['pages'])
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            errors.append({'code': 'UNIT_DATA_EVIDENCE_MISSING' if on_data else 'UNIT_NATIVE_EVIDENCE_MISSING',
                           'item': unit.get('unit_id'), 'next_action': str(exc)})
    return errors


def has_rendered_artifact(root, refs):
    """A non-cell DATA_FILE visual needs an actual local image/PDF, not just a text note."""
    if not isinstance(refs, list):
        return False
    for ref in refs:
        if not isinstance(ref, str):
            continue
        path = (root/ref.split('#', 1)[0]).resolve()
        if (path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.gif', '.tif', '.tiff', '.webp', '.pdf'}
                or not path.is_relative_to(root) or not path.is_file()):
            continue
        try:
            with path.open('rb') as stream:
                prefix = stream.read(12)
        except OSError:
            continue
        if (prefix.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff', b'GIF87a', b'GIF89a', b'%PDF-',
                               b'II\x2a\x00', b'MM\x00\x2a')) or (prefix[:4], prefix[8:]) == (b'RIFF', b'WEBP')):
            return True
    return False


def data_table_ready(root, packet, unit, acquisition=None):
    """Only located tabular data values can stand in for pixels, not a resolved scalar or header."""
    if not enabled(packet) or not extensions_enabled(packet) or unit.get('kind') != 'TABLE':
        return False
    if acquisition is None:
        acquisition = checked_acquisition(root, packet)
    try:
        return _data_reading(Path(root).resolve(), unit, acquisition['data'])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def structured_ready(root, packet, unit, acquisition=None):
    """Non-pixel structured evidence that may replace viewing: complete native PDF or data-file tables."""
    if not enabled(packet) or unit.get('kind') != 'TABLE':
        return False
    if acquisition is None:
        acquisition = checked_acquisition(root, packet)
    if unit.get('source_id') in acquisition['data']:
        return data_table_ready(root, packet, unit, acquisition)
    return native_table_ready(root, packet, unit, acquisition)


def native_table_ready(root, packet, unit, acquisition=None):
    if not enabled(packet) or unit.get('kind') != 'TABLE':
        return False
    root = Path(root).resolve()
    if acquisition is None:
        acquisition = checked_acquisition(root, packet)
    try:
        record, selected = _reading(root, packet, unit, acquisition['pages'])
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


def structured_review_errors(root, packet, review, acquisition=None):
    if not enabled(packet):
        return []
    from reading_review_modes import review_plan
    root = Path(root).resolve()
    required = set(review_plan(packet)['required_unit_ids']) | set(review.get('checked_unit_ids', []))
    candidates = [u for u in packet.get('units', []) if u.get('kind') == 'TABLE' and u['unit_id'] in required]
    if not candidates:
        return []
    if acquisition is None:
        acquisition = checked_acquisition(root, packet)
    tables = {u['unit_id'] for u in candidates if structured_ready(root, packet, u, acquisition)}
    if not tables:
        return []
    record = review.get('structured_inspection', {})
    refs = record.get('evidence_refs', []) if isinstance(record, dict) else []
    ids = record.get('unit_ids', []) if isinstance(record, dict) else []
    if (not isinstance(ids, list) or set(ids) != tables or len(ids) != len(tables)
            or not isinstance(refs, list) or not refs
            or any(not isinstance(ref, str) or not (root/ref.split('#', 1)[0]).is_file() for ref in refs)):
        return [{'code': 'REVIEW_NATIVE_INCOMPLETE', 'item': 'G3',
                 'next_action': 'Independently inspect every required native or data-file table and save reviewer-owned structured_inspection evidence.'}]
    return []
