"""Checks for complete-reading runs opened from a screening record. Other runs are untouched.

Authority, in order:
  1. handoffs/screening/promotion.json  the promotion record written once by `promote` (history, never edited);
     it names the screening snapshot it was decided on, by hash.
  2. paper_packet.json `promotion`      the run's binding to that record (its hash and the fields repeated from it).
  3. task.json `promotion`              a copy of the packet binding for role prompts; it must equal the packet's.
Nothing here is a second scientific record: every comparison is against the one promotion record.
"""
import hashlib
import json
import os
from pathlib import Path

SCHEMA = 1
LEADS_DIR = 'handoffs/screening/'
COUNTED_STATES = {'UNDERSTOOD', 'CHECKED', 'NON_INFORMATIVE'}
LINK_FIELDS = ('corpus_id', 'paper_id', 'from_depth', 'trigger')


def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return None


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() if Path(path).is_file() else None


def _task_link(root):
    task = _json(Path(root)/'task.json')
    return task.get('promotion') if isinstance(task, dict) else None


def promoted(root, packet):
    """A run opened from a screening record, recognized by any trace of the promotion.

    A run that was never promoted has none of the three and is never asked for these fields.
    """
    return (packet.get('promotion') is not None or (Path(root)/LEADS_DIR/'promotion.json').is_file()
            or _task_link(root) is not None)


def _is_lead(root, ref):
    """Whether a reference resolves into the screening leads, however the path is spelled."""
    if not isinstance(ref, str) or not ref.strip():
        return False
    base = os.path.normcase(str((Path(root)/LEADS_DIR).resolve()))
    path = os.path.normcase(str((Path(root)/ref.split('#', 1)[0]).resolve()))
    return path == base or path.startswith(base + os.sep)


def _only_leads(root, refs):
    refs = [ref for ref in refs or [] if isinstance(ref, str)]
    return bool(refs) and all(_is_lead(root, ref) for ref in refs)


def _binding(target):
    """Same binding as the screening layer: identity, revision and hash of the target's content."""
    if not target:
        return None
    digest = hashlib.sha256(json.dumps(target, sort_keys=True, ensure_ascii=False).encode('utf8')).hexdigest()
    return {'target_id': target.get('target_id'), 'revision': target.get('revision'), 'sha256': digest}


def basis_errors(record, snapshot):
    """Was the upgrade decided on the source version and decision the promotion record names?"""
    sha = (record.get('source') or {}).get('sha256')
    if not isinstance(snapshot, dict) or snapshot.get('paper_id') != record.get('paper_id'):
        return ['the screening snapshot is not the record of this paper']
    problems = []
    if (snapshot.get('full_text') or {}).get('current_sha256') != sha:
        problems.append('the screening record named another source version when the paper was promoted')
    trigger = record.get('trigger') or {}
    if trigger.get('kind') == 'DECISION':
        decisions = snapshot.get('decisions') or []
        decision = decisions[-1] if decisions else {}
        if decision.get('decision_id') != trigger.get('ref'):
            problems.append('the cited decision was not the current decision at promotion')
        elif decision.get('decision') != 'PROMOTE_TO_L3':
            problems.append('the cited decision does not promote to complete reading')
        elif decision.get('source_sha256') not in (None, sha):
            problems.append('the cited decision was made on another source version')
        elif decision.get('target') != record.get('target'):
            problems.append('the cited decision was made for another research target or revision')
    elif trigger.get('kind') == 'USER_REQUEST':
        if (snapshot.get('depth') or {}).get('user_requested') != 'L3':
            problems.append('the screening record holds no user request for complete reading')
    else:
        problems.append('the promotion names no decision or user request')
    return problems


def promotion_errors(root, packet):
    """Screening notes are leads. They cannot stand in for reading, a gate, or a user's scope decision."""
    if not promoted(root, packet):
        return []
    root = Path(root)
    link = packet.get('promotion')
    errors = []

    def error(code, item, action):
        errors.append({'code': code, 'item': item, 'next_action': action})

    if not isinstance(link, dict) or link.get('schema_version') != SCHEMA:
        error('PROMOTION_RECORD_INVALID', 'paper_packet.json', 'The packet promotion field is missing or of an unknown version. '
              'Restore it from the promotion record; this helper does not migrate or rebuild it.')
        return errors
    mirror = _task_link(root)
    if mirror != link:
        differing = sorted(key for key in set(link) | set(mirror or {}) if (mirror or {}).get(key) != link.get(key))
        error('PROMOTION_RECORDS_DISAGREE', 'task.json', 'task.json and paper_packet.json must carry the same promotion binding '
              '(differs: ' + ', '.join(differing) + '). The promotion record under handoffs/screening/ decides which is right.')
    path = root/LEADS_DIR/'promotion.json'
    record = None
    if link.get('promotion_ref') != LEADS_DIR + 'promotion.json' or _sha(path) != link.get('promotion_sha256'):
        error('PROMOTION_RECORD_CHANGED', 'promotion', 'Restore the original promotion record; upgrade history is not editable.')
    else:
        record = _json(path)
    sources = packet.get('sources') or [{}]
    if sources[0].get('sha256') != link.get('source_sha256'):
        error('PROMOTION_SOURCE_MISMATCH', sources[0].get('source_id'),
              'This run reads a different source version than the screening record; its leads do not apply here.')
    if isinstance(record, dict):
        differing = [key for key in LINK_FIELDS if record.get(key) != link.get(key)]
        if (record.get('source') or {}).get('sha256') != link.get('source_sha256'):
            differing.append('source_sha256')
        if (record.get('reused') or {}).get('native_extraction') != link.get('extraction_reused'):
            differing.append('extraction_reused')
        if differing:
            error('PROMOTION_RECORDS_DISAGREE', 'paper_packet.json', 'The packet binding contradicts the promotion record '
                  '(differs: ' + ', '.join(differing) + '). The record is the history; correct the binding.')
        snapshot_path = root/LEADS_DIR/'screening_record.json'
        if _sha(snapshot_path) != record.get('screening_record_sha256'):
            error('PROMOTION_RECORD_CHANGED', 'screening_record.json', 'Restore the screening snapshot the promotion was decided on.')
        else:
            for problem in basis_errors(record, _json(snapshot_path)):
                error('PROMOTION_BASIS_STALE', 'promotion', 'The upgrade does not rest on what it cites: ' + problem
                      + '. Promote again from the current screening record.')
        state = _json(root/'execution_state.json') or {}
        targets = [packet.get('research_target')] + list(state.get('research_target_history') or [])
        if record.get('target') not in [_binding(target) for target in targets]:
            error('PROMOTION_TARGET_MISMATCH', 'research_target', 'The run never carried the research target revision the paper was '
                  'promoted for. Bind targets with set-target so the change stays in the history.')
    for unit in packet.get('units', []):
        if unit.get('read_state') in COUNTED_STATES and _only_leads(root, unit.get('evidence_refs')):
            error('SCREENING_NOTE_NOT_EVIDENCE', unit.get('unit_id'),
                  'Read and check this unit in the complete-reading run; an earlier skim or targeted note is a lead, not evidence.')
    for gate in ['G0', 'G1', 'G2']:
        row = packet.get('gate_results', {}).get(gate, {})
        if row.get('decision') == 'PASS' and _only_leads(root, row.get('evidence_refs')):
            error('SCREENING_NOTE_NOT_EVIDENCE', gate, 'A gate passes on evidence from this run, not on screening notes.')
    for entry in packet.get('scope_exclusions', []):
        if _is_lead(root, entry.get('user_authorization_ref')):
            error('PROMOTION_SCOPE_ABUSE', entry.get('unit_id'),
                  'A routing decision or screening note is not user authorization. Read the unit; only the user can narrow scope.')
    return errors
