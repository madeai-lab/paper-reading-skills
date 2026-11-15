"""Local native PDF extraction. pdfplumber is optional; no OCR or model fallback."""
import hashlib
import json
import math
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


def extract_elements(root, parser=None):
    root = Path(root).resolve()
    packet = load(root/'paper_packet.json')
    acquisition = packet.get('content_acquisition', {})
    if acquisition != {'method': 'PDFPLUMBER_NATIVE', 'manifest_ref': 'source_elements/manifest.json'}:
        raise ElementError('ELEMENTS_INVALID', 'Initialize a new native-elements run; existing runs are not migrated.')
    destination = root/'source_elements'
    if destination.exists():
        raise ElementError('ELEMENTS_EXIST', 'Use a fresh run; never overwrite extraction evidence.')
    if parser is None:
        try:
            import pdfplumber as parser
        except ImportError as exc:
            raise ElementError('PDFPLUMBER_UNAVAILABLE', 'Use an explicitly provisioned extraction Python with pdfplumber; no automatic install or fallback.') from exc
    sources = packet.get('sources', [])
    if not sources:
        raise ElementError('ELEMENTS_INVALID', 'Register source PDFs before extraction.')
    manifest = {'schema_version': 1, 'parser': {'name': 'pdfplumber', 'version': str(getattr(parser, '__version__', 'UNKNOWN'))},
                'ocr_used': False, 'sources': []}
    total_chars = 0
    # A same-filesystem temporary directory becomes visible only after all sources succeed.
    with tempfile.TemporaryDirectory(prefix='.native-elements-', dir=root) as temporary:
        staging = Path(temporary).resolve()
        if not staging.is_relative_to(root):
            raise ElementError('ELEMENTS_INVALID', 'Extraction staging must remain inside this run.')
        for si, source in enumerate(sources):
            if source.get('access_state') != 'AVAILABLE':
                if source.get('required_for_scope'):
                    raise ElementError('ELEMENT_SOURCE_UNAVAILABLE', 'A required source is unavailable.')
                continue
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
                for number, page in enumerate(document.pages, 1):
                    data = page_elements(page, number, sid)
                    total_chars += max(len(data['text']), len(data['chars']))
                    if total_chars > MAX_CHARACTERS:
                        raise ElementError('PDF_ELEMENTS_LIMIT', 'Native text exceeds the extraction character limit.')
                    name = ('' if si == 0 else sid+'-') + f'page-{number:04}.json'
                    save(staging/name, data)
                    entry['pages'].append({'page': number, 'ref': 'source_elements/'+name,
                                           'sha256': sha(staging/name)})
            manifest['sources'].append(entry)
        if not manifest['sources']:
            raise ElementError('ELEMENTS_INVALID', 'No readable source PDF was registered.')
        save(staging/'manifest.json', manifest)
        staging.rename(destination)
    return {'manifest_ref': acquisition['manifest_ref'], 'source_count': len(manifest['sources']),
            'page_count': sum(s['page_count'] for s in manifest['sources']), 'ocr_used': False,
            'reading_state_changed': False, 'notice': 'Extraction records PDF elements, not understanding or acceptance.'}


def read_elements(root, pages, bbox=None, max_chars=MAX_READ_CHARS, source_id=None):
    from reading_element_contracts import element_errors
    root = Path(root).resolve()
    packet = load(root/'paper_packet.json')
    errors = element_errors(root, packet)
    if errors:
        raise ElementError(errors[0]['code'], errors[0]['next_action'])
    if not packet.get('content_acquisition'):
        raise ElementError('ELEMENTS_INVALID', 'This legacy run has no native extraction contract.')
    manifest = load(root/packet['content_acquisition']['manifest_ref'])
    sources = manifest['sources']
    source = next((s for s in sources if s['source_id'] == (source_id or sources[0]['source_id'])), None)
    if (source is None or not isinstance(pages, list) or not pages or len(pages) > 4
            or len(set(pages)) != len(pages) or any(type(p) is not int or not 1 <= p <= source['page_count'] for p in pages)
            or type(max_chars) is not int or not 1 <= max_chars <= MAX_READ_CHARS):
        raise ElementError('ELEMENT_READ_LIMIT', 'Select 1-4 valid pages and a character budget at most 18000.')
    selected_box = box(bbox) if bbox is not None else None
    result = {'source_id': source['source_id'], 'pages': [], 'ocr_used': False, 'truncated': False}
    for number in pages:
        row = next(p for p in source['pages'] if p['page'] == number)
        page = load(root/row['ref'])
        if selected_box and not (0 <= selected_box[0] < selected_box[2] <= page['width'] and 0 <= selected_box[1] < selected_box[3] <= page['height']):
            raise ElementError('ELEMENT_READ_LIMIT', 'The bounding box must stay inside the page.')
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
    if len(json.dumps(result, ensure_ascii=True, separators=(',', ':'))) + 1 > max_chars:
        raise ElementError('ELEMENT_READ_LIMIT', 'Slice by page/region or read specific saved records; no content was silently truncated.')
    return result
