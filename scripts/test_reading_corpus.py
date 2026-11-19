"""Simulated-flow tests for batch screening: import, de-duplication, queue, logs and mixed evidence tiers.

Records are constructed by the tests. Passing shows that the bookkeeping holds, not that
real papers were screened well.
"""
import copy
import csv
import json
from pathlib import Path
import subprocess
import sys

import reading_corpus as store
import reading_run_control as control
import reading_triage as triage
import test_reading_run_control as run_fixtures
from test_reading_data_sources import MAIN, workbook
from test_reading_triage import NONE, TARGET, Workspace, decision

SCRIPT = Path(__file__).with_name('reading_triage_control.py')
RECORDS = [
    ['Title', 'Abstract', 'DOI', 'URL', 'Year', 'Authors'],
    ['Agent Workflows for Laboratory Automation', 'We describe an agent system.', '10.1000/abc.1', '', '2025', 'A. One and B. Two'],
    ['Agent workflows for laboratory automation', 'Preprint.', '', 'https://arxiv.org/abs/2501.01234v2', '2025', 'A. One'],
    ['Agent Workflows  for Laboratory Automation!', 'Same DOI, other export.', 'https://doi.org/10.1000/ABC.1', '', '2025', ''],
    ['Radar Retrieval of Soil Moisture', 'Radar retrieval.', '10.1000/soil.9', '', '2024', 'C. Three'],
    ['Radar retrieval of soil moisture', 'Different paper, same title.', '10.2000/other.1', '', '2023', 'D. Four'],
    ['', '', '', '', '', ''],
]


class BatchScreeningTests(Workspace):
    def write_csv(self, rows=RECORDS, name='records.csv'):
        path = self.base/name
        with path.open('w', encoding='utf8', newline='') as stream:
            csv.writer(stream).writerows(rows)
        return path

    def test_import_merges_identifier_duplicates_and_keeps_versions_traceable(self):
        result = store.import_records(self.ws, self.write_csv())
        self.assertEqual((result['records'], result['new_papers'], result['merged_versions'], result['possible_duplicates']),
                         (5, 3, 2, 1))
        outcomes = [(row['outcome'], row.get('paper_id'), row.get('basis')) for row in result['results']]
        self.assertEqual(outcomes, [('NEW_PAPER', 'P0001', None), ('MERGED_VERSION', 'P0001', 'TITLE'),
                                    ('MERGED_VERSION', 'P0001', 'DOI'), ('NEW_PAPER', 'P0002', None),
                                    ('NEW_PAPER', 'P0003', None)])
        first = self.record('P0001')
        self.assertEqual([row['record_id'] for row in first['source_records']], ['REC-01', 'REC-02', 'REC-03'])
        self.assertEqual(first['source_records'][1]['identifiers']['arxiv_id'], '2501.01234')
        self.assertEqual(first['source_records'][1]['identifiers']['arxiv_version'], 'v2')
        self.assertEqual(first['source_records'][1]['origin'], {'import_id': 'I01', 'file': 'records/I01-records.csv', 'locator': 'row 3'})
        self.assertEqual((first['identity']['doi'], first['identity']['arxiv_id']), ('10.1000/abc.1', '2501.01234'))
        # Same title with conflicting DOIs is flagged for a person to decide, never merged silently.
        self.assertEqual(self.record('P0003')['possible_duplicate_of'], ['P0002'])
        self.assertEqual(self.record('P0002')['possible_duplicate_of'], ['P0003'])
        self.assertTrue((self.ws/'records/I01-records.csv').is_file())
        again = store.import_records(self.ws, self.write_csv())
        self.assertEqual((again['new_papers'], again['duplicate_records']), (0, 5))
        self.assertEqual(len(store.load_corpus(self.ws)['paper_ids']), 3)

    def test_json_bibtex_and_xlsx_records_join_the_same_candidate_set(self):
        store.import_records(self.ws, self.write_csv())
        data = self.base/'more.json'
        data.write_text(json.dumps({'records': [
            {'title': 'Agent workflows, revisited', 'doi': '10.1000/abc.1'},
            {'title': 'Planning with tool feedback', 'arxiv': 'arXiv:2403.00001', 'abstract': 'Tools return errors.'},
            {'note': 'no identifier at all'}]}), encoding='utf8')
        result = store.import_records(self.ws, data)
        self.assertEqual([row['outcome'] for row in result['results']], ['MERGED_VERSION', 'NEW_PAPER', 'UNUSABLE'])
        bib = self.base/'refs.bib'
        bib.write_text('@comment{ignored}\n@article{lee2024,\n  title = {Planning with {Tool} Feedback},\n'
                       '  author = "Lee, A. and Kim, B.",\n  eprint = {2403.00001v3},\n  year = 2024,\n}\n'
                       '@inproceedings{new2025, title={Human oversight of agent teams}, booktitle={Conf}, doi={10.48550/arXiv.2505.11111}}\n',
                       encoding='utf8')
        result = store.import_records(self.ws, bib)
        self.assertEqual([(row['outcome'], row.get('basis')) for row in result['results']],
                         [('MERGED_VERSION', 'ARXIV_ID'), ('NEW_PAPER', None)])
        oversight = self.record(result['results'][1]['paper_id'])
        self.assertEqual((oversight['identity']['doi'], oversight['identity']['arxiv_id']), (None, '2505.11111'))
        cell = lambda ref, text: f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'
        sheet = (f'<worksheet xmlns="{MAIN}"><sheetData><row r="1">{cell("A1", "标题")}{cell("B1", "DOI")}</row>'
                 f'<row r="2">{cell("A2", "Human oversight of agent teams")}{cell("B2", "")}</row>'
                 f'<row r="3">{cell("A3", "Memory compaction for long tasks")}{cell("B3", "10.3000/mem.7")}</row>'
                 '</sheetData></worksheet>')
        book = self.base/'queue.xlsx'
        book.write_bytes(workbook(sheet))
        result = store.import_records(self.ws, book)
        self.assertEqual([(row['outcome'], row.get('basis')) for row in result['results']],
                         [('MERGED_VERSION', 'TITLE'), ('NEW_PAPER', None)])
        flow = store.flow(self.ws)
        self.assertEqual((flow['records_identified'], flow['records_unusable'], flow['papers']), (12, 1, 6))
        self.assertEqual(flow['not_yet_screened'], 6)

    def test_identifier_spellings_short_titles_and_bridging_records(self):
        first = store.add_record(self.ws, {'title': 'Planning with tool feedback', 'arxiv_id': 'arXiv:2301.12345 [cs.LG]'})
        self.assertEqual(self.record(first['paper_id'])['identity']['arxiv_id'], '2301.12345')
        again = store.add_record(self.ws, {'url': 'https://arxiv.org/pdf/2301.12345v3.pdf'})
        self.assertEqual((again['outcome'], again['basis']), ('MERGED_VERSION', 'ARXIV_ID'))
        self.assertEqual(store.add_record(self.ws, {'title': '智能体协同规划综述'})['outcome'], 'NEW_PAPER')
        self.assertEqual(store.add_record(self.ws, {'title': '智能体协同规划综述 '})['basis'], 'TITLE')
        self.assertEqual(store.add_record(self.ws, {'title': 'Methods'})['outcome'], 'NEW_PAPER')
        self.assertEqual(store.add_record(self.ws, {'title': 'Methods'})['outcome'], 'NEW_PAPER')  # too short to identify a paper
        journal = store.add_record(self.ws, {'title': 'A journal article', 'doi': '10.1000/journal.1'})['paper_id']
        bridge = store.add_record(self.ws, {'title': 'A record naming both', 'doi': '10.1000/journal.1', 'arxiv_id': '2301.12345'})
        self.assertEqual((bridge['paper_id'], bridge['possible_duplicate_of']), (journal, [first['paper_id']]))
        self.assertEqual(self.record(first['paper_id'])['possible_duplicate_of'], [journal])
        later = store.add_record(self.ws, {'arxiv_id': '2301.12345'})
        self.assertEqual(later['paper_id'], first['paper_id'])  # the bridging record did not re-point the identifier
        before = len(store.load_corpus(self.ws)['paper_ids'])
        self.expect('USER_INSTRUCTION_REQUIRED', store.add_record, self.ws, {'title': 'A paper with a bad depth request'}, 'L3', '')
        self.assertEqual(len(store.load_corpus(self.ws)['paper_ids']), before)

    def test_each_paper_keeps_a_complete_screening_record(self):
        store.import_records(self.ws, self.write_csv())
        store.submit(self.ws, {**self.l0('P0001', topic_relevance='HIGH', research_utility='HIGH'), 'decision': decision('PROMOTE_TO_L1')})
        record = self.record('P0001')
        status = store.status(self.ws, 'P0001')
        self.assertEqual(record['paper_id'], 'P0001')
        self.assertTrue(all(row['origin'] and row['sha256'] for row in record['source_records']))        # source / version
        self.assertEqual(record['passes'][0]['target']['target_id'], TARGET['target_id'])               # research target
        self.assertEqual(status['effective_depth'], 'L0')                                                # screening depth
        self.assertEqual(set(record['assessments'][0]['dimensions']), set(triage.DIMENSIONS))            # relevance assessment
        self.assertEqual(status['routing']['decision'], 'PROMOTE_TO_L1')                                 # reading decision
        self.assertEqual(status['coverage']['examined_by_kind'], {'ABSTRACT': 1, 'TITLE': 1})            # evidence coverage
        self.assertEqual(status['uncertainty_flags'][0]['code'], 'BODY_NOT_READ')                        # uncertainty
        self.assertEqual((status['independent_review'], status['l3_state']), ('NONE', 'NONE'))           # review status
        self.assertEqual([(row['from'], row['to']) for row in status['upgrade_history']], [(None, 'L0')])  # upgrade history

    def test_queue_log_and_matrix_are_derived_from_records(self):
        store.import_records(self.ws, self.write_csv())
        store.submit(self.ws, {**self.l0('P0001', topic_relevance='HIGH', research_utility='HIGH'), 'decision': decision('PROMOTE_TO_L1')})
        store.submit(self.ws, {**self.l0('P0002', **NONE), 'decision': decision('EXCLUDE_FOR_TARGET')})
        extra = store.add_record(self.ws, {'title': 'Memory compaction for long agent tasks'})['paper_id']
        store.submit(self.ws, {**self.l0(extra, topic_relevance='MEDIUM'), 'decision': decision('PROMOTE_TO_L1')})
        requested = store.add_record(self.ws, {'title': 'A paper the user wants verified'}, 'L3', 'Verify this one fully.')['paper_id']
        queue = store.queue(self.ws)
        order = [(row['paper_id'], row['next_action']) for row in queue['queue']]
        self.assertEqual(order, [(requested, 'PROMOTE_L3'), ('P0001', 'ATTACH_FULL_TEXT'), (extra, 'ATTACH_FULL_TEXT'),
                                 ('P0003', 'SCREEN_L0')])
        self.assertEqual(queue['not_queued'], {'EXCLUDE_FOR_TARGET': 1})
        flow = store.flow(self.ws)
        self.assertEqual((flow['papers'], flow['reached_L0_or_deeper'], flow['excluded_for_target'], flow['not_yet_screened']), (5, 3, 1, 2))
        self.assertEqual(flow['exclusions_by_criterion_or_decider'], {'ROUTER_RULES': 1})
        log = store.export(self.ws, 'log')
        self.assertEqual(log['decisions'], 3)
        rows = json.loads((self.ws/'exports/screening_log.json').read_text(encoding='utf8'))
        self.assertTrue(all(row['independent_review'] is False and row['reasons'] and row['current'] for row in rows))
        store.export(self.ws, 'matrix')
        with (self.ws/'exports/comparison_matrix.csv').open(encoding='utf-8-sig', newline='') as stream:
            table = {row['paper_id']: row for row in csv.DictReader(stream)}
        self.assertEqual(table['P0002']['evidence_tier'], 'METADATA_SCREENED')
        self.assertEqual(table['P0001']['topic_relevance'], 'HIGH (METADATA_ONLY)')
        self.assertEqual(table['P0001']['evidence_adequacy'], 'UNKNOWN (NOT_ASSESSED)')
        self.assertFalse({'score', 'total', 'rank'} & {key.lower() for key in table['P0001']})
        self.assertIn('evidence tier', (self.ws/'exports/comparison_matrix.md').read_text(encoding='utf8'))

    def test_systematic_review_mode_requires_a_stated_criterion(self):
        review = self.base/'review'
        self.expect('INVALID_ARGUMENT', store.init_corpus, review, 'owner', copy.deepcopy(TARGET), 'SYSTEMATIC_REVIEW')
        store.init_corpus(review, 'owner', copy.deepcopy(TARGET), 'SYSTEMATIC_REVIEW',
                          [{'id': 'E1', 'text': 'Not about software agents.'}])
        self.ws = review
        pid = self.add('Radar retrieval of soil moisture')
        store.submit(self.ws, self.l0(pid, **NONE))
        self.expect('EXCLUSION_CRITERION_REQUIRED', store.route, self.ws, pid, decision('EXCLUDE_FOR_TARGET'))
        store.route(self.ws, pid, decision('EXCLUDE_FOR_TARGET', exclusion_criterion='E1'))
        flow = store.flow(self.ws)
        self.assertEqual((flow['protocol_mode'], flow['exclusions_by_criterion_or_decider']), ('SYSTEMATIC_REVIEW', {'E1': 1}))

    def test_command_line_reports_errors_as_json_without_writing(self):
        records = self.write_csv()
        call = lambda *args: subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding='utf8')
        result = call('import', str(self.ws), '--file', str(records))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['new_papers'], 3)
        handoff = self.base/'handoff.json'
        handoff.write_text(json.dumps({**self.l0('P0001', **NONE), 'gate_results': {}}), encoding='utf8')
        before = (self.ws/'papers/P0001/screening.json').read_bytes()
        result = call('validate', str(self.ws), '--file', str(handoff))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)['error_code'], 'INVALID_SCREENING_HANDOFF')
        handoff.write_text(json.dumps(self.l0('P0001', **NONE)), encoding='utf8')
        self.assertTrue(json.loads(call('validate', str(self.ws), '--file', str(handoff)).stdout)['valid'])
        self.assertEqual((self.ws/'papers/P0001/screening.json').read_bytes(), before)
        self.assertEqual(json.loads(call('submit', str(self.ws), '--file', str(handoff)).stdout)['tier'], 'METADATA_SCREENED')
        self.assertEqual(json.loads(call('recommend', str(self.ws), '--paper', 'P0001').stdout)['decision'], 'EXCLUDE_FOR_TARGET')
        template = json.loads(call('handoff-template', str(self.ws), '--paper', 'P0002', '--depth', 'L1', '--writer', 'w').stdout)
        self.assertEqual(set(template['assessment']['dimensions']), set(triage.DIMENSIONS))
        self.assertEqual(json.loads(call('status', str(self.ws), '--paper', 'P9999').stdout)['error_code'], 'INVALID_ARGUMENT')


class MixedEvidenceSynthesisTests(Workspace):
    """Stage 09 must tell an accepted complete reading from targeted, skimmed and metadata-only papers."""

    def accepted_run(self):
        fixture = run_fixtures.ReadingRunControlTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.packet['claims'] += [
            {'claim_id': 'C-HOLD', 'allowed_use': 'HOLD', 'supporting_units': ['F1']},
            {'claim_id': 'C-COND', 'allowed_use': 'CONDITIONAL', 'supporting_units': ['F1']}]
        fixture.packet['reviews'][0]['checked_claim_ids'] = ['C1', 'C-HOLD', 'C-COND']
        control.render(fixture.root, fixture.packet)
        fixture.save()
        fixture.packet['reviews'][0]['reviewed_content_sha256'] = control.content_fingerprint(fixture.root, fixture.packet)
        fixture.save()
        self.assertEqual(control.assess(fixture.root)['terminal_decision'], 'ACCEPTED')
        return fixture

    def corpus(self):
        self.fixture = self.accepted_run()
        self.verified = self.add('An accepted complete reading')
        store.link_run(self.ws, self.verified, self.fixture.root)
        ratings = dict(methodological_relevance='MEDIUM', research_utility='MEDIUM')
        self.targeted = self.skimmed(**ratings)
        handoff = self.l2(self.targeted)
        handoff['targeted']['local_claims'].append({
            'claim_id': 'LC-OPEN', 'text': 'Replanning lowers failures.', 'attribution': 'AUTHOR_CLAIM', 'focus_id': 'F1',
            'evidence_state': 'UNDETERMINED', 'missing_evidence': ['The ablation table was only skimmed.']})
        store.submit(self.ws, handoff)
        self.skim = self.skimmed(route=decision('REMAIN_AT_L1', refs=('S-INTRO',)), topic_relevance='MEDIUM')
        self.metadata = self.add('A metadata-only paper')
        store.submit(self.ws, {**self.l0(self.metadata, topic_relevance='LOW'), 'decision': decision('BACKGROUND_ONLY')})
        self.unscreened = self.add('An unscreened candidate')

    def test_tiers_follow_actual_state_not_labels(self):
        self.corpus()
        tiers = store.evidence_tiers(self.ws)
        by_id = {row['paper_id']: row for row in tiers['papers']}
        self.assertEqual({pid: row['tier'] for pid, row in by_id.items()},
                         {self.verified: 'VERIFIED_COMPLETE', self.targeted: 'TARGETED_READ', self.skim: 'SKIMMED',
                          self.metadata: 'METADATA_SCREENED', self.unscreened: 'UNSCREENED'})
        self.assertEqual(tiers['counts_by_tier']['VERIFIED_COMPLETE'], 1)
        self.assertEqual(by_id[self.verified]['permitted_use'], 'ACCEPTED_CLAIMS_WITHIN_ALLOWED_USE')
        self.assertEqual(by_id[self.targeted]['permitted_use']['local_claims'], {'LC1': 'CANDIDATE_COMPARISON', 'LC-OPEN': 'HOLD'})
        self.assertEqual(by_id[self.targeted]['independent_review'], 'NONE')
        self.assertEqual(by_id[self.verified]['independent_review'], 'ACCEPTED')
        self.assertEqual(store.flow(self.ws)['complete_reading_accepted'], 1)
        self.assertEqual(store.export(self.ws, 'tiers')['counts_by_tier'], tiers['counts_by_tier'])
        # Content changed after the review: the run is no longer accepted, so the tier drops.
        self.fixture.packet['claims'][0]['allowed_use'] = 'CONDITIONAL'
        self.fixture.save()
        dropped = {row['paper_id']: row for row in store.evidence_tiers(self.ws)['papers']}[self.verified]
        self.assertEqual((dropped['tier'], dropped['l3_state'], dropped['independent_review']), ('UNSCREENED', 'IN_PROGRESS', 'PENDING'))

    def test_a_run_counts_for_one_paper_and_one_source_version(self):
        self.corpus()
        other = self.add('Another paper claiming the same run')
        self.expect('LINK_REFUSED', store.link_run, self.ws, other, self.fixture.root)
        self.attach(other)  # bytes that differ from the run's source
        fresh = self.accepted_run()
        self.assertIn('different source version', self.expect('LINK_REFUSED', store.link_run, self.ws, other, fresh.root))
        self.assertEqual(self.record(self.verified)['l3']['identity_binding'], 'ASSERTED_BY_OWNER')
        # Attaching other bytes to the accepted paper: the run no longer speaks for what this record names.
        self.attach(self.verified)
        status = store.status(self.ws, self.verified)
        self.assertEqual((status['tier'], status['l3_state'], status['independent_review']), ('UNSCREENED', 'OTHER_SOURCE_VERSION', 'NONE'))
        result = store.check_synthesis(self.ws, [{'synthesis_claim_id': 'SC', 'text': 'Claimed as accepted.', 'evidence_basis': 'ACCEPTED',
                                                 'strength': 'CONCLUSION', 'support': [{'paper_id': self.verified, 'claim_id': 'C1'}]}])
        self.assertEqual([error['code'] for error in result['errors']], ['SHALLOW_EVIDENCE_MISLABELED'])

    def test_shallow_reading_cannot_be_presented_as_accepted_evidence(self):
        self.corpus()
        claim = lambda cid, basis, strength, support, **extra: {'synthesis_claim_id': cid, 'text': 'Synthesis statement.',
                                                                 'evidence_basis': basis, 'strength': strength,
                                                                 'support': support, **extra}
        limited = {'limitation': 'Targeted and skim reading only; unreviewed.'}
        cases = [
            (claim('OK-ACCEPTED', 'ACCEPTED', 'CONCLUSION', [{'paper_id': self.verified, 'claim_id': 'C1'}]), None),
            (claim('OK-COND', 'ACCEPTED', 'CONCLUSION', [{'paper_id': self.verified, 'claim_id': 'C-COND', 'conditions_acknowledged': True}]), None),
            (claim('OK-CANDIDATE', 'SCREENING_LIMITED', 'CANDIDATE', [{'paper_id': self.targeted, 'local_claim_id': 'LC1'}], **limited), None),
            (claim('OK-BACKGROUND', 'SCREENING_LIMITED', 'BACKGROUND', [{'paper_id': self.metadata}], **limited), None),
            (claim('L2-AS-ACCEPTED', 'ACCEPTED', 'CONCLUSION', [{'paper_id': self.targeted, 'claim_id': 'LC1'}]), 'SHALLOW_EVIDENCE_MISLABELED'),
            (claim('L1-AS-ACCEPTED', 'ACCEPTED', 'CANDIDATE', [{'paper_id': self.skim, 'claim_id': 'C1'}]), 'SHALLOW_EVIDENCE_MISLABELED'),
            (claim('L0-AS-ACCEPTED', 'ACCEPTED', 'BACKGROUND', [{'paper_id': self.metadata, 'claim_id': 'C1'}]), 'SHALLOW_EVIDENCE_MISLABELED'),
            (claim('MIXED', 'ACCEPTED', 'CONCLUSION', [{'paper_id': self.verified, 'claim_id': 'C1'}, {'paper_id': self.skim, 'claim_id': 'C1'}]),
             'SHALLOW_EVIDENCE_MISLABELED'),
            (claim('HOLD', 'ACCEPTED', 'CONCLUSION', [{'paper_id': self.verified, 'claim_id': 'C-HOLD'}]), 'HOLD_CLAIM_USED'),
            (claim('COND', 'ACCEPTED', 'CONCLUSION', [{'paper_id': self.verified, 'claim_id': 'C-COND'}]), 'CONDITIONS_NOT_CARRIED'),
            (claim('L1-CONCLUSION', 'SCREENING_LIMITED', 'CONCLUSION', [{'paper_id': self.skim}], **limited), 'SCREENING_EVIDENCE_OVERSTATED'),
            (claim('L0-CANDIDATE', 'SCREENING_LIMITED', 'CANDIDATE', [{'paper_id': self.metadata}], **limited), 'SCREENING_EVIDENCE_OVERSTATED'),
            (claim('NO-LIMIT', 'SCREENING_LIMITED', 'CANDIDATE', [{'paper_id': self.targeted, 'local_claim_id': 'LC1'}]),
             'SYNTHESIS_LIMITATION_MISSING'),
            (claim('L1-CANDIDATE', 'SCREENING_LIMITED', 'CANDIDATE', [{'paper_id': self.skim}], **limited), 'SCREENING_EVIDENCE_OVERSTATED'),
            (claim('L2-NO-CLAIM', 'SCREENING_LIMITED', 'CANDIDATE', [{'paper_id': self.targeted}], **limited), 'SCREENING_EVIDENCE_OVERSTATED'),
            (claim('OK-L1-BACKGROUND', 'SCREENING_LIMITED', 'BACKGROUND', [{'paper_id': self.skim}], **limited), None),
            (claim('OPEN-LOCAL', 'SCREENING_LIMITED', 'CANDIDATE', [{'paper_id': self.targeted, 'local_claim_id': 'LC-OPEN'}], **limited), 'HOLD_CLAIM_USED'),
            (claim('UNKNOWN', 'ACCEPTED', 'CONCLUSION', [{'paper_id': 'P9999', 'claim_id': 'C1'}]), 'SYNTHESIS_SUPPORT_UNKNOWN'),
        ]
        for item, expected in cases:
            result = store.check_synthesis(self.ws, [item])
            codes = [error['code'] for error in result['errors']]
            self.assertEqual(codes, [expected] if expected else [], item['synthesis_claim_id'])
        result = store.check_synthesis(self.ws, [item for item, _ in cases])
        self.assertFalse(result['valid'])
        self.assertEqual(result['claims'][2]['support_tiers'], ['TARGETED_READ'])


class SharedExampleTests(Workspace):
    """The documented examples must stay valid against the helper they illustrate."""

    def test_documented_examples_follow_the_contract(self):
        import eval_adaptive_reading as evaluation
        root = Path(__file__).resolve().parent.parent
        load = lambda name: json.loads((root/name).read_text(encoding='utf8'))
        self.assertEqual(store.import_records(self.ws, root/'shared/candidates.example.csv')['new_papers'], 3)
        status = store.submit(self.ws, load('shared/screening-handoff.L0.example.json'))
        self.assertEqual(status['next_action']['kind'], 'ATTACH_FULL_TEXT')
        self.attach('P0001')
        status = store.submit(self.ws, load('shared/screening-handoff.L1.example.json'))
        self.assertEqual((status['tier'], status['next_action']['kind']), ('SKIMMED', 'TARGETED_READ_L2'))
        status = store.submit(self.ws, load('shared/screening-handoff.L2.example.json'))
        self.assertEqual(status['permitted_use']['local_claims'],
                         {'LC1': 'CANDIDATE_COMPARISON', 'LC2': 'CANDIDATE_COMPARISON', 'LC3': 'HOLD'})
        status = store.route(self.ws, 'P0001', load('shared/routing-decision.example.json'))
        self.assertEqual(status['next_action']['kind'], 'NONE')
        checked = store.check_synthesis(self.ws, load('shared/synthesis-claims.example.json'))
        self.assertEqual([(error['code'], error['item']) for error in checked['errors']], [('SHALLOW_EVIDENCE_MISLABELED', 'SC1')])
        scored = evaluation.evaluate_records(self.ws, load('evals/adaptive/gold.example.json'))
        self.assertEqual((scored['evaluation_tier'], scored['routing_accuracy'], scored['evidence_attribution_accuracy']),
                         ('SIMULATED_FLOW', 1.0, 1.0))
        store.set_target(self.ws, {**TARGET, 'revision': 2, 'purpose': 'Failure handling in agent systems.'})
        self.assertEqual(store.status(self.ws, 'P0001')['permitted_use']['local_claims']['LC1'], 'REASSESS_FOR_TARGET')
        status = store.reassess(self.ws, load('shared/reassessment.example.json'))
        self.assertEqual(status['permitted_use']['local_claims']['LC1'], 'CANDIDATE_COMPARISON')
        self.assertEqual(status['next_action']['kind'], 'NONE')
        with_criteria = self.base/'with-criteria'
        store.init_corpus(with_criteria, 'owner', copy.deepcopy(TARGET), criteria=load('shared/exclusion-criteria.example.json'))
        self.assertEqual(sorted(store.criteria_index(store.load_corpus(with_criteria))), ['C-SCOPE', 'C-TYPE'])


if __name__ == '__main__':
    import unittest
    unittest.main()
