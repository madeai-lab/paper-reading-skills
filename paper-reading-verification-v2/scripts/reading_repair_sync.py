"""Read-only dependency discovery and repair evidence checks; never rewrites prose."""
import hashlib
import json


TEXT = {'.md', '.txt', '.json', '.csv', '.tsv', '.html', '.svg'}
HISTORY = {'reviews', 'handoffs', 'repair_sync'}
CONTROL = {'paper_packet.json', 'execution_state.json', 'task.json', 'assignment_map.json'}


def sha(value):
    return hashlib.sha256(value).hexdigest()


def current_documents(root, packet):
    """Include unlinked notes and old manual notebooks, not just deliverables."""
    excluded = {packet.get('deliverables', {}).get('independent_review')}
    documents = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root).as_posix()
        if (not path.is_file() or path.suffix.lower() not in TEXT
                or path.relative_to(root).parts[0] in HISTORY
                or relative in CONTROL or relative in excluded):
            continue
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Current artifacts must stay inside the run: ' + relative)
        documents[relative] = path.read_text(encoding='utf-8-sig')
    # Decision/status bookkeeping must not invalidate a scientific repair seal.
    scientific = {k: v for k, v in packet.items() if k not in
                  {'reviews', 'gate_results', 'paper_status'}}
    documents['paper_packet.json'] = json.dumps(scientific, sort_keys=True, ensure_ascii=False)
    return documents


def scan(root, packet, request, review_id, terms=None, obsolete=None):
    identifiers = [item for key in ['unit_ids', 'claim_ids', 'issue_ids', 'affected_claim_ids']
                   for item in request.get(key, [])]
    focus = sorted(set([request['repair_id'], *identifiers, *(terms or [])]))
    if any(not isinstance(term, str) or not term.strip() for term in focus + (obsolete or [])):
        raise ValueError('Focus and obsolete literals must be nonempty strings.')
    documents = current_documents(root, packet)
    files = []
    for path, content in documents.items():
        hits = [{'line': n, 'terms': [t for t in focus if t.casefold() in line.casefold()]}
                for n, line in enumerate(content.splitlines(), 1)
                if any(t.casefold() in line.casefold() for t in focus)]
        files.append({'path': path, 'sha256': sha(content.encode('utf8')),
                      'matches': hits, 'disposition': None, 'reason': ''})
    return {'review_id': review_id, 'repair_id': request['repair_id'],
            'request_sha256': sha(json.dumps(request, sort_keys=True, ensure_ascii=False).encode('utf8')),
            'focus_terms': focus, 'obsolete_literals': obsolete or [],
            'historical_occurrences': [], 'files': files,
            'notice': 'Read-only discovery. Inspect every current file; hashes and dispositions do not prove semantic consistency.'}


def validate(root, packet, request, review_id, report):
    """Reject missing files, stale scans and declared obsolete current wording."""
    expected = scan(root, packet, request, review_id,
                    report.get('focus_terms'), report.get('obsolete_literals'))
    for key in ['review_id', 'repair_id', 'request_sha256', 'focus_terms']:
        if report.get(key) != expected[key]:
            raise ValueError('Repair synchronization identity/focus changed: ' + key)
    rows = report.get('files', [])
    if (not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
            or len({row.get('path') for row in rows}) != len(rows)):
        raise ValueError('Use one synchronization disposition per current file.')
    by_path = {row.get('path'): row for row in rows}
    if set(by_path) != {row['path'] for row in expected['files']}:
        raise ValueError('Current file set changed or files were omitted; rescan all current artifacts.')
    for row in expected['files']:
        actual = by_path[row['path']]
        if actual.get('sha256') != row['sha256']:
            raise ValueError('File changed after synchronization scan: ' + row['path'])
        if (actual.get('disposition') not in {'UPDATED', 'CHECKED_UNCHANGED', 'HISTORICAL_CONTEXT'}
                or not isinstance(actual.get('reason'), str) or not actual['reason'].strip()):
            raise ValueError('Inspect and explain the disposition for ' + row['path'])
    history = report.get('historical_occurrences', [])
    if not isinstance(history, list) or any(not isinstance(h, dict) or not str(h.get('reason', '')).strip() for h in history):
        raise ValueError('Historical exceptions require exact path, line, literal and explanation.')
    allowed = {(h.get('path'), h.get('line'), h.get('literal')) for h in history}
    found = set()
    for path, content in current_documents(root, packet).items():
        for number, line in enumerate(content.splitlines(), 1):
            for literal in expected['obsolete_literals']:
                if literal.casefold() in line.casefold():
                    hit = (path, number, literal)
                    found.add(hit)
                    if hit not in allowed:
                        raise ValueError(f'Obsolete current wording at {path}:{number}: {literal}')
    if allowed - found:
        raise ValueError('Historical exception does not match an actual obsolete occurrence.')
    return expected


def progress_current(root, packet, state, request, review_id):
    """Recheck the saved report, not just an Owner-ready flag."""
    progress = state.get('repair_progress', {}).get(request['repair_id'], {})
    if not packet.get('review_requirements', {}).get('repair_dependency_sync'):
        return True
    if (progress.get('status') != 'READY_FOR_REVIEW' or progress.get('review_id') != review_id
            or progress.get('scope_revision') != packet.get('scope_revision')):
        return False
    try:
        ref = progress['dependency_sync_ref']
        path = (root / ref).resolve()
        if not path.is_relative_to((root / 'repair_sync').resolve()):
            return False
        raw = path.read_bytes()
        if sha(raw) != progress['dependency_sync_sha256']:
            return False
        validate(root, packet, request, review_id, json.loads(raw))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False
    return True
