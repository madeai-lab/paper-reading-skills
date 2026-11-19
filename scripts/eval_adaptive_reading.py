"""Behavioural evaluation for adaptive reading depth. Reports which evidence tier each number rests on.

router   Rule-engine routing on gold ratings (SIMULATED_FLOW): tests the routing rules, not an agent's reading.
records  Scores screening records an agent actually produced against a human gold file.

Neither mode is a real-paper end-to-end result unless the gold file binds every paper to the attached source bytes.
"""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))  # also under an isolated interpreter (-I)

import reading_corpus as store
import reading_resources as resources
import reading_triage as triage

PROMOTE = set(triage.PROMOTIONS)
TIERS = ('STATIC_UNIT', 'SIMULATED_FLOW', 'REAL_PAPER_E2E')


def _ratio(numerator, denominator):
    return None if not denominator else round(numerator / denominator, 4)


def synthetic_record(case):
    """A minimal record with the stated depth; it contains no reading content."""
    paper = case['paper']
    record = triage.new_record('P0001', {'title': case.get('description', case['case_id'])}, {
        'record_id': 'REC-01', 'origin': {'locator': 'eval case'}, 'identifiers': {}, 'fields': {}, 'original': {}, 'sha256': ''})
    record['reading_policy'] = case.get('reading_policy', 2)
    record['identity']['paper_type'] = paper.get('paper_type', 'EMPIRICAL')
    access = paper.get('full_text', 'NOT_ATTEMPTED')
    sha = 'eval-source' if access == 'AVAILABLE' else None
    record['full_text'].update(access_state=access, current_sha256=sha,
                               missing_reason='Not obtainable in this case.' if access == 'UNAVAILABLE' else None)
    record['depth']['user_requested'] = paper.get('user_requested')
    conflicts = [{'conflict_id': 'K1', 'description': 'Abstract and table disagree.', 'items': [], 'status': 'OPEN'}] \
        if paper.get('open_conflict') else []
    for depth in triage.SCREENING_DEPTHS[:triage.SCREENING_DEPTHS.index(paper.get('depth', 'L0')) + 1]:
        record['passes'].append({'pass_id': depth + '-01', 'depth': depth, 'status': 'CURRENT',
                                 'source_sha256': None if depth == 'L0' else sha, 'examined': [], 'not_examined': [],
                                 'uncertainty_flags': [], 'conflicts': conflicts if depth != 'L0' else []})
    return record


def synthetic_assessment(case):
    ratings = {name: 'LOW' for name in triage.DIMENSIONS}
    ratings.update(case.get('ratings', {}))
    return {'assessment_id': 'A01', 'dimensions': {name: {'rating': rating, 'basis': 'gold rating', 'evidence_level': 'METADATA_ONLY',
                                                          'refs': []} for name, rating in ratings.items()},
            'uncertainty': {'level': 'MEDIUM', 'missing_information': case.get('missing_information', ['Stated by the case.'])},
            'mechanisms_worth_study': case.get('mechanisms', ['Mechanism named by the case.'])}


def score_decisions(rows):
    """rows: [{case_id, decision, acceptable_decisions, is_core}]"""
    core = [row for row in rows if row.get('is_core')]
    missed = [row['case_id'] for row in core if row['decision'] not in PROMOTE | {'DEFER_FOR_EVIDENCE', 'REMAIN_AT_L2'}]
    deferred = [row['case_id'] for row in core if row['decision'] == 'DEFER_FOR_EVIDENCE']
    wrong = [row['case_id'] for row in rows if row['decision'] not in row['acceptable_decisions']]
    return {'cases': len(rows), 'routing_accuracy': _ratio(len(rows) - len(wrong), len(rows)), 'misrouted_case_ids': wrong,
            'core_papers': len(core), 'core_paper_miss_rate': _ratio(len(missed), len(core)), 'missed_core_case_ids': missed,
            'core_papers_deferred': deferred}


def evaluate_router(cases):
    rows = []
    for case in cases:
        result = triage.recommend(synthetic_record(case), synthetic_assessment(case))
        rows.append({'case_id': case['case_id'], 'decision': result['decision'], 'rule': result['rule'],
                     'acceptable_decisions': case['acceptable_decisions'], 'is_core': bool(case.get('is_core'))})
    return {'evaluation_tier': 'SIMULATED_FLOW', **score_decisions(rows), 'results': rows,
            'real_paper_e2e': 'NOT_RUN',
            'notice': 'Routing rules applied to gold ratings. This does not measure how well an agent reads, rates or attributes; '
                      'run the records mode on real agent output for that.'}


def _statement(record, path):
    """Resolve card.headline_evidence[0], card.core_method, screening.potential_value[1] or targeted.local_claims.LC1."""
    match = re.fullmatch(r'(screening|card|targeted)\.([a-z_]+)(?:\[(\d+)\]|\.([A-Za-z0-9_.-]+))?', path)
    if not match:
        return None
    section, key, index, name = match.groups()
    depth = {'screening': 'L0', 'card': 'L1', 'targeted': 'L2'}[section]
    value = ((triage.latest_pass(record, depth) or {}).get(section) or {}).get(key)
    if isinstance(value, list):
        if name is not None:
            return next((row for row in value if row.get('claim_id') == name), None)
        return value[int(index)] if index is not None and int(index) < len(value) else None
    return value if index is None and name is None else None


def _recorded_statements(record):
    count = 0
    for depth, section in [('L0', 'screening'), ('L1', 'card'), ('L2', 'targeted')]:
        data = (triage.latest_pass(record, depth) or {}).get(section) or {}
        for key, value in data.items():
            if key == 'local_claims':
                count += sum(1 for claim in value if claim['evidence_state'] in {'SUPPORTED', 'LIMITED'})
            elif isinstance(value, list):
                count += sum(1 for row in value if isinstance(row, dict) and 'attribution' in row)
            elif isinstance(value, dict) and 'attribution' in value:
                count += 1
    return count


def evaluate_records(workspace, gold):
    workspace = Path(workspace).resolve()
    corpus = store.load_corpus(workspace)
    declared = gold.get('evaluation_tier')
    if declared not in TIERS[1:]:
        raise ValueError('The gold file declares evaluation_tier SIMULATED_FLOW or REAL_PAPER_E2E.')
    rows, checked, matched, unsupported, statements, unbound = [], 0, 0, 0, 0, []
    for paper in gold['papers']:
        record = store.load_record(workspace, paper['paper_id'])
        decision, _ = triage.current_decision(record, corpus['research_target'])
        rows.append({'case_id': paper['paper_id'], 'decision': (decision or {}).get('decision'),
                     'acceptable_decisions': paper['acceptable_decisions'], 'is_core': bool(paper.get('is_core'))})
        for item in paper.get('statements', []):
            checked += 1
            found = _statement(record, item['path'])
            matched += bool(found) and found.get('attribution') == item['expected_attribution']
        statements += _recorded_statements(record)
        unsupported += sum(1 for path in paper.get('unsupported_statements', []) if _statement(record, path))
        if paper.get('source_sha256') != record['full_text'].get('current_sha256') or not paper.get('source_sha256'):
            unbound.append(paper['paper_id'])
    tier = declared
    note = None
    if declared == 'REAL_PAPER_E2E' and unbound:
        tier = 'SIMULATED_FLOW'
        note = ('Not reported as real-paper end-to-end: no source bytes bound for ' + ', '.join(unbound)
                + '. Bind each gold paper to the hash of the paper actually read.')
    usage = resources.summary(workspace)
    tiers = store.evidence_tiers(workspace)['counts_by_tier']
    reviewer = usage['reported_reviewer_calls']
    return {'evaluation_tier': tier, 'tier_note': note, **score_decisions(rows),
            'evidence_attribution_accuracy': _ratio(matched, checked), 'attribution_statements_checked': checked,
            'unsupported_claim_rate': _ratio(unsupported, statements), 'recorded_statements': statements,
            'computational_cost': usage,
            'reviewer_utilization': {'reported_reviewer_calls': reviewer,
                                     'reviewer_calls_below_L3': None if reviewer is None else reviewer['below_L3'],
                                     'papers_by_tier': tiers,
                                     'note': 'Reviewer calls are host-reported. Screening depths L0-L2 dispatch no reviewer.'},
            'results': rows,
            'real_paper_e2e': 'REPORTED_ABOVE' if tier == 'REAL_PAPER_E2E' else 'NOT_RUN',
            'notice': 'Scores compare recorded output with a human gold file. Missing measurements stay null; '
                      'no cost reduction is implied without a controlled comparison run.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mode', choices=['router', 'records'])
    parser.add_argument('--cases', type=Path, help='router: case file.')
    parser.add_argument('--workspace', type=Path, help='records: screening workspace an agent produced.')
    parser.add_argument('--gold', type=Path, help='records: human gold annotations.')
    args = parser.parse_args()
    if args.mode == 'router':
        result = evaluate_router(json.loads(args.cases.read_text(encoding='utf-8-sig'))['cases'])
    else:
        result = evaluate_records(args.workspace, json.loads(args.gold.read_text(encoding='utf-8-sig')))
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
