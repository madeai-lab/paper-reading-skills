"""Mode-aware review coverage and delta evidence; never establishes understanding."""
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import unquote

from reading_data_sources import data_paths, registered_data

MODES = {'KEY_CLAIMS', 'FULL_DOUBLE_READ'}
LABELS = {'KEY_CLAIMS': 'COMPLETE_READING_KEY_CLAIMS_CHECKED',
          'FULL_DOUBLE_READ': 'COMPLETE_INDEPENDENT_DOUBLE_READ'}


def review_mode(packet):
    mode = packet.get('review_mode', 'FULL_DOUBLE_READ')
    if mode not in MODES:
        raise ValueError('Unknown review_mode; choose KEY_CLAIMS or FULL_DOUBLE_READ.')
    return mode


def _ids(value, field):
    if (not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value)
            or len(set(value)) != len(value)):
        raise ValueError(field + ' must be an array of unique nonempty IDs.')
    return set(value)


def _closure(units, seeds):
    result, todo = set(), list(seeds)
    while todo:
        uid = todo.pop()
        if uid not in units:
            raise ValueError('Unknown evidence dependency: ' + str(uid))
        if uid in result:
            continue
        result.add(uid)
        row = units[uid]
        todo.extend(_ids(row.get('dependencies', []), 'dependencies') - result)
        if row.get('parent_id'):
            todo.append(row['parent_id'])
    return result


def review_plan(packet):
    mode = review_mode(packet)
    units = {u['unit_id']: u for u in packet.get('units', [])}
    claims = packet.get('claims', [])
    cids = _ids([c['claim_id'] for c in claims], 'claim IDs')
    if 'review_mode' not in packet:
        # New dependency contracts must not reinterpret frozen legacy records.
        return {'review_mode': mode, 'coverage_label': LABELS[mode],
                'key_claim_ids': sorted(cids), 'key_unit_ids': sorted(units),
                'sampled_unit_ids': [], 'required_unit_ids': sorted(units)}
    seeds = _ids(packet.get('review_requirements', {}).get('key_unit_ids', []), 'key_unit_ids')
    experiments = {e['experiment_id']: e for e in packet.get('experiments', [])}
    for claim in claims:
        seeds.update(_ids(claim.get('supporting_units', []), 'supporting_units'))
        for eid in _ids(claim.get('experiment_refs', []), 'experiment_refs'):
            if eid not in experiments:
                raise ValueError('Unknown claim experiment: ' + eid)
            seeds.update(_ids(experiments[eid].get('unit_refs', []), 'experiment unit_refs'))
    for exp in experiments.values():
        if set(exp.get('claim_refs', [])) & cids:
            seeds.update(_ids(exp.get('unit_refs', []), 'experiment unit_refs'))
    for issue in packet.get('issues', []):
        if issue.get('status') not in {'CORRECTED', 'EXPLAINED'}:
            seeds.update(_ids(issue.get('unit_refs', []), 'issue unit_refs'))
    # NON_INFORMATIVE and explicit scope exclusions need independent scrutiny.
    seeds.update(uid for uid, u in units.items()
                 if u.get('read_state') in {'NON_INFORMATIVE', 'OUT_OF_SCOPE'})
    key = _closure(units, seeds)
    ordinary = sorted(set(units) - key)
    sample = set()
    if ordinary and mode == 'KEY_CLAIMS':
        count = min(len(ordinary), max(5, math.ceil(len(ordinary) * .2)))
        groups = {}
        for uid in ordinary:
            row = units[uid]
            sections = [str(loc.get('section')) for loc in row.get('locators', []) if loc.get('section')]
            stratum = (str(row.get('kind', 'UNKNOWN')), str(row.get('source_id', '')),
                       sections[0] if sections else '')
            groups.setdefault(stratum, []).append(uid)
        # Coverage of present sections/types may exceed the global minimum.
        rank = lambda uid: hashlib.sha256(uid.encode('utf8')).hexdigest()
        groups = {kind: sorted(rows, key=rank) for kind, rows in sorted(groups.items())}
        sample.update(rows[0] for rows in groups.values())
        for uid in sorted(ordinary, key=rank):
            if len(sample) >= max(count, len(groups)):
                break
            sample.add(uid)
        sample = _closure(units, sample) - key
    required = set(units) if mode == 'FULL_DOUBLE_READ' else key | sample
    return {'review_mode': mode, 'coverage_label': LABELS[mode],
            'key_claim_ids': sorted(cids), 'key_unit_ids': sorted(key),
            'sampled_unit_ids': sorted(sample), 'required_unit_ids': sorted(required)}


def _error(code, message):
    return {'code': code, 'item': 'G3', 'next_action': message}


def coverage_errors(root, packet, review, acquisition=None):
    try:
        plan = review_plan(packet)
        checked = _ids(review.get('checked_unit_ids', []), 'checked_unit_ids')
        claims = _ids(review.get('checked_claim_ids', []), 'checked_claim_ids')
    except (ValueError, KeyError, TypeError) as exc:
        return [_error('REVIEW_PLAN_INVALID', str(exc))]
    errors = []
    from reading_element_contracts import structured_review_errors
    errors.extend(structured_review_errors(root, packet, review, acquisition))
    if (set(plan['required_unit_ids']) - checked or set(plan['key_claim_ids']) - claims):
        errors.append(_error('REVIEW_COVERAGE_MISSING', 'Inspect required units and every current claim from review-plan.'))
    if checked - {u['unit_id'] for u in packet.get('units', [])} or claims - set(plan['key_claim_ids']):
        errors.append(_error('REVIEW_COVERAGE_INVALID', 'Checked IDs must resolve to current records.'))
    if 'review_mode' not in packet:
        return errors
    if review.get('review_mode') != plan['review_mode'] or review.get('coverage_label') != plan['coverage_label']:
        errors.append(_error('REVIEW_MODE_MISMATCH', 'Record the actual mode and its distinct coverage label.'))
    coverage = review.get('coverage_check', {})
    refs = coverage.get('evidence_refs', []) if isinstance(coverage, dict) else []
    if (not isinstance(coverage, dict) or coverage.get('source_structure_checked') is not True
            or coverage.get('owner_coverage_checked') is not True or coverage.get('omissions') != []
            or not isinstance(refs, list) or not refs
            or any(not isinstance(x, str) or not (Path(root)/x.split('#', 1)[0]).is_file() for x in refs)):
        errors.append(_error('REVIEW_COVERAGE_CHECK_MISSING', 'Save source-first structure and Owner coverage inspection, resolving omissions.'))
    return errors


def required_visual_ids(packet, review=None, root=None, acquisition=None):
    from reading_review_contracts import VISUAL
    units = packet.get('units', [])
    visuals = {u['unit_id'] for u in units if u.get('kind') in VISUAL or u.get('visual_review', {}).get('required')}
    if review_mode(packet) != 'FULL_DOUBLE_READ':
        selected = set(review_plan(packet)['required_unit_ids'])
        if review:  # Extra checked visuals also require truthful direct observations.
            selected.update(review.get('checked_unit_ids', []))
        visuals &= selected
    tables = [u for u in units if u.get('kind') == 'TABLE' and u['unit_id'] in visuals]
    if root is not None and tables:
        from reading_element_contracts import checked_acquisition, structured_ready
        if acquisition is None:
            acquisition = checked_acquisition(root, packet)
        visuals -= {u['unit_id'] for u in tables if structured_ready(root, packet, u, acquisition)}
    return visuals


def artifact_manifest(root, packet):
    from reading_repair_sync import current_documents, sha
    root = Path(root)
    files = {name: sha(text.encode('utf8')) for name, text in current_documents(root, packet).items()}
    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {'artifact_refs', 'evidence_refs', 'page_refs', 'conflict_resolution_refs'} and isinstance(item, list):
                    for ref in item:
                        if isinstance(ref, str):
                            path = root/ref.split('#', 1)[0]
                            files[ref] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else 'MISSING'
                else:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
    collect({k: packet.get(k) for k in ['units', 'claims', 'experiments', 'report_visuals']})
    for source in packet.get('sources', []):
        if source.get('local_path'):
            path = root/source['local_path']
            files[source['local_path']] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else 'MISSING'
    for source in registered_data(packet):
        provenance = source.get('provenance')
        acquisition = provenance.get('acquisition_ref') if isinstance(provenance, dict) else None
        if isinstance(acquisition, str):
            path = root/acquisition
            files[acquisition] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else 'MISSING'
    raw_sources = data_paths(root, packet)
    # Match the report fingerprint's implicit inline-image registration.
    for name in list(files):
        document = root/name
        if document.suffix.lower() == '.md' and document.is_file() and document.resolve() not in raw_sources:
            for match in re.finditer(r'!\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)', document.read_text(encoding='utf-8-sig')):
                destination = unquote(match[1].strip('<>').split('#', 1)[0])
                if not destination or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', destination) or destination.startswith('data:'):
                    continue
                path = (document.parent/destination).resolve()
                ref = path.relative_to(root.resolve()).as_posix() if path.is_relative_to(root.resolve()) else str(path)
                files[ref] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else 'MISSING'
    return files


def review_baseline(root, packet):
    return {'scope_revision': packet.get('scope_revision'),
            'source_hashes': {s['source_id']: s.get('sha256') for s in packet.get('sources', [])},
            'files': artifact_manifest(root, packet),
            'units': packet.get('units', []), 'claims': packet.get('claims', []),
            'experiments': packet.get('experiments', []), 'methods_taxonomy': packet.get('methods_taxonomy', [])}


def review_delta(root, packet):
    reviews = packet.get('reviews', [])
    if not reviews:
        return {'previous_review_id': None, 'changed_files': [], 'changed_unit_ids': [],
                'changed_claim_ids': [], 'expanded_review_required': False}
    previous = reviews[-1]
    ref = Path(root)/'reviews'/(previous['review_id']+'.baseline.json')
    if not ref.is_file():
        current = review_baseline(root, packet)
        return {'previous_review_id': previous['review_id'], 'changed_files': sorted(current['files']),
                'changed_unit_ids': sorted(u['unit_id'] for u in packet.get('units', [])),
                'changed_claim_ids': sorted(c['claim_id'] for c in packet.get('claims', [])),
                'expanded_review_required': True, 'baseline_missing': True}
    baseline = json.loads(ref.read_text(encoding='utf8'))
    current = review_baseline(root, packet)
    changed_files = sorted(name for name in set(baseline['files']) | set(current['files'])
                           if baseline['files'].get(name) != current['files'].get(name))
    result = {'previous_review_id': previous['review_id'], 'changed_files': changed_files,
              'expanded_review_required': any(baseline[k] != current[k] for k in ['scope_revision', 'source_hashes'])}
    if any(s.get('local_path') in changed_files for s in packet.get('sources', [])):
        result['expanded_review_required'] = True
    for key, field in [('units', 'unit_id'), ('claims', 'claim_id')]:
        before = {x[field]: x for x in baseline[key]}
        after = {x[field]: x for x in current[key]}
        result['changed_'+('unit' if key == 'units' else 'claim')+'_ids'] = sorted(
            uid for uid in set(before) | set(after) if before.get(uid) != after.get(uid))
    # Changes in local evidence reopen the units that cite it.
    for unit in packet.get('units', []):
        refs = unit.get('evidence_refs', []) + unit.get('visual_review', {}).get('artifact_refs', [])
        reading = unit.get('content_reading', {})
        refs += reading.get('page_refs', []) + reading.get('conflict_resolution_refs', [])
        if any(ref in changed_files or ref.split('#', 1)[0] in changed_files for ref in refs):
            result['changed_unit_ids'].append(unit['unit_id'])
    affected = set(result['changed_unit_ids'])
    before_exp = {e['experiment_id']: e for e in baseline.get('experiments', [])}
    after_exp = {e['experiment_id']: e for e in packet.get('experiments', [])}
    changed_exp = {eid for eid in set(before_exp) | set(after_exp) if before_exp.get(eid) != after_exp.get(eid)}
    experiment_claims = set()
    for eid in changed_exp:
        for exp in [before_exp.get(eid, {}), after_exp.get(eid, {})]:
            affected.update(exp.get('unit_refs', []))
            experiment_claims.update(exp.get('claim_refs', []))
    for claim in packet.get('claims', []):
        if claim['claim_id'] in experiment_claims or set(claim.get('experiment_refs', [])) & changed_exp:
            affected.update(claim.get('supporting_units', []))
    # Follow both the evidence prerequisites and units depending on those facts.
    units = {u['unit_id']: u for u in packet.get('units', [])}
    affected &= set(units)
    while True:
        expanded = _closure(units, affected)
        expanded.update(uid for uid, u in units.items()
                        if set(u.get('dependencies', [])) & expanded or u.get('parent_id') in expanded)
        if expanded == affected:
            break
        affected = expanded
    changed_claims = set(result['changed_claim_ids']) | experiment_claims
    methods_changed = baseline.get('methods_taxonomy', []) != current['methods_taxonomy']
    for claim in packet.get('claims', []):
        if (set(claim.get('supporting_units', [])) & affected
                or set(claim.get('experiment_refs', [])) & changed_exp or methods_changed):
            changed_claims.add(claim['claim_id'])
    result['changed_unit_ids'] = sorted(affected)
    result['changed_claim_ids'] = sorted(changed_claims)
    return result


def continuation_errors(root, packet, review):
    if 'review_mode' not in packet or not packet.get('reviews'):
        return []
    previous = packet['reviews'][-1]
    if previous.get('review_id') == review.get('review_id'):
        return []
    try:
        delta = review_delta(root, packet)
        record = review.get('continuation', {})
        retained = _ids(record.get('retained_unit_ids', []), 'retained_unit_ids')
        rechecked = _ids(record.get('rechecked_unit_ids', []), 'rechecked_unit_ids')
        checked = _ids(review.get('checked_unit_ids', []), 'checked_unit_ids')
        inspected_files = _ids(record.get('inspected_changed_files', []), 'inspected_changed_files')
        if record.get('previous_review_id') != previous['review_id']:
            raise ValueError('Link continuation to the latest actual review.')
        if retained & rechecked or retained | rechecked != checked:
            raise ValueError('Partition checked coverage into retained and actually rechecked unit IDs.')
        same = (review.get('reviewer_session_id') == previous.get('reviewer_session_id')
                and review.get('reviewer_id') == previous.get('reviewer_id')
                and review.get('reviewer_session_id') not in {None, '', 'HOST_NOT_EXPOSED'})
        if retained and not same:
            raise ValueError('Only the same actual reviewer session may retain its own coverage.')
        if not same and not record.get('replacement_reason'):
            raise ValueError('Disclose replacement and directly recheck required coverage.')
        if not same and not set(review_plan(packet)['key_claim_ids']) <= _ids(record.get('rechecked_claim_ids', []), 'rechecked_claim_ids'):
            raise ValueError('A replacement must directly recheck every current claim.')
        if retained - set(previous.get('checked_unit_ids', [])):
            raise ValueError('Retained units must have been inspected by this reviewer previously.')
        if retained & set(delta['changed_unit_ids']) or (retained and delta['expanded_review_required']):
            raise ValueError('Changed sources, scope or units require actual reinspection.')
        if set(delta['changed_files']) - inspected_files:
            raise ValueError('Inspect every changed artifact and its affected dependency chain.')
        if not set(delta['changed_claim_ids']) <= _ids(record.get('rechecked_claim_ids', []), 'rechecked_claim_ids'):
            raise ValueError('Recheck changed claims and document affected unchanged dependencies.')
    except (ValueError, TypeError, KeyError, OSError, AttributeError) as exc:
        return [_error('REVIEW_CONTINUATION_INVALID', str(exc))]
    return []
