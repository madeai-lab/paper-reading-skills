"""Stage 09: validate a bounded use of an L2 claim, never a paper acceptance."""
from pathlib import Path

from reading_run_records import digest, read
from reading_triage import canonical_sha, examined_items, latest_pass, local_claim_labels, target_binding

# Each check is a short source-grounded description, not a tick box.
CHECKS = {'METHOD': ('mechanism', 'context'),
          'COMPARISON': ('result', 'metric', 'baseline', 'conditions'),
          'MECHANISM_EFFECT': ('result', 'metric', 'baseline', 'conditions', 'control_or_ablation')}


def text(value):
    return isinstance(value, str) and bool(value.strip())


def validate(directory, record, target, assertion, support):
    """Return (binding digest, review label, defect). A binding is for this wording and source use only."""
    row = latest_pass(record, 'L2')
    cid = support.get('local_claim_id')
    labels = {x['claim_id']: x for x in local_claim_labels(record, target)}
    if not row or cid not in labels or labels[cid]['use'] != 'CANDIDATE_COMPARISON':
        return None, None, 'Cite a current SUPPORTED or LIMITED local claim applicable to this target.'
    claim = next(c for c in row['targeted']['local_claims'] if c['claim_id'] == cid)
    kind, checks = assertion.get('use_kind'), support.get('checks')
    if not isinstance(kind, str) or kind not in CHECKS or not isinstance(checks, dict) or not all(text(checks.get(k)) for k in CHECKS[kind]):
        return None, None, 'Name the use and describe its source checks: ' + str(CHECKS)
    if not text(assertion.get('limitation')) or support.get('source_sha256') != row['source_sha256']:
        return None, None, 'Keep the examined scope, limits and the exact source SHA with the assertion.'
    if support.get('attribution') != claim['attribution'] or support.get('evidence_state') != claim['evidence_state']:
        return None, None, 'Carry the recorded attribution and support state into the synthesis.'
    focus = next(f for f in row['targeted']['focus'] if f['focus_id'] == claim['focus_id'])
    items = examined_items(record)
    ids = set(focus['items'] + claim['supporting_items'] + claim['conflicting_items'])
    source = next(v for v in record['full_text']['versions'] if v['sha256'] == row['source_sha256'])
    path = (directory/source['local_path']).resolve()
    if not path.is_relative_to(directory.resolve()) or not path.is_file() or digest(path) != row['source_sha256']:
        return None, None, 'Restore the bound source or read the changed version.'
    assets = {}
    for i in ids:
        for ref in items[i].get('artifact_refs', []):
            path = (directory/ref).resolve()
            if not path.is_relative_to(directory.resolve()) or not path.is_file():
                return None, None, 'Restore the cited source image.'
            assets[ref] = digest(path)
    binding = canonical_sha({'paper': record['paper_id'], 'pass': row['pass_id'], 'target': target_binding(target),
                             'source': row['source_sha256'], 'claim': claim, 'scope': row['targeted']['scope_statement'],
                             'focus': focus, 'items': [items[i] for i in sorted(ids)], 'image_hashes': assets,
                             'conflicts': row['conflicts'], 'flags': row['uncertainty_flags'],
                             'assertion': {k: v for k, v in assertion.items() if k != 'support'},
                             'support': [{k: v for k, v in s.items() if k != 'review_ref'} for s in assertion['support']]})
    ref = support.get('review_ref')
    if not ref and assertion['strength'] != 'CONCLUSION':
        return binding, 'NOT_INDEPENDENTLY_REVIEWED', None
    if not text(ref):
        return binding, None, 'A main-line conclusion needs an independent scoped review, not Owner approval.'
    folder = directory/'scoped_reviews'
    path = (directory/ref).resolve()
    if not path.is_relative_to(folder.resolve()) or not path.is_file() or path.suffix != '.json' or folder.resolve().parent != directory.resolve():
        return binding, None, 'Use a reviewer-authored JSON file under this paper\'s scoped_reviews directory.'
    review = read(path)
    writers = {r['writer_id'] for r in record['passes']} | {a.get('writer_id') for a in record['assessments']} | {assertion.get('writer_id')}
    if (not isinstance(review, dict) or review.get('kind') != 'SCOPED_CLAIM_REVIEW' or review.get('binding_sha256') != binding
            or not text(assertion.get('writer_id')) or not text(review.get('reviewer_id')) or review['reviewer_id'] in writers
            or review.get('decision') != 'SUPPORTS_WITHIN_SCOPE' or not text(review.get('source_observation'))
            or not text(review.get('limits')) or not text(review.get('independence_disclosure'))):
        return binding, None, 'Missing, stale, negative or non-independent scoped review; withhold this conclusion.'
    return binding, 'INDEPENDENTLY_CHECKED_FOR_THIS_USE', None
