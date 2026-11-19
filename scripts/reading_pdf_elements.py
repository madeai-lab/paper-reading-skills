"""Local native PDF extraction. pdfplumber is optional; no OCR or model fallback."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

MAX_PAGES = 500
MAX_SOURCE_BYTES = 100 * 1024 * 1024
MAX_CHARACTERS = 10_000_000
MAX_READ_CHARS = 18_000


class ElementError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8')


def box(value):
    values = [float(x) for x in value]
    if len(values) != 4 or not all(math.isfinite(x) for x in values) or values[0] > values[2] or values[1] > values[3]:
        raise ElementError('ELEMENTS_INVALID', 'Invalid native object bounding box.')
    return values


def object_box(row):
    return box([row['x0'], row['top'], row['x1'], row['bottom']])


def compact_geometry(rows, prefix):
    result = []
    for n, row in enumerate(rows, 1):
        item = {'id': prefix+f'{n:04}', 'bbox': object_box(row)}
        for key in ['linewidth', 'stroke', 'fill', 'stroking_color', 'non_stroking_color', 'pts', 'path']:
            if key in row:
                item[key] = row[key]
        result.append(item)
    return result


def page_elements(page, number, source_id):
    prefix = f'p{number:04}'
    chars = [{'id': prefix+f'-g{n:05}', 'text': char['text'], 'bbox': object_box(char),
              'fontname': char.get('fontname'), 'size': char.get('size')}
             for n, char in enumerate(page.chars, 1)]
    words = []
    for n, word in enumerate(page.extract_words(x_tolerance=.5, y_tolerance=3), 1):
        words.append({'id': prefix+f'-w{n:05}', 'text': word['text'], 'bbox': object_box(word)})
    text = page.extract_text(x_tolerance=.5, y_tolerance=3) or ''
    flags = []
    if not text.strip():
        flags.append('NO_NATIVE_TEXT')
    if '\ufffd' in text or '(cid:' in text or '\x00' in text:
        flags.append('GLYPH_MAPPING_CONFLICT')
    if any(len(word['text']) > 45 for word in words):
        flags.append('CHECK_WORD_JOINING')
    tables = []
    for n, table in enumerate(sorted(page.find_tables(), key=lambda t: (t.bbox[1], t.bbox[0])), 1):
        rows = table.extract()
        cells = []
        table_rows = getattr(table, 'rows', [])
        if table_rows:
            for ri, row in enumerate(table_rows):
                for ci, cell in enumerate(row.cells):
                    cells.append({'row': ri, 'column': ci, 'bbox': box(cell) if cell else None})
        else:
            cells = [{'bbox': box(cell) if cell else None} for cell in getattr(table, 'cells', [])]
        table_flags = []
        if not rows or any(not isinstance(row, list) for row in rows):
            table_flags.append('TABLE_STRUCTURE_CONFLICT')
        elif len({len(row) for row in rows}) != 1 or any(value is None or value == '' for row in rows for value in row):
            table_flags.append('TABLE_EMPTY_OR_MERGED_CELLS')
        if not cells or any(cell['bbox'] is None for cell in cells):
            table_flags.append('TABLE_GEOMETRY_CONFLICT')
        tables.append({'id': prefix+f'-t{n:03}', 'bbox': box(table.bbox),
                       'rows': rows, 'cells': cells, 'flags': table_flags})
    images = [{'id': prefix+f'-i{n:03}', 'bbox': object_box(image),
               'srcsize': list(image.get('srcsize', [])), 'bits': image.get('bits')}
              for n, image in enumerate(sorted(page.images, key=lambda x: (x['top'], x['x0'])), 1)]
    return {'source_id': source_id, 'page': number, 'width': float(page.width), 'height': float(page.height),
            'text_id': prefix+'-text', 'text': text, 'chars': chars, 'words': words, 'tables': tables, 'images': images,
            'lines': compact_geometry(page.lines, prefix+'-l'),
            'rects': compact_geometry(page.rects, prefix+'-r'),
            'curves': compact_geometry(page.curves, prefix+'-c'), 'flags': flags,
            'ocr_used': False}


def _import_parser(parser):
    if parser is not None:
        return parser
    try:
        import pdfplumber
    except ImportError as exc:
        raise ElementError('PDFPLUMBER_UNAVAILABLE', 'Use an explicitly provisioned extraction Python with pdfplumber; no automatic install or fallback.') from exc
    return pdfplumber


def _parser_record(parser):
    return {'name': 'pdfplumber', 'version': str(getattr(parser, '__version__', 'UNKNOWN'))}


def _extract_pdf(root, parser, source, staging, name_prefix, ref_prefix, total_chars):
    """Write one source's page records into staging; return its manifest entry and running character total."""
    sid = source.get('source_id', '')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', sid):
        raise ElementError('ELEMENTS_INVALID', 'Use a safe source ID.')
    path = root/source.get('local_path', '')
    if not path.is_file() or sha(path) != source.get('sha256'):
        raise ElementError('ELEMENT_SOURCE_CHANGED', 'Source bytes do not match the frozen identity: '+sid)
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise ElementError('PDF_ELEMENTS_LIMIT', 'Source exceeds the native extraction byte limit.')
    entry = {'source_id': sid, 'local_path': source['local_path'], 'sha256': source['sha256'], 'pages': []}
    try:
        opened = parser.open(path)
    except Exception as exc:
        code = 'PDF_ELEMENTS_ENCRYPTED' if any(s in type(exc).__name__.lower() for s in ['password', 'encrypt']) else 'ELEMENTS_INVALID'
        raise ElementError(code, 'Native PDF parser could not open this source: '+type(exc).__name__) from exc
    with opened as document:
        underlying = getattr(document, 'doc', None)
        if (getattr(document, 'is_encrypted', False) or getattr(underlying, 'encryption', None)
                or getattr(underlying, 'is_extractable', True) is False):
            raise ElementError('PDF_ELEMENTS_ENCRYPTED', 'Encrypted/restricted PDFs are not extracted.')
        entry['page_count'] = len(document.pages)
        if not 0 < entry['page_count'] <= MAX_PAGES:
            raise ElementError('PDF_ELEMENTS_LIMIT', 'Source exceeds page limits or has no pages.')
        if source.get('page_count') is not None and source['page_count'] != entry['page_count']:
            raise ElementError('ELEMENTS_INVALID', 'Registered PDF page count does not match source: ' + sid)
        for number, page in enumerate(document.pages, 1):
            data = page_elements(page, number, sid)
            total_chars += max(len(data['text']), len(data['chars']))
            if total_chars > MAX_CHARACTERS:
                raise ElementError('PDF_ELEMENTS_LIMIT', 'Native text exceeds the extraction character limit.')
            name = name_prefix + f'page-{number:04}.json'
            save(staging/name, data)
            entry['pages'].append({'page': number, 'ref': ref_prefix+name, 'sha256': sha(staging/name)})
    return entry, total_chars


def _data_entry(root, packet, source):
    from reading_data_sources import DataError, manifest_entry
    try:
        return manifest_entry(root, packet, source)
    except DataError as exc:
        raise ElementError(exc.code, str(exc)) from exc


def extract_elements(root, parser=None, append=False, packet=None):
    """Extract native elements for a run, or for a screening workspace that supplies its own source record.

    A supplied packet is a read-only acquisition descriptor (sources and contract); no run record is created
    from it, and appends stay exclusive to real runs.
    """
    root = Path(root).resolve()
    if packet is None:
        packet = load(root/'paper_packet.json')
    elif append:
        raise ElementError('ELEMENTS_APPEND_UNSUPPORTED', 'Append binds sources of an initialized run only.')
    acquisition = packet.get('content_acquisition', {})
    if acquisition != {'method': 'PDFPLUMBER_NATIVE', 'manifest_ref': 'source_elements/manifest.json'}:
        raise ElementError('ELEMENTS_INVALID', 'Initialize a new native-elements run; existing runs are not migrated.')
    from reading_data_sources import check_registry, extensions_enabled, is_data_source
    extended = extensions_enabled(packet)
    if append:
        if not extended:
            raise ElementError('ELEMENTS_APPEND_UNSUPPORTED', 'Runs before 2.10 are not migrated; use a continuation run.')
        # Serialise publishers. A crash leaves a visible lock, never permission to replace evidence.
        lock = root/'.source-append.lock'
        try:
            lock.mkdir()
        except FileExistsError as exc:
            raise ElementError('ELEMENTS_APPEND_BUSY', 'Another append is running or was interrupted. Confirm the writer stopped before removing the empty lock.') from exc
        try:
            return _append(root, packet, parser)
        finally:
            lock.rmdir()
    destination = root/'source_elements'
    if destination.exists():
        raise ElementError('ELEMENTS_EXIST', 'Never overwrite extraction evidence. ' + (
            'Register and sync newly available sources, then use extract-elements --append.' if extended
            else 'Runs before 2.10 are not migrated; use a fresh run.'))
    sources = packet.get('sources', [])
    if extended:
        check_registry(sources)
    parser = _import_parser(parser)
    if not sources:
        raise ElementError('ELEMENTS_INVALID', 'Register source PDFs before extraction.')
    manifest = {'schema_version': 2 if extended else 1, 'parser': _parser_record(parser),
                'ocr_used': False, 'sources': []}
    data_sources = []
    total_chars = 0
    # A same-filesystem temporary directory becomes visible only after all sources succeed.
    with tempfile.TemporaryDirectory(prefix='.native-elements-', dir=root) as temporary:
        staging = Path(temporary).resolve()
        if not staging.is_relative_to(root):
            raise ElementError('ELEMENTS_INVALID', 'Extraction staging must remain inside this run.')
        for si, source in enumerate(sources):
            if source.get('access_state') != 'AVAILABLE':
                if not extended and source.get('required_for_scope'):
                    raise ElementError('ELEMENT_SOURCE_UNAVAILABLE', 'A required source is unavailable.')
                continue
            if is_data_source(source):
                if not extended:
                    raise ElementError('ELEMENTS_INVALID', 'Data-file sources need a run initialized at 2.10 or later; existing runs are not migrated.')
                data_sources.append(_data_entry(root, packet, source))
                continue
            prefix = '' if si == 0 else source.get('source_id', '')+'-'
            entry, total_chars = _extract_pdf(root, parser, source, staging, prefix, 'source_elements/', total_chars)
            manifest['sources'].append(entry)
        if not manifest['sources']:
            raise ElementError('ELEMENTS_INVALID', 'No readable source PDF was registered.')
        if extended:
            manifest['data_sources'] = data_sources
            manifest['history'] = [{'sequence': 1, 'operation': 'INITIAL', 'parser': manifest['parser'],
                                    'source_ids': [s['source_id'] for s in manifest['sources']],
                                    'data_source_ids': [d['source_id'] for d in data_sources],
                                    'previous_manifest_ref': None, 'previous_manifest_sha256': None}]
        save(staging/'manifest.json', manifest)
        staging.rename(destination)
    result = {'manifest_ref': acquisition['manifest_ref'], 'source_count': len(manifest['sources']),
              'page_count': sum(s['page_count'] for s in manifest['sources']), 'ocr_used': False,
              'reading_state_changed': False, 'notice': 'Extraction records PDF elements, not understanding or acceptance.'}
    if extended:
        result.update(data_source_count=len(data_sources), code_executed=False)
    return result


def _verify_existing_snapshot(snapshot, previous_bytes):
    if snapshot.resolve() != snapshot or snapshot.read_bytes() != previous_bytes:
        raise ElementError('ELEMENTS_INVALID', f'Conflicting history snapshot at {snapshot}; it was not overwritten. '
                           'Back up the run and verify its committed history. Manually quarantine the file outside '
                           'history only if confirmed to be an unreferenced remnant of an interrupted append.')


def _publish_snapshot(snapshot, previous_bytes):
    snapshot.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.snapshot-', dir=snapshot.parent) as temporary:
        staged = Path(temporary)/snapshot.name
        with staged.open('xb') as stream:
            stream.write(previous_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        if staged.read_bytes() != previous_bytes:
            raise ElementError('ELEMENTS_INVALID', 'Staged history snapshot differs from the current manifest; retry append.')
        try:
            # Windows rename refuses an existing destination; POSIX rename would replace it.
            if os.name == 'nt':
                os.rename(staged, snapshot)
            else:
                os.link(staged, snapshot)
        except FileExistsError:
            # A previous attempt may have published this snapshot but not swapped the manifest.
            _verify_existing_snapshot(snapshot, previous_bytes)


def _append(root, packet, parser):
    """Bind newly registered sources into an existing 2.10+ extraction without touching earlier evidence."""
    from reading_element_contracts import error_code, validate_acquisition
    destination = root/'source_elements'
    manifest_path = destination/'manifest.json'
    if not manifest_path.is_file():
        raise ElementError('ELEMENTS_INVALID', 'No extraction exists yet; run extract-elements without --append first.')
    if manifest_path.resolve() != manifest_path:
        raise ElementError('ELEMENTS_INVALID', 'Do not follow redirected manifest paths when appending.')
    try:
        previous_bytes = manifest_path.read_bytes()
        manifest = json.loads(previous_bytes.decode('utf-8-sig'))
        sequence = len(manifest['history']) + 1
        snapshot_ref = f'source_elements/history/manifest-{sequence-1:04}.json'
        snapshot = root/snapshot_ref
        if snapshot.resolve() != snapshot:
            raise ElementError('ELEMENTS_INVALID', 'Do not follow redirected history paths when appending.')
        # Diagnose legacy partial snapshots before the general history validator rejects the extra file.
        if snapshot.exists():
            _verify_existing_snapshot(snapshot, previous_bytes)
        state = validate_acquisition(root, packet, allow_pending=True)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ElementError(error_code(exc), str(exc)) from exc
    new_pdf, new_data = state['pending_pdf'], state['pending_data']
    if not new_pdf and not new_data:
        raise ElementError('ELEMENTS_NOTHING_TO_APPEND', 'Every AVAILABLE source is already bound. Register lawfully acquired sources in 01_sources.json and sync first.')
    name = f'append-{sequence:04}'
    suffix = 1
    while (destination/name).exists():
        # An unreferenced directory from an interrupted attempt is never reused or removed.
        suffix += 1
        name = f'append-{sequence:04}-{suffix}'
    ref_prefix = f'source_elements/{name}/'
    total_chars = sum(max(len(page['text']), len(page['chars'])) for page in state['pages'].values())
    entries = []
    history = {'sequence': sequence, 'operation': 'APPEND', 'parser': None,
               'source_ids': [s['source_id'] for s in new_pdf], 'data_source_ids': [s['source_id'] for s in new_data],
               'previous_manifest_ref': snapshot_ref, 'previous_manifest_sha256': hashlib.sha256(previous_bytes).hexdigest()}
    if new_pdf:
        parser = _import_parser(parser)
        history['parser'] = _parser_record(parser)
    with tempfile.TemporaryDirectory(prefix='.native-elements-', dir=root) as temporary:
        staging = Path(temporary).resolve()/'pages'
        staging.mkdir()
        if not staging.is_relative_to(root):
            raise ElementError('ELEMENTS_INVALID', 'Extraction staging must remain inside this run.')
        for source in new_pdf:
            entry, total_chars = _extract_pdf(root, parser, source, staging, source['source_id']+'-', ref_prefix, total_chars)
            entries.append(entry)
        data_entries = [_data_entry(root, packet, source) for source in new_data]
        manifest['sources'] += entries
        manifest['data_sources'] += data_entries
        manifest['history'].append(history)
        pending = Path(temporary)/'manifest.json'
        save(pending, manifest)
        if manifest_path.read_bytes() != previous_bytes or load(root/'paper_packet.json')['sources'] != packet['sources']:
            raise ElementError('ELEMENT_SOURCE_CHANGED', 'Sources or manifest changed during append; retry on a stable inventory.')
        # Until the final swap readers still see the old manifest and, at most, its exact snapshot.
        _publish_snapshot(snapshot, previous_bytes)
        if entries:
            staging.rename(destination/name)
        os.replace(pending, manifest_path)
    return {'manifest_ref': 'source_elements/manifest.json', 'operation': 'APPEND', 'sequence': sequence,
            'appended_source_ids': history['source_ids'], 'appended_data_source_ids': history['data_source_ids'],
            'page_count': sum(e['page_count'] for e in entries), 'previous_manifest_ref': snapshot_ref,
            'ocr_used': False, 'code_executed': False, 'reading_state_changed': False,
            'notice': 'Appended evidence binds new sources only; earlier pages are unchanged. Prior review snapshots are stale.'}


def word_text(words):
    if not words:
        return ''
    parts = [words[0]['text']]
    for prev, word in zip(words, words[1:]):
        top = word['bbox'][1]; old = prev['bbox']
        gap = top - old[3]
        sep = '\n\n' if gap > max(3, (old[3]-old[1])*.6) else ('\n' if top-old[1] > 3 else ' ')
        parts.extend((sep, word['text']))
    return ''.join(parts)


def read_elements(root, pages, bbox=None, max_chars=MAX_READ_CHARS, source_id=None, *, view='detail', packet=None, contained_words=False):
    from reading_element_contracts import element_errors
    if view not in ('detail', 'locator', 'text'):
        raise ElementError('INVALID_ARGUMENT', 'Use detail, locator or text for the native read view.')
    root = Path(root).resolve()
    if packet is None:
        packet = load(root/'paper_packet.json')
    errors = element_errors(root, packet)
    if errors:
        raise ElementError(errors[0]['code'], errors[0]['next_action'])
    if not packet.get('content_acquisition'):
        raise ElementError('ELEMENTS_INVALID', 'This legacy run has no native extraction contract.')
    manifest = load(root/packet['content_acquisition']['manifest_ref'])
    sources = manifest['sources']
    if source_id in {d['source_id'] for d in manifest.get('data_sources', [])}:
        raise ElementError('INVALID_ARGUMENT', 'This is a DATA_FILE source; read it with read-data, not PDF pages.')
    source = next((s for s in sources if s['source_id'] == (source_id or sources[0]['source_id'])), None)
    if source is None:
        raise ElementError('INVALID_ARGUMENT', 'Unknown source_id; select a source in the frozen manifest.')
    if (not isinstance(pages, list) or not pages or len(pages) > 4
            or any(type(p) is not int or not 1 <= p <= source['page_count'] for p in pages)
            or len(set(pages)) != len(pages)):
        raise ElementError('ELEMENT_READ_LIMIT', f"Choose 1–4 distinct physical pages from 1 to {source['page_count']}; for prose use read-section --id ID --format text.")
    if type(max_chars) is not int or not 1 <= max_chars <= MAX_READ_CHARS:
        raise ElementError('ELEMENT_READ_LIMIT', 'Omit --max-chars (default 18000) or use 1–18000. For prose use read-section and its continuation cursor.')
    selected_box = box(bbox) if bbox is not None else None
    result = {'source_id': source['source_id'], 'pages': [], 'ocr_used': False, 'truncated': False}
    if view == 'locator':
        result.update(view='locator', purpose='NAVIGATION_ONLY', source_ref=source['local_path'],
                      reading_state_changed=False)
    text_pages = []
    for number in pages:
        row = next(p for p in source['pages'] if p['page'] == number)
        page = load(root/row['ref'])
        if selected_box and not (0 <= selected_box[0] < selected_box[2] <= page['width'] and 0 <= selected_box[1] < selected_box[3] <= page['height']):
            raise ElementError('ELEMENT_READ_LIMIT', 'The bounding box must stay inside the page.')
        if view == 'text':
            if selected_box is None:
                text = page['text']
            else:
                x0, top, x1, bottom = selected_box
                if contained_words:
                    text = word_text([w for w in page['words'] if x0 <= w['bbox'][0] and w['bbox'][2] <= x1
                                      and top <= w['bbox'][1] and w['bbox'][3] <= bottom])
                else:
                    text = word_text([w for w in page['words'] if x0 <= (w['bbox'][0]+w['bbox'][2])/2 < x1
                                      and top <= (w['bbox'][1]+w['bbox'][3])/2 < bottom])
            flags = ', '.join(page['flags']) or 'none'
            region = f' bbox={selected_box}' if selected_box else ''
            text_pages.append(f"[{source['source_id']} p{number} {row['ref']} {page['text_id']}{region} flags={flags}]\n{text}")
            continue
        if view == 'locator':
            from reading_element_locators import locator_page
            result['pages'].append(locator_page(page, row['ref'], selected_box))
            continue
        def within(item):
            if selected_box is None:
                return True
            b = item['bbox']
            return b[0] < selected_box[2] and b[2] > selected_box[0] and b[1] < selected_box[3] and b[3] > selected_box[1]
        data = {'page': number, 'page_ref': row['ref'], 'text_id': page['text_id'],
                'text': page['text'] if selected_box is None else None,
                'tables': [{k: t[k] for k in ['id', 'bbox', 'rows', 'flags']}
                           for t in page['tables'] if within(t)],
                'images': [i for i in page['images'] if within(i)],
                'graphics_counts': {k: len(page[k]) for k in ['lines', 'rects', 'curves']},
                'flags': page['flags']}
        if selected_box:
            data['words'] = [w for w in page['words'] if within(w)]
            data['chars'] = [c for c in page['chars'] if within(c)]
        result['pages'].append(data)
    if view == 'text':
        output = '\n\n'.join(text_pages)
        if len(output) + 1 > max_chars:
            raise ElementError('ELEMENT_READ_LIMIT', 'Select a smaller --bbox or fewer pages. For continuous prose use read-section --format text and its cursor.')
        return output
    if len(json.dumps(result, ensure_ascii=True, separators=(',', ':'))) + 1 > max_chars:
        raise ElementError('ELEMENT_READ_LIMIT', 'Slice by page/region or read specific saved records; no content was silently truncated.')
    return result
