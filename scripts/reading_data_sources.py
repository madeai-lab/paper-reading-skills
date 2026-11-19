"""Registered non-PDF data supplements read with the standard library only.

Files are parsed as inert data: no formula evaluation, macro, script, notebook or
external-link execution, no network access and no format conversion on disk.
"""
import codecs
import csv
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile

DATA_KIND = 'DATA_FILE'
EXTENSIONS_REVISION = (2, 10)
FORMATS = {'CSV': ('.csv',), 'TSV': ('.tsv', '.tab'), 'XLSX': ('.xlsx',), 'JSON': ('.json',),
           'MD': ('.md', '.markdown'), 'TXT': ('.txt',)}
TABULAR = {'CSV', 'TSV', 'XLSX'}
ENCODINGS = {'utf-8', 'utf-16', 'cp1252', 'latin-1'}
DATA_UNIT_KINDS = {'TABLE', 'SECTION', 'APPENDIX', 'BIBLIOGRAPHY'}
LOCATOR_KEYS = {'sheet', 'rows', 'header_row', 'fields', 'json_pointer', 'lines', 'object_label', 'section'}
MAX_DATA_BYTES = 50 * 1024 * 1024
MAX_XML_BYTES = 100 * 1024 * 1024
MAX_CELLS = 2_000_000
MAX_READ_CHARS = 18_000
_HEX = re.compile(r'[0-9a-f]{64}')
_CACHE = {}


class DataError(ValueError):
    def __init__(self, code, message):
        super().__init__(code + ': ' + message)
        self.code = code


class _Conflict(Exception):
    """Content that the supported reader cannot represent; recorded, never repaired silently."""
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def extensions_enabled(packet):
    try:
        revision = tuple(int(x) for x in packet.get('skill_revision', '0').split('.'))
    except (ValueError, AttributeError):
        return False
    return revision >= EXTENSIONS_REVISION


def is_data_source(source):
    return isinstance(source, dict) and source.get('source_kind') == DATA_KIND


def registered_data(packet):
    """Only 2.10+ data files are raw source inputs rather than Owner documents."""
    if not extensions_enabled(packet):
        return []
    return [s for s in packet.get('sources', []) if is_data_source(s)]


def data_paths(root, packet):
    return {(root/s['local_path']).resolve() for s in registered_data(packet) if isinstance(s.get('local_path'), str)}


def check_registry(sources):
    """Source IDs also become filenames: reject collisions on case-insensitive filesystems."""
    seen = set()
    for source in sources:
        sid = source.get('source_id')
        if not isinstance(sid, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', sid) or sid.casefold() in seen:
            raise DataError('ELEMENTS_INVALID', 'Register unique, filename-safe source IDs (ignoring case).')
        seen.add(sid.casefold())
        if source.get('source_kind') not in (None, 'PDF', DATA_KIND):
            raise DataError('DATA_SOURCE_INVALID', 'Unsupported source_kind for ' + sid)


def sha256_file(path, limit=None):
    h = hashlib.sha256()
    size = 0
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            size += len(chunk)
            if limit is not None and size > limit:
                raise DataError('DATA_LIMIT', 'Data file exceeds the %d-byte limit.' % limit)
            h.update(chunk)
    return h.hexdigest()


def _inside(root, ref, what):
    if not isinstance(ref, str) or not ref or Path(ref).is_absolute() or '\\' in ref:
        raise DataError('DATA_SOURCE_INVALID', what + ' must be a nonempty run-relative path with / separators.')
    path = (root/ref).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise DataError('DATA_SOURCE_INVALID', what + ' must be an existing file inside this run: ' + ref)
    return path


def check_record(root, packet, source):
    """Validate a DATA_FILE source record against its local files; raises DataError."""
    root = Path(root).resolve()
    sid = source.get('source_id')
    if not isinstance(sid, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', sid):
        raise DataError('DATA_SOURCE_INVALID', 'Use a safe source_id.')
    fmt = source.get('format')
    if fmt not in FORMATS:
        raise DataError('DATA_SOURCE_INVALID', sid + ': format must be one of ' + ', '.join(sorted(FORMATS))
                        + '. Code, notebooks, macro workbooks and build files are never data sources.')
    path = _inside(root, source.get('local_path'), sid + ' local_path')
    if path.suffix.lower() not in FORMATS[fmt]:
        raise DataError('DATA_SOURCE_INVALID', sid + ': the file extension does not match format ' + fmt + '.')
    if source.get('page_count') is not None:
        raise DataError('DATA_SOURCE_INVALID', sid + ': data files have no pages; keep page_count null.')
    if not isinstance(source.get('sha256'), str) or not _HEX.fullmatch(source['sha256']):
        raise DataError('DATA_SOURCE_INVALID', sid + ': record the actual lowercase SHA-256 of the local file.')
    encoding = source.get('encoding')
    if encoding is not None and (fmt == 'XLSX' or encoding not in ENCODINGS):
        raise DataError('DATA_SOURCE_INVALID', sid + ': encoding applies to text formats only and must be one of '
                        + ', '.join(sorted(ENCODINGS)) + '.')
    others = {s.get('source_id') for s in packet.get('sources', []) if s is not source}
    if source.get('supplement_of') not in others or source.get('supplement_of') == sid:
        raise DataError('DATA_SOURCE_INVALID', sid + ': supplement_of must name the source this file supplements.')
    provenance = source.get('provenance')
    if not isinstance(provenance, dict) or not isinstance(provenance.get('origin'), str) or not provenance['origin'].strip():
        raise DataError('DATA_SOURCE_INVALID', sid + ': provenance.origin must record the published URL, DOI or citation.')
    acquisition = _inside(root, provenance.get('acquisition_ref'), sid + ' provenance.acquisition_ref')
    if acquisition == path or not acquisition.stat().st_size:
        raise DataError('DATA_SOURCE_INVALID', sid + ': provide a separate, nonempty acquisition record.')
    container = provenance.get('container')
    if container is not None:
        if (not isinstance(container, dict) or set(container) != {'local_path', 'sha256', 'member'}
                or not isinstance(container.get('sha256'), str) or not _HEX.fullmatch(container['sha256'])
                or not isinstance(container.get('member'), str) or not container['member']):
            raise DataError('DATA_SOURCE_INVALID', sid + ': container needs exactly local_path, sha256 and member.')
        _inside(root, container['local_path'], sid + ' container local_path')
    return path


def verify_container(root, source):
    """At acquisition time, prove the registered file is the named archive member byte for byte."""
    container = (source.get('provenance') or {}).get('container')
    if container is None:
        return None
    root = Path(root).resolve()
    archive = (root/container['local_path']).resolve()
    if sha256_file(archive) != container['sha256']:
        raise DataError('ELEMENT_SOURCE_CHANGED', source['source_id'] + ': the container archive does not match its recorded hash.')
    try:
        with zipfile.ZipFile(archive) as package:
            info = package.getinfo(container['member'])
            if info.file_size > MAX_DATA_BYTES:
                raise DataError('DATA_LIMIT', source['source_id'] + ': archive member exceeds the data-file limit.')
            h = hashlib.sha256()
            with package.open(info) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    h.update(chunk)
    except (zipfile.BadZipFile, KeyError, NotImplementedError, RuntimeError) as exc:
        raise DataError('DATA_SOURCE_INVALID', source['source_id'] + ': container must be a readable ZIP containing the member ('
                        + type(exc).__name__ + ').') from exc
    if h.hexdigest() != source['sha256']:
        raise DataError('DATA_SOURCE_INVALID', source['source_id'] + ': the local file is not byte-identical to the declared archive member.')
    return {'local_path': container['local_path'], 'sha256': container['sha256'], 'member': container['member']}


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _decode(raw, encoding):
    encoding = encoding or 'utf-8'
    if encoding == 'utf-8' and raw.startswith(codecs.BOM_UTF8):
        raw = raw[len(codecs.BOM_UTF8):]
    try:
        return raw.decode(encoding)
    except UnicodeDecodeError as exc:
        raise _Conflict('TEXT_DECODING_CONFLICT', 'Bytes are not valid %s at offset %d; declare the actual encoding '
                        'only after inspecting the file.' % (encoding, exc.start)) from exc


def _guard(data, name):
    # Workbook parts are UTF-8; refusing other encodings keeps the declaration check meaningful.
    if data[:2] in (b'\xff\xfe', b'\xfe\xff') or b'\x00' in data[:512]:
        raise _Conflict('XLSX_STRUCTURE_CONFLICT', 'Only UTF-8 workbook XML is read: ' + name)
    if b'<!DOCTYPE' in data or b'<!ENTITY' in data:
        raise _Conflict('XLSX_STRUCTURE_CONFLICT', 'XML document type/entity declarations are not read: ' + name)


def _xml(data, name):
    _guard(data, name)
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise _Conflict('XLSX_STRUCTURE_CONFLICT', 'Malformed workbook XML in ' + name) from exc


def _text(node):
    parts = []
    for child in node:
        tag = _local(child.tag)
        if tag == 't':
            parts.append(child.text or '')
        elif tag == 'r':
            parts.extend(t.text or '' for t in child if _local(t.tag) == 't')
    return ''.join(parts)


def _column(ref, row):
    match = re.fullmatch(r'([A-Z]{1,3})(\d+)', ref or '')
    if not match or int(match[2]) != row:
        raise _Conflict('XLSX_STRUCTURE_CONFLICT', 'Unsupported cell reference: ' + str(ref))
    number = 0
    for letter in match[1]:
        number = number * 26 + ord(letter) - 64
    return number


def _xlsx(path):
    try:
        package = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise _Conflict('XLSX_STRUCTURE_CONFLICT', 'The workbook is not a readable ZIP package.') from exc
    with package:
        infos = {info.filename: info for info in package.infolist()}
        budget = [0]

        def member(name):
            info = infos.get(name)
            if info is None:
                raise _Conflict('XLSX_STRUCTURE_CONFLICT', 'Missing workbook part: ' + name)
            budget[0] += info.file_size
            if budget[0] > MAX_XML_BYTES:
                raise DataError('DATA_LIMIT', 'Workbook XML exceeds the %d-byte reading limit.' % MAX_XML_BYTES)
            try:
                return package.read(info)
            except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as exc:
                raise _Conflict('XLSX_STRUCTURE_CONFLICT', 'Unreadable workbook part: ' + name) from exc

        flags = set()
        if any(n.lower().endswith('vbaproject.bin') for n in infos):
            flags.add('MACRO_PROJECT_PRESENT_NOT_EXECUTED')
        if any(n.startswith(('xl/charts/', 'xl/drawings/', 'xl/media/')) for n in infos):
            flags.add('EMBEDDED_GRAPHICS_NOT_REPRESENTED')
        if any(n.startswith('xl/externalLinks/') for n in infos):
            flags.add('EXTERNAL_LINKS_NOT_FOLLOWED')
        workbook = _xml(member('xl/workbook.xml'), 'xl/workbook.xml')
        rels = _xml(member('xl/_rels/workbook.xml.rels'), 'xl/_rels/workbook.xml.rels')
        targets, shared_ref = {}, None
        for rel in rels:
            if _local(rel.tag) != 'Relationship':
                continue
            target = rel.get('Target') or ''
            target = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
            targets[rel.get('Id')] = target
            if (rel.get('Type') or '').endswith('/sharedStrings'):
                shared_ref = target
        shared = []
        if shared_ref:
            shared = [_text(si) for si in _xml(member(shared_ref), shared_ref) if _local(si.tag) == 'si']
        tables, cells = {}, 0
        for sheet in workbook.iter():
            if _local(sheet.tag) != 'sheet':
                continue
            name = sheet.get('name')
            rid = next((v for k, v in sheet.attrib.items() if _local(k) == 'id'), None)
            if not name or name in tables or rid not in targets:
                raise _Conflict('XLSX_STRUCTURE_CONFLICT', 'Sheet names must be unique and resolve to worksheet parts.')
            data = member(targets[rid])
            _guard(data, 'sheet ' + name)
            rows, sheet_flags, last = {}, set(), 0
            if sheet.get('state') in {'hidden', 'veryHidden'}:
                sheet_flags.add('HIDDEN_SHEET')
            try:
                for _, node in ET.iterparse(io.BytesIO(data), events=('end',)):
                    tag = _local(node.tag)
                    if tag == 'mergeCell':
                        sheet_flags.add('MERGED_CELLS')
                    if tag != 'row':
                        continue
                    number = int(node.get('r') or last + 1)
                    if not last < number <= 1_048_576:
                        raise _Conflict('XLSX_STRUCTURE_CONFLICT', 'Rows are duplicated or out of order in sheet ' + name)
                    last = number
                    if node.get('hidden') in {'1', 'true'}:
                        sheet_flags.add('HIDDEN_ROWS')
                    values, column = {}, 0
                    for cell in node:
                        if _local(cell.tag) != 'c':
                            continue
                        column = _column(cell.get('r'), number) if cell.get('r') else column + 1
                        if column in values or column > 16_384:
                            raise _Conflict('XLSX_STRUCTURE_CONFLICT', 'Duplicate or invalid cell in sheet ' + name)
                        parts = {_local(child.tag): child for child in cell}
                        kind, raw = cell.get('t', 'n'), parts.get('v')
                        raw = raw.text if raw is not None else None
                        if 'f' in parts:
                            sheet_flags.add('FORMULA_CACHED_VALUES')
                        if kind == 's':
                            index = int(raw) if raw not in (None, '') else -1
                            if not 0 <= index < len(shared):
                                raise _Conflict('XLSX_STRUCTURE_CONFLICT', 'Shared string index is out of range in sheet ' + name)
                            values[column] = shared[index]
                        elif kind == 'inlineStr':
                            values[column] = _text(parts['is']) if 'is' in parts else ''
                        elif kind == 'b':
                            values[column] = 'TRUE' if raw == '1' else 'FALSE' if raw == '0' else raw
                        else:
                            values[column] = raw
                    # The dense row below allocates missing cells too. Bound that allocation, not just XML nodes.
                    width = max(values, default=0)
                    cells += max(width, 1)
                    if cells > MAX_CELLS:
                        raise DataError('DATA_LIMIT', 'Workbook exceeds the %d-cell reading limit.' % MAX_CELLS)
                    rows[number] = [values.get(i) for i in range(1, width + 1)]
                    node.clear()
            except (ET.ParseError, ValueError) as exc:
                if isinstance(exc, DataError):
                    raise
                raise _Conflict('XLSX_STRUCTURE_CONFLICT', 'Unreadable worksheet XML in sheet ' + name) from exc
            tables[name] = {'rows': rows, 'flags': sorted(sheet_flags), 'state': sheet.get('state', 'visible')}
        if not tables:
            raise _Conflict('XLSX_STRUCTURE_CONFLICT', 'The workbook lists no worksheets.')
        return tables, sorted(flags)


@dataclass(frozen=True)
class _JsonNumber:
    """A JSON number token, deliberately neither a binary float nor a string value."""
    __slots__ = ('token',)
    token: str


def _json_int(token):
    # Keep ordinary integers native. Preserve signed zero and avoid Python's
    # configurable decimal digit limit (and costly conversions of huge integers).
    return int(token) if len(token) <= 640 and token != '-0' else _JsonNumber(token)


def _json(text):
    def pairs(items):
        keys = [k for k, _ in items]
        if len(set(keys)) != len(keys):
            raise _Conflict('JSON_DUPLICATE_KEY', 'An object repeats a key; the standard reader would hide one value.')
        return dict(items)

    def constant(name):
        raise _Conflict('JSON_PARSE_CONFLICT', 'Non-standard JSON constant ' + name)
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant,
                          parse_int=_json_int, parse_float=_JsonNumber)
    except (ValueError, RecursionError) as exc:
        raise _Conflict('JSON_PARSE_CONFLICT', 'The file is not valid JSON: ' + type(exc).__name__) from exc


def parse(path, source, digest):
    """Parse a hash-verified data file into an inert in-memory document."""
    key = (digest, source.get('format'), source.get('encoding'))
    if key in _CACHE:
        return _CACHE[key]
    fmt = source['format']
    try:
        if Path(path).stat().st_size > MAX_DATA_BYTES:
            raise DataError('DATA_LIMIT', 'Data file exceeds the %d-byte limit.' % MAX_DATA_BYTES)
        if fmt == 'XLSX':
            tables, flags = _xlsx(path)
            doc = {'format': fmt, 'tables': tables, 'flags': flags}
        else:
            text = _decode(Path(path).read_bytes(), source.get('encoding'))
            if fmt in {'CSV', 'TSV'}:
                previous_limit = csv.field_size_limit(MAX_DATA_BYTES)
                try:
                    records = []
                    cells = 0
                    for row in csv.reader(io.StringIO(text, newline=''), delimiter=',' if fmt == 'CSV' else '\t', strict=True):
                        cells += max(1, len(row))
                        if cells > MAX_CELLS:
                            raise DataError('DATA_LIMIT', 'Delimited text exceeds the cell reading limit.')
                        records.append(row)
                except csv.Error as exc:
                    raise _Conflict('CSV_PARSE_CONFLICT', 'Malformed quoting or delimiter use: ' + str(exc)) from exc
                finally:
                    csv.field_size_limit(previous_limit)
                if not records:
                    raise _Conflict('CSV_PARSE_CONFLICT', 'The table has no records.')
                flags = ['RAGGED_ROWS'] if len({len(r) for r in records}) > 1 else []
                doc = {'format': fmt, 'flags': [],
                       'tables': {None: {'rows': dict(enumerate(records, 1)), 'flags': flags, 'state': 'visible'}}}
            elif fmt == 'JSON':
                doc = {'format': fmt, 'flags': [], 'value': _json(text)}
            else:
                lines = re.split(r'\r\n|\r|\n', text)
                if lines and lines[-1] == '':
                    lines.pop()
                doc = {'format': fmt, 'flags': [], 'lines': lines}
    except _Conflict as conflict:
        doc = {'format': fmt, 'conflict': conflict.code, 'detail': str(conflict)}
    if len(_CACHE) >= 16:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = doc
    return doc


def summary(doc):
    """Navigation-only structure recorded in the acquisition manifest."""
    if 'conflict' in doc:
        return {'parse_state': 'CONFLICT', 'conflict': doc['conflict'], 'detail': doc['detail']}
    result = {'parse_state': 'PARSED', 'flags': doc['flags']}
    if 'tables' in doc:
        result['tables'] = []
        for name, table in doc['tables'].items():
            numbers = sorted(table['rows'])
            result['tables'].append({
                'sheet': name, 'state': table['state'], 'row_count': len(numbers),
                'first_row': numbers[0] if numbers else None, 'last_row': numbers[-1] if numbers else None,
                'column_count': max((len(v) for v in table['rows'].values()), default=0),
                'row_1_values': table['rows'].get(1), 'flags': table['flags']})
    elif 'value' in doc:
        value = doc['value']
        names = {dict: 'object', list: 'array', str: 'string', bool: 'boolean',
                 int: 'number', float: 'number', _JsonNumber: 'number'}
        result['top_level'] = names.get(type(value), 'null')
        if isinstance(value, dict):
            result['keys'] = list(value)
        elif isinstance(value, list):
            result['length'] = len(value)
    else:
        result['line_count'] = len(doc['lines'])
    return result


def _pair(value, name, low=1):
    if (not isinstance(value, list) or len(value) != 2 or any(type(x) is not int for x in value)
            or not low <= value[0] <= value[1]):
        raise DataError('DATA_LOCATOR_INVALID', name + ' must be [first, last] with %d <= first <= last.' % low)
    return value


def _pointer(value, pointer):
    if pointer == '':
        return value
    if not pointer.startswith('/'):
        raise DataError('DATA_LOCATOR_INVALID', 'json_pointer must be "" or start with "/" (RFC 6901).')
    for raw in pointer[1:].split('/'):
        if re.search(r'~(?![01])', raw):
            raise DataError('DATA_LOCATOR_INVALID', 'JSON pointer contains an invalid escape.')
        token = raw.replace('~1', '/').replace('~0', '~')
        if isinstance(value, dict) and token in value:
            value = value[token]
        elif isinstance(value, list) and re.fullmatch(r'0|[1-9]\d*', token) and int(token) < len(value):
            value = value[int(token)]
        else:
            raise DataError('DATA_LOCATOR_INVALID', 'json_pointer does not resolve: ' + pointer)
    return value


def resolve(doc, locator):
    """Resolve one file + row/field locator; raises DataError and returns only the selected content."""
    if 'conflict' in doc:
        raise DataError('DATA_PARSE_CONFLICT', doc['conflict'] + ': ' + doc['detail']
                        + ' Record the representation conflict; do not transcode or edit the source.')
    if not isinstance(locator, dict) or not locator or set(locator) - LOCATOR_KEYS:
        raise DataError('DATA_LOCATOR_INVALID', 'Data locators use only ' + ', '.join(sorted(LOCATOR_KEYS))
                        + '; pages and native element IDs do not apply.')
    fmt = doc['format']
    if fmt in TABULAR:
        if set(locator) & {'json_pointer', 'lines'}:
            raise DataError('DATA_LOCATOR_INVALID', 'Tabular files use sheet/rows/header_row/fields locators.')
        sheet = locator.get('sheet')
        if fmt == 'XLSX':
            if not isinstance(sheet, str) or sheet not in doc['tables']:
                raise DataError('DATA_LOCATOR_INVALID', 'Name an existing worksheet: ' + ', '.join(doc['tables']))
        elif sheet is not None:
            raise DataError('DATA_LOCATOR_INVALID', 'CSV/TSV files have no sheets.')
        table = doc['tables'][sheet]
        if not table['rows']:
            raise DataError('DATA_LOCATOR_INVALID', 'The selected table has no rows.')
        first, last = _pair(locator.get('rows'), 'rows')
        if first < min(table['rows']) or last > max(table['rows']):
            raise DataError('DATA_LOCATOR_INVALID', 'rows must stay within %d-%d.' % (min(table['rows']), max(table['rows'])))
        header_row = locator.get('header_row', 1)
        if header_row is not None and (type(header_row) is not int or header_row not in table['rows']):
            raise DataError('DATA_LOCATOR_INVALID', 'header_row must name an existing row, or be null for no header.')
        header = table['rows'][header_row] if header_row is not None else None
        fields = locator.get('fields')
        if fields is None:
            columns = None
        else:
            if (header is None or not isinstance(fields, list) or not fields
                    or any(not isinstance(f, str) or not f for f in fields) or len(set(fields)) != len(fields)):
                raise DataError('DATA_LOCATOR_INVALID', 'fields must be unique header names from header_row.')
            columns = []
            for name in fields:
                matches = [i for i, value in enumerate(header) if value == name]
                if len(matches) != 1:
                    raise DataError('DATA_LOCATOR_INVALID', 'Field %r occurs %d times in the header.' % (name, len(matches)))
                columns.append(matches[0])

        def pick(values):
            return values if columns is None else [values[i] if i < len(values) else None for i in columns]
        rows = [{'row': n, 'values': pick(v)} for n, v in table['rows'].items() if first <= n <= last]
        if not rows:
            raise DataError('DATA_LOCATOR_INVALID', 'No stored rows in the specified range.')
        return {'sheet': sheet, 'header_row': header_row, 'header': pick(header) if header is not None else None,
                'rows': rows,
                'flags': sorted(set(table['flags']) | set(doc['flags']))}
    if fmt == 'JSON':
        if set(locator) - {'json_pointer', 'object_label', 'section'} or not isinstance(locator.get('json_pointer'), str):
            raise DataError('DATA_LOCATOR_INVALID', 'JSON files use a json_pointer locator.')
        return {'json_pointer': locator['json_pointer'], 'value': _pointer(doc['value'], locator['json_pointer'])}
    if set(locator) - {'lines', 'object_label', 'section'}:
        raise DataError('DATA_LOCATOR_INVALID', 'Markdown/text files use a lines locator.')
    first, last = _pair(locator.get('lines'), 'lines')
    if last > len(doc['lines']):
        raise DataError('DATA_LOCATOR_INVALID', 'lines must stay within 1-%d.' % len(doc['lines']))
    return {'lines': [first, last], 'text': '\n'.join(doc['lines'][first - 1:last])}


def manifest_entry(root, packet, source):
    """Bind one registered data file to the acquisition manifest; no extraction artifact is written."""
    path = check_record(root, packet, source)
    digest = sha256_file(path, MAX_DATA_BYTES)
    if digest != source['sha256']:
        raise DataError('ELEMENT_SOURCE_CHANGED', 'Data file bytes do not match the frozen identity: ' + source['source_id'])
    container = verify_container(root, source)
    return {'source_id': source['source_id'], 'local_path': source['local_path'], 'sha256': digest,
            'format': source['format'], 'encoding': source.get('encoding'), 'container': container,
            'origin': source['provenance']['origin'], 'supplement_of': source['supplement_of'],
            'acquisition_ref': source['provenance']['acquisition_ref'],
            'acquisition_sha256': sha256_file(root/source['provenance']['acquisition_ref']),
            'structure': summary(parse(path, source, digest))}


def _read_chars(doc, locator, chars):
    """Window one decoded value, without extending resolve()'s scientific locators."""
    first, last = _pair(chars, 'chars')
    if not isinstance(locator, dict):
        raise DataError('DATA_LOCATOR_INVALID', '--chars needs a line, named cell or JSON string locator.')
    fmt = doc['format']
    if fmt in TABULAR:
        start, end = _pair(locator.get('rows'), 'rows')
        fields = locator.get('fields')
        if start != end or (fields is not None and (not isinstance(fields, list) or len(fields) != 1)):
            raise DataError('DATA_LOCATOR_INVALID', '--chars needs one row and one field (omit fields for a single-column row).')
    elif fmt != 'JSON':
        start, end = _pair(locator.get('lines'), 'lines')
        if start != end:
            raise DataError('DATA_LOCATOR_INVALID', '--chars needs exactly one line.')

    selected = resolve(doc, locator)

    def window(value):
        if not isinstance(value, str):
            raise DataError('DATA_LOCATOR_INVALID', '--chars needs a string value, not a number, null or container.')
        size = len(value)
        if last > size:
            raise DataError('DATA_LOCATOR_INVALID', 'Selected value has %d characters; narrow --chars or omit it.' % size)
        selected.update(chars=[first, last], total_chars=size, partial=(first != 1 or last != size))
        return value[first - 1:last]

    if fmt in TABULAR:
        row, = selected['rows']
        if len(row['values']) != 1:
            raise DataError('DATA_LOCATOR_INVALID', '--chars needs exactly one field; name it in --fields for a multi-column row.')
        # An unprojected values list belongs to the cache. Replace, never edit it.
        row['values'] = [window(row['values'][0])]
        if locator.get('fields') is None:
            selected['column'] = 1
            if selected['header_row'] == row['row']:
                del selected['header']  # The selected header cell itself must not escape the window.
            elif selected['header'] is not None:
                selected['header'] = selected['header'][:1]
    elif fmt == 'JSON':
        selected['value'] = window(selected['value'])
    else:
        selected['text'] = window(selected['text'])
    return selected


def _check_budget(max_chars):
    if type(max_chars) is not int or not 1 <= max_chars <= MAX_READ_CHARS:
        raise DataError('DATA_READ_LIMIT', 'Choose a character budget from 1 to %d.' % MAX_READ_CHARS)


def data_json(result, *, max_chars=MAX_READ_CHARS):
    """Compact ASCII JSON (no newline); the budget includes one final CLI LF.

    Write only validated number tokens unquoted. Bound the output as we go: e.g.
    a rejected multi-megabyte string must not allocate its full ASCII escape form.
    """
    _check_budget(max_chars)
    out = io.StringIO()

    def reserve(size):
        if out.tell() + size + 1 > max_chars:
            raise DataError('DATA_READ_LIMIT', 'Narrow rows, fields, lines or the JSON pointer. For one line, cell '
                            'or JSON string try --chars 1 1, or narrow the character range. Increase --max-chars '
                            'if the locator and metadata alone exceed the budget; nothing was silently truncated.')

    def put(token):
        reserve(len(token))
        out.write(token)

    def emit(value):
        if isinstance(value, dict):
            put('{')
            for i, (name, child) in enumerate(value.items()):
                if not isinstance(name, str):
                    raise TypeError('JSON object keys must be strings.')
                if i:
                    put(',')
                emit(name)
                put(':')
                emit(child)
            put('}')
        elif isinstance(value, (list, tuple)):
            put('[')
            for i, child in enumerate(value):
                if i:
                    put(',')
                emit(child)
            put(']')
        elif isinstance(value, _JsonNumber):
            reserve(len(value.token))
            if not re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?', value.token):
                raise ValueError('Invalid JSON number token.')
            put(value.token)
        else:
            if isinstance(value, str):
                reserve(len(value) + 2)
            put(json.dumps(value, ensure_ascii=True, allow_nan=False))

    try:
        emit(result)
    except RecursionError as exc:
        raise DataError('DATA_READ_LIMIT', 'Selection is too deeply nested; choose a narrower JSON pointer.') from exc
    return out.getvalue()


def read_data(root, source_id, locator=None, max_chars=MAX_READ_CHARS, *, chars=None):
    """Read verified data. Optional chars=[first,last] counts Unicode code points from one."""
    from reading_element_contracts import validate_acquisition, error_code
    root = Path(root).resolve()
    packet = json.loads((root/'paper_packet.json').read_text(encoding='utf-8-sig'))
    _check_budget(max_chars)
    try:
        bound = validate_acquisition(root, packet)['data']
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise DataError(error_code(exc), str(exc)) from exc
    if source_id not in bound:
        raise DataError('INVALID_ARGUMENT', 'Select a DATA_FILE source bound in the acquisition manifest.')
    source, entry = bound[source_id]
    result = {'source_id': source_id, 'local_path': source['local_path'], 'format': source['format'],
              'reading_state_changed': False, 'code_executed': False}
    if locator is None:
        if chars is not None:
            raise DataError('DATA_LOCATOR_INVALID', '--chars needs a content locator, not a navigation-only structure.')
        result.update(view='structure', purpose='NAVIGATION_ONLY', structure=entry['structure'])
    else:
        doc = parse(root/source['local_path'], source, entry['sha256'])
        selected = resolve(doc, locator) if chars is None else _read_chars(doc, locator, chars)
        result.update(locator=locator, **selected)
    data_json(result, max_chars=max_chars)
    return result
