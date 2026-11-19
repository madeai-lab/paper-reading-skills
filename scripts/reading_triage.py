"""Adaptive reading depth: screening records, relevance assessment and routing guardrails.

A screening record describes what was examined below complete reading (L0-L2). It can never hold
a gate, a review or an acceptance; only a promoted L3 run with actual independent review can.
"""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from reading_run_records import RunError

SCHEMA = 1
DEPTHS = ('L0', 'L1', 'L2', 'L3')
SCREENING_DEPTHS = ('L0', 'L1', 'L2')
# Upgrades a router may propose. Any other jump needs an explicit user request.
ROUTER_TRANSITIONS = {None: ('L0',), 'L0': ('L1',), 'L1': ('L2', 'L3'), 'L2': ('L3',)}
PROMOTIONS = {'PROMOTE_TO_L1': 'L1', 'PROMOTE_TO_L2': 'L2', 'PROMOTE_TO_L3': 'L3'}
DECISIONS = set(PROMOTIONS) | {'REMAIN_AT_L1', 'REMAIN_AT_L2', 'BACKGROUND_ONLY',
                               'DEFER_FOR_EVIDENCE', 'EXCLUDE_FOR_TARGET'}
RELEVANCE_VERDICTS = {'REMAIN_AT_L1', 'REMAIN_AT_L2', 'BACKGROUND_ONLY', 'EXCLUDE_FOR_TARGET'}
DECIDERS = {'ROUTER_RULES', 'AGENT_JUDGMENT', 'USER'}
DIMENSIONS = ('topic_relevance', 'methodological_relevance', 'transferability', 'evidence_adequacy',
              'novelty_potential', 'practical_applicability', 'research_utility')
# Novelty and evidence adequacy never justify dropping a paper; these five decide exclusion.
EXCLUSION_DIMENSIONS = ('topic_relevance', 'methodological_relevance', 'transferability',
                        'practical_applicability', 'research_utility')
RATINGS = ('NONE', 'LOW', 'MEDIUM', 'HIGH')
EVIDENCE_LEVELS = {'EXAMINED_SOURCE', 'AUTHOR_STATEMENT', 'METADATA_ONLY', 'NOT_ASSESSED'}
PAPER_TYPES = {'EMPIRICAL', 'SYSTEM', 'BENCHMARK', 'CASE_STUDY', 'SURVEY', 'THEORY', 'POSITION', 'UNKNOWN'}
EMPIRICAL_TYPES = {'EMPIRICAL', 'SYSTEM', 'BENCHMARK', 'CASE_STUDY'}
METADATA_KINDS = {'TITLE', 'ABSTRACT', 'METADATA'}
VISUAL_KINDS = {'FIGURE', 'OTHER_VISUAL'}
ITEM_KINDS = METADATA_KINDS | VISUAL_KINDS | {'SECTION', 'TABLE', 'EQUATION', 'ALGORITHM', 'APPENDIX', 'SUPPLEMENT'}
READ_LEVELS = ('SKIMMED', 'READ_IN_FULL')
# CONTENT: examined parts of the paper disagree. VERSION_DIFFERENCE: a record and the attached file describe
# different versions. Only the first is settled by reading the passages in full.
CONFLICT_KINDS = {'CONTENT', 'VERSION_DIFFERENCE'}
LOCATOR_KEYS = ('physical_page', 'printed_page', 'section', 'object_label', 'panel', 'paragraph_or_cell')
ATTRIBUTIONS = {'AUTHOR_CLAIM', 'REPORTED_OBSERVATION', 'ANALYST_INFERENCE', 'FIELD_CHALLENGE'}
EVIDENCE_STATES = {'SUPPORTED', 'LIMITED', 'CONTRADICTED', 'UNDETERMINED'}
HANDOFF_KEYS = {'writer_id', 'paper_id', 'depth', 'paper_type', 'field', 'identity_check', 'examined',
                'not_examined', 'screening', 'card', 'targeted', 'conflicts', 'assessment', 'decision',
                'uncertainty_flags', 'notes_refs'}
# Acceptance vocabulary belongs to the complete-reading run and its independent reviewer.
ACCEPTANCE_KEYS = {'gate_results', 'gate_decisions', 'G0', 'G1', 'G2', 'G3', 'review_id', 'reviewer_id',
                   'reviews', 'paper_status', 'read_state', 'checked_unit_ids', 'checked_claim_ids',
                   'coverage_label', 'review_mode'}
ACCEPTANCE_VALUES = {'VERIFIED_FOR_SCOPE', 'VERIFIED_WITH_USER_REVIEW', 'CHECKED', 'ACCEPTED',
                     'COMPLETE_READING_KEY_CLAIMS_CHECKED', 'COMPLETE_INDEPENDENT_DOUBLE_READ'}
SCORE_KEY = re.compile(r'(^|_)(score|scores|total|overall|weighted|composite|aggregate)(_|$)', re.I)
TIER_BY_DEPTH = {None: 'UNSCREENED', 'L0': 'METADATA_SCREENED', 'L1': 'SKIMMED', 'L2': 'TARGETED_READ'}
SURVEY_FOCUS = ['Taxonomy and its assignment rules', 'Corpus search and selection method',
                'Comparison tables and coverage boundaries']
SKIM_PLANS = {
    'EMPIRICAL': ['Abstract', 'Introduction: research question and claimed contributions', 'Method overview',
                  'Key architecture or pipeline figure', 'Main results table or figure', 'Conclusion', 'Limitations'],
    'SURVEY': ['Abstract', 'Introduction: scope and claimed contributions', 'Survey method: search and selection',
               'Taxonomy figure or table', 'Comparison tables', 'Open problems', 'Conclusion and limitations'],
    'THEORY': ['Abstract', 'Introduction: problem and claimed results', 'Assumptions and main statements',
               'Proof strategy overview', 'Conclusion', 'Limitations and scope of the assumptions'],
    'POSITION': ['Abstract', 'Introduction: thesis', 'Core argument', 'Counter-arguments addressed', 'Conclusion'],
}


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf8')).hexdigest()


def target_binding(target):
    if not target:
        return None
    return {'target_id': target['target_id'], 'revision': target['revision'], 'sha256': canonical_sha(target)}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _texts(value, allow_empty=True):
    return isinstance(value, list) and all(_text(x) for x in value) and (allow_empty or bool(value))


def _fail(code, message):
    raise RunError(code, message)


def _local_file(directory, ref):
    """An existing file inside this paper's workspace; no absolute or parent-directory escapes."""
    if not _text(ref):
        return False
    base = Path(directory).resolve()
    path = (base/ref.split('#', 1)[0]).resolve()
    return path.is_relative_to(base) and path.is_file()


def check_schema(record):
    if (not isinstance(record, dict) or record.get('screening_schema_version') != SCHEMA
            or record.get('record_kind') != 'SCREENING_RECORD'):
        _fail('UNSUPPORTED_SCREENING_SCHEMA',
              'This helper reads screening schema %d only; other versions are neither migrated nor rewritten.' % SCHEMA)
    return record


def new_record(paper_id, identity, source_record):
    return {'screening_schema_version': SCHEMA, 'record_kind': 'SCREENING_RECORD', 'paper_id': paper_id,
            'identity': {**{k: None for k in ['title', 'authors', 'year', 'venue', 'doi', 'arxiv_id', 'url', 'field']},
                         **identity, 'paper_type': 'UNKNOWN', 'identity_state': 'METADATA_ONLY'},
            'source_records': [source_record], 'possible_duplicate_of': [],
            'full_text': {'access_state': 'NOT_ATTEMPTED', 'missing_reason': None,
                          'current_sha256': None, 'versions': []},
            'depth': {'user_requested': None, 'user_request': None},
            'passes': [], 'assessments': [], 'decisions': [], 'upgrade_history': [],
            'l3': None, 'independent_review': 'NONE'}


# ---------------------------------------------------------------- derived views

def pass_current(record, row):
    return (row.get('status') == 'CURRENT'
            and row.get('source_sha256') in (None, record['full_text'].get('current_sha256')))


def current_passes(record):
    rows = [row for row in record.get('passes', []) if pass_current(record, row)]
    return sorted(rows, key=lambda row: DEPTHS.index(row['depth']))


def effective_depth(record):
    """Highest screening depth still valid for the current source version."""
    rows = current_passes(record)
    return rows[-1]['depth'] if rows else None


def examined_items(record):
    """Items examined in valid passes; a deeper pass may restate an item at a higher read level."""
    items = {}
    for row in current_passes(record):
        for item in row.get('examined', []):
            items[item['item_id']] = item
    return items


def latest_pass(record, depth):
    return next((row for row in reversed(current_passes(record)) if row['depth'] == depth), None)


def deepest_pass(record):
    rows = current_passes(record)
    return rows[-1] if rows else None


def uncertainty_flags(record):
    """Flags of the deepest valid pass. Each pass restates what is still uncertain; an earlier pass's
    "body not read" would contradict a later reading if both were shown."""
    return list((deepest_pass(record) or {}).get('uncertainty_flags', []))


def not_examined(record):
    """What the deepest valid pass left unexamined; earlier lists are superseded by it, and kept in the passes."""
    return list((deepest_pass(record) or {}).get('not_examined', []))


def open_conflicts(record):
    latest = {}
    for row in current_passes(record):  # ascending depth: a deeper pass restates an earlier conflict
        for conflict in row.get('conflicts', []):
            latest[conflict['conflict_id']] = conflict
    return [conflict for conflict in latest.values() if conflict.get('status') == 'OPEN']


def criterion_sha(criterion):
    return canonical_sha({'id': criterion['id'], 'text': criterion['text']})


def current_decision(record, target, criteria=None):
    """Return (decision, stale_reason). A changed target, source version or cited criterion suspends a decision.

    criteria maps stated criterion IDs to their hash; None skips that comparison.
    """
    if not record.get('decisions'):
        return None, None
    decision = record['decisions'][-1]
    if decision.get('target') != target_binding(target):
        return None, 'TARGET_CHANGED'
    if decision.get('source_sha256') not in (None, record['full_text'].get('current_sha256')):
        return None, 'SOURCE_VERSION_CHANGED'
    if (criteria is not None and decision.get('criterion_sha256')
            and criteria.get(decision.get('exclusion_criterion')) != decision['criterion_sha256']):
        return None, 'CRITERION_CHANGED'
    return decision, None


def decision_current(record, decision, target, criteria=None):
    return decision is record['decisions'][-1] and current_decision(record, target, criteria)[0] is decision


def current_assessment(record, target):
    binding = target_binding(target)
    for row in reversed(record.get('assessments', [])):
        if row.get('target') == binding and row.get('source_sha256') in (None, record['full_text'].get('current_sha256')):
            return row
    return None


def coverage_summary(record):
    items = examined_items(record)
    kinds = {}
    for item in items.values():
        kinds[item['kind']] = kinds.get(item['kind'], 0) + 1
    version = next((v for v in record['full_text']['versions']
                    if v['sha256'] == record['full_text'].get('current_sha256')), None)
    pages = sorted({p for item in items.values() if item['kind'] not in METADATA_KINDS
                    for p in item.get('pages', [])})
    return {'examined_item_count': len(items), 'examined_by_kind': dict(sorted(kinds.items())),
            'read_in_full_item_ids': sorted(i for i, x in items.items() if x['read_level'] == 'READ_IN_FULL'),
            'pages_with_examined_items': pages,
            'page_count': (version or {}).get('extraction', {}).get('page_count'),
            'not_examined': not_examined(record),
            'full_text_access': record['full_text']['access_state'],
            'complete_paper_coverage': False,
            'notice': 'Counts locate what was examined; they do not establish understanding or complete reading.'}


def skim_plan(paper_type, research=False):
    """Navigation priorities for an evidence-aware skim; the skim records what was actually opened."""
    key = paper_type if paper_type in SKIM_PLANS else ('EMPIRICAL' if paper_type in EMPIRICAL_TYPES | {'UNKNOWN'} else paper_type)
    required = ['research_problem', 'claimed_contributions', 'core_method', 'potential_limitations']
    required.append('taxonomy_or_scope' if paper_type == 'SURVEY' else 'headline_evidence')
    return {'paper_type': paper_type, 'priority_reading': SKIM_PLANS.get(key, SKIM_PLANS['EMPIRICAL']),
            'required_card_fields': ['research_problem', 'core_method'] if research else required,
            'notice': 'A plan is navigation. Record the sections, figures and tables actually examined and those not examined.'}


# ---------------------------------------------------------------- handoff validation

def _scan_forbidden(value, where):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ACCEPTANCE_KEYS:
                _fail('ACCEPTANCE_FIELDS_FORBIDDEN', f'{where}: "{key}" belongs to a complete-reading run and its independent '
                      'reviewer. A screening record cannot carry gates, reviews or acceptance.')
            _scan_forbidden(item, where)
    elif isinstance(value, list):
        for item in value:
            _scan_forbidden(item, where)
    elif isinstance(value, str) and value in ACCEPTANCE_VALUES:
        _fail('ACCEPTANCE_FIELDS_FORBIDDEN', f'{where}: "{value}" is an acceptance state; screening depth cannot claim it.')


def _scan_scores(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if SCORE_KEY.search(key):
                _fail('COMPOSITE_SCORE_FORBIDDEN', f'Keep the dimensions separate; "{key}" would merge them into an unverified score.')
            _scan_scores(item)
    elif isinstance(value, list):
        for item in value:
            _scan_scores(item)


def _items(record, payload, depth, paper_dir):
    rows = payload.get('examined')
    if not isinstance(rows, list) or not rows or any(not isinstance(x, dict) for x in rows):
        _fail('INVALID_SCREENING_HANDOFF', 'List every item actually examined in this pass.')
    sha = record['full_text'].get('current_sha256')
    version = next((v for v in record['full_text']['versions'] if v['sha256'] == sha), None)
    page_count = (version or {}).get('extraction', {}).get('page_count')
    records = {r['record_id'] for r in record['source_records']}
    result, seen = [], set()
    for row in rows:
        uid = row.get('item_id')
        if not isinstance(uid, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', uid) or uid in seen:
            _fail('INVALID_SCREENING_HANDOFF', 'Examined items need unique safe item_id values.')
        seen.add(uid)
        kind = row.get('kind')
        if kind not in ITEM_KINDS or not _text(row.get('label')) or row.get('read_level') not in READ_LEVELS:
            _fail('INVALID_SCREENING_HANDOFF', f'{uid}: give kind, label and read_level (SKIMMED or READ_IN_FULL).')
        item = {'item_id': uid, 'kind': kind, 'label': row['label'].strip(), 'read_level': row['read_level'],
                'note': row.get('note') or ''}
        if kind == 'SECTION' and item['label'].casefold().startswith(('abstract', '摘要')):
            _fail('INVALID_SCREENING_HANDOFF', f'{uid}: record the abstract as kind ABSTRACT. It is what the authors state, '
                  'wherever it was read.')
        in_body = kind == 'ABSTRACT' and depth != 'L0' and isinstance(row.get('locator'), dict)
        if kind in METADATA_KINDS and not in_body:
            if row.get('source_ref') not in records:
                _fail('INVALID_SCREENING_HANDOFF', f'{uid}: metadata items cite the imported record they came from.')
            item.update(source_ref=row['source_ref'], source_sha256=None)
        else:
            if depth == 'L0':
                _fail('DEPTH_BOUNDARY', f'{uid}: L0 examines metadata only. Opening the paper body is an L1 skim; '
                      'record it at that depth instead of calling it metadata screening.')
            locator = row.get('locator')
            if (not isinstance(locator, dict) or not any(locator.get(k) not in (None, '') for k in
                                                         ('physical_page', 'section', 'object_label'))):
                _fail('INVALID_SCREENING_HANDOFF', f'{uid}: locate the examined content by page, section or object label.')
            from reading_scope import check_item
            check_item(record, locator, row.get('artifact_refs'), paper_dir)
            pages = locator.get('physical_page')
            pages = [] if pages is None else pages if isinstance(pages, list) else [pages]
            if any(type(p) is not int or p < 1 or (page_count and p > page_count) for p in pages):
                _fail('INVALID_SCREENING_HANDOFF', f'{uid}: physical pages must exist in the attached source; never guess a page.')
            kept = {key: locator[key] for key in (*LOCATOR_KEYS, 'bbox') if locator.get(key) not in (None, '')}
            if any(not isinstance(value, (str, int, list)) or isinstance(value, bool) for value in kept.values()):
                _fail('INVALID_SCREENING_HANDOFF', f'{uid}: locator values are page numbers or short labels.')
            item.update(locator=kept, pages=pages, source_sha256=sha)
            if kind in VISUAL_KINDS:
                refs = row.get('artifact_refs') or []
                viewed = row.get('actually_viewed') is True
                if viewed and (not _texts(refs, allow_empty=False)
                               or any(not _local_file(paper_dir, ref) for ref in refs)):
                    _fail('INVALID_SCREENING_HANDOFF', f'{uid}: a viewed figure links the image actually opened, '
                          'inside this paper workspace.')
                if not viewed and row.get('caption_only') is not True:
                    _fail('INVALID_SCREENING_HANDOFF', f'{uid}: either open the figure (actually_viewed with artifact_refs) '
                          'or mark caption_only. A caption is not the figure.')
                if not viewed and row['read_level'] == 'READ_IN_FULL':
                    _fail('INVALID_SCREENING_HANDOFF', f'{uid}: a caption-only figure was not read in full.')
                item.update(actually_viewed=viewed, caption_only=not viewed, artifact_refs=list(refs))
            elif row.get('artifact_refs'):
                refs = row['artifact_refs']
                if not _texts(refs, allow_empty=False) or any(not _local_file(paper_dir, ref) for ref in refs):
                    _fail('INVALID_SCREENING_HANDOFF', f'{uid}: artifact_refs are images inside this paper workspace.')
                item.update(artifact_refs=list(refs), checked_against_image=row.get('actually_viewed') is True)
        result.append(item)
    if depth == 'L0' and not any(x['kind'] in METADATA_KINDS for x in result):
        _fail('INVALID_SCREENING_HANDOFF', 'L0 names the metadata actually used.')
    if depth != 'L0' and not any(_grounded(x) for x in result):
        _fail('DEPTH_BOUNDARY', 'No part of the paper body was examined; this is metadata screening (L0), not a skim.')
    return result


def _grounded(item):
    """Body content actually read or seen, as opposed to metadata or a caption."""
    return item['kind'] not in METADATA_KINDS and not item.get('caption_only')


def _statement(row, items, where, attributions=ATTRIBUTIONS):
    if not isinstance(row, dict) or not _text(row.get('text')) or row.get('attribution') not in attributions:
        _fail('INVALID_SCREENING_HANDOFF', f'{where}: give text and an attribution from {sorted(attributions)}.')
    refs = row.get('from_items')
    if not _texts(refs, allow_empty=False) or any(ref not in items for ref in refs):
        _fail('UNSUPPORTED_STATEMENT', f'{where}: cite the examined items this statement comes from.')
    if row['attribution'] == 'REPORTED_OBSERVATION' and not any(_grounded(items[ref]) for ref in refs):
        _fail('ATTRIBUTION_UNSUPPORTED', f'{where}: an abstract, title or caption is what the authors state. '
              'Use AUTHOR_CLAIM, or examine the result itself before recording an observation.')
    if row.get('verification', 'NOT_VERIFIED') != 'NOT_VERIFIED':
        _fail('ATTRIBUTION_UNSUPPORTED', f'{where}: screening and skim statements stay NOT_VERIFIED.')
    return {'text': row['text'].strip(), 'attribution': row['attribution'], 'from_items': list(refs),
            'verification': 'NOT_VERIFIED'}


def _statements(rows, items, where, allow_empty=True, attributions=ATTRIBUTIONS):
    if not isinstance(rows, list) or (not rows and not allow_empty):
        _fail('INVALID_SCREENING_HANDOFF', f'{where}: provide a list of sourced statements.')
    return [_statement(row, items, f'{where}[{i}]', attributions) for i, row in enumerate(rows)]


def _flags(payload):
    rows = payload.get('uncertainty_flags')
    if not isinstance(rows, list):
        _fail('INVALID_SCREENING_HANDOFF', 'State uncertainty_flags explicitly (an empty list if none were found).')
    result = []
    for row in rows:
        row = {'code': row, 'detail': ''} if isinstance(row, str) else row
        if not isinstance(row, dict) or not _text(row.get('code')):
            _fail('INVALID_SCREENING_HANDOFF', 'Each uncertainty flag needs a code and a detail.')
        result.append({'code': row['code'].strip().upper().replace(' ', '_'), 'detail': row.get('detail') or ''})
    return result


def _conflicts(payload, items):
    result = []
    for row in payload.get('conflicts') or []:
        if (not isinstance(row, dict) or not _text(row.get('conflict_id')) or not _text(row.get('description'))
                or row.get('status') not in {'OPEN', 'EXPLAINED'}
                or not _texts(row.get('items'), allow_empty=False) or any(i not in items for i in row['items'])):
            _fail('INVALID_SCREENING_HANDOFF', 'A conflict names its examined items, a description and OPEN or EXPLAINED.')
        if row['status'] == 'EXPLAINED' and not _text(row.get('explanation')):
            _fail('INVALID_SCREENING_HANDOFF', 'An explained conflict states the explanation that was checked.')
        if row.get('kind', 'CONTENT') not in CONFLICT_KINDS:
            _fail('INVALID_SCREENING_HANDOFF', 'Conflict kind is one of: ' + ', '.join(sorted(CONFLICT_KINDS)))
        result.append({**{k: copy.deepcopy(row.get(k)) for k in ['conflict_id', 'description', 'items', 'status', 'explanation']},
                       'kind': row.get('kind', 'CONTENT')})
    return result


def _card(payload, items, paper_type, flags, research=False):
    card = payload.get('card')
    if not isinstance(card, dict):
        _fail('INVALID_SCREENING_HANDOFF', 'An L1 skim returns a card.')
    result = {'research_problem': _statement(card.get('research_problem'), items, 'card.research_problem'),
              'claimed_contributions': _statements(card.get('claimed_contributions', []), items, 'card.claimed_contributions',
                                                   allow_empty=research, attributions={'AUTHOR_CLAIM'}),
              'core_method': _statement(card.get('core_method'), items, 'card.core_method'),
              'headline_evidence': _statements(card.get('headline_evidence', []), items, 'card.headline_evidence'),
              'potential_limitations': _statements(card.get('potential_limitations', []), items, 'card.potential_limitations')}
    codes = {flag['code'] for flag in flags}
    if research:
        if card.get('taxonomy_or_scope'):
            result['taxonomy_or_scope'] = _statement(card['taxonomy_or_scope'], items, 'card.taxonomy_or_scope')
        return result
    if paper_type == 'SURVEY':
        # A survey contributes a classification, not experiments; never ask it for invented results.
        result['taxonomy_or_scope'] = _statement(card.get('taxonomy_or_scope'), items, 'card.taxonomy_or_scope')
    elif paper_type in EMPIRICAL_TYPES and not result['headline_evidence'] and 'HEADLINE_EVIDENCE_NOT_FOUND' not in codes:
        _fail('INVALID_SCREENING_HANDOFF', 'Record the headline evidence examined, or flag HEADLINE_EVIDENCE_NOT_FOUND.')
    if not result['potential_limitations'] and 'LIMITATIONS_NOT_FOUND' not in codes:
        _fail('INVALID_SCREENING_HANDOFF', 'Record potential limitations, or flag LIMITATIONS_NOT_FOUND for the examined parts.')
    return result


def _targeted(payload, items, target, research=False):
    data = payload.get('targeted')
    if not isinstance(data, dict):
        _fail('INVALID_SCREENING_HANDOFF', 'An L2 pass returns its focus and local claims.')
    if not target and not research:
        _fail('TARGET_REQUIRED', 'Legacy targeted reading requires its explicit target.')
    questions = {q['id'] for q in target['questions']} if target else set()
    focus = {}
    for row in data.get('focus') or []:
        if (not isinstance(row, dict) or not _text(row.get('focus_id')) or not _text(row.get('description'))
                or not _texts(row.get('question_ids'), allow_empty=not target) or set(row['question_ids']) - questions
                or not _texts(row.get('items'), allow_empty=False) or any(i not in items for i in row['items'])
                or row['focus_id'] in focus):
            _fail('INVALID_SCREENING_HANDOFF', 'Each focus has an ID, a description, current target question IDs and examined items.')
        if not any(items[i]['read_level'] == 'READ_IN_FULL' and _grounded(items[i]) for i in row['items']):
            _fail('DEPTH_BOUNDARY', f"{row['focus_id']}: targeted reading reads its focus content in full, with the context it needs.")
        focus[row['focus_id']] = {k: copy.deepcopy(row[k]) for k in ['focus_id', 'description', 'question_ids', 'items']}
    if not focus:
        _fail('INVALID_SCREENING_HANDOFF', 'Name at least one focus tied to the research target.')
    claims, seen = [], set()
    for row in data.get('local_claims') or []:
        cid = row.get('claim_id') if isinstance(row, dict) else None
        if (not _text(cid) or cid in seen or not _text(row.get('text')) or row.get('attribution') not in ATTRIBUTIONS
                or row.get('focus_id') not in focus or row.get('evidence_state') not in EVIDENCE_STATES):
            _fail('INVALID_SCREENING_HANDOFF', 'Local claims need a unique ID, text, attribution, focus_id and evidence_state.')
        seen.add(cid)
        supporting = row.get('supporting_items') or []
        conflicting = row.get('conflicting_items') or []
        for ref in supporting + conflicting:
            if ref not in items:
                _fail('UNSUPPORTED_STATEMENT', f'{cid}: evidence items must have been examined in this record.')
            if items[ref]['read_level'] != 'READ_IN_FULL' or not _grounded(items[ref]):
                _fail('UNSUPPORTED_STATEMENT', f'{cid}: {ref} was only skimmed, is metadata or is a caption. Judge evidence '
                      'only on content read in full; otherwise leave the claim UNDETERMINED.')
        state = row['evidence_state']
        if state in {'SUPPORTED', 'LIMITED'} and not supporting:
            _fail('UNSUPPORTED_STATEMENT', f'{cid}: {state} needs supporting items read in full.')
        if state == 'CONTRADICTED' and not conflicting:
            _fail('UNSUPPORTED_STATEMENT', f'{cid}: name the examined items that contradict the claim.')
        if row['attribution'] == 'REPORTED_OBSERVATION' and not (supporting or conflicting):
            _fail('ATTRIBUTION_UNSUPPORTED', f'{cid}: an observation names the examined content it was observed in. '
                  'Without it the statement is an author claim or an analyst inference.')
        if state == 'UNDETERMINED' and not _texts(row.get('missing_evidence'), allow_empty=False):
            _fail('UNSUPPORTED_STATEMENT', f'{cid}: state which evidence is missing instead of guessing a verdict.')
        if not _texts(row.get('conditions') or []):
            _fail('INVALID_SCREENING_HANDOFF', f'{cid}: conditions must be a list of strings.')
        claims.append({'claim_id': cid, 'text': row['text'].strip(), 'attribution': row['attribution'],
                       'focus_id': row['focus_id'], 'evidence_state': state,
                       'supporting_items': list(supporting), 'conflicting_items': list(conflicting),
                       'conditions': list(row.get('conditions') or []), 'limits': row.get('limits') or '',
                       'missing_evidence': list(row.get('missing_evidence') or []),
                       'independent_review': False})
    if not claims:
        _fail('INVALID_SCREENING_HANDOFF', 'Targeted reading records local claim-to-evidence links, including undetermined ones.')
    if not _text(data.get('scope_statement')):
        _fail('INVALID_SCREENING_HANDOFF', 'State what this targeted pass covers and what it leaves unread.')
    return {'focus': list(focus.values()), 'local_claims': claims, 'scope_statement': data['scope_statement'].strip(),
            'complete_paper_verified': False}


def validate_assessment(record, assessment, depth, target, items):
    """A multi-dimensional, sourced relevance judgement. No composite score is accepted."""
    if not target:
        _fail('TARGET_REQUIRED', 'Relevance is judged against an explicit research target; without one, omit the assessment.')
    if not isinstance(assessment, dict):
        _fail('INVALID_ASSESSMENT', 'The assessment must be an object.')
    _scan_scores(assessment)
    dimensions = assessment.get('dimensions')
    if not isinstance(dimensions, dict) or set(dimensions) != set(DIMENSIONS):
        _fail('INVALID_ASSESSMENT', 'Rate exactly these dimensions separately: ' + ', '.join(DIMENSIONS))
    result = {}
    unknown = []
    for name in DIMENSIONS:
        row = dimensions[name]
        if (not isinstance(row, dict) or row.get('rating') not in RATINGS + ('UNKNOWN',)
                or not _text(row.get('basis')) or row.get('evidence_level') not in EVIDENCE_LEVELS):
            _fail('INVALID_ASSESSMENT', f'{name}: give an ordinal rating (or UNKNOWN), its basis and its evidence_level.')
        refs = row.get('refs') or []
        if not _texts(refs) or any(ref not in items for ref in refs):
            _fail('INVALID_ASSESSMENT', f'{name}: refs must name examined items.')
        level = row['evidence_level']
        if row['rating'] == 'UNKNOWN':
            unknown.append(name)
        elif level == 'NOT_ASSESSED':
            _fail('INVALID_ASSESSMENT', f'{name}: a rating needs a basis that was assessed; otherwise use UNKNOWN.')
        elif not refs:
            _fail('INVALID_ASSESSMENT', f'{name}: cite the examined items this rating was judged from.')
        if level == 'EXAMINED_SOURCE' and not any(_grounded(items[ref]) for ref in refs):
            _fail('INVALID_ASSESSMENT', f'{name}: EXAMINED_SOURCE needs body content that was actually examined. '
                  'An abstract is AUTHOR_STATEMENT or METADATA_ONLY.')
        result[name] = {'rating': row['rating'], 'basis': row['basis'].strip(), 'evidence_level': level, 'refs': list(refs)}
    if depth == 'L0' and result['evidence_adequacy']['rating'] != 'UNKNOWN':
        _fail('DEPTH_BOUNDARY', 'evidence_adequacy stays UNKNOWN at L0: an abstract cannot establish experimental quality.')
    uncertainty = assessment.get('uncertainty')
    if (not isinstance(uncertainty, dict) or uncertainty.get('level') not in {'LOW', 'MEDIUM', 'HIGH'}
            or not _texts(uncertainty.get('missing_information'))):
        _fail('INVALID_ASSESSMENT', 'Record uncertainty: a level and the missing information.')
    if unknown and not uncertainty['missing_information']:
        _fail('INVALID_ASSESSMENT', 'Name the missing information behind each UNKNOWN dimension: ' + ', '.join(unknown))
    links = assessment.get('target_links')
    questions = {q['id'] for q in target['questions']}
    if (not isinstance(links, list) or any(not isinstance(x, dict) or x.get('question_id') not in questions
                                           or not _text(x.get('relation')) for x in links)):
        _fail('INVALID_ASSESSMENT', 'target_links tie the paper to current target questions with a stated relation.')
    related = any(result[name]['rating'] in {'MEDIUM', 'HIGH'} for name in EXCLUSION_DIMENSIONS)
    if related and not links:
        _fail('INVALID_ASSESSMENT', 'State the concrete link to the research questions that the ratings rely on.')
    for key in ['mechanisms_worth_study', 'author_stated_only']:
        if not _texts(assessment.get(key, [])):
            _fail('INVALID_ASSESSMENT', key + ' must be a list of strings.')
    points = assessment.get('evidenced_points', [])
    if (not isinstance(points, list) or any(not isinstance(x, dict) or not _text(x.get('text'))
                                            or not _texts(x.get('refs'), allow_empty=False)
                                            or any(ref not in items or not _grounded(items[ref]) for ref in x['refs'])
                                            for x in points)):
        _fail('INVALID_ASSESSMENT', 'evidenced_points cite body items actually examined; move the rest to author_stated_only.')
    if not _text(assessment.get('depth_rationale')) or not _texts(assessment.get('decision_changers'), allow_empty=False):
        _fail('INVALID_ASSESSMENT', 'Explain the recommended depth and which new evidence would change it.')
    return {'depth': depth, 'target': target_binding(target), 'dimensions': result,
            'uncertainty': {'level': uncertainty['level'], 'missing_information': list(uncertainty['missing_information'])},
            'target_links': [{'question_id': x['question_id'], 'relation': x['relation'].strip()} for x in links],
            'mechanisms_worth_study': list(assessment.get('mechanisms_worth_study', [])),
            'evidenced_points': [{'text': x['text'].strip(), 'refs': list(x['refs'])} for x in points],
            'author_stated_only': list(assessment.get('author_stated_only', [])),
            'depth_rationale': assessment['depth_rationale'].strip(),
            'decision_changers': list(assessment['decision_changers']),
            'novelty_externally_checked': False, 'independent_review': False}


def unmet_floor(record):
    """The user-requested depth that automatic routing may not undercut, or None.

    A request for complete reading is met only by an accepted run, which this record cannot see, so it
    keeps binding the router. Lower requests are met once that depth has been reached.
    """
    floor = record['depth'].get('user_requested')
    if floor and (floor == 'L3' or _index(effective_depth(record)) < _index(floor)):
        return floor
    return None


def _index(depth):
    return -1 if depth is None else DEPTHS.index(depth)


def depth_ceiling(record, workspace_ceiling=None):
    """The deepest reading the user allowed for this paper, or None when unlimited.

    A limit recorded on the paper replaces the workspace-wide one, including when the user lifted it.
    """
    own = record['depth'].get('ceiling')
    return own.get('depth') if isinstance(own, dict) else workspace_ceiling


def standing_instructions(record, workspace_limit=None):
    """What the user said about how far to read this paper, in the user's words, oldest first.

    A depth can be enforced; a scope ("only the appendix") cannot be parsed, so it is shown wherever the
    next step is decided and stays in force until the user says otherwise.
    """
    rows = []
    if isinstance(workspace_limit, dict) and workspace_limit.get('user_instruction'):
        rows.append({'applies_to': 'WORKSPACE', 'kind': 'LIMIT', 'depth': workspace_limit.get('depth'),
                     'user_instruction': workspace_limit['user_instruction'], 'at': workspace_limit.get('at')})
    for row in record.get('depth_requests', []):
        rows.append({'applies_to': 'PAPER', 'kind': 'LIMIT' if 'limit' in row else 'REQUEST',
                     'depth': row.get('limit', row.get('depth')), 'user_instruction': row['user_instruction'], 'at': row.get('at')})
    return sorted(rows, key=lambda row: row.get('at') or '')


def limit_depth(record, depth, instruction):
    """Record that the user limited how deep this paper may be read ("abstract only", a time budget)."""
    check_schema(record)
    if depth not in SCREENING_DEPTHS or not _text(instruction):
        _fail('USER_INSTRUCTION_REQUIRED', 'Give the deepest allowed depth (L0, L1 or L2) and what the user actually asked.')
    record = copy.deepcopy(record)
    record['depth']['ceiling'] = {'depth': depth, 'user_instruction': instruction.strip(), 'at': now()}
    if _index(record['depth'].get('user_requested')) > _index(depth):
        # The later instruction wins: an earlier request for more is withdrawn, visibly.
        record['depth'].update(user_requested=None, user_request=None)
    record.setdefault('depth_requests', []).append({'limit': depth, 'user_instruction': instruction.strip(), 'at': now()})
    return record


def upgrade_trigger(record, depth, target, ceiling=None):
    """Find what authorizes moving to a deeper level; no silent upgrades."""
    current = effective_depth(record)
    limit = depth_ceiling(record, ceiling)
    if limit is not None and _index(depth) > _index(limit):
        _fail('USER_DEPTH_CEILING', f'The user limited this reading to {limit}. A recommendation to go deeper can be recorded; '
              f'reading at {depth} needs the user to ask for it (request-depth).')
    if depth == 'L3' and record.get('reading_policy') == 2 and record['depth'].get('user_requested') != 'L3':
        _fail('UPGRADE_NOT_AUTHORIZED', 'Complete verification needs a user mandate; relevance or a recommendation is not one.')
    if _index(depth) <= _index(current):
        return {'kind': 'REVISION', 'ref': None}
    if depth == 'L0':
        return {'kind': 'INITIAL_SCREENING', 'ref': None}
    earlier = next((row for row in record['passes'] if row['status'] == 'STALE_SOURCE_VERSION'
                    and _index(row['depth']) >= _index(depth)), None)
    if earlier:
        # A depth already authorized for another version of this paper may be redone on the current one.
        return {'kind': 'REEXAMINE_NEW_VERSION', 'ref': earlier['pass_id']}
    floor = record['depth'].get('user_requested')
    if floor and _index(floor) >= _index(depth):
        return {'kind': 'USER_REQUEST', 'ref': record['depth'].get('user_request')}
    decision, _ = current_decision(record, target)
    if decision and PROMOTIONS.get(decision['decision']) == depth:
        if decision['decided_by'] != 'USER' and depth not in ROUTER_TRANSITIONS.get(current, ()):
            _fail('ILLEGAL_TRANSITION', f'A router decision cannot jump from {current} to {depth}.')
        return {'kind': 'DECISION', 'ref': decision['decision_id']}
    _fail('UPGRADE_NOT_AUTHORIZED', f'Moving from {current or "unscreened"} to {depth} needs a current PROMOTE_TO_{depth} '
          'decision or an explicit user request. Record the routing decision first.')


def apply_handoff(record, payload, target, paper_dir, handoff_ref, ceiling=None, criteria=None, decide=True):
    """Validate one screening pass and return the updated record; the input record is not modified."""
    check_schema(record)
    if isinstance(payload, dict):
        payload = {key: value for key, value in payload.items() if not str(key).startswith('_')}  # scaffold guidance
    if not isinstance(payload, dict) or payload.keys() - HANDOFF_KEYS:
        _fail('INVALID_SCREENING_HANDOFF', 'Unknown screening handoff fields: '
              + ', '.join(sorted(payload.keys() - HANDOFF_KEYS)) if isinstance(payload, dict) else 'Use a JSON object.')
    _scan_forbidden(payload, 'handoff')
    depth = payload.get('depth')
    if depth == 'L3':
        _fail('DEPTH_BOUNDARY', 'L3 is a complete-reading run with its own gates. Use promote, then the run controller.')
    if depth not in SCREENING_DEPTHS or not _text(payload.get('writer_id')) or payload.get('paper_id') != record['paper_id']:
        _fail('INVALID_SCREENING_HANDOFF', 'Give the actual writer_id, this paper_id and depth L0, L1 or L2.')
    current = effective_depth(record)
    if _index(depth) < _index(current):
        _fail('DEPTH_REGRESSION', f'This paper is at {current}; revise that pass rather than resubmitting {depth}.')
    trigger = upgrade_trigger(record, depth, target, ceiling)
    record = copy.deepcopy(record)
    sha = record['full_text'].get('current_sha256')
    if depth != 'L0':
        if not sha:
            _fail('FULL_TEXT_REQUIRED', 'A skim or targeted pass reads the paper itself. Attach the full text, or keep L0 and '
                  'record DEFER_FOR_EVIDENCE; do not infer the body from the abstract.')
        check = payload.get('identity_check')
        if not isinstance(check, dict) or check.get('state') not in {'VERIFIED_AGAINST_SOURCE', 'MISMATCH'} or not _text(check.get('basis')):
            _fail('INVALID_SCREENING_HANDOFF', 'Compare the attached source with the metadata: identity_check {state, basis}.')
        if check['state'] == 'MISMATCH':
            _fail('IDENTITY_MISMATCH', 'The attached file is not this paper. Isolate it and attach the correct version; '
                  'nothing was recorded from the mismatched source.')
        record['identity']['identity_state'] = 'VERIFIED_AGAINST_SOURCE'
        record['identity']['identity_basis'] = check['basis'].strip()
    paper_type = payload.get('paper_type', record['identity']['paper_type'])
    if paper_type not in PAPER_TYPES or (depth != 'L0' and paper_type == 'UNKNOWN'):
        _fail('INVALID_SCREENING_HANDOFF', 'Classify paper_type' + (' (not UNKNOWN after opening the paper).' if depth != 'L0' else '.'))
    record['identity']['paper_type'] = paper_type
    if _text(payload.get('field')):
        record['identity']['field'] = payload['field'].strip()
    new_items = _items(record, payload, depth, paper_dir)
    not_examined = payload.get('not_examined')
    if (not isinstance(not_examined, list) or any(not isinstance(x, dict) or not _text(x.get('label')) or not _text(x.get('reason'))
                                                  for x in not_examined)):
        _fail('INVALID_SCREENING_HANDOFF', 'not_examined rows need a label and a reason.')
    if depth != 'L0' and not not_examined:
        _fail('COVERAGE_BOUNDARY_MISSING', f'{depth} does not cover the whole paper. List the content that was not examined.')
    flags = _flags(payload)
    for ref in payload.get('notes_refs') or []:
        if not _local_file(paper_dir, ref):
            _fail('INVALID_SCREENING_HANDOFF', 'notes_refs must be existing files inside this paper workspace.')
    serial = sum(1 for row in record['passes'] if row['depth'] == depth) + 1
    entry = {'pass_id': f'{depth}-{serial:02}', 'depth': depth, 'writer_id': payload['writer_id'],
             'submitted_at': now(), 'target': target_binding(target), 'source_sha256': None if depth == 'L0' else sha,
             'handoff_ref': handoff_ref, 'status': 'CURRENT', 'examined': new_items,
             'not_examined': copy.deepcopy(not_examined), 'uncertainty_flags': flags,
             'notes_refs': list(payload.get('notes_refs') or []), 'independent_review': False}
    for row in record['passes']:
        if row['depth'] == depth and row['status'] == 'CURRENT':
            row['status'] = 'SUPERSEDED' if row['source_sha256'] == entry['source_sha256'] else 'STALE_SOURCE_VERSION'
    record['passes'].append(entry)
    items = examined_items(record)
    entry['conflicts'] = _conflicts(payload, items)
    if depth == 'L0':
        data = payload.get('screening')
        if not isinstance(data, dict) or data.get('full_text_read') is not False:
            _fail('DEPTH_BOUNDARY', 'L0 states full_text_read: false. It never claims the paper was read.')
        entry['screening'] = {'potential_value': _statements(data.get('potential_value', []), items, 'screening.potential_value',
                                                             attributions={'AUTHOR_CLAIM', 'ANALYST_INFERENCE'}),
                              'full_text_read': False}
    elif depth == 'L1':
        entry['card'] = _card(payload, items, paper_type, flags, record.get('reading_policy') == 2)
    else:
        entry['targeted'] = _targeted(payload, items, target, record.get('reading_policy') == 2)
    if current != depth:
        record['upgrade_history'].append({'from': current, 'to': depth, 'at': entry['submitted_at'], 'trigger': trigger,
                                          'pass_id': entry['pass_id'], 'source_sha256': entry['source_sha256'],
                                          'reused_pass_ids': [row['pass_id'] for row in current_passes(record)
                                                              if row['pass_id'] != entry['pass_id']],
                                          'completion_inherited': False})
    assessment = payload.get('assessment')
    if target and assessment is None:
        _fail('ASSESSMENT_REQUIRED', 'A research target is bound: assess the dimensions for it, with UNKNOWN where evidence is missing.')
    if assessment is not None:
        row = validate_assessment(record, assessment, depth, target, items)
        row.update(assessment_id=f'A{len(record["assessments"]) + 1:02}', pass_id=entry['pass_id'],
                   source_sha256=entry['source_sha256'], assessed_at=entry['submitted_at'])
        record['assessments'].append(row)
    if not decide:
        return record  # preview of a pass before its routing decision is written
    if payload.get('decision') is not None:
        record = apply_decision(record, payload['decision'], target, criteria, ceiling)
    elif depth == 'L1':
        _fail('INVALID_SCREENING_HANDOFF', 'A skim ends with a reading recommendation: include the routing decision.')
    return record


# ---------------------------------------------------------------- routing

def _rank(assessment, name):
    rating = assessment['dimensions'][name]['rating']
    return None if rating == 'UNKNOWN' else RATINGS.index(rating)


def recommend(record, assessment, ceiling=None):
    """Transparent rule baseline. It proposes; it is neither an independent review nor a relevance score."""
    depth = effective_depth(record)
    paper_type = record['identity']['paper_type']
    trace = []
    rank = {name: _rank(assessment, name) for name in DIMENSIONS}
    at_least = lambda name, level: rank[name] is not None and rank[name] >= RATINGS.index(level)
    unknown = [name for name in EXCLUSION_DIMENSIONS if rank[name] is None]
    core = at_least('research_utility', 'HIGH') and (at_least('topic_relevance', 'HIGH') or at_least('methodological_relevance', 'HIGH'))
    mechanism = (at_least('methodological_relevance', 'MEDIUM') or at_least('transferability', 'MEDIUM')
                 or at_least('practical_applicability', 'HIGH'))
    worthwhile = mechanism and at_least('research_utility', 'MEDIUM')
    related = at_least('topic_relevance', 'MEDIUM') or at_least('research_utility', 'MEDIUM')
    if mechanism and not worthwhile and rank['research_utility'] is not None:
        trace.append('MECHANISM_NOTED: a method or transferable mechanism is on record, but research utility is rated low, '
                     'so targeted reading is not proposed. It stays in mechanisms_worth_study; a higher utility rating changes the route.')
    unresolved = open_conflicts(record)
    conflicts = [c for c in unresolved if c.get('kind', 'CONTENT') == 'CONTENT']
    focus, needed, restrictions = [], [], []
    if rank['novelty_potential'] is not None and rank['novelty_potential'] <= 1:
        trace.append('NOVELTY_NOT_USED_TO_EXCLUDE: low novelty potential does not lower the route; '
                     'research value is judged on the other dimensions.')
    if core and record.get('reading_policy') == 2:
        level, rule = 2, 'CORE_RESEARCH_READING'
        focus = list(assessment.get('mechanisms_worth_study') or []) or [q['relation'] for q in assessment.get('target_links', [])]
        trace.append('Read the source dependencies of the intended conclusions. Relevance does not require whole-paper verification.')
    elif core:
        level, rule = 3, 'CORE_FOR_TARGET'
        trace.append('High research utility with high topic or methodological relevance.')
        if paper_type == 'SURVEY' and not at_least('methodological_relevance', 'HIGH'):
            level, rule = 2, 'SURVEY_TARGETED_FIRST'
            focus = list(SURVEY_FOCUS)
            trace.append('A survey is read for its taxonomy and selection method first; complete reading follows '
                         'when that classification is itself the method to build on.')
    elif worthwhile:
        level, rule = 2, 'SPECIFIC_MECHANISM'
        focus = list(assessment.get('mechanisms_worth_study') or [])
        trace.append('A method, transferable mechanism or deployment condition is worth targeted reading, '
                     'although the paper is not core for the target.')
    elif related:
        level, rule = 1, 'RELATED_NOT_CORE'
        trace.append('Related to the target without a mechanism that needs deeper reading yet.')
    elif unknown and depth in (None, 'L0') and record['full_text'].get('current_sha256'):
        level, rule = 1, 'EVIDENCE_GAP_SKIM'
        trace.append('Unknown is not irrelevant: ' + ', '.join(unknown) + ' cannot be judged from the metadata. '
                     'The full text is attached, so a skim can settle it.')
    elif unknown:
        level, rule = None, 'EVIDENCE_GAP'
        needed = list(assessment['uncertainty']['missing_information'])
        trace.append('Unknown is not irrelevant: ' + ', '.join(unknown) + ' cannot be judged from what was examined.')
    elif rank['topic_relevance'] == 0 and all(rank[name] <= 1 for name in EXCLUSION_DIMENSIONS):
        level, rule = -1, 'NO_LINK_TO_TARGET'
        trace.append('Topic, method, transferability, applicability and utility are all rated none or low, with a stated basis.')
    else:
        level, rule = 0, 'LOW_RELEVANCE'
        trace.append('No deciding dimension calls for deeper reading; usable as bounded background only.')
    if conflicts and level is not None and level >= 1:
        level = max(level, 2)
        focus = focus + ['Resolve conflict ' + c['conflict_id'] + ': ' + c['description'] for c in conflicts]
        trace.append('Open conflicts in examined content need the passages read in full before they are used.')
    elif conflicts:
        # A paper with no reason to be read further is not read further because of a conflict; its statements stay restricted.
        restrictions.append('OPEN_CONFLICT: ' + ', '.join(c['conflict_id'] for c in conflicts)
                            + ' unresolved; do not cite the conflicting statements as facts.')
    versions = [c['conflict_id'] for c in unresolved if c.get('kind') == 'VERSION_DIFFERENCE']
    if versions:
        restrictions.append('VERSION_DIFFERENCE: ' + ', '.join(versions) + ' open; say which version a statement comes from. '
                            'It is settled by obtaining the other version, not by reading this one more closely.')
    if paper_type in EMPIRICAL_TYPES and rank['evidence_adequacy'] is not None and rank['evidence_adequacy'] <= 1:
        restrictions.append('WEAK_EVIDENCE: examined evidence is thin; statements from this paper stay conditional.')
        trace.append('Weak evidence restricts how the paper may be used; it is a reason to check, not to exclude.')
    if level is None:
        decision = 'DEFER_FOR_EVIDENCE'
    elif level == -1:
        decision = 'EXCLUDE_FOR_TARGET'
    elif level == 0:
        decision = 'BACKGROUND_ONLY'
    else:
        wanted = DEPTHS[level]
        if _index(wanted) <= _index(depth):
            decision = {'L1': 'REMAIN_AT_L1', 'L2': 'REMAIN_AT_L2'}.get(depth, 'BACKGROUND_ONLY')
        else:
            # Climb one router step at a time; the anticipated depth is kept for the queue.
            step = wanted if depth == 'L1' else ROUTER_TRANSITIONS[depth or 'L0'][0]
            decision = 'PROMOTE_TO_' + step
            if step != wanted:
                trace.append(f'Anticipated depth {wanted}; a skim comes first to confirm it.')
    anticipated = None if level is None or level < 1 else DEPTHS[level]
    if (PROMOTIONS.get(decision) and not record['full_text'].get('current_sha256')
            and record['full_text']['access_state'] == 'UNAVAILABLE'):
        decision, rule = 'DEFER_FOR_EVIDENCE', 'FULL_TEXT_UNAVAILABLE'
        needed.append('Full text: ' + (record['full_text'].get('missing_reason') or 'not available'))
        trace.append('The next depth needs the paper itself, which is unavailable.')
    floor = unmet_floor(record)
    if floor and _index(PROMOTIONS.get(decision)) < _index(floor):
        trace.append(f'USER_DEPTH_FLOOR: the user asked for {floor}; relevance ratings cannot lower that.')
        decision, rule, anticipated = 'PROMOTE_TO_' + floor, 'USER_DEPTH_FLOOR', floor
    limit = depth_ceiling(record, ceiling)
    beyond = limit is not None and _index(PROMOTIONS.get(decision)) > _index(limit)
    if beyond:
        trace.append(f'USER_DEPTH_CEILING: the user limited this reading to {limit}. This is a recommendation only; '
                     'going deeper needs the user.')
    return {'decision': decision, 'rule': rule, 'anticipated_depth': anticipated, 'focus_hint': focus,
            'requires_user_approval': beyond,
            'evidence_needed': needed, 'use_restrictions': restrictions, 'trace': trace,
            'assessment_id': assessment.get('assessment_id'), 'independent_review': False,
            'notice': 'Rule-based routing suggestion from recorded ratings. It is not a review, a score or a verified finding.'}


def _criterion_basis(decision, items, criteria):
    """An exclusion that rests on a criterion stated beforehand and on what the source explicitly says."""
    cid = decision.get('exclusion_criterion')
    if not criteria or cid not in criteria:
        _fail('EXCLUSION_CRITERION_REQUIRED', 'Cite a criterion stated in this workspace before the decision; '
              'a criterion invented for one paper is not a stated criterion.')
    rows = decision.get('criterion_evidence')
    if (not isinstance(rows, list) or not rows or any(
            not isinstance(row, dict) or not _text(row.get('text')) or not _texts(row.get('from_items'), allow_empty=False)
            or any(ref not in items for ref in row['from_items']) for row in rows)):
        _fail('EXCLUSION_UNSUPPORTED', 'State what the examined source says that violates the criterion, with the items it comes from. '
              'Missing information is not a violation: defer instead.')
    return [{'text': row['text'].strip(), 'from_items': list(row['from_items'])} for row in rows]


def apply_decision(record, decision, target, criteria=None, ceiling=None):
    """Validate and append a routing decision; guardrails apply to every non-user decision.

    criteria maps the workspace's stated criterion IDs to their hash.
    """
    check_schema(record)
    if not isinstance(decision, dict):
        _fail('INVALID_DECISION', 'The decision must be an object.')
    _scan_forbidden(decision, 'decision')
    kind, by = decision.get('decision'), decision.get('decided_by')
    if kind not in DECISIONS or by not in DECIDERS:
        _fail('INVALID_DECISION', 'Use a known decision and decided_by ROUTER_RULES, AGENT_JUDGMENT or USER.')
    if not _texts(decision.get('reasons'), allow_empty=False):
        _fail('DECISION_BASIS_MISSING', 'Record the reasons for this decision.')
    record = copy.deepcopy(record)
    depth = effective_depth(record)
    items = examined_items(record)
    assessment = current_assessment(record, target)
    refs = decision.get('source_refs') or []
    known = set(items) | {'assessment:' + a['assessment_id'] for a in record['assessments']} | {
        r['record_id'] for r in record['source_records']}
    promoted = PROMOTIONS.get(kind)
    basis = decision.get('basis', 'RATINGS')
    if basis not in {'RATINGS', 'STATED_CRITERION'} or (basis == 'STATED_CRITERION' and kind != 'EXCLUDE_FOR_TARGET'):
        _fail('INVALID_DECISION', 'basis is RATINGS or, for an exclusion only, STATED_CRITERION.')
    evidence = _criterion_basis(decision, items, criteria) if basis == 'STATED_CRITERION' else []
    if by == 'USER':
        if not _text(decision.get('user_instruction')):
            _fail('USER_INSTRUCTION_REQUIRED', 'Quote or reference what the user actually asked; never simulate a user decision.')
        if promoted != record['depth'].get('user_requested'):
            # The user's own decision raises, lowers or withdraws the requested depth.
            record['depth'].update(user_requested=promoted, user_request=decision['user_instruction'].strip())
            record.setdefault('depth_requests', []).append({'depth': promoted, 'at': now(),
                                                            'user_instruction': decision['user_instruction'].strip()})
        if promoted:
            _raise_limit(record, promoted, decision['user_instruction'], ceiling)
    else:
        if not _texts(refs, allow_empty=False) or set(refs) - known:
            _fail('DECISION_BASIS_MISSING', 'source_refs name the examined items, records or assessment the decision rests on.')
        floor = unmet_floor(record)
        if floor and _index(promoted) < _index(floor):
            _fail('USER_DEPTH_FLOOR', f'The user asked for {floor}. Automatic routing may recommend more, never less; '
                  'only the user can lower the requested depth.')
        if promoted and promoted not in ROUTER_TRANSITIONS.get(depth, ()) and not (floor and _index(promoted) <= _index(floor)):
            _fail('ILLEGAL_TRANSITION', f'From {depth or "unscreened"} a router may propose '
                  f'{", ".join(ROUTER_TRANSITIONS.get(depth, ())) or "nothing further"}; other jumps need the user.')
        if kind in {'REMAIN_AT_L1', 'REMAIN_AT_L2'} and kind[-2:] != depth:
            _fail('ILLEGAL_TRANSITION', f'{kind} applies only at that depth; this paper is at {depth}.')
        stop_without_target = (record.get('reading_policy') == 2 and target is None and by == 'AGENT_JUDGMENT'
                               and kind in {'REMAIN_AT_L1', 'REMAIN_AT_L2'})
        if (kind in RELEVANCE_VERDICTS or by == 'ROUTER_RULES') and assessment is None and basis == 'RATINGS' and not stop_without_target:
            _fail('ASSESSMENT_REQUIRED', 'This decision is a relevance verdict: record a current assessment for the bound target first.')
        if by == 'ROUTER_RULES' and basis == 'STATED_CRITERION':
            _fail('INVALID_DECISION', 'The rating rules know no criteria. Record a criterion-based exclusion as AGENT_JUDGMENT with its evidence.')
        if kind in {'EXCLUDE_FOR_TARGET', 'BACKGROUND_ONLY'} and basis == 'RATINGS':
            ranks = {name: _rank(assessment, name) for name in EXCLUSION_DIMENSIONS}
            missing = [name for name, value in ranks.items() if value is None]
            if kind == 'EXCLUDE_FOR_TARGET' and (missing or any(v > 1 for v in ranks.values()) or ranks['topic_relevance'] != 0):
                _fail('EXCLUSION_UNSUPPORTED', 'Exclusion needs topic relevance NONE and every other deciding dimension NONE or LOW, '
                      'each with a basis' + (' (unknown: ' + ', '.join(missing) + ')' if missing else '')
                      + '. Missing evidence is uncertainty: use DEFER_FOR_EVIDENCE. Low novelty alone never excludes a paper.')
            if kind == 'BACKGROUND_ONLY' and missing:
                _fail('EXCLUSION_UNSUPPORTED', 'Unknown: ' + ', '.join(missing) + '. Defer for evidence rather than demoting the paper.')
        if by == 'ROUTER_RULES' and recommend(record, assessment)['decision'] != kind:
            _fail('INVALID_DECISION', 'ROUTER_RULES records the rule recommendation as returned. A different choice is '
                  'AGENT_JUDGMENT with its own reasons.')
    if kind == 'PROMOTE_TO_L2' and not _texts(decision.get('focus'), allow_empty=False):
        _fail('FOCUS_REQUIRED', 'Name the sections, mechanisms or experiments the targeted pass must check.')
    if kind == 'DEFER_FOR_EVIDENCE' and not _texts(decision.get('evidence_needed'), allow_empty=False):
        _fail('DECISION_BASIS_MISSING', 'State which evidence is needed before this paper can be routed.')
    if not _texts(decision.get('decision_changers', [])):
        _fail('INVALID_DECISION', 'decision_changers must be a list of strings.')
    row = {'decision_id': f'D{len(record["decisions"]) + 1:02}', 'decision': kind, 'decided_by': by,
           'depth_at_decision': depth, 'target': target_binding(target),
           'source_sha256': None if depth in (None, 'L0') else record['full_text'].get('current_sha256'),
           'assessment_id': assessment['assessment_id'] if assessment else None,
           'reasons': list(decision['reasons']), 'source_refs': list(refs), 'focus': list(decision.get('focus') or []),
           'evidence_needed': list(decision.get('evidence_needed') or []),
           'decision_changers': list(decision.get('decision_changers') or []),
           'basis': basis, 'exclusion_criterion': decision.get('exclusion_criterion'),
           'criterion_sha256': (criteria or {}).get(decision.get('exclusion_criterion')) if decision.get('exclusion_criterion') else None,
           'criterion_evidence': evidence,
           'user_instruction': decision.get('user_instruction') if by == 'USER' else None,
           'rule_recommendation': recommend(record, assessment)['decision'] if assessment else None,
           'recorded_at': now(), 'independent_review': False}
    record['decisions'].append(row)
    return record


def _raise_limit(record, depth, instruction, workspace_ceiling=None):
    """Let a user request through an existing limit, and no further.

    "Read this one at L2" under an abstracts-only limit allows L2 for this paper; complete reading still
    needs the user. A limit that already allows the request is left exactly as it was.
    """
    limit = depth_ceiling(record, workspace_ceiling)
    if limit is not None and _index(depth) > _index(limit):
        record['depth']['ceiling'] = {'depth': None if depth == 'L3' else depth, 'user_instruction': instruction.strip(),
                                      'at': now()}


def request_depth(record, depth, instruction, workspace_ceiling=None):
    """Record an explicit user depth request; later automatic routing cannot go below it."""
    check_schema(record)
    if depth not in DEPTHS[1:] or not _text(instruction):
        _fail('USER_INSTRUCTION_REQUIRED', 'Give depth L1, L2 or L3 and what the user actually asked.')
    record = copy.deepcopy(record)
    record['depth'].update(user_requested=depth, user_request=instruction.strip())
    _raise_limit(record, depth, instruction, workspace_ceiling)
    record.setdefault('depth_requests', []).append({'depth': depth, 'user_instruction': instruction.strip(), 'at': now()})
    return record


def focus_applicability(record, target):
    """Whether each targeted-reading focus was judged for the current research target.

    What was read and where is a fact about the source and stays. Which target question a focus serves
    is a judgement made for one target revision; under another it must be made again.
    """
    row = latest_pass(record, 'L2')
    if row is None:
        return {}
    binding = target_binding(target)
    focus = {item['focus_id']: item for item in row['targeted']['focus']}
    if row.get('target') == binding and (binding is not None or record.get('reading_policy') == 2):
        return {fid: {'state': 'CURRENT', 'question_ids': item['question_ids'], 'judged_in': row['pass_id']}
                for fid, item in focus.items()}
    judged = next((entry for entry in reversed(record.get('applicability', []))
                   if entry['target'] == binding and entry['pass_id'] == row['pass_id']), None) if binding else None
    result = {}
    for fid in focus:
        entry = (judged or {}).get('focus', {}).get(fid)
        if entry is None:
            result[fid] = {'state': 'REASSESS_FOR_TARGET', 'question_ids': [], 'judged_in': None}
        else:
            result[fid] = {'state': 'CURRENT' if entry['applies'] else 'NOT_APPLICABLE', 'question_ids': entry['question_ids'],
                           'judged_in': judged['reassessment_id']}
    return result


def local_claim_labels(record, target):
    """Each local claim with what a reader of a synthesis must know before using it."""
    row = latest_pass(record, 'L2')
    if row is None:
        return []
    applicability = focus_applicability(record, target)
    items = examined_items(record)
    labels = []
    for claim in row['targeted']['local_claims']:
        state = applicability[claim['focus_id']]['state']
        use = ('REASSESS_FOR_TARGET' if state == 'REASSESS_FOR_TARGET' else 'SOURCE_NOTE_ONLY' if state == 'NOT_APPLICABLE'
               else 'CANDIDATE_COMPARISON' if claim['evidence_state'] in {'SUPPORTED', 'LIMITED'} else 'HOLD')
        labels.append({'claim_id': claim['claim_id'], 'attribution': claim['attribution'], 'evidence_state': claim['evidence_state'],
                       'focus_id': claim['focus_id'], 'target_applicability': state, 'use': use,
                       'read_scope': [{'item_id': ref, 'label': items[ref]['label'], 'locator': items[ref].get('locator'),
                                       'read_level': items[ref]['read_level']}
                                      for ref in claim['supporting_items'] + claim['conflicting_items'] if ref in items],
                       'source_sha256': row['source_sha256'], 'pass_id': row['pass_id'], 'writer_id': row['writer_id'],
                       'independent_review': 'NONE', 'complete_paper_verified': False})
    return labels


def permitted_use(record, target):
    """How statements from this record may be used before any complete reading and review."""
    depth = effective_depth(record)
    return {'tier': TIER_BY_DEPTH[depth], 'statements': 'NONE' if depth is None else
            'BACKGROUND_METADATA' if depth == 'L0' else 'BOUNDED_BACKGROUND',
            'local_claims': {label['claim_id']: label['use'] for label in local_claim_labels(record, target)}}


REASSESSMENT_KEYS = {'writer_id', 'paper_id', 'assessment', 'decision', 'focus_applicability'}


def apply_reassessment(record, payload, target, criteria=None, ceiling=None):
    """Judge relevance again for the current target on what was already examined. Records no new reading."""
    check_schema(record)
    if not target:
        _fail('TARGET_REQUIRED', 'Reassessment judges relevance for a bound research target.')
    if isinstance(payload, dict):
        payload = {key: value for key, value in payload.items() if not str(key).startswith('_')}  # scaffold guidance
    if not isinstance(payload, dict) or payload.keys() - REASSESSMENT_KEYS:
        _fail('INVALID_REASSESSMENT', 'A reassessment carries writer_id, paper_id, assessment, optional decision and focus_applicability. '
              'New reading is submitted as a pass.')
    _scan_forbidden(payload, 'reassessment')
    depth = effective_depth(record)
    if depth is None or not _text(payload.get('writer_id')) or payload.get('paper_id') != record['paper_id']:
        _fail('INVALID_REASSESSMENT', 'Give the actual writer_id and this paper_id; a paper with no valid pass is screened first.')
    record = copy.deepcopy(record)
    items = examined_items(record)
    deepest = current_passes(record)[-1]
    serial = 'T%02d' % (len(record.get('applicability', [])) + sum(1 for a in record['assessments'] if a.get('kind') == 'REASSESSMENT') + 1)
    stale = [fid for fid, row in focus_applicability(record, target).items() if row['state'] == 'REASSESS_FOR_TARGET']
    rows = payload.get('focus_applicability') or []
    if stale or rows:
        l2 = latest_pass(record, 'L2')
        known = {item['focus_id'] for item in l2['targeted']['focus']} if l2 else set()
        questions = {q['id'] for q in target['questions']}
        judged = {}
        for row in rows:
            fid = row.get('focus_id') if isinstance(row, dict) else None
            if (fid not in known or fid in judged or type(row.get('applies')) is not bool or not _text(row.get('note'))
                    or not _texts(row.get('question_ids', []))
                    or set(row.get('question_ids', [])) - questions or (row['applies'] and not row.get('question_ids'))):
                _fail('INVALID_REASSESSMENT', 'Each focus_applicability row names a focus of the targeted pass, applies true or false, '
                      'current target question IDs when it applies, and a note with the reason.')
            judged[fid] = {'applies': row['applies'], 'question_ids': list(row.get('question_ids', [])) if row['applies'] else [],
                           'note': row['note'].strip()}
        if set(stale) - set(judged):
            _fail('INVALID_REASSESSMENT', 'The targeted pass was read for another target revision. Judge each focus for the current one: '
                  + ', '.join(sorted(set(stale) - set(judged))))
        record.setdefault('applicability', []).append({'reassessment_id': serial, 'target': target_binding(target),
                                                       'pass_id': l2['pass_id'], 'writer_id': payload['writer_id'], 'at': now(),
                                                       'focus': judged, 'reading_performed': False})
    row = validate_assessment(record, payload.get('assessment'), depth, target, items)
    row.update(assessment_id=f'A{len(record["assessments"]) + 1:02}', pass_id=deepest['pass_id'], kind='REASSESSMENT',
               source_sha256=deepest['source_sha256'], assessed_at=now(), writer_id=payload['writer_id'],
               reading_performed=False)
    record['assessments'].append(row)
    if payload.get('decision') is not None:
        record = apply_decision(record, payload['decision'], target, criteria, ceiling)
    return record


def next_step(record, target, ceiling=None, criteria=None):
    """Route the host to the next action for this paper; nothing here advances a state."""
    depth = effective_depth(record)
    decision, stale = current_decision(record, target, criteria)
    if record.get('l3'):
        return {'kind': 'CONTINUE_L3_RUN', 'instruction': 'Use reading_run_control.py next on the promoted run; '
                'its gates and independent review decide acceptance.', 'run_path': record['l3']['run_path']}
    floor = record['depth'].get('user_requested')
    if depth is None and not (floor and floor != 'L0'):
        return {'kind': 'SCREEN_L0', 'instruction': 'Screen the metadata and record what it can and cannot show.'}
    focus_due = sorted(fid for fid, row in focus_applicability(record, target).items() if row['state'] == 'REASSESS_FOR_TARGET')
    if stale == 'TARGET_CHANGED' or focus_due:
        return {'kind': 'REASSESS_FOR_TARGET', 'focus_ids': focus_due,
                'standing_user_instructions': standing_instructions(record),
                'instruction': 'The research target changed. What was examined, and where, stays. Relevance, routing, exclusion '
                               'and the link between each targeted-reading focus and the target questions must be judged again '
                               '(reassess). A new target is not a new permission: what the user said about how far or which part '
                               'to read still holds. If the new target needs content beyond it, recommend that reading and ask.'}
    if stale == 'CRITERION_CHANGED':
        return {'kind': 'RECORD_ROUTING_DECISION', 'instruction': 'The stated criterion this exclusion cited was changed or removed. '
                'Decide again against the current criteria and ratings.'}
    stale_passes = [row['pass_id'] for row in record['passes']
                    if (row['status'] == 'STALE_SOURCE_VERSION' or (row['status'] == 'CURRENT' and not pass_current(record, row)))
                    and _index(row['depth']) > _index(depth)]
    if stale_passes:
        return {'kind': 'REEXAMINE_NEW_VERSION', 'stale_pass_ids': stale_passes,
                'instruction': 'The attached source version changed. Notes from the other version are leads, not coverage of this one.'}
    wanted = floor if floor and _index(depth) < _index(floor) else PROMOTIONS.get((decision or {}).get('decision'))
    limit = depth_ceiling(record, ceiling)
    if wanted and _index(wanted) > _index(depth):
        if limit is not None and _index(wanted) > _index(limit):
            return {'kind': 'UPGRADE_NEEDS_USER', 'recommended_depth': wanted, 'allowed_depth': limit,
                    'instruction': f'Reading to {wanted} is recommended, but the user limited this reading to {limit}. '
                                   'Report the recommendation and its reasons; do not read deeper unless the user asks.'}
        if wanted == 'L3' and record.get('reading_policy') == 2 and floor != 'L3':
            return {'kind': 'UPGRADE_NEEDS_USER', 'recommended_depth': 'L3', 'instruction': 'Report the reason for a whole-paper audit; do not start it without authorization.'}
        if wanted == 'L3' and record.get('reading_scope'):
            return {'kind': 'UPGRADE_NEEDS_USER', 'instruction': 'The section limit still applies; a target or depth decision is not permission to read other sections.'}
        if wanted == 'L3':
            return {'kind': 'PROMOTE_L3', 'instruction': 'Run promote to open a complete-reading run. Earlier notes become leads; '
                    'every unit, gate and the independent review start from the beginning.'}
        if not record['full_text'].get('current_sha256'):
            return {'kind': 'ATTACH_FULL_TEXT', 'instruction': 'Attach the lawfully obtained full text, or record why it is unavailable.'}
        return {'kind': 'SKIM_L1' if wanted == 'L1' else 'TARGETED_READ_L2', 'focus': (decision or {}).get('focus', []),
                'instruction': 'Read at the requested depth and record examined and unexamined content.'}
    if decision is not None and decision['decision'] == 'DEFER_FOR_EVIDENCE' and record.get('reading_scope'):
        return {'kind': 'UPGRADE_NEEDS_USER', 'evidence_needed': decision['evidence_needed'],
                'instruction': 'Report the gap. Use only authorized evidence; ask before expanding the section scope.'}
    if decision is not None and decision['decision'] == 'DEFER_FOR_EVIDENCE':
        return {'kind': 'OBTAIN_EVIDENCE', 'evidence_needed': decision['evidence_needed'],
                'instruction': 'Obtain the named evidence, then assess and route again. Deferral is not exclusion.'}
    if decision is None:
        return {'kind': 'RECORD_ROUTING_DECISION', 'instruction': 'Assess the dimensions for the bound target and record a decision with reasons.'}
    return {'kind': 'NONE', 'decision': decision['decision'],
            'instruction': 'No further reading is planned for this target. New evidence, a new target or the user can reopen it.'}
