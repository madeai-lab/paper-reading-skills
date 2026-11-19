"""Literature candidate sets: import, de-duplication, screening records, reading queue and evidence tiers.

The workspace keeps one screening record per paper, separate from any complete-reading run.
Status tables are derived from those records on demand rather than stored as mirrors.
"""
import copy
import csv
import io
import json
import os
from pathlib import Path
import re
import shutil
import unicodedata

from reading_run_records import RunError, read, write, digest
import reading_resources as resources
import reading_triage as triage

CORPUS_SCHEMA = 1
MODES = {'EXPLORATORY', 'SYSTEMATIC_REVIEW'}
FORMATS = {'.csv': 'CSV', '.tsv': 'TSV', '.json': 'JSON', '.bib': 'BIBTEX', '.xlsx': 'XLSX'}
ALIASES = {
    'title': {'title', 'paper title', 'article title', '标题', '题名', '题目'},
    'abstract': {'abstract', 'summary', '摘要'},
    'doi': {'doi'},
    'arxiv_id': {'arxiv', 'arxiv_id', 'arxiv id', 'arxivid', 'eprint'},
    'url': {'url', 'link', 'pdf_url', 'pdf url', '链接'},
    'authors': {'authors', 'author', '作者'},
    'year': {'year', 'publication year', 'pub_year', 'date', '年份'},
    'venue': {'venue', 'journal', 'booktitle', 'conference', 'publication', 'source title', '期刊', '会议'},
    'key': {'id', 'key', 'citekey', 'citation key', 'record id'},
}
ARXIV = re.compile(r'(\d{4}\.\d{4,5}|[a-z\-]+(?:\.[a-z]{2})?/\d{7})(v\d+)?', re.I)
TIERS = ('UNSCREENED', 'METADATA_SCREENED', 'SKIMMED', 'TARGETED_READ', 'VERIFIED_USER_SCOPE', 'VERIFIED_COMPLETE')
VERIFIED_TIERS = {'VERIFIED_USER_SCOPE', 'VERIFIED_COMPLETE'}
ACTION_ORDER = ['CONTINUE_L3_RUN', 'PROMOTE_L3', 'TARGETED_READ_L2', 'SKIM_L1', 'ATTACH_FULL_TEXT', 'OBTAIN_EVIDENCE',
                'UPGRADE_NEEDS_USER', 'REEXAMINE_NEW_VERSION', 'REASSESS_FOR_TARGET', 'RECORD_ROUTING_DECISION', 'SCREEN_L0']


def _text(value):
    return isinstance(value, str) and bool(value.strip())


# ---------------------------------------------------------------- workspace records

def load_corpus(root):
    root = Path(root).resolve()
    if not (root/'corpus.json').is_file():
        raise RunError('CORPUS_MISSING', 'Initialize a screening workspace first (reading_triage_control.py init).')
    corpus = read(root/'corpus.json')
    if not isinstance(corpus, dict) or corpus.get('corpus_schema_version') != CORPUS_SCHEMA:
        raise RunError('UNSUPPORTED_SCREENING_SCHEMA', 'Unknown corpus schema; this helper neither migrates nor rewrites it.')
    return corpus


def paper_dir(root, paper_id):
    if not isinstance(paper_id, str) or not re.fullmatch(r'P\d{4,}', paper_id):
        raise RunError('INVALID_ARGUMENT', 'Select a paper by its ID, for example --paper P0001.')
    path = Path(root).resolve()/'papers'/paper_id
    if not (path/'screening.json').is_file():
        raise RunError('INVALID_ARGUMENT', 'Unknown paper in this workspace: ' + paper_id)
    return path


def load_record(root, paper_id):
    return triage.check_schema(read(paper_dir(root, paper_id)/'screening.json'))


def save_record(root, record):
    write(Path(root).resolve()/'papers'/record['paper_id']/'screening.json', record)


def _check_criteria(criteria, mode):
    criteria = criteria or []
    if (not isinstance(criteria, list) or any(not isinstance(c, dict) or not _text(c.get('id')) or not _text(c.get('text'))
                                              for c in criteria) or len({c['id'] for c in criteria}) != len(criteria)):
        raise RunError('INVALID_ARGUMENT', 'Exclusion criteria are a list of {id, text} with unique IDs.')
    if mode == 'SYSTEMATIC_REVIEW' and not criteria:
        raise RunError('INVALID_ARGUMENT', 'A systematic-review workspace states its exclusion criteria up front.')
    return [{'id': c['id'].strip(), 'text': c['text'].strip()} for c in criteria]


def criteria_index(corpus):
    """Stated criterion IDs with the hash of their wording; a decision cites the wording it was made under."""
    return {c['id']: triage.criterion_sha(c) for c in corpus['protocol']['exclusion_criteria']}


def workspace_ceiling(corpus):
    return (corpus['protocol'].get('depth_ceiling') or {}).get('depth')


def _limit(depth, instruction):
    if depth not in triage.SCREENING_DEPTHS or not _text(instruction):
        raise RunError('USER_INSTRUCTION_REQUIRED', 'A depth limit needs the deepest allowed depth (L0, L1 or L2) and what the user actually asked.')
    return {'depth': depth, 'user_instruction': instruction.strip(), 'at': triage.now()}


def init_corpus(root, owner, target=None, mode='EXPLORATORY', criteria=None, max_depth=None, instruction=None):
    from reading_run_control import validate_target
    root = Path(root).resolve()
    if root.exists():
        raise RunError('CORPUS_EXISTS', 'Choose a new workspace directory; existing records are never overwritten.')
    if mode not in MODES or not _text(owner):
        raise RunError('INVALID_ARGUMENT', 'Use mode EXPLORATORY or SYSTEMATIC_REVIEW and the actual owner ID.')
    validate_target(target)
    criteria = _check_criteria(criteria, mode)
    ceiling = _limit(max_depth, instruction) if max_depth else None
    root.mkdir(parents=True)
    corpus = {'corpus_schema_version': CORPUS_SCHEMA, 'corpus_id': root.name, 'owner_id': owner.strip(), 'reading_policy': 2,
              'protocol': {'mode': mode, 'exclusion_criteria': criteria, 'criteria_history': [], 'depth_ceiling': ceiling},
              'research_target': copy.deepcopy(target), 'target_history': [], 'paper_ids': [], 'imports': [],
              'manual_records': 0,
              'history': ['Workspace created %s; screening records are separate from complete-reading runs.' % triage.now()]}
    write(root/'corpus.json', corpus)
    return {'corpus_id': corpus['corpus_id'], 'mode': mode, 'target': triage.target_binding(target),
            'notice': 'Screening depth and independent review scope are separate choices. Nothing here grants acceptance.'}


def set_target(root, target):
    from reading_run_control import validate_target
    root = Path(root).resolve()
    corpus = load_corpus(root)
    validate_target(target)
    old = corpus.get('research_target')
    history = corpus.setdefault('target_history', [])
    if target:
        previous = [entry for entry in history + [old] if entry and entry.get('target_id') == target['target_id']]
        if any(entry != target and target['revision'] <= entry.get('revision', 0) for entry in previous):
            raise RunError('INVALID_TARGET', 'Changed content under the same target_id needs a higher revision.')
    if old and old not in history:
        history.append(copy.deepcopy(old))
    corpus['research_target'] = copy.deepcopy(target)
    corpus['history'].append('Research target set to %s at %s; earlier relevance decisions need reassessment.'
                             % (json.dumps(triage.target_binding(target)), triage.now()))
    write(root/'corpus.json', corpus)
    stale = [pid for pid in corpus['paper_ids']
             if triage.next_step(load_record(root, pid), target)['kind'] == 'REASSESS_FOR_TARGET']
    return {'target': triage.target_binding(target), 'papers_requiring_reassessment': stale,
            'notice': 'What was examined, and where, is kept. Relevance, routing, exclusion and the link between targeted-reading '
                      'focus and target questions were judged for another target and do not carry over until reassessed.'}


def set_criteria(root, criteria):
    """Replace the stated criteria. Exclusions that cited a changed or removed criterion need a new decision."""
    root = Path(root).resolve()
    corpus = load_corpus(root)
    criteria = _check_criteria(criteria, corpus['protocol']['mode'])
    corpus['protocol'].setdefault('criteria_history', []).append({'replaced_at': triage.now(),
                                                                  'criteria': corpus['protocol']['exclusion_criteria']})
    corpus['protocol']['exclusion_criteria'] = criteria
    corpus['history'].append('Stated criteria replaced at %s.' % triage.now())
    write(root/'corpus.json', corpus)
    index = criteria_index(corpus)
    stale = [pid for pid in corpus['paper_ids']
             if triage.current_decision(load_record(root, pid), corpus['research_target'], index)[1] == 'CRITERION_CHANGED']
    return {'criteria': criteria, 'papers_requiring_a_new_decision': stale,
            'notice': 'Criteria apply to decisions recorded from now on. Earlier exclusions under other wording are suspended, not rewritten.'}


def set_scope(root, paper_id, spec, instruction):
    from reading_scope import bind
    record = load_record(root, paper_id)
    bind(record, spec, instruction, paper_dir(root, paper_id))
    save_record(root, record)
    return status(root, paper_id)


def limit_depth(root, paper_id, depth, instruction):
    """Record a user limit on reading depth for one paper, or for the whole workspace when no paper is named."""
    root = Path(root).resolve()
    corpus = load_corpus(root)
    if paper_id:
        save_record(root, triage.limit_depth(load_record(root, paper_id), depth, instruction))
        return status(root, paper_id)
    corpus['protocol']['depth_ceiling'] = _limit(depth, instruction)
    corpus['history'].append('User limited reading depth to %s at %s.' % (depth, triage.now()))
    write(root/'corpus.json', corpus)
    return {'workspace_depth_ceiling': corpus['protocol']['depth_ceiling'],
            'notice': 'Applies to every paper without its own request or limit. Deeper reading can be recommended, not performed, '
                      'until the user asks for it.'}


# ---------------------------------------------------------------- identifiers and parsing

def norm_doi(value):
    if not _text(value):
        return None
    doi = re.sub(r'^(https?://(dx\.)?doi\.org/|doi:\s*)', '', value.strip().lower()).strip().rstrip('.')
    return doi if re.fullmatch(r'10\.\d{4,9}/\S+', doi) else None


def norm_arxiv(value):
    """Return (identifier without version, version suffix or None)."""
    if not _text(value):
        return None, None
    text = re.sub(r'^(https?://)?(www\.)?arxiv\.org/(abs|pdf)/', '', value.strip(), flags=re.I)
    text = re.sub(r'\.pdf$', '', re.sub(r'^arxiv:\s*', '', text, flags=re.I), flags=re.I)
    text = re.sub(r'\s*\[[^\]]+\]$', '', text)
    match = ARXIV.fullmatch(text)
    return (match.group(1).lower(), (match.group(2) or '').lower() or None) if match else (None, None)


def title_key(title):
    if not _text(title):
        return None
    text = re.sub(r'[^\w]+', ' ', unicodedata.normalize('NFKC', title).casefold())
    return ' '.join(text.split()) or None


def identifiers(fields):
    doi = norm_doi(fields.get('doi')) or norm_doi(fields.get('url'))
    arxiv, version = norm_arxiv(fields.get('arxiv_id'))
    if arxiv is None and _text(fields.get('url')) and 'arxiv.org' in fields['url'].lower():
        arxiv, version = norm_arxiv(fields['url'])
    if doi and doi.startswith('10.48550/arxiv.'):
        # An arXiv DOI names the preprint, not a separate publisher version.
        if arxiv is None:
            arxiv, version = norm_arxiv(doi[len('10.48550/arxiv.'):])
        doi = None
    return {'doi': doi, 'arxiv_id': arxiv, 'arxiv_version': version, 'title_key': title_key(fields.get('title'))}


def canonical_fields(raw):
    """Map source column names onto canonical ones; keep every original value as text."""
    lowered = {str(key).strip().casefold(): value for key, value in raw.items() if key is not None}
    fields = {}
    for name, names in ALIASES.items():
        value = next((lowered[key] for key in lowered if key in names and lowered[key] not in (None, '')), None)
        if value is not None:
            fields[name] = str(value).strip()
    original = {str(key): '' if value is None else str(value) for key, value in raw.items() if key is not None}
    return fields, original


def _bibtex(text):
    rows = []
    for match in re.finditer(r'@(\w+)\s*\{\s*([^,\s]*)\s*,', text):
        if match.group(1).lower() in {'comment', 'string', 'preamble'}:
            continue
        depth, end = 1, match.end()
        while end < len(text) and depth:
            depth += (text[end] == '{') - (text[end] == '}')
            end += 1
        body, pos, fields = text[match.end():end - 1], 0, {}
        while True:
            name = re.compile(r'\s*([A-Za-z_][\w\-]*)\s*=\s*').match(body, pos)
            if not name or name.end() >= len(body):
                break
            pos = name.end()
            if body[pos] == '{':
                level, stop = 1, pos + 1
                while stop < len(body) and level:
                    level += (body[stop] == '{') - (body[stop] == '}')
                    stop += 1
                value, pos = body[pos + 1:stop - 1], stop
            elif body[pos] == '"':
                level, stop = 0, pos + 1
                while stop < len(body) and (body[stop] != '"' or level):
                    level += (body[stop] == '{') - (body[stop] == '}')
                    stop += 1
                value, pos = body[pos + 1:stop], stop + 1
            else:
                bare = re.compile(r'[^,]*').match(body, pos)
                value, pos = bare.group(0), bare.end()
            fields[name.group(1).lower()] = re.sub(r'\s+', ' ', value.replace('{', '').replace('}', '')).strip()
            comma = re.compile(r'\s*,').match(body, pos)
            if not comma:
                break
            pos = comma.end()
        fields.update(key=match.group(2), bibtex_type=match.group(1).lower())
        rows.append(('entry ' + match.group(2), fields))
    return rows


def _table(rows, label):
    """rows: {row_number: [cells]} with a header in the first present row."""
    numbers = sorted(rows)
    if not numbers:
        return []
    header = [str(cell).strip() if cell is not None else '' for cell in rows[numbers[0]]]
    return [(f'{label}row {number}', {name: value for name, value in zip(header, rows[number]) if name})
            for number in numbers[1:] if any(cell not in (None, '') for cell in rows[number])]


def parse_records(path, fmt, sheet=None):
    path = Path(path)
    if fmt == 'XLSX':
        from reading_data_sources import parse
        doc = parse(path, {'format': 'XLSX'}, digest(path))
        if 'conflict' in doc:
            raise RunError('IMPORT_UNREADABLE', 'The workbook could not be read: ' + doc['detail'])
        names = [name for name, table in doc['tables'].items() if table.get('state', 'visible') == 'visible']
        name = sheet or (names[0] if names else None)
        if name not in doc['tables']:
            raise RunError('IMPORT_UNREADABLE', 'Choose a worksheet with --sheet: ' + ', '.join(doc['tables']))
        return _table(doc['tables'][name]['rows'], f'sheet {name} ')
    text = path.read_text(encoding='utf-8-sig')
    if fmt in {'CSV', 'TSV'}:
        try:
            rows = list(csv.reader(io.StringIO(text, newline=''), delimiter=',' if fmt == 'CSV' else '\t', strict=True))
        except csv.Error as exc:
            raise RunError('IMPORT_UNREADABLE', 'Malformed delimited records: ' + str(exc)) from exc
        return _table(dict(enumerate(rows, 1)), '')
    if fmt == 'JSON':
        data = json.loads(text)
        if isinstance(data, dict):
            data = next((data[key] for key in ('records', 'papers', 'items', 'references') if isinstance(data.get(key), list)), None)
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise RunError('IMPORT_UNREADABLE', 'JSON records are an array of objects (optionally under "records").')
        return [(f'index {number}', row) for number, row in enumerate(data)]
    if fmt == 'BIBTEX':
        return _bibtex(text)
    raise RunError('INVALID_ARGUMENT', 'Supported record formats: CSV, TSV, JSON, BIBTEX, XLSX.')


# ---------------------------------------------------------------- import and de-duplication

def _index(root, corpus):
    index = {'doi': {}, 'arxiv': {}, 'title': {}, 'ids': {}}
    for pid in corpus['paper_ids']:
        _register(index, load_record(root, pid))
    return index


def _register(index, record):
    pid = record['paper_id']
    dois, arxivs = set(), set()
    for row in record['source_records']:
        ids = row['identifiers']
        if ids.get('doi'):
            dois.add(ids['doi'])
            index['doi'].setdefault(ids['doi'], pid)
        if ids.get('arxiv_id'):
            arxivs.add(ids['arxiv_id'])
            index['arxiv'].setdefault(ids['arxiv_id'], pid)
        if ids.get('title_key') and pid not in index['title'].setdefault(ids['title_key'], []):
            index['title'][ids['title_key']].append(pid)
    index['ids'][pid] = {'doi': dois, 'arxiv': arxivs}


def _match(index, ids):
    by_doi = index['doi'].get(ids['doi']) if ids['doi'] else None
    by_arxiv = index['arxiv'].get(ids['arxiv_id']) if ids['arxiv_id'] else None
    if by_doi:
        # One record naming two existing papers is a question for a person, not a merge of both.
        return by_doi, 'DOI', [by_arxiv] if by_arxiv and by_arxiv != by_doi else []
    if by_arxiv:
        return by_arxiv, 'ARXIV_ID', []
    possible = []
    key = ids['title_key']
    # A short title such as "Introduction" identifies nothing on its own. CJK titles carry more per character.
    enough = key and len(key) >= (6 if any(ord(char) > 0x2E7F for char in key) else 12)
    for pid in index['title'].get(key, []) if enough else []:
        other = index['ids'][pid]
        if (ids['doi'] and other['doi'] and ids['doi'] not in other['doi']) or (
                ids['arxiv_id'] and other['arxiv'] and ids['arxiv_id'] not in other['arxiv']):
            possible.append(pid)
        else:
            return pid, 'TITLE', []
    return None, None, possible


def _identity(fields, ids):
    authors = [a.strip() for a in re.split(r'\s+and\s+|;', fields.get('authors', '')) if a.strip()]
    year = re.search(r'(19|20)\d{2}', fields.get('year', ''))
    return {'title': fields.get('title'), 'authors': authors or None, 'year': int(year.group(0)) if year else None,
            'venue': fields.get('venue'), 'doi': ids['doi'], 'arxiv_id': ids['arxiv_id'], 'url': fields.get('url')}


def _ingest(root, corpus, index, raw, origin):
    fields, original = canonical_fields(raw)
    ids = identifiers(fields)
    if not (ids['title_key'] or ids['doi'] or ids['arxiv_id'] or _text(fields.get('url'))):
        return {'outcome': 'UNUSABLE', 'locator': origin['locator'], 'reason': 'No title, DOI, arXiv ID or URL.'}
    pid, basis, possible = _match(index, ids)
    source = {'origin': origin, 'identifiers': ids, 'fields': fields, 'original': original,
              'sha256': triage.canonical_sha(original)}
    if pid:
        record = load_record(root, pid)
        if any(row['sha256'] == source['sha256'] and row['identifiers'] == ids for row in record['source_records']):
            return {'outcome': 'DUPLICATE_RECORD', 'paper_id': pid, 'basis': basis, 'locator': origin['locator']}
        source['record_id'] = 'REC-%02d' % (len(record['source_records']) + 1)
        record['source_records'].append(source)
        for key, value in _identity(fields, ids).items():
            if record['identity'].get(key) in (None, '', []) and value not in (None, '', []):
                record['identity'][key] = value
        for other in possible:
            peer = load_record(root, other)
            for one, two in [(record, other), (peer, pid)]:
                if two not in one['possible_duplicate_of']:
                    one['possible_duplicate_of'].append(two)
            save_record(root, peer)
        save_record(root, record)
        _register(index, record)
        return {'outcome': 'MERGED_VERSION', 'paper_id': pid, 'basis': basis, 'locator': origin['locator'],
                'possible_duplicate_of': possible}
    pid = 'P%04d' % (len(corpus['paper_ids']) + 1)
    source['record_id'] = 'REC-01'
    record = triage.new_record(pid, _identity(fields, ids), source)
    if 'reading_policy' in corpus:
        record['reading_policy'] = corpus['reading_policy']
    record['possible_duplicate_of'] = list(possible)
    (Path(root)/'papers'/pid).mkdir(parents=True)
    save_record(root, record)
    for other in possible:
        peer = load_record(root, other)
        if pid not in peer['possible_duplicate_of']:
            peer['possible_duplicate_of'].append(pid)
            save_record(root, peer)
    corpus['paper_ids'].append(pid)
    _register(index, record)
    return {'outcome': 'NEW_PAPER', 'paper_id': pid, 'possible_duplicate_of': possible, 'locator': origin['locator']}


def import_records(root, file, fmt=None, sheet=None):
    root = Path(root).resolve()
    corpus = load_corpus(root)
    file = Path(file).resolve()
    fmt = (fmt or FORMATS.get(file.suffix.lower(), '')).upper()
    with resources.timed(root, 'IMPORT') as measured:
        rows = parse_records(file, fmt, sheet)
        import_id = 'I%02d' % (len(corpus['imports']) + 1)
        stored = 'records/%s-%s' % (import_id, re.sub(r'[^A-Za-z0-9_.-]+', '_', file.name))
        (root/'records').mkdir(exist_ok=True)
        shutil.copyfile(file, root/stored)
        index = _index(root, corpus)
        results = [_ingest(root, corpus, index, raw, {'import_id': import_id, 'file': stored, 'locator': locator})
                   for locator, raw in rows]
        count = lambda outcome: sum(1 for row in results if row['outcome'] == outcome)
        entry = {'import_id': import_id, 'file': stored, 'sha256': digest(root/stored), 'format': fmt,
                 'records': len(rows), 'new_papers': count('NEW_PAPER'), 'merged_versions': count('MERGED_VERSION'),
                 'duplicate_records': count('DUPLICATE_RECORD'), 'unusable_records': count('UNUSABLE'),
                 'possible_duplicates': sum(1 for row in results if row.get('possible_duplicate_of')),
                 'imported_at': triage.now()}
        corpus['imports'].append(entry)
        write(root/'corpus.json', corpus)
        measured.update(records=len(rows))
    return {**entry, 'results': results,
            'notice': 'Records sharing a DOI, arXiv ID or exact normalized title are kept as versions of one paper. '
                      'Possible duplicates with conflicting identifiers are flagged, not merged. Nothing was screened yet.'}


def add_record(root, fields, depth=None, instruction=None):
    root = Path(root).resolve()
    corpus = load_corpus(root)
    if depth and (depth not in triage.DEPTHS[1:] or not _text(instruction)):
        raise RunError('USER_INSTRUCTION_REQUIRED', 'A depth request needs depth L1, L2 or L3 and what the user actually asked.')
    index = _index(root, corpus)
    result = _ingest(root, corpus, index, fields, {'import_id': None, 'file': None,
                                                  'locator': 'manual entry %d' % (corpus.get('manual_records', 0) + 1)})
    if result['outcome'] == 'UNUSABLE':
        raise RunError('INVALID_ARGUMENT', 'Give at least a title, DOI, arXiv ID or URL.')
    corpus['manual_records'] = corpus.get('manual_records', 0) + 1
    write(root/'corpus.json', corpus)
    if depth:
        save_record(root, triage.request_depth(load_record(root, result['paper_id']), depth, instruction,
                                               workspace_ceiling(corpus)))
    return {**result, 'status': status(root, result['paper_id'])}


# ---------------------------------------------------------------- per-paper operations

def _protocol(corpus, decision):
    if (corpus['protocol']['mode'] == 'SYSTEMATIC_REVIEW' and isinstance(decision, dict)
            and decision.get('decision') == 'EXCLUDE_FOR_TARGET'
            and decision.get('exclusion_criterion') not in {c['id'] for c in corpus['protocol']['exclusion_criteria']}):
        raise RunError('EXCLUSION_CRITERION_REQUIRED', 'This workspace follows a review protocol: cite the stated exclusion criterion.')


def submit(root, payload, dry_run=False):
    root = Path(root).resolve()
    corpus = load_corpus(root)
    if not isinstance(payload, dict):
        raise RunError('INVALID_SCREENING_HANDOFF', 'A screening handoff is a JSON object; use handoff-template.')
    record = load_record(root, payload.get('paper_id'))
    _protocol(corpus, payload.get('decision'))
    ref = 'handoffs/%s.json' % triage.canonical_sha(payload)
    directory = paper_dir(root, record['paper_id'])
    updated = triage.apply_handoff(record, payload, corpus['research_target'], directory, ref,
                                   ceiling=workspace_ceiling(corpus), criteria=criteria_index(corpus))
    if dry_run:
        return {'valid': True, 'paper_id': record['paper_id'], 'depth': payload['depth'],
                'notice': 'Read-only shape, attribution and boundary validation; nothing was written and no reading was verified.'}
    write(directory/ref, payload)
    save_record(root, updated)
    return status(root, record['paper_id'])


def route(root, paper_id, decision):
    root = Path(root).resolve()
    corpus = load_corpus(root)
    _protocol(corpus, decision)
    save_record(root, triage.apply_decision(load_record(root, paper_id), decision, corpus['research_target'],
                                            criteria_index(corpus), workspace_ceiling(corpus)))
    return status(root, paper_id)


def reassess(root, payload, dry_run=False):
    """Record a new relevance judgement for the current target on existing coverage; no reading is claimed."""
    root = Path(root).resolve()
    corpus = load_corpus(root)
    if not isinstance(payload, dict):
        raise RunError('INVALID_REASSESSMENT', 'A reassessment is a JSON object; use reassess-template.')
    record = load_record(root, payload.get('paper_id'))
    _protocol(corpus, payload.get('decision'))
    updated = triage.apply_reassessment(record, payload, corpus['research_target'], criteria_index(corpus),
                                        workspace_ceiling(corpus))
    if dry_run:
        return {'valid': True, 'paper_id': record['paper_id'], 'notice': 'Read-only validation; nothing was written.'}
    write(paper_dir(root, record['paper_id'])/('handoffs/%s.json' % triage.canonical_sha(payload)), payload)
    save_record(root, updated)
    return status(root, record['paper_id'])


def request_depth(root, paper_id, depth, instruction):
    root = Path(root).resolve()
    corpus = load_corpus(root)
    save_record(root, triage.request_depth(load_record(root, paper_id), depth, instruction, workspace_ceiling(corpus)))
    return status(root, paper_id)


def recommend(root, paper_id, payload=None):
    """Rule recommendation for the recorded assessment, or for a pass that has not been submitted yet."""
    root = Path(root).resolve()
    corpus = load_corpus(root)
    record = load_record(root, paper_id)
    if payload is not None:
        # Preview: validate the pass in memory, without its decision, and say what the rules would propose.
        if not isinstance(payload, dict) or payload.get('paper_id') != paper_id:
            raise RunError('INVALID_SCREENING_HANDOFF', 'Preview a pass for the paper named with --paper.')
        record = triage.apply_handoff(record, payload, corpus['research_target'], paper_dir(root, paper_id), 'handoffs/preview.json',
                                      ceiling=workspace_ceiling(corpus), criteria=criteria_index(corpus), decide=False)
    assessment = triage.current_assessment(record, corpus['research_target'])
    if assessment is None:
        raise RunError('ASSESSMENT_REQUIRED', 'Record a relevance assessment for the current target and source version first.')
    result = triage.recommend(record, assessment, workspace_ceiling(corpus))
    if payload is not None:
        result['preview'] = 'Computed for the pass in the file; nothing was written. Submit the pass with its decision next.'
    return result


def _run_path(root, record):
    return (Path(root).resolve()/record['l3']['run_path']).resolve()


def paper_tier(root, record):
    """Evidence tier usable now. Only an accepted complete-reading run counts as verified."""
    depth = triage.effective_depth(record)
    result = {'tier': triage.TIER_BY_DEPTH[depth], 'effective_depth': depth, 'l3_state': 'NONE',
              'independent_review': 'NONE', 'review_mode': None, 'coverage_label': None}
    if not record.get('l3'):
        return result
    run = _run_path(root, record)
    if not (run/'paper_packet.json').is_file():
        result['l3_state'] = 'RUN_UNAVAILABLE'
        return result
    from reading_run_check import inspect_run
    import reading_run_control as control
    try:
        packet = read(run/'paper_packet.json')
        assessment = control.assess(run)
        errors = inspect_run(run)
    except (RunError, OSError, ValueError, TypeError, KeyError, AttributeError):
        result['l3_state'] = 'RUN_UNREADABLE'
        return result
    origin = packet.get('promotion')
    if isinstance(origin, dict) and origin.get('paper_id') != record['paper_id']:
        result['l3_state'] = 'RUN_OF_ANOTHER_PAPER'
        return result
    result.update(l3_state='IN_PROGRESS', review_mode=packet.get('review_mode'), independent_review='PENDING')
    reviews = packet.get('reviews') or []
    if reviews:
        result['last_review_decision'] = reviews[-1].get('decision')
    run_sha = (packet.get('sources') or [{}])[0].get('sha256')
    current = record['full_text'].get('current_sha256')
    if run_sha != record['l3'].get('source_sha256') or (current and current != run_sha):
        # The run reads other bytes than this record now names; its state says nothing about them.
        result.update(l3_state='OTHER_SOURCE_VERSION', independent_review='NONE')
        return result
    if assessment.get('terminal_decision') == 'ACCEPTED' and not errors:
        result.update(l3_state='ACCEPTED', coverage_label=assessment.get('coverage_label'),
                      paper_status=packet.get('paper_status'), independent_review='ACCEPTED',
                      tier='VERIFIED_COMPLETE' if packet.get('scope_mode') == 'COMPLETE_PAPER' else 'VERIFIED_USER_SCOPE')
    return result


def status(root, paper_id):
    root = Path(root).resolve()
    corpus = load_corpus(root)
    record = load_record(root, paper_id)
    target = corpus['research_target']
    criteria, ceiling = criteria_index(corpus), workspace_ceiling(corpus)
    decision, stale = triage.current_decision(record, target, criteria)
    return {'paper_id': paper_id, 'title': record['identity'].get('title'),
            'paper_type': record['identity']['paper_type'], **paper_tier(root, record),
            'user_requested_depth': record['depth'].get('user_requested'),
            'user_depth_ceiling': triage.depth_ceiling(record, ceiling),
            'standing_user_instructions': triage.standing_instructions(record, corpus['protocol'].get('depth_ceiling')),
            'reading_scope': record.get('reading_scope'),
            'target_dependent': {'focus_applicability': triage.focus_applicability(record, target),
                                 'local_claims': triage.local_claim_labels(record, target)},
            'routing': {'decision': (decision or {}).get('decision'), 'decided_by': (decision or {}).get('decided_by'),
                        'decision_id': (decision or {}).get('decision_id'), 'stale_reason': stale,
                        'target': triage.target_binding(target)},
            'coverage': triage.coverage_summary(record), 'uncertainty_flags': triage.uncertainty_flags(record),
            'open_conflicts': [c['conflict_id'] for c in triage.open_conflicts(record)],
            'possible_duplicate_of': record['possible_duplicate_of'], 'permitted_use': triage.permitted_use(record, target),
            'upgrade_history': record['upgrade_history'], 'next_action': triage.next_step(record, target, ceiling, criteria),
            'notice': 'Screening status describes what was examined. It is not a gate, a review or an acceptance.'}


def link_run(root, paper_id, run):
    """Attach an existing complete-reading run so its actual state can be reported next to screened papers."""
    root = Path(root).resolve()
    load_corpus(root)
    record = load_record(root, paper_id)
    corpus = load_corpus(root)
    from reading_scope import block_unbounded
    block_unbounded(record, 'Linking a complete-reading run')
    run = Path(run).resolve()
    if record.get('l3') or not (run/'paper_packet.json').is_file():
        raise RunError('INVALID_ARGUMENT', 'Link one existing run directory to a paper without a run.')
    packet = read(run/'paper_packet.json')
    run_sha = (packet.get('sources') or [{}])[0].get('sha256')
    for other in corpus['paper_ids']:
        linked = load_record(root, other).get('l3')
        if other != paper_id and linked and (Path(root)/linked['run_path']).resolve() == run:
            raise RunError('LINK_REFUSED', 'This run is already linked to ' + other + '; one run reads one paper.')
    origin = packet.get('promotion') or {}
    if origin and (origin.get('paper_id'), origin.get('corpus_id')) != (paper_id, corpus['corpus_id']):
        raise RunError('LINK_REFUSED', 'This run was promoted for another paper or workspace.')
    current = record['full_text'].get('current_sha256')
    if current and current != run_sha:
        raise RunError('LINK_REFUSED', 'The run reads a different source version than the one attached to this paper.')
    record['l3'] = {'run_path': _relative(root, run), 'run_id': packet.get('task_id'), 'linked_at': triage.now(),
                    'source_sha256': run_sha, 'origin': 'LINKED_EXISTING_RUN', 'extraction_reused': False,
                    # Without attached bytes the link rests on the owner's word that this run reads this paper.
                    'identity_binding': 'SOURCE_HASH_MATCH' if current else 'ASSERTED_BY_OWNER'}
    record['upgrade_history'].append({'from': triage.effective_depth(record), 'to': 'L3', 'at': record['l3']['linked_at'],
                                      'trigger': {'kind': 'LINKED_EXISTING_RUN', 'ref': record['l3']['run_id']},
                                      'source_sha256': record['l3']['source_sha256'], 'completion_inherited': False})
    save_record(root, record)
    return status(root, paper_id)


def _relative(root, path):
    try:
        return Path(os.path.relpath(path, root)).as_posix()
    except ValueError:  # another drive
        return str(path)


# ---------------------------------------------------------------- queue, counts and exports

def queue_priority(entry):
    """Sort key for the reading queue (smaller sorts first).

    Policy: finish what the user asked for, then what is already open, then by the next action.
    Within one action class, compare utility, topic and method ratings one after another; the
    dimensions are never summed into a score.
    """
    rank = lambda name: -(triage.RATINGS.index(entry['ratings'][name]) if entry['ratings'].get(name) in triage.RATINGS else -1)
    return (0 if entry['user_requested_pending'] else 1, ACTION_ORDER.index(entry['next_action']),
            rank('research_utility'), rank('topic_relevance'), rank('methodological_relevance'), entry['paper_id'])


def _row(root, corpus, pid):
    record = load_record(root, pid)
    target = corpus['research_target']
    criteria, ceiling = criteria_index(corpus), workspace_ceiling(corpus)
    decision, stale = triage.current_decision(record, target, criteria)
    assessment = triage.current_assessment(record, target)
    tier = paper_tier(root, record)
    labels = triage.local_claim_labels(record, target)
    reached = 'L3' if record.get('l3') else tier['effective_depth']
    floor = record['depth'].get('user_requested')
    return record, {'paper_id': pid, 'title': record['identity'].get('title'), 'year': record['identity'].get('year'),
                    'paper_type': record['identity']['paper_type'], **tier,
                    'decision': (decision or {}).get('decision'), 'decided_by': (decision or {}).get('decided_by'),
                    'stale_reason': stale, 'user_requested_depth': floor,
                    'user_requested_pending': bool(floor) and triage.DEPTHS.index(floor) > (triage.DEPTHS.index(reached) if reached else -1),
                    'ratings': {name: assessment['dimensions'][name]['rating'] for name in triage.DIMENSIONS} if assessment else {},
                    'evidence_levels': {name: assessment['dimensions'][name]['evidence_level'] for name in triage.DIMENSIONS} if assessment else {},
                    'uncertainty_level': assessment['uncertainty']['level'] if assessment else None,
                    'target_questions': sorted({x['question_id'] for x in assessment['target_links']}) if assessment else [],
                    'next_action': triage.next_step(record, target, ceiling, criteria)['kind'],
                    'user_depth_ceiling': triage.depth_ceiling(record, ceiling),
                    'local_claims': labels, 'exclusion_basis': (decision or {}).get('basis'),
                    'focus': (decision or {}).get('focus', []), 'open_conflicts': len(triage.open_conflicts(record)),
                    'uncertainty_flags': len(triage.uncertainty_flags(record)),
                    'coverage': triage.coverage_summary(record)}


def rows(root):
    root = Path(root).resolve()
    corpus = load_corpus(root)
    return corpus, [_row(root, corpus, pid) for pid in corpus['paper_ids']]


def queue(root):
    corpus, data = rows(root)
    entries = [row for _, row in data if row['next_action'] != 'NONE' and not (
        row['next_action'] == 'CONTINUE_L3_RUN' and row['l3_state'] == 'ACCEPTED')]
    entries.sort(key=queue_priority)
    closed = {}
    for _, row in data:
        if row['next_action'] == 'NONE':
            closed[row['decision']] = closed.get(row['decision'], 0) + 1
    return {'target': triage.target_binding(corpus['research_target']),
            'queue': [{k: row[k] for k in ['paper_id', 'title', 'next_action', 'tier', 'effective_depth', 'decision',
                                           'decided_by', 'user_requested_depth', 'stale_reason', 'focus', 'ratings']}
                      for row in entries],
            'not_queued': dict(sorted(closed.items())),
            'notice': 'Ordering is a routing aid from recorded ratings, compared one dimension at a time. '
                      'It is not a quality ranking of the papers.'}


def flow(root):
    """Screening counts in the spirit of a PRISMA flow; a full protocol is required only in SYSTEMATIC_REVIEW mode."""
    corpus, data = rows(root)
    count = lambda test: sum(1 for record, row in data if test(record, row))
    depth_at_least = lambda row, depth: row['effective_depth'] is not None and triage.DEPTHS.index(row['effective_depth']) >= triage.DEPTHS.index(depth)
    exclusions = {}
    for record, row in data:
        if row['decision'] == 'EXCLUDE_FOR_TARGET':
            decision, _ = triage.current_decision(record, corpus['research_target'], criteria_index(corpus))
            key = decision.get('exclusion_criterion') or decision['decided_by']
            exclusions[key] = exclusions.get(key, 0) + 1
    return {'protocol_mode': corpus['protocol']['mode'], 'target': triage.target_binding(corpus['research_target']),
            'records_identified': sum(i['records'] for i in corpus['imports']) + corpus.get('manual_records', 0),
            'records_unusable': sum(i['unusable_records'] for i in corpus['imports']),
            'records_merged_as_duplicates_or_versions': sum(i['merged_versions'] + i['duplicate_records'] for i in corpus['imports']),
            'papers': len(data),
            'possible_duplicates_flagged': count(lambda record, row: bool(record['possible_duplicate_of'])),
            'not_yet_screened': count(lambda record, row: row['effective_depth'] is None and row['l3_state'] == 'NONE'),
            'reached_L0_or_deeper': count(lambda record, row: depth_at_least(row, 'L0')),
            'excluded_for_target': count(lambda record, row: row['decision'] == 'EXCLUDE_FOR_TARGET'),
            'exclusions_by_criterion_or_decider': dict(sorted(exclusions.items())),
            'background_only': count(lambda record, row: row['decision'] == 'BACKGROUND_ONLY'),
            'deferred_for_evidence': count(lambda record, row: row['decision'] == 'DEFER_FOR_EVIDENCE'),
            'decisions_needing_reassessment': count(lambda record, row: row['stale_reason'] is not None),
            'full_text_attached': count(lambda record, row: bool(record['full_text'].get('current_sha256'))),
            'full_text_unavailable': count(lambda record, row: record['full_text']['access_state'] == 'UNAVAILABLE'),
            'reached_L1_or_deeper': count(lambda record, row: depth_at_least(row, 'L1')),
            'reached_L2': count(lambda record, row: depth_at_least(row, 'L2')),
            'passes_by_depth': {depth: count(lambda record, row, depth=depth: triage.latest_pass(record, depth) is not None)
                                for depth in triage.SCREENING_DEPTHS},
            'complete_reading_runs_opened': count(lambda record, row: row['l3_state'] != 'NONE'),
            'complete_reading_accepted': count(lambda record, row: row['tier'] in VERIFIED_TIERS),
            'notice': 'Counts are derived from current records. Exclusions and relevance apply to the bound target only.'}


def evidence_tiers(root):
    """Stage-09 input: what each paper can support, by actual state rather than by label."""
    corpus, data = rows(root)
    counts = {tier: 0 for tier in TIERS}
    papers = []
    for record, row in data:
        counts[row['tier']] += 1
        papers.append({'paper_id': row['paper_id'], 'title': row['title'], 'tier': row['tier'], 'l3_state': row['l3_state'],
                       'effective_depth': row['effective_depth'], 'independent_review': row['independent_review'],
                       'review_mode': row['review_mode'], 'coverage_label': row['coverage_label'],
                       'decision': row['decision'], 'run_path': (record.get('l3') or {}).get('run_path'),
                       'decision_stale': row['stale_reason'], 'source_sha256': record['full_text'].get('current_sha256'),
                       'local_claims': [] if row['tier'] in VERIFIED_TIERS else row['local_claims'],
                       'permitted_use': 'ACCEPTED_CLAIMS_WITHIN_ALLOWED_USE' if row['tier'] in VERIFIED_TIERS
                       else triage.permitted_use(record, corpus['research_target'])})
    return {'target': triage.target_binding(corpus['research_target']), 'counts_by_tier': counts, 'papers': papers,
            'notice': 'Only VERIFIED tiers come from an accepted complete-reading run. TARGETED_READ, SKIMMED and '
                      'METADATA_SCREENED material may appear as labelled background or candidate comparison, never as accepted evidence.'}


def check_synthesis(root, claims):
    """Reject synthesis claims that present shallow reading as accepted evidence."""
    root = Path(root).resolve()
    corpus, data = rows(root)
    by_id = {row['paper_id']: (record, row) for record, row in data}
    if not isinstance(claims, list) or any(not isinstance(c, dict) for c in claims):
        raise RunError('INVALID_ARGUMENT', 'Synthesis claims are an array of objects.')
    errors, summary = [], []

    def error(code, cid, action):
        errors.append({'code': code, 'item': cid, 'next_action': action})

    for claim in claims:
        cid = claim.get('synthesis_claim_id')
        basis, strength, support = claim.get('evidence_basis'), claim.get('strength'), claim.get('support')
        if (not _text(cid) or not _text(claim.get('text')) or basis not in {'ACCEPTED', 'SCREENING_LIMITED', 'SCOPED_L2'}
                or strength not in {'CONCLUSION', 'CANDIDATE', 'BACKGROUND'}
                or not isinstance(support, list) or not support or any(not isinstance(s, dict) for s in support)):
            error('SYNTHESIS_CLAIM_INVALID', cid, 'Give an ID, text, evidence_basis, strength and at least one support entry.')
            continue
        tiers, scoped = [], []
        for entry in support:
            pid = entry.get('paper_id')
            if pid not in by_id:
                error('SYNTHESIS_SUPPORT_UNKNOWN', cid, f'{pid} is not a paper in this workspace.')
                continue
            record, row = by_id[pid]
            tiers.append(row['tier'])
            verified = row['tier'] in VERIFIED_TIERS
            if basis == 'SCOPED_L2':
                from reading_scoped_use import validate
                binding, status, defect = validate(paper_dir(root, pid), record, corpus['research_target'], claim, entry)
                scoped.append({'paper_id': pid, 'local_claim_id': entry.get('local_claim_id'), 'binding_sha256': binding,
                               'review_status': status, 'complete_paper_verified_by_this_check': False})
                if defect:
                    error('SCOPED_USE_INCOMPLETE', cid, defect)
                continue
            if basis == 'ACCEPTED':
                if not verified:
                    error('SHALLOW_EVIDENCE_MISLABELED', cid, f"{pid} is {row['tier']}: it has no accepted complete reading. "
                          'Use evidence_basis SCREENING_LIMITED with a stated limitation, or complete and review the paper.')
                    continue
                packet = read(_run_path(root, record)/'paper_packet.json')
                found = next((c for c in packet.get('claims', []) if c.get('claim_id') == entry.get('claim_id')), None)
                if found is None:
                    error('SYNTHESIS_SUPPORT_UNKNOWN', cid, f'{pid}: cite a claim_id from the accepted packet.')
                elif found.get('allowed_use') == 'HOLD':
                    error('HOLD_CLAIM_USED', cid, f"{pid}/{found['claim_id']} is on HOLD and cannot support a synthesis claim.")
                elif found.get('allowed_use') == 'CONDITIONAL' and entry.get('conditions_acknowledged') is not True:
                    error('CONDITIONS_NOT_CARRIED', cid, f"{pid}/{found['claim_id']} is CONDITIONAL: carry its conditions into the synthesis.")
            else:
                local = {label['claim_id']: label for label in row['local_claims']}
                ref = entry.get('local_claim_id')
                if ref is not None and ref not in local and not verified:
                    error('SYNTHESIS_SUPPORT_UNKNOWN', cid, f'{pid}: unknown local claim {ref}.')
                elif ref in local and local[ref]['target_applicability'] != 'CURRENT' and strength != 'BACKGROUND':
                    error('TARGET_APPLICABILITY_STALE', cid, f"{pid}/{ref} was read for another research target "
                          f"({local[ref]['target_applicability']}). What the source says stays usable as background; "
                          'its use as a candidate for this target needs a reassessment first.')
                elif ref in local and local[ref]['evidence_state'] in {'CONTRADICTED', 'UNDETERMINED'} and strength != 'BACKGROUND':
                    error('HOLD_CLAIM_USED', cid, f'{pid}/{ref} is {local[ref]["evidence_state"]} within its examined scope; '
                          'it can be mentioned as background with that status, not used as a candidate finding.')
                if strength != 'CANDIDATE' or verified:
                    continue  # CONCLUSION is refused once below; BACKGROUND needs no local claim
                if row['tier'] != 'TARGETED_READ':
                    error('SCREENING_EVIDENCE_OVERSTATED', cid, f"{pid} is {row['tier']}: skim and metadata material supports "
                          'background mention only. A candidate needs a local claim from targeted reading.')
                elif ref not in local:
                    error('SCREENING_EVIDENCE_OVERSTATED', cid, f'{pid}: a candidate cites the supported or limited local claim it rests on.')
        if basis == 'SCREENING_LIMITED':
            if strength == 'CONCLUSION':
                error('SCREENING_EVIDENCE_OVERSTATED', cid, 'Screening-level material cannot carry a conclusion, ranking or mean; '
                      'label it CANDIDATE or BACKGROUND.')
            if not _text(claim.get('limitation')):
                error('SYNTHESIS_LIMITATION_MISSING', cid, 'State the limitation: which depth was reached and what was not examined or reviewed.')
        summary.append({'synthesis_claim_id': cid, 'evidence_basis': basis, 'strength': strength, 'support_tiers': tiers, **({'scoped_uses': scoped} if scoped else {})})
    return {'valid': not errors, 'errors': errors, 'claims': summary,
            'counts_by_tier': evidence_tiers(root)['counts_by_tier'],
            'notice': 'Structural use check only. No paper or new synthesis inference is accepted by this command.'}


def export(root, kind):
    root = Path(root).resolve()
    corpus, data = rows(root)
    out = root/'exports'
    out.mkdir(exist_ok=True)
    if kind == 'log':
        entries = []
        for record, row in data:
            for decision in record['decisions']:
                entries.append({'recorded_at': decision['recorded_at'], 'paper_id': row['paper_id'], 'title': row['title'],
                                **{k: decision.get(k) for k in ['decision_id', 'decision', 'decided_by', 'depth_at_decision',
                                                               'rule_recommendation', 'assessment_id', 'exclusion_criterion',
                                                               'user_instruction']},
                                'target_id': (decision.get('target') or {}).get('target_id'),
                                'target_revision': (decision.get('target') or {}).get('revision'),
                                'basis': decision.get('basis', 'RATINGS'),
                                'current': triage.decision_current(record, decision, corpus['research_target'], criteria_index(corpus)),
                                'reasons': decision['reasons'], 'source_refs': decision['source_refs'],
                                'independent_review': False})
        entries.sort(key=lambda entry: (entry['recorded_at'], entry['paper_id'], entry['decision_id']))
        write(out/'screening_log.json', entries)
        _csv(out/'screening_log.csv', entries)
        return {'kind': 'log', 'files': ['exports/screening_log.json', 'exports/screening_log.csv'], 'decisions': len(entries),
                'notice': 'Every recorded routing decision, including superseded ones. These are triage decisions, not reviews.'}
    if kind == 'matrix':
        table = []
        for record, row in data:
            coverage = row['coverage']
            line = {'paper_id': row['paper_id'], 'title': row['title'], 'year': row['year'], 'paper_type': row['paper_type'],
                    'evidence_tier': row['tier'], 'screening_depth': row['effective_depth'], 'l3_state': row['l3_state'],
                    'independent_review': row['independent_review'], 'decision': row['decision'], 'decided_by': row['decided_by'],
                    'decision_stale': row['stale_reason']}
            for name in triage.DIMENSIONS:
                line[name] = ('%s (%s)' % (row['ratings'][name], row['evidence_levels'][name])) if row['ratings'] else None
            line.update(uncertainty=row['uncertainty_level'], target_questions=row['target_questions'],
                        examined_items=coverage['examined_item_count'],
                        pages_with_examined_items=len(coverage['pages_with_examined_items']), page_count=coverage['page_count'],
                        open_conflicts=row['open_conflicts'], uncertainty_flags=row['uncertainty_flags'],
                        user_depth_ceiling=row['user_depth_ceiling'],
                        local_claims_usable_for_target=sum(1 for c in row['local_claims'] if c['use'] == 'CANDIDATE_COMPARISON'),
                        local_claims_needing_reassessment=sum(1 for c in row['local_claims'] if c['use'] == 'REASSESS_FOR_TARGET'))
            table.append(line)
        write(out/'comparison_matrix.json', table)
        _csv(out/'comparison_matrix.csv', table)
        (out/'comparison_matrix.md').write_text(_markdown(table), encoding='utf8')
        return {'kind': 'matrix', 'files': ['exports/comparison_matrix.json', 'exports/comparison_matrix.csv',
                                            'exports/comparison_matrix.md'], 'papers': len(table),
                'notice': 'Each row carries its evidence tier. Ratings are separate ordinal judgements with their evidence level; '
                          'no total is computed.'}
    if kind == 'tiers':
        result = evidence_tiers(root)
        write(out/'09_evidence_tiers.json', result)
        return {'kind': 'tiers', 'files': ['exports/09_evidence_tiers.json'], 'counts_by_tier': result['counts_by_tier'],
                'notice': result['notice']}
    raise RunError('INVALID_ARGUMENT', 'Export kind is log, matrix or tiers.')


def _cell(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return '' if value is None else str(value)


def _csv(path, table):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        if table:
            writer = csv.DictWriter(stream, fieldnames=list(table[0]))
            writer.writeheader()
            writer.writerows({key: _cell(value) for key, value in line.items()} for line in table)


def _markdown(table):
    lines = ['# Screening comparison matrix', '',
             'Rows state the evidence tier actually reached. Ratings are routing judgements for the bound research target, '
             'not verified findings; only a VERIFIED tier comes from an accepted complete reading.', '']
    if table:
        keys = list(table[0])
        lines += ['| ' + ' | '.join(keys) + ' |', '|' + '---|' * len(keys)]
        lines += ['| ' + ' | '.join(_cell(line[key]).replace('|', '\\|').replace('\n', ' ') for key in keys) + ' |' for line in table]
    return '\n'.join(lines) + '\n'
