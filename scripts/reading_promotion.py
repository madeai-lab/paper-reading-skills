"""Full text for screening records, and the explicit upgrade into a complete-reading run.

Reuse is limited to what is deterministic and bound to the same source bytes: the file, its native
extraction and rendered crops. Earlier notes travel as leads. No read state, gate or review is inherited.
"""
import copy
from pathlib import Path
import shutil

from reading_run_records import RunError, read, write, digest
import reading_corpus as store
import reading_resources as resources
import reading_triage as triage
import reading_scope as scope

SOURCE_ID = 'SRC-01'
SNAPSHOT_SUFFIXES = {'.txt', '.md', '.html', '.htm'}
LEADS = 'handoffs/screening'
NOT_INHERITED = ['unit inventory and read states', 'G0, G1, G2 and G3', 'independent review and its coverage',
                 'claim registry (local claims are leads)', 'scope exclusions', 'report and readability records']


def acquisition_packet(sha):
    """The source descriptor a new run receives, so extracted pages stay byte-compatible with that run."""
    from reading_run_control import REVISION
    return {'skill_revision': REVISION, 'units': [],
            'content_acquisition': {'method': 'PDFPLUMBER_NATIVE', 'manifest_ref': 'source_elements/manifest.json'},
            'sources': [{'source_id': SOURCE_ID, 'source_kind': 'PDF', 'local_path': 'source.pdf', 'sha256': sha,
                         'page_count': None, 'access_state': 'AVAILABLE', 'required_for_scope': True,
                         'supplement_of': None}]}


def _current(record, pdf=True):
    sha = record['full_text'].get('current_sha256')
    version = next((v for v in record['full_text']['versions'] if v['sha256'] == sha), None)
    if version is None:
        raise RunError('FULL_TEXT_REQUIRED', 'Attach the full text first (attach-source).')
    if pdf and version['kind'] != 'PDF':
        raise RunError('FULL_TEXT_REQUIRED', 'Native extraction and complete reading need the PDF; a text snapshot is a '
                       'different source version. Attach the PDF and re-examine it.')
    return version


def attach_source(root, paper_id, source):
    root = Path(root).resolve()
    store.load_corpus(root)
    record = store.load_record(root, paper_id)
    directory = store.paper_dir(root, paper_id)
    source = Path(source).resolve()
    with source.open('rb') as stream:
        header = stream.read(5)
    if header == b'%PDF-':
        kind, name = 'PDF', 'source.pdf'
    elif source.suffix.lower() in SNAPSHOT_SUFFIXES:
        kind, name = 'TEXT_SNAPSHOT', 'source' + source.suffix.lower()
    else:
        raise RunError('INVALID_SOURCE', 'Attach a PDF, or a saved text/HTML snapshot of the paper.')
    sha = digest(source)
    full = record['full_text']
    previous = full.get('current_sha256')
    if sha == previous:
        return {'attached': False, 'sha256': sha, 'reason': 'This exact version is already attached; nothing was repeated.'}
    version = next((v for v in full['versions'] if v['sha256'] == sha), None)
    if version is None:
        relative = 'versions/' + sha[:16]
        (directory/relative).mkdir(parents=True)
        shutil.copyfile(source, directory/relative/name)
        version = {'sha256': sha, 'kind': kind, 'directory': relative, 'local_path': relative + '/' + name,
                   'attached_at': triage.now(), 'extraction': {'state': 'NONE'}}
        full['versions'].append(version)
    stale = []
    if previous:
        # Notes were taken on other bytes: keep them as history, stop counting them as coverage.
        for row in record['passes']:
            if row['status'] == 'CURRENT' and row.get('source_sha256') == previous:
                row['status'] = 'STALE_SOURCE_VERSION'
                stale.append(row['pass_id'])
        full.setdefault('version_events', []).append({'at': triage.now(), 'from': previous, 'to': sha,
                                                      'stale_pass_ids': stale})
    full.update(current_sha256=sha, access_state='AVAILABLE', missing_reason=None)
    store.save_record(root, record)
    return {'attached': True, 'sha256': sha, 'kind': kind, 'previous_sha256': previous, 'stale_pass_ids': stale,
            'effective_depth': triage.effective_depth(record),
            'notice': 'Source bytes are frozen by hash. Coverage, assessments and decisions made on another version '
                      'are kept as history and no longer count for this one.' if previous else
                      'Source bytes are frozen by hash. Attaching a file reads nothing.'}


def mark_unavailable(root, paper_id, reason, attempts):
    root = Path(root).resolve()
    store.load_corpus(root)
    record = store.load_record(root, paper_id)
    if (record['full_text'].get('current_sha256') or not isinstance(reason, str) or not reason.strip()
            or not isinstance(attempts, list) or not attempts or any(not isinstance(a, str) or not a.strip() for a in attempts)):
        raise RunError('INVALID_ARGUMENT', 'Record an actual reason and the lawful access attempts for a paper without attached full text.')
    record['full_text'].update(access_state='UNAVAILABLE', missing_reason=reason.strip(), attempts=list(attempts))
    store.save_record(root, record)
    return store.status(root, paper_id)


def _workspace(root, paper_id):
    root = Path(root).resolve()
    store.load_corpus(root)
    record = store.load_record(root, paper_id)
    version = _current(record)
    return root, record, version, store.paper_dir(root, paper_id)/version['directory']


def extract(root, paper_id, parser=None):
    """Extract native elements once per source version; a second request reuses the frozen pages."""
    from reading_element_contracts import validate_acquisition
    from reading_pdf_elements import extract_elements
    root, record, version, directory = _workspace(root, paper_id)
    sha = version['sha256']
    packet = acquisition_packet(sha)
    if (directory/'source_elements').exists():
        state = validate_acquisition(directory, packet)
        resources.record(root, 'EXTRACTION_REUSED', paper_id, source_sha256=sha, stage='SCREENING')
        result = {'extracted': False, 'reused': True, 'page_count': len(state['pages'])}
    else:
        with resources.timed(root, 'PDF_EXTRACTION', paper_id, source_sha256=sha) as measured:
            outcome = extract_elements(directory, parser=parser, packet=packet)
            measured.update(page_count=outcome['page_count'])
        result = {'extracted': True, 'reused': False, 'page_count': outcome['page_count']}
    if version['extraction'].get('state') != 'EXTRACTED':
        manifest = directory/'source_elements'/'manifest.json'
        version['extraction'] = {'state': 'EXTRACTED', 'page_count': result['page_count'],
                                 'manifest_sha256': digest(manifest), 'parser': read(manifest)['parser'],
                                 'extracted_at': triage.now()}
        store.save_record(root, record)
    return {**result, 'paper_id': paper_id, 'source_sha256': sha, 'ocr_used': False, 'reading_state_changed': False,
            'notice': 'Extraction is navigation and evidence binding, not reading. The same pages are reused if this '
                      'paper is promoted with the same source bytes.'}


def _extracted(version):
    if version['extraction'].get('state') != 'EXTRACTED':
        raise RunError('EXTRACTION_REQUIRED', 'Run extract for this paper first; it needs a provisioned pdfplumber interpreter.')


def outline(root, paper_id):
    from reading_outline import run_outline, outline_text
    root, record, version, directory = _workspace(root, paper_id)
    scope.block_unbounded(record, 'outline')
    _extracted(version)
    with resources.timed(root, 'OUTLINE', paper_id, source_sha256=version['sha256']):
        result, _, _ = run_outline(directory, SOURCE_ID, None, packet=acquisition_packet(version['sha256']))
    return outline_text(result)


def read_pages(root, paper_id, pages, view='text', bbox=None, max_chars=18000):
    from reading_pdf_elements import read_elements
    root, record, version, directory = _workspace(root, paper_id)
    if record.get('reading_scope'):
        for page in pages or []:
            scope.regions_for(record, page, bbox)
        if bbox is not None and view != 'text':
            scope.block_unbounded(record, 'Overlapping objects in detail/locator views')
    _extracted(version)
    with resources.timed(root, 'PAGE_READ', paper_id, source_sha256=version['sha256'], pages=list(pages or []),
                         view=view, bbox=list(bbox) if bbox else None):
        try:
            return read_elements(directory, pages, bbox, max_chars, SOURCE_ID, view=view,
                                 packet=acquisition_packet(version['sha256']), contained_words=bool(record.get('reading_scope')))
        except ValueError as exc:
            if getattr(exc, 'code', None) == 'ELEMENT_READ_LIMIT':
                # The shared helper points to run-only commands; say what works in a screening workspace.
                raise RunError('ELEMENT_READ_LIMIT', 'The selection does not fit this read: either the pages are not 1-4 distinct '
                               'existing pages, or their text is longer than --max-chars (default and maximum 18000; a smaller '
                               'value is not a way to get an excerpt). Request fewer pages, or a region with --bbox x0 top x1 '
                               'bottom.') from exc
            raise


def find_text(root, paper_id, terms, limit=40):
    """Locate terms in the extracted text without reading whole pages. Navigation only: a hit is not reading."""
    root, record, version, directory = _workspace(root, paper_id)
    scope.block_unbounded(record, 'find-text')
    _extracted(version)
    if not isinstance(terms, list) or not terms or any(not isinstance(t, str) or not t.strip() for t in terms):
        raise RunError('INVALID_ARGUMENT', 'Give one or more search terms with --terms.')
    hits, pages_with_hits, counts = [], set(), {term: 0 for term in terms}
    with resources.timed(root, 'TEXT_SEARCH', paper_id, source_sha256=version['sha256'], terms=list(terms)):
        for path in sorted((directory/'source_elements').glob('page-*.json')):
            page = read(path)
            text = ' '.join(page['text'].split())
            folded = text.casefold()
            for term in terms:
                start = folded.find(term.casefold())
                while start != -1:
                    counts[term] += 1
                    pages_with_hits.add(page['page'])
                    if len(hits) < limit:
                        hits.append({'page': page['page'], 'term': term,
                                     'snippet': text[max(0, start - 70):start + len(term) + 70]})
                    start = folded.find(term.casefold(), start + len(term))
    return {'paper_id': paper_id, 'source_sha256': version['sha256'], 'counts': counts, 'pages_with_hits': sorted(pages_with_hits),
            'hits': hits, 'truncated': sum(counts.values()) > len(hits), 'purpose': 'NAVIGATION_ONLY',
            'notice': 'Search locates passages in the extracted text; glyph conflicts and two-column order can hide a match. '
                      'A snippet, or the absence of a hit, is not a reading of the paper.'}


def crop(root, paper_id, page, bbox, name, scale=2.0):
    from reading_crop import render_crop
    root, record, version, directory = _workspace(root, paper_id)
    scope.regions_for(record, page, bbox)
    _extracted(version)
    with resources.timed(root, 'CROP', paper_id, source_sha256=version['sha256'], pages=[page]):
        result = render_crop(directory, SOURCE_ID, page, bbox, Path('evidence')/Path(name).name, scale=scale,
                             packet=acquisition_packet(version['sha256']))
    result['paper_relative_path'] = version['directory'] + '/' + result['path']
    receipts = directory/'evidence'/'receipts.json'
    saved = read(receipts, {})
    saved[Path(result['path']).name] = {key: result[key] for key in ['source_sha256', 'physical_page', 'bbox', 'scale',
                                                                     'pixel_size', 'image_sha256', 'page_ref']}
    write(receipts, saved)
    result['notice'] = 'A render receipt binds the crop to the source. Open the image before recording actually_viewed.'
    return result


def claim_leads(record):
    """Local claims and card statements as a checklist for the complete-reading Owner: what was said, and where to look.

    Every row is TO_VERIFY. A lead becomes a claim only after the Owner confirms it against the source in the
    run and registers it with that run's units; a lead may also turn out wrong.
    """
    items = triage.examined_items(record)

    def scope(refs):
        return [{'item_id': ref, 'kind': items[ref]['kind'], 'label': items[ref]['label'], 'locator': items[ref].get('locator'),
                 'read_level': items[ref]['read_level']} for ref in refs if ref in items]

    rows = []
    targeted = (triage.latest_pass(record, 'L2') or {}).get('targeted') or {}
    for claim in targeted.get('local_claims', []):
        rows.append({'lead_id': 'LEAD-' + claim['claim_id'], 'from': 'L2 local claim', 'text': claim['text'],
                     'attribution_at_screening': claim['attribution'], 'evidence_state_at_screening': claim['evidence_state'],
                     'where_to_check': scope(claim['supporting_items'] + claim['conflicting_items']),
                     'conditions': claim['conditions'], 'limits': claim['limits'], 'missing_evidence': claim['missing_evidence'],
                     'status': 'TO_VERIFY'})
    card = (triage.latest_pass(record, 'L1') or {}).get('card') or {}
    for key, value in card.items():
        for number, row in enumerate(value if isinstance(value, list) else [value], 1):
            rows.append({'lead_id': 'LEAD-CARD-%s-%d' % (key, number), 'from': 'L1 card: ' + key, 'text': row['text'],
                         'attribution_at_screening': row['attribution'], 'evidence_state_at_screening': 'NOT_VERIFIED',
                         'where_to_check': scope(row['from_items']), 'conditions': [], 'limits': '', 'missing_evidence': [],
                         'status': 'TO_VERIFY'})
    for conflict in triage.open_conflicts(record):
        rows.append({'lead_id': 'LEAD-CONFLICT-' + conflict['conflict_id'], 'from': 'open conflict', 'text': conflict['description'],
                     'attribution_at_screening': 'ANALYST_INFERENCE', 'evidence_state_at_screening': 'OPEN',
                     'where_to_check': scope(conflict['items']), 'conditions': [], 'limits': '', 'missing_evidence': [],
                     'status': 'TO_VERIFY'})
    return rows


def _locator(item):
    if 'locator' not in item:
        return item.get('source_ref') or ''
    locator = item['locator']
    parts = [('p' + ','.join(map(str, item.get('pages', [])))) if item.get('pages') else '',
             locator.get('section') or '', locator.get('object_label') or '']
    return ' · '.join(part for part in parts if part)


def render_leads(record, crops):
    current = triage.current_passes(record)
    items = triage.examined_items(record)
    title = record['identity'].get('title') or record['paper_id']
    sha = record['full_text'].get('current_sha256') or 'no full text'
    lines = [f'# Screening leads: {title} ({record["paper_id"]})', '',
             'These notes were taken below complete reading, in a screening workspace. In this run they are leads only: '
             'none of them is a read state, a checked unit, a registered claim, a gate decision or a review. '
             'Inventory the source and read every unit here; cite evidence from this run.', '',
             f'Source version: `{sha}`. Screening depth reached: {triage.effective_depth(record) or "none"}.', '',
             '## Examined at screening depth', '']
    lines += [f"- `{uid}` · {item['kind']} · {item['label']} · {_locator(item)} · {item['read_level']}"
              + (f" — {item['note']}" if item.get('note') else '') for uid, item in items.items()] or ['- Nothing.']
    lines += ['', '## Not examined at screening depth', '']
    lines += [f"- {row['label']}: {row['reason']}" for row in triage.not_examined(record)] or ['- Not recorded.']
    card = (triage.latest_pass(record, 'L1') or {}).get('card')
    if card:
        lines += ['', '## Skim statements (NOT_VERIFIED)', '']
        for key, value in card.items():
            for row in value if isinstance(value, list) else [value]:
                lines.append(f"- {key} · {row['attribution']} · from {', '.join(row['from_items'])}: {row['text']}")
    targeted = (triage.latest_pass(record, 'L2') or {}).get('targeted')
    if targeted:
        lines += ['', '## Local claims from targeted reading (writer only, never reviewed)', '']
        lines += [f"- `{c['claim_id']}` · {c['attribution']} · {c['evidence_state']} within examined scope · "
                  f"items {', '.join(c['supporting_items'] + c['conflicting_items']) or 'none'}: {c['text']}"
                  for c in targeted['local_claims']]
        lines += ['', 'Scope of that pass: ' + targeted['scope_statement']]
    rows = claim_leads(record)
    if rows:
        lines += ['', '## Leads to verify (`claim_leads.json`)', '',
                  'Each lead names where to look. Confirm it against the source in this run, correct it or reject it, and '
                  'register what survives as a claim with this run\'s unit IDs. A lead is never evidence, and some will be wrong: '
                  'note the ones you reject.', '']
        for row in rows:
            where = '; '.join('%s %s (%s)' % (w['label'], w['locator'] or '', w['read_level']) for w in row['where_to_check'])
            lines.append(f"- `{row['lead_id']}` · {row['attribution_at_screening']} · {row['evidence_state_at_screening']} · "
                         f"check: {where or 'no examined item'}")
    conflicts = triage.open_conflicts(record)
    if conflicts:
        lines += ['', '## Open conflicts to resolve from the source', '']
        lines += [f"- `{c['conflict_id']}` ({', '.join(c['items'])}): {c['description']}" for c in conflicts]
    flags = triage.uncertainty_flags(record)
    if flags:
        lines += ['', '## Uncertainty flags', ''] + [f"- {f['code']}: {f['detail']}" for f in flags]
    if crops:
        lines += ['', '## Crops rendered from the same source bytes', '',
                  'Reusable image files. Where page and box are given, compare them with your unit before rendering again; '
                  'viewing the image in this run is still required before any visual record.', '']
        lines += [f"- `{c['path']}`" + (f" · page {c['physical_page']} · bbox {c['bbox']} · scale {c['scale']}"
                                        if c.get('bbox') else ' · no render receipt: page and box unknown')
                  for c in crops]
    other = [row for row in record['passes'] if row['status'] == 'STALE_SOURCE_VERSION']
    if other:
        lines += ['', '## Notes taken on another source version (VERSION_DIFFERENCE)', '',
                  'Do not merge these with the current version.', '']
        lines += [f"- pass {row['pass_id']} on `{row['source_sha256']}`: {len(row['examined'])} examined items" for row in other]
    return '\n'.join(lines) + '\n'


def promote(root, paper_id, run, owner, language='en', review_mode='KEY_CLAIMS', source=None):
    """Open a complete-reading run for a screened paper. Review mode is chosen independently of reading depth."""
    import reading_run_control as control
    root = Path(root).resolve()
    corpus = store.load_corpus(root)
    target = corpus['research_target']
    run = Path(run).resolve()
    if run.exists():
        raise RunError('RUN_EXISTS', 'Choose a new output directory; existing runs are never overwritten.')
    # Authorization comes first, so a refused promotion changes nothing.
    ceiling = store.workspace_ceiling(corpus)
    record = store.load_record(root, paper_id)
    scope.block_unbounded(record, 'Complete-paper promotion')
    triage.upgrade_trigger(record, 'L3', target, ceiling)
    if source is not None:
        attach_source(root, paper_id, source)
    record = store.load_record(root, paper_id)
    previous = record.get('l3')
    if previous and previous.get('source_sha256') == record['full_text'].get('current_sha256'):
        raise RunError('ALREADY_PROMOTED', 'This paper already has a complete-reading run for this source version: '
                       + previous['run_path'])
    trigger = triage.upgrade_trigger(record, 'L3', target, ceiling)
    version = _current(record)
    directory = store.paper_dir(root, paper_id)/version['directory']
    sha = version['sha256']
    depth = triage.effective_depth(record)
    snapshot = copy.deepcopy(record)
    control.initialize(run, directory/'source.pdf', owner, language, copy.deepcopy(target), review_mode)
    try:
        return _open_run(root, corpus, record, snapshot, version, directory, run, trigger, depth, review_mode, previous)
    except BaseException:
        # Nothing was read in a run created a moment ago; do not leave it half linked.
        shutil.rmtree(run, ignore_errors=True)
        raise


def _open_run(root, corpus, record, snapshot, version, directory, run, trigger, depth, review_mode, previous):
    import reading_run_control as control
    from reading_element_contracts import validate_acquisition
    paper_id, target, sha = record['paper_id'], corpus['research_target'], version['sha256']
    packet, state = read(run/'paper_packet.json'), read(run/'execution_state.json')
    reused, note = False, 'No native extraction existed for this source version.'
    if version['extraction'].get('state') == 'EXTRACTED':
        try:
            # One validation, in the new run: it hashes every adopted page against the manifest.
            shutil.copytree(directory/'source_elements', run/'source_elements')
            validate_acquisition(run, packet)
            reused, note = True, 'Adopted the frozen native pages of the same source bytes; extraction was not repeated.'
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            shutil.rmtree(run/'source_elements', ignore_errors=True)
            note = 'Extraction was not reused and must run again in the new run: ' + str(exc)
    crops = []
    if (directory/'evidence').is_dir():
        for path in sorted((directory/'evidence').rglob('*.png')):
            destination = run/'evidence'/'screening'/path.relative_to(directory/'evidence')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            receipt = read(directory/'evidence'/'receipts.json', {}).get(path.name, {})
            known = receipt.get('image_sha256') == digest(destination) and receipt.get('source_sha256') == sha
            crops.append({'path': destination.relative_to(run).as_posix(), 'sha256': digest(destination),
                          # Page and box let the Owner match the crop to a unit instead of rendering it again.
                          'physical_page': receipt.get('physical_page') if known else None,
                          'bbox': receipt.get('bbox') if known else None, 'scale': receipt.get('scale') if known else None})
    leads = run/LEADS
    write(leads/'screening_record.json', snapshot)
    write(leads/'claim_leads.json', claim_leads(snapshot))
    (leads/'leads.md').write_text(render_leads(snapshot, crops), encoding='utf8')
    promoted_at = triage.now()
    write(leads/'promotion.json', {
        'promotion_schema_version': 1, 'corpus_id': corpus['corpus_id'], 'paper_id': paper_id, 'promoted_at': promoted_at,
        'from_depth': depth, 'to_depth': 'L3', 'trigger': trigger, 'target': triage.target_binding(target),
        'review_mode': review_mode,
        'source': {'sha256': sha, 'same_bytes_as_screening_source': True},
        # The basis of the upgrade is this snapshot: the decision or user request it holds, on this source version.
        'screening_record_sha256': digest(leads/'screening_record.json'), 'leads_sha256': digest(leads/'leads.md'),
        'reused': {'source_bytes': True, 'native_extraction': reused, 'native_extraction_note': note,
                   'rendered_crops': crops, 'leads': LEADS + '/leads.md', 'screening_record': LEADS + '/screening_record.json',
                   'claim_leads': LEADS + '/claim_leads.json', 'claim_lead_count': len(claim_leads(snapshot)),
                   'screening_pass_ids': [row['pass_id'] for row in triage.current_passes(snapshot)]},
        'not_inherited': NOT_INHERITED,
        'notice': 'Screening notes are leads. This run must meet COMPLETE_PAPER coverage and G0-G3 from the beginning; '
                  'the reviewer scope chosen here is independent of the depth the paper came from.'})
    link = {'schema_version': 1, 'corpus_id': corpus['corpus_id'], 'paper_id': paper_id, 'from_depth': depth,
            'trigger': trigger, 'promotion_ref': LEADS + '/promotion.json',
            'promotion_sha256': digest(leads/'promotion.json'), 'source_sha256': sha, 'extraction_reused': reused}
    packet['promotion'] = link
    task = read(run/'task.json')
    task['promotion'] = copy.deepcopy(link)
    write(run/'task.json', task)
    assessment = control.commit(run, packet, state, 'Opened from screening depth %s (%s); no read state, gate or review was inherited.'
                                % (depth or 'none', paper_id))
    if previous:
        record.setdefault('l3_history', []).append({**previous, 'superseded_at': promoted_at,
                                                    'reason': 'A run for another source version.'})
    record['l3'] = {'run_path': store._relative(root, run), 'run_id': run.name, 'promoted_at': promoted_at,
                    'source_sha256': sha, 'origin': 'PROMOTED', 'extraction_reused': reused,
                    'identity_binding': 'SOURCE_HASH_MATCH'}
    record['upgrade_history'].append({'from': depth, 'to': 'L3', 'at': promoted_at, 'trigger': trigger,
                                      'source_sha256': sha, 'run_path': record['l3']['run_path'],
                                      'reused': {'source_bytes': True, 'native_extraction': reused, 'rendered_crops': len(crops),
                                                 'leads_from_pass_ids': [row['pass_id'] for row in triage.current_passes(snapshot)]},
                                      'completion_inherited': False})
    store.save_record(root, record)
    if reused:
        resources.record(root, 'EXTRACTION_REUSED', paper_id, source_sha256=sha, stage='PROMOTION',
                         page_count=version['extraction'].get('page_count'))
    return {'paper_id': paper_id, 'run': str(run), 'from_depth': depth, 'review_mode': review_mode,
            'reused': {'source_bytes': True, 'native_extraction': reused, 'native_extraction_note': note,
                       'rendered_crops': len(crops), 'leads': LEADS + '/leads.md'},
            'not_inherited': NOT_INHERITED, 'run_assessment': assessment,
            'notice': 'Continue with reading_run_control.py on the new run. Its gates start PENDING and only an actual '
                      'independent review can pass G3.'}
