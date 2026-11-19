"""Output profiles: one evidence record, several presentations. A profile never changes evidence status.

Derived outputs live in the screening workspace, outside any complete-reading run, so a change of
presentation does not alter the content a reviewer accepted.
"""
import json
from pathlib import Path
import shutil

from reading_run_records import RunError, read, write, digest
import reading_corpus as store
import reading_triage as triage

BASES = ('NONE', 'METADATA', 'SKIM', 'TARGETED_READING', 'COMPLETE_READING')
BASIS_BY_DEPTH = {None: 'NONE', 'L0': 'METADATA', 'L1': 'SKIM', 'L2': 'TARGETED_READING'}
PROFILES = {
    'PAPER_CARD': ('METADATA', ['Identity and source version', 'What the authors state', 'Relevance by dimension for the bound target',
                                'Reading recommendation', 'Not examined and uncertainty']),
    'QUICK_SUMMARY': ('SKIM', ['Research problem', 'Claimed contributions', 'Core method', 'Headline evidence as stated or observed',
                               'Potential limitations', 'Not examined']),
    'GROUP_MEETING': ('SKIM', ['Why this paper', 'Problem and approach', 'Evidence shown and its status', 'Discussion questions',
                               'What was not examined']),
    'TECHNICAL_EXPLANATION': ('TARGETED_READING', ['Focus and target questions', 'Mechanism in the examined passages',
                                                   'Local claims and their evidence', 'Conditions and limits', 'Outside the examined scope']),
    'FULL_READING_REPORT': ('COMPLETE_READING', ['The run\'s own report.md from stage 07']),
    'PEER_REVIEW_STYLE': ('COMPLETE_READING', ['Summary of claims', 'Strengths with evidence', 'Concerns with source locations',
                                               'Questions for the authors', 'Claims on HOLD or CONDITIONAL']),
    'REPRODUCTION_CHECKLIST': ('COMPLETE_READING', ['Data and splits', 'Models, tools and budgets', 'Metrics and baselines',
                                                    'Reported versus NOT_REPORTED details', 'Known deviations and limits']),
    'CROSS_PAPER_MATRIX': ('NONE', ['Use export --kind matrix; every row carries its own evidence tier']),
}
STATEMENTS = {
    'NONE': 'Evidence status: not screened. Nothing about this paper has been examined.',
    'METADATA': 'Evidence status: metadata screening only (L0). The paper body was not read; statements repeat what the '
                'title, abstract or record say and were not checked.',
    'SKIM': 'Evidence status: evidence-aware skim (L1) of selected parts. This is not a complete reading; author statements '
            'are not verified conclusions and nothing was independently reviewed.',
    'TARGETED_READING': 'Evidence status: targeted reading (L2) of the listed focus. Judgements hold only for the examined '
                        'passages; the rest of the paper was not verified and nothing was independently reviewed.',
}


def evidence_status(root, paper_id):
    root = Path(root).resolve()
    record = store.load_record(root, paper_id)
    target = store.load_corpus(root)['research_target']
    tier = store.paper_tier(root, record)
    basis = BASIS_BY_DEPTH[tier['effective_depth']]
    review, binding = 'NONE', triage.canonical_sha({
        'identity': record['identity'], 'passes': triage.current_passes(record), 'target': triage.target_binding(target),
        'assessment': triage.current_assessment(record, target), 'decision': triage.current_decision(record, target)[0],
        'local_claims': triage.local_claim_labels(record, target)})
    restricted = []
    if tier['l3_state'] in {'IN_PROGRESS', 'ACCEPTED'}:
        from reading_run_records import content_fingerprint
        run = store._run_path(root, record)
        packet = read(run/'paper_packet.json')
        gates = packet.get('gate_results', {})
        if all(gates.get(g, {}).get('decision') == 'PASS' for g in ['G0', 'G1', 'G2']):
            basis, binding = 'COMPLETE_READING', content_fingerprint(run, packet)
            review = 'ACCEPTED' if tier['l3_state'] == 'ACCEPTED' else 'PENDING'
            restricted = [{'claim_id': c.get('claim_id'), 'allowed_use': c.get('allowed_use')}
                          for c in packet.get('claims', []) if c.get('allowed_use') in {'HOLD', 'CONDITIONAL'}]
    return {'paper_id': paper_id, 'reading_basis': basis, 'evidence_tier': tier['tier'], 'independent_review': review,
            'review_mode': tier['review_mode'] if review != 'NONE' else None, 'coverage_label': tier['coverage_label'],
            'source_sha256': record['full_text'].get('current_sha256'), 'binding_sha256': binding,
            'restricted_claims': restricted}


def banner(status, profile):
    marker = ('<!-- evidence-status profile=%s paper=%s basis=%s tier=%s review=%s binding=%s -->'
              % (profile, status['paper_id'], status['reading_basis'], status['evidence_tier'],
                 status['independent_review'], status['binding_sha256'][:16]))
    if status['reading_basis'] != 'COMPLETE_READING':
        statement = STATEMENTS[status['reading_basis']]
    elif status['independent_review'] == 'ACCEPTED':
        statement = ('Evidence status: complete reading accepted by an independent reviewer (mode %s, coverage %s). '
                     'Claims keep their USE, CONDITIONAL or HOLD restrictions.' % (status['review_mode'], status['coverage_label']))
    else:
        statement = ('Evidence status: complete reading by the Owner; independent review is pending. '
                     'This output is not accepted and must not be presented as verified.')
    return {'marker': marker, 'statement': statement}


def plan(root, paper_id, profile):
    if profile not in PROFILES:
        raise RunError('INVALID_ARGUMENT', 'Unknown output profile. Choose: ' + ', '.join(sorted(PROFILES)))
    status = evidence_status(root, paper_id)
    minimum, sections = PROFILES[profile]
    allowed = BASES.index(status['reading_basis']) >= BASES.index(minimum)
    return {'profile': profile, 'allowed': allowed, 'minimum_reading_basis': minimum, 'evidence_status': status,
            'banner': banner(status, profile), 'sections': sections,
            'rules': ['Put the banner marker and statement at the top, unchanged.',
                      'Restate recorded content only. A new assertion goes back to source reading and, for a complete-reading run, to stage 08.',
                      'Keep attribution: author statements stay author statements at every profile.',
                      'Carry HOLD and CONDITIONAL restrictions into the output.',
                      'Save the output outside the complete-reading run; register it with register-output.'],
            'next_action': None if allowed else 'Reach %s first, or choose a profile this evidence can support.' % minimum,
            'notice': 'A profile changes presentation, never coverage or review status.'}


def _directory(root, paper_id):
    path = Path(root).resolve()/'outputs'/paper_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def register(root, paper_id, profile, file):
    """Bind a derived output to the evidence it presents."""
    root = Path(root).resolve()
    outline = plan(root, paper_id, profile)
    if not outline['allowed']:
        raise RunError('PROFILE_NOT_SUPPORTED', outline['next_action'])
    if profile in {'FULL_READING_REPORT', 'CROSS_PAPER_MATRIX'}:
        raise RunError('INVALID_ARGUMENT', 'This profile is produced by its own stage or export, not registered as a derived output.')
    file = Path(file).resolve()
    record = store.load_record(root, paper_id)
    if record.get('l3') and file.is_relative_to(store._run_path(root, record)):
        raise RunError('OUTPUT_INSIDE_RUN', 'Keep derived outputs outside the complete-reading run: a presentation file '
                       'inside it would change the content the reviewer accepted.')
    text = file.read_text(encoding='utf-8-sig')
    marker = outline['banner']['marker']
    if marker not in text or outline['banner']['statement'] not in text:
        raise RunError('EVIDENCE_BANNER_MISSING', 'Start the output with the exact banner marker and statement from profile-plan.')
    directory = _directory(root, paper_id)
    target = directory/(profile + file.suffix.lower())
    if target != file:
        shutil.copyfile(file, target)
    binding = {'profile': profile, 'paper_id': paper_id, 'file': target.relative_to(root).as_posix(),
               'file_sha256': digest(target), 'evidence_status': outline['evidence_status'], 'registered_at': triage.now()}
    write(directory/(profile + '.binding.json'), binding)
    return {**binding, 'restricted_claims': outline['evidence_status']['restricted_claims'],
            'notice': 'Registered as a presentation of existing evidence. It adds no coverage and needs no new scientific review '
                      'unless it asserts something new.'}


def check(root, paper_id, profile):
    root = Path(root).resolve()
    store.paper_dir(root, paper_id)  # validates the ID before any path is built from it
    path = _directory(root, paper_id)/(profile + '.binding.json')
    if not path.is_file():
        raise RunError('INVALID_ARGUMENT', 'No registered output for this paper and profile.')
    binding = read(path)
    current = evidence_status(root, paper_id)
    errors = []
    file = root/binding['file']
    if not file.is_file() or digest(file) != binding['file_sha256']:
        errors.append({'code': 'OUTPUT_CHANGED', 'item': binding['file'], 'next_action': 'Register the edited output again.'})
    bound = binding['evidence_status']
    if any(bound[key] != current[key] for key in ['reading_basis', 'evidence_tier', 'independent_review', 'binding_sha256']):
        errors.append({'code': 'OUTPUT_STALE', 'item': binding['file'],
                       'next_action': 'The underlying evidence or its review status changed. Regenerate the output from current records.'})
    return {'current': not errors, 'errors': errors, 'evidence_status': current,
            'notice': 'Checks the binding only; it does not judge the prose.'}


def render_card(root, paper_id):
    """Deterministic PAPER_CARD from the screening record; every line states where it comes from."""
    root = Path(root).resolve()
    corpus = store.load_corpus(root)
    record = store.load_record(root, paper_id)
    outline = plan(root, paper_id, 'PAPER_CARD')
    if not outline['allowed']:
        raise RunError('PROFILE_NOT_SUPPORTED', outline['next_action'])
    target = corpus['research_target']
    identity = record['identity']
    lines = [outline['banner']['marker'], '', '# ' + (identity.get('title') or paper_id), '',
             '> ' + outline['banner']['statement'], '',
             '| Field | Value |', '|---|---|']
    for key in ['authors', 'year', 'venue', 'doi', 'arxiv_id', 'url', 'paper_type', 'field', 'identity_state']:
        value = identity.get(key)
        if value not in (None, '', []):
            lines.append('| %s | %s |' % (key, ', '.join(value) if isinstance(value, list) else value))
    lines.append('| source version | %s |' % (record['full_text'].get('current_sha256') or 'no full text attached'))
    statements = []
    screening = (triage.latest_pass(record, 'L0') or {}).get('screening')
    for row in (screening or {}).get('potential_value', []):
        statements.append(('potential value', row))
    card = (triage.latest_pass(record, 'L1') or {}).get('card') or {}
    for key, value in card.items():
        statements += [(key.replace('_', ' '), row) for row in (value if isinstance(value, list) else [value])]
    if statements:
        lines += ['', '## Statements and where they come from', '']
        lines += ['- **%s** (%s, from %s, not verified): %s' % (label, row['attribution'], ', '.join(row['from_items']), row['text'])
                  for label, row in statements]
    l2 = triage.latest_pass(record, 'L2')
    if l2:
        targeted = l2['targeted']
        labels = {label['claim_id']: label for label in triage.local_claim_labels(record, target)}
        lines += ['', '## Targeted reading: local claims', '',
                  'Writer `%s`, pass %s, source version `%s`. Independent review: none. The paper as a whole was not verified.'
                  % (l2['writer_id'], l2['pass_id'], l2['source_sha256']), '',
                  'Scope of this pass: ' + targeted['scope_statement'], '']
        for claim in targeted['local_claims']:
            label = labels[claim['claim_id']]
            where = '; '.join('%s (%s, %s)' % (row['label'], json.dumps(row['locator'], ensure_ascii=False), row['read_level'])
                              for row in label['read_scope']) or 'no examined item'
            lines += ['- `%s` %s' % (claim['claim_id'], claim['text']),
                      '  - Attribution: %s. Evidence within the examined scope: %s. Use for the current target: %s.'
                      % (claim['attribution'], claim['evidence_state'], label['use']),
                      '  - Read: %s' % where]
            if claim['conditions'] or claim['limits']:
                lines += ['  - Conditions and limits: ' + '; '.join(claim['conditions'] + ([claim['limits']] if claim['limits'] else []))]
            if claim['missing_evidence']:
                lines += ['  - Missing evidence: ' + '; '.join(claim['missing_evidence'])]
        stale = sorted(fid for fid, row in triage.focus_applicability(record, target).items() if row['state'] == 'REASSESS_FOR_TARGET')
        if stale:
            lines += ['', 'Focus %s was chosen for another research target. The source notes above stand; their relevance to the '
                      'current target has not been judged.' % ', '.join(stale)]
    assessment = triage.current_assessment(record, target)
    if assessment:
        lines += ['', '## Relevance to target `%s` r%s' % (target['target_id'], target['revision']), '',
                  '| Dimension | Rating | Evidence level | Basis |', '|---|---|---|---|']
        lines += ['| %s | %s | %s | %s |' % (name, row['rating'], row['evidence_level'], row['basis'].replace('|', '\\|'))
                  for name, row in assessment['dimensions'].items()]
        lines += ['', 'Ratings are separate judgements; no total is computed. Novelty potential was not checked against external literature.']
        if assessment['uncertainty']['missing_information']:
            lines += ['', 'Missing information: ' + '; '.join(assessment['uncertainty']['missing_information'])]
    decision, stale = triage.current_decision(record, target)
    lines += ['', '## Reading recommendation', '']
    if decision:
        lines += ['%s (%s; a triage decision, not a review). Reasons: %s' % (
            decision['decision'], decision['decided_by'], ' '.join(decision['reasons']))]
        if decision['decision_changers']:
            lines += ['', 'Would change with: ' + '; '.join(decision['decision_changers'])]
    else:
        lines += ['No current decision' + (' (%s).' % stale if stale else '.')]
    coverage = triage.coverage_summary(record)
    lines += ['', '## Not examined and uncertainty', '']
    lines += ['- Not examined — %s: %s' % (row['label'], row['reason']) for row in coverage['not_examined']] or (
        ['- The paper body was not opened.'] if outline['evidence_status']['reading_basis'] == 'METADATA' else [])
    lines += ['- %s: %s' % (flag['code'], flag['detail']) for flag in triage.uncertainty_flags(record)]
    path = _directory(root, paper_id)/'PAPER_CARD.md'
    binding = path.with_name('PAPER_CARD.binding.json')
    if path.is_file() and binding.is_file():
        # A card for an earlier source version, target or decision is history, not something to overwrite silently.
        earlier = read(binding)
        if earlier['evidence_status']['binding_sha256'] != outline['evidence_status']['binding_sha256']:
            history = path.parent/'history'
            history.mkdir(exist_ok=True)
            shutil.copyfile(path, history/('PAPER_CARD.%s.md' % earlier['evidence_status']['binding_sha256'][:12]))
    path.write_text('\n'.join(lines) + '\n', encoding='utf8')
    return register(root, paper_id, 'PAPER_CARD', path)
