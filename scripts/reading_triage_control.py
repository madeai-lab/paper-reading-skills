"""Adaptive reading depth: screening workspace, routing, upgrades and exports; no model launcher.

Depth L0-L2 lives here, in screening records. Complete reading (L3) stays with reading_run_control.py:
`promote` opens such a run, and its gates and independent review are unchanged.
"""
import argparse
import json
from pathlib import Path
import sys

# An isolated interpreter (-I) does not put this directory on the module path; the sibling helpers live here.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True  # an installed skill directory stays as it was delivered

from reading_run_records import RunError, read
import reading_corpus as store
import reading_triage as triage

COMMANDS = ['init', 'set-target', 'set-criteria', 'import', 'add', 'request-depth', 'limit-depth', 'set-scope', 'attach-source',
            'mark-unavailable', 'extract', 'outline', 'find-text', 'read-pages', 'render-crop', 'skim-plan', 'handoff-template',
            'validate',
            'submit', 'reassess-template', 'reassess', 'recommend',
            'route', 'status', 'queue', 'flow', 'export', 'tiers', 'check-synthesis', 'promote', 'link-run',
            'log-usage', 'resources', 'profile-plan', 'render-card', 'register-output', 'check-output']
PAPER_COMMANDS = {'set-scope', 'request-depth', 'attach-source', 'mark-unavailable', 'extract', 'outline', 'find-text', 'read-pages', 'render-crop',
                  'skim-plan', 'handoff-template', 'reassess-template', 'recommend', 'route', 'status', 'promote', 'link-run', 'log-usage',
                  'profile-plan', 'render-card', 'register-output', 'check-output'}
FILE_COMMANDS = {'set-scope', 'set-target', 'set-criteria', 'import', 'validate', 'submit', 'reassess', 'route', 'check-synthesis',
                 'register-output'}


def assessment_template():
    return {'dimensions': {name: {'rating': 'UNKNOWN', 'basis': '', 'evidence_level': 'NOT_ASSESSED', 'refs': []}
                           for name in triage.DIMENSIONS},
            'uncertainty': {'level': 'HIGH', 'missing_information': []},
            'target_links': [], 'mechanisms_worth_study': [], 'evidenced_points': [], 'author_stated_only': [],
            'depth_rationale': '', 'decision_changers': []}


def handoff_template(root, paper_id, depth, writer):
    corpus = store.load_corpus(root)
    record = store.load_record(root, paper_id)
    if depth not in triage.SCREENING_DEPTHS or not writer:
        raise RunError('INVALID_ARGUMENT', 'Give --depth L0, L1 or L2 and --writer with the actual reading agent ID.')
    statement = {'text': '', 'attribution': 'AUTHOR_CLAIM', 'from_items': []}
    result = {'writer_id': writer, 'paper_id': paper_id, 'depth': depth, 'paper_type': record['identity']['paper_type'],
              'examined': [], 'not_examined': [], 'uncertainty_flags': [], 'conflicts': []}
    if depth == 'L0':
        result['examined'] = [{'item_id': 'M-ABS', 'kind': 'ABSTRACT', 'label': 'Abstract', 'read_level': 'READ_IN_FULL',
                               'source_ref': record['source_records'][0]['record_id'], 'note': ''}]
        result['screening'] = {'full_text_read': False, 'potential_value': [dict(statement)]}
    else:
        result['identity_check'] = {'state': 'VERIFIED_AGAINST_SOURCE', 'basis': ''}
        result['examined'] = [{'item_id': 'S-INTRO', 'kind': 'SECTION', 'label': '1 Introduction', 'read_level': 'SKIMMED',
                               'locator': {'physical_page': 1, 'section': '1 Introduction', 'object_label': None}, 'note': ''}]
        result['not_examined'] = [{'label': '', 'reason': ''}]
    if depth == 'L1':
        result['card'] = {'research_problem': dict(statement), 'claimed_contributions': [dict(statement)],
                          'core_method': dict(statement), 'headline_evidence': [dict(statement)],
                          'potential_limitations': [dict(statement)]}
        result['decision'] = {'decision': '', 'decided_by': 'ROUTER_RULES', 'reasons': [], 'source_refs': [],
                              'focus': [], 'evidence_needed': [], 'decision_changers': []}
    if depth == 'L2':
        result['targeted'] = {'focus': [{'focus_id': 'F1', 'description': '', 'question_ids': [], 'items': []}],
                              'local_claims': [{'claim_id': 'LC1', 'text': '', 'attribution': 'AUTHOR_CLAIM', 'focus_id': 'F1',
                                                'evidence_state': 'UNDETERMINED', 'supporting_items': [], 'conflicting_items': [],
                                                'conditions': [], 'limits': '', 'missing_evidence': []}],
                              'scope_statement': ''}
    if corpus['research_target']:
        result['assessment'] = assessment_template()
    if depth != 'L1':
        result['decision'] = {'decision': '', 'decided_by': 'ROUTER_RULES', 'reasons': [], 'source_refs': [],
                              'focus': [], 'evidence_needed': [], 'decision_changers': []}
    if record.get('reading_policy') == 2:
        if depth == 'L1':
            result['card'] = {key: result['card'][key] for key in ('research_problem', 'core_method')}
        if not corpus['research_target'] and depth != 'L0':
            result['decision'].update(decision='REMAIN_AT_' + depth, decided_by='AGENT_JUDGMENT')
    result['_guide'] = guide(record, depth)
    return result


def guide(record, depth):
    """Allowed values for the scaffold. Keys starting with an underscore are ignored on submit."""
    kinds = sorted(triage.METADATA_KINDS) if depth == 'L0' else sorted(triage.ITEM_KINDS)
    return {
        'this_key': 'Guidance only; ignored on validate and submit. Fill every other field from what you actually examined.',
        'examined.kind': kinds, 'examined.read_level': list(triage.READ_LEVELS),
        'examined.source_ref (TITLE, ABSTRACT, METADATA from a record)': [row['record_id'] for row in record['source_records']],
        'examined.locator (body items)': list(triage.LOCATOR_KEYS),
        'examined.locator.physical_page': 'one page number or a list of page numbers',
        'figures': 'actually_viewed: true with artifact_refs inside this paper workspace, or caption_only: true',
        'other body items': 'optional artifact_refs when the text was checked against a rendered image',
        'paper_type': sorted(triage.PAPER_TYPES), 'statement.attribution': sorted(triage.ATTRIBUTIONS),
        'assessment.rating': list(triage.RATINGS) + ['UNKNOWN'],
        'assessment.evidence_level': sorted(triage.EVIDENCE_LEVELS) + ['(EXAMINED_SOURCE needs body items; UNKNOWN pairs with NOT_ASSESSED)'],
        'local_claims.evidence_state (L2)': sorted(triage.EVIDENCE_STATES),
        'conflicts.status': ['OPEN', 'EXPLAINED'], 'conflicts.kind': sorted(triage.CONFLICT_KINDS),
        'uncertainty_flags': '[{code, detail}]',
        'decision.decision': sorted(triage.DECISIONS), 'decision.decided_by': sorted(triage.DECIDERS),
        'decision.basis': ['RATINGS', 'STATED_CRITERION (exclusion only: exclusion_criterion + criterion_evidence [{text, from_items}])'],
        'decision': 'Optional here except after a skim (L1), where it is required. Remove it to route later with `route`. '
                    'ROUTER_RULES must equal the output of `recommend`; otherwise use AGENT_JUDGMENT with reasons. '
                    'Preview the rule output for this pass before submitting: recommend <workspace> --paper <id> --file <this file>.',
        'decision.source_refs': 'examined item IDs, record IDs or assessment:<id>'}


def reassess_template(root, paper_id, writer):
    corpus = store.load_corpus(root)
    record = store.load_record(root, paper_id)
    if not writer:
        raise RunError('INVALID_ARGUMENT', 'Give --writer with the actual agent ID.')
    result = {'writer_id': writer, 'paper_id': paper_id, 'assessment': assessment_template(),
              'decision': {'decision': '', 'decided_by': 'ROUTER_RULES', 'reasons': [], 'source_refs': [], 'decision_changers': []}}
    stale = [fid for fid, row in triage.focus_applicability(record, corpus['research_target']).items()
             if row['state'] == 'REASSESS_FOR_TARGET']
    if stale:
        result['focus_applicability'] = [{'focus_id': fid, 'applies': False, 'question_ids': [], 'note': ''} for fid in stale]
    return result


def run(args):
    root = args.workspace.resolve()
    command = args.command
    payload = read(args.file) if args.file and command in FILE_COMMANDS - {'import', 'register-output'} else None
    if command == 'init':
        if not args.owner:
            raise RunError('INVALID_ARGUMENT', 'init needs --owner.')
        return store.init_corpus(root, args.owner, read(args.target) if args.target else None, args.mode,
                                 read(args.file) if args.file else None, args.max_depth, args.user_instruction)
    if command == 'set-scope':
        return store.set_scope(root, args.paper, payload, args.user_instruction)
    if command == 'set-target':
        return store.set_target(root, payload)
    if command == 'set-criteria':
        return store.set_criteria(root, payload)
    if command == 'limit-depth':
        return store.limit_depth(root, args.paper, args.depth, args.user_instruction)
    if command == 'reassess-template':
        return reassess_template(root, args.paper, args.writer)
    if command == 'reassess':
        return store.reassess(root, payload)
    if command == 'import':
        return store.import_records(root, args.file, args.format, args.sheet)
    if command == 'add':
        fields = {'title': args.title, 'doi': args.doi, 'arxiv_id': args.arxiv_id, 'url': args.url}
        if args.abstract_file:
            fields['abstract'] = args.abstract_file.read_text(encoding='utf-8-sig')
        return store.add_record(root, {k: v for k, v in fields.items() if v}, args.depth, args.user_instruction)
    if command == 'request-depth':
        return store.request_depth(root, args.paper, args.depth, args.user_instruction)
    if command == 'validate':
        return store.submit(root, payload, dry_run=True)
    if command == 'submit':
        return store.submit(root, payload)
    if command == 'recommend':
        return store.recommend(root, args.paper, read(args.file) if args.file else None)
    if command == 'route':
        return store.route(root, args.paper, payload)
    if command == 'status':
        return store.status(root, args.paper)
    if command == 'skim-plan':
        record = store.load_record(root, args.paper)
        return triage.skim_plan(args.paper_type or record['identity']['paper_type'], record.get('reading_policy') == 2)
    if command == 'handoff-template':
        return handoff_template(root, args.paper, args.depth, args.writer)
    if command == 'queue':
        return store.queue(root)
    if command == 'flow':
        return store.flow(root)
    if command == 'export':
        return store.export(root, args.kind)
    if command == 'tiers':
        return store.evidence_tiers(root)
    if command == 'check-synthesis':
        return store.check_synthesis(root, payload)
    if command == 'link-run':
        return store.link_run(root, args.paper, args.run)
    if command in {'attach-source', 'mark-unavailable', 'extract', 'outline', 'find-text', 'read-pages', 'render-crop', 'promote'}:
        import reading_promotion as promotion
        if command == 'attach-source':
            if args.source is None:
                raise RunError('INVALID_ARGUMENT', 'attach-source needs --source.')
            return promotion.attach_source(root, args.paper, args.source)
        if command == 'mark-unavailable':
            return promotion.mark_unavailable(root, args.paper, args.reason, args.attempts)
        if command == 'extract':
            return promotion.extract(root, args.paper)
        if command == 'outline':
            return promotion.outline(root, args.paper)
        if command == 'find-text':
            return promotion.find_text(root, args.paper, args.terms)
        if command == 'read-pages':
            return promotion.read_pages(root, args.paper, args.pages, args.view or 'text', args.bbox, args.max_chars)
        if command == 'render-crop':
            if not args.pages or len(args.pages) != 1 or not args.bbox or not args.out:
                raise RunError('INVALID_ARGUMENT', 'render-crop needs one --pages value, --bbox x0 top x1 bottom and --out NAME.png.')
            return promotion.crop(root, args.paper, args.pages[0], args.bbox, args.out, 2.0 if args.scale is None else args.scale)
        if args.run is None or not args.owner:
            raise RunError('INVALID_ARGUMENT', 'promote needs --run NEW_RUN_DIRECTORY and --owner.')
        return promotion.promote(root, args.paper, args.run, args.owner, args.language, args.review_mode, args.source)
    if command in {'log-usage', 'resources'}:
        import reading_resources as resources
        store.load_corpus(root)
        if command == 'resources':
            result = resources.summary(root, args.paper)
            _, data = store.rows(root)
            selected = [row for _, row in data if args.paper in (None, row['paper_id'])]
            result['content_units_examined'] = sum(row['coverage']['examined_item_count'] for row in selected)
            result['pages_with_examined_items'] = sum(len(row['coverage']['pages_with_examined_items']) for row in selected)
            return result
        store.load_record(root, args.paper)
        return resources.log_usage(root, args.kind, args.paper, args.depth, tokens_in=args.tokens_in,
                                   tokens_out=args.tokens_out, duration_s=args.duration_s,
                                   measured_by=args.measured_by, note=args.note, review_round=args.review_round,
                                   phase=args.phase, task_kind=args.task_kind)
    import reading_output_profiles as profiles
    if command == 'profile-plan':
        return profiles.plan(root, args.paper, args.profile)
    if command == 'render-card':
        return profiles.render_card(root, args.paper)
    if command == 'register-output':
        return profiles.register(root, args.paper, args.profile, args.file)
    return profiles.check(root, args.paper, args.profile)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=COMMANDS)
    parser.add_argument('workspace', type=Path, help='Screening workspace directory (new for init).')
    parser.add_argument('--paper', help='Paper ID in this workspace, for example P0001.')
    parser.add_argument('--file', type=Path, help='Input file: target, records, pass, reassessment, decision, criteria or output.')
    parser.add_argument('--target', type=Path, help='init only: explicit research-target JSON.')
    parser.add_argument('--owner', help='Actual owner ID for init or promote.')
    parser.add_argument('--mode', choices=sorted(store.MODES), default='EXPLORATORY',
                        help='init only: SYSTEMATIC_REVIEW requires stated exclusion criteria (--file).')
    parser.add_argument('--format', choices=sorted(set(store.FORMATS.values())), help='import only: record format.')
    parser.add_argument('--sheet', help='import only: XLSX worksheet.')
    parser.add_argument('--title')
    parser.add_argument('--doi')
    parser.add_argument('--arxiv-id')
    parser.add_argument('--url')
    parser.add_argument('--abstract-file', type=Path)
    parser.add_argument('--depth', choices=list(triage.DEPTHS), help='Depth for a template, a user request, a user limit or a usage entry.')
    parser.add_argument('--paper-type', choices=sorted(triage.PAPER_TYPES),
                        help='skim-plan only: plan for this type when the record does not classify the paper yet.')
    parser.add_argument('--max-depth', choices=list(triage.SCREENING_DEPTHS),
                        help='init only: deepest reading the user allowed for the whole workspace (needs --user-instruction).')
    parser.add_argument('--user-instruction', help='What the user actually asked; required for a user depth request.')
    parser.add_argument('--source', type=Path, help='Full-text file for attach-source or promote.')
    parser.add_argument('--reason')
    parser.add_argument('--attempts', nargs='+')
    parser.add_argument('--pages', nargs='+', type=int)
    parser.add_argument('--terms', nargs='+', help='find-text only: terms to locate in the extracted text (navigation, not reading).')
    parser.add_argument('--bbox', nargs=4, type=float)
    parser.add_argument('--view', choices=('text', 'locator', 'detail'))
    parser.add_argument('--max-chars', type=int, default=18000)
    parser.add_argument('--out', help='render-crop only: new PNG name under this version\'s evidence/.')
    parser.add_argument('--scale', type=float)
    parser.add_argument('--writer')
    parser.add_argument('--kind', help='export: log, matrix or tiers. log-usage: MODEL_CALL or REVIEWER_CALL.')
    parser.add_argument('--run', type=Path, help='promote: new run directory. link-run: existing run directory.')
    parser.add_argument('--language', choices=['zh-CN', 'en'], default='en')
    parser.add_argument('--review-mode', choices=['KEY_CLAIMS', 'FULL_DOUBLE_READ'], default='KEY_CLAIMS',
                        help='promote only: independent review scope, chosen separately from reading depth.')
    parser.add_argument('--task-kind', help='Optional host usage tag.')
    parser.add_argument('--phase', help='Optional host phase for a usage event.')
    parser.add_argument('--review-round', type=int, help='Actual review round (first = 1); omit when unknown.')
    parser.add_argument('--tokens-in', type=int)
    parser.add_argument('--tokens-out', type=int)
    parser.add_argument('--duration-s', type=float)
    parser.add_argument('--measured-by', help='Where reported tokens or duration were measured.')
    parser.add_argument('--note')
    parser.add_argument('--profile', help='Output profile name.')
    args = parser.parse_args()
    if args.command in PAPER_COMMANDS and not args.paper:
        parser.error(args.command + ' needs --paper')
    if args.command in FILE_COMMANDS and args.file is None:
        parser.error(args.command + ' needs --file')
    try:
        result = run(args)
        if isinstance(result, str):
            if hasattr(sys.stdout, 'buffer'):
                sys.stdout.buffer.write((result + '\n').encode('utf-8'))
            else:
                print(result)
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (RunError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(json.dumps({'error_code': getattr(exc, 'code', 'RECORD_ERROR'), 'message': str(exc),
                          'screening_only': True}, ensure_ascii=True, indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
