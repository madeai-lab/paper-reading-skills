"""Structural safeguards for review evidence; never certifies actual viewing."""
from pathlib import Path
import hashlib
import json

VISUAL = {'FIGURE', 'PANEL', 'TABLE', 'OTHER_VISUAL'}


def visual_fingerprint(root, review):
    root = Path(root)
    record = review.get('visual_inspection', {})
    refs = set(record.get('tool_evidence_refs', []))
    if review.get('source_first_inventory_ref'):
        refs.add(review['source_first_inventory_ref'])
    structured = review.get('structured_inspection')
    if isinstance(structured, dict):
        refs.update(structured.get('evidence_refs', []))
    for row in record.get('units', []):
        refs.update(row.get('artifact_refs', []))
    files = {}
    for ref in sorted(refs):
        path = root/ref.split('#', 1)[0]
        files[ref] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else 'MISSING'
    data = {'reviewer_session_id': review.get('reviewer_session_id'),
            'visual_inspection': record, 'files': files}
    if structured is not None:
        data['structured_inspection'] = structured
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode('utf8')).hexdigest()


def enabled(packet):
    try:
        revision = tuple(int(x) for x in packet.get('skill_revision', '0').split('.'))
    except (ValueError, AttributeError):
        revision = (0,)
    return revision >= (2, 4) or packet.get('review_requirements', {}).get('direct_visual_inspection') is True


def visual_review_errors(root, packet, review):
    if not enabled(packet):
        return []
    root = Path(root)
    from reading_review_modes import required_visual_ids
    try:
        required = required_visual_ids(packet, review, root)
    except (ValueError, TypeError, KeyError) as exc:
        return [{'code': 'REVIEW_PLAN_INVALID', 'item': 'G3', 'next_action': str(exc)}]
    record = review.get('visual_inspection', {})
    def fail(message):
        return [{'code': 'REVIEW_VISUAL_INCOMPLETE', 'item': 'G3', 'next_action': message}]
    if not isinstance(record, dict):
        return fail('Record the actual reviewer visual_inspection object.')
    if not required:
        if (record.get('status') == 'NOT_APPLICABLE' and record.get('units') == []
                and review.get('reviewed_visual_evidence_sha256') == visual_fingerprint(root, review)):
            return []
        return fail('Explain that the source has no informative visual units and bind its source-first evidence.')
    if (record.get('status') != 'COMPLETE' or record.get('direct_pixels_available') is not True
            or record.get('blocked_unit_ids') != []):
        return fail('Direct reviewer image access is required; blocked pixels cannot support accepted G3.')
    if (not review.get('reviewer_session_id') or record.get('session_id') != review['reviewer_session_id']):
        return fail('Tie direct visual observations to this actual reviewer session, not another reader.')
    refs = record.get('tool_evidence_refs', [])
    if (not isinstance(refs, list) or not refs or any(not isinstance(x, str)
            or not (root/x.split('#', 1)[0]).is_file() for x in refs)):
        return fail('Save existing local reviewer tool/observation evidence; a writer viewing flag is insufficient.')
    rows = record.get('units', [])
    if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
        return fail('Use an array of per-unit direct reviewer observations.')
    ids = [x.get('unit_id') for x in rows]
    if any(not isinstance(x, str) for x in ids) or len(set(ids)) != len(ids) or set(ids) != required:
        return fail('Inspect every current visual unit exactly once in the reviewer visual record.')
    for row in rows:
        refs = row.get('artifact_refs', [])
        if (row.get('actually_viewed') is not True or not isinstance(row.get('observations'), str)
                or not row['observations'].strip() or not isinstance(refs, list) or not refs
                or any(not isinstance(x, str) or not (root/x.split('#', 1)[0]).is_file() for x in refs)):
            return fail('Record actual visible relationships and existing image artifacts for '+row['unit_id'])
    if review.get('reviewed_visual_evidence_sha256') != visual_fingerprint(root, review):
        return fail('Reviewer evidence changed or lacks its own snapshot; run snapshot --file with this inspected review draft.')
    return []


def structure_errors(packet):
    if not enabled(packet):
        return []
    errors = []
    units = {u['unit_id']: u for u in packet.get('units', [])}
    for uid, unit in units.items():
        parent = unit.get('parent_id')
        if unit.get('kind') == 'PANEL' and (not parent or parent == uid or units.get(parent, {}).get('kind') != 'FIGURE'):
            errors.append({'code': 'UNIT_PARENT_INVALID', 'item': uid, 'next_action': 'Retain a composite FIGURE parent and connect its panels.'})
        seen = {uid}
        ancestor = parent
        while ancestor in units:
            if ancestor in seen:
                errors.append({'code': 'UNIT_PARENT_INVALID', 'item': uid, 'next_action': 'Remove the parent cycle without removing source units.'})
                break
            seen.add(ancestor)
            ancestor = units[ancestor].get('parent_id')
        if parent and (parent not in units or uid not in units[parent].get('children', [])):
            errors.append({'code': 'UNIT_PARENT_INVALID', 'item': uid, 'next_action': 'Make parent_id and children reciprocal using existing unit IDs.'})
        for child in unit.get('children', []):
            if child not in units or units[child].get('parent_id') != uid:
                errors.append({'code': 'UNIT_CHILD_INVALID', 'item': uid, 'next_action': 'Correct the child reference and reciprocal parent_id.'})
    experiments = {x['experiment_id']: x for x in packet.get('experiments', [])}
    for eid, row in experiments.items():
        refs = row.get('same_as', [])
        refs = [refs] if isinstance(refs, str) else refs
        if not isinstance(refs, list) or any(not isinstance(x, str) or x == eid or x not in experiments for x in refs):
            errors.append({'code': 'EXPERIMENT_LINK_INVALID', 'item': eid, 'next_action': 'same_as must resolve to other current experiment IDs; count shared evidence once.'})
    return errors
