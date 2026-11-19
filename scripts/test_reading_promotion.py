"""Simulated-flow tests for upgrading a screened paper into a complete-reading run.

A fixture parser and a one-page fixture PDF stand in for real extraction. The tests show that
upgrade bookkeeping cannot shortcut complete reading or review; they are not real-paper trials.
"""
import copy
import json
from pathlib import Path
import shutil

import eval_adaptive_reading as evaluation
import reading_corpus as store
import reading_output_profiles as profiles
import reading_promotion as promotion
import reading_resources as resources
import reading_run_control as control
import reading_triage as triage
from reading_promotion_contracts import promotion_errors
from reading_run_check import inspect_run
from reading_run_records import RunError
import test_reading_run_control as run_fixtures
from test_reading_pdf_elements import FakeParser
from test_reading_triage import NONE, Workspace, decision

ROOT = Path(__file__).resolve().parent.parent
INVENTORY = [
    {'unit_id': 'S1', 'kind': 'SECTION', 'label': 'Native evidence', 'source_id': 'SRC-01', 'assigned_owner': 'owner',
     'parent_id': None, 'children': [], 'locators': [{'physical_page': 1, 'section': 'Native evidence', 'body': {}}]},
    {'unit_id': 'S2', 'kind': 'APPENDIX', 'label': 'Appendix A', 'source_id': 'SRC-01', 'assigned_owner': 'owner',
     'parent_id': None, 'children': [], 'locators': [{'physical_page': 1, 'section': 'Appendix A'}]}]


class PromotionFixture(Workspace):
    def setUp(self):
        super().setUp()
        # Historical promotions used the unversioned policy. Exercise resumption of that exact contract.
        corpus = store.load_corpus(self.ws)
        corpus.pop('reading_policy')
        control.write(self.ws/'corpus.json', corpus)

    def core_paper(self, extract=True):
        """Skimmed at L1 and routed to complete reading."""
        ratings = dict(topic_relevance='HIGH', methodological_relevance='HIGH', research_utility='HIGH')
        pid = self.skimmed(route=decision('PROMOTE_TO_L3', refs=('S-INTRO', 'T-MAIN')), **ratings)
        if extract:
            promotion.extract(self.ws, pid, parser=FakeParser())
        return pid

    def promote(self, pid, name='run', **kwargs):
        run = self.base/name
        return run, promotion.promote(self.ws, pid, run, 'owner', **kwargs)

    def merge(self, run, payload):
        return control.merge_handoff(run, payload)

    def sync(self, run):
        (run/'01_inventory.json').write_text(json.dumps(INVENTORY), encoding='utf8')
        packet, state = control.read(run/'paper_packet.json'), control.read(run/'execution_state.json')
        control.sync_inventory(run, packet, state)
        return control.commit(run, packet, state, 'Synced a test inventory.')


class UpgradeToCompleteReadingTests(PromotionFixture):
    def test_skim_to_complete_reading_starts_every_gate_from_the_beginning(self):
        pid = self.core_paper()
        screening_manifest = next((self.ws/'papers'/pid/'versions').glob('*/source_elements/manifest.json')).read_bytes()
        run, result = self.promote(pid, review_mode='FULL_DOUBLE_READ')
        packet = control.read(run/'paper_packet.json')
        self.assertEqual(packet['scope_mode'], 'COMPLETE_PAPER')
        self.assertEqual(packet['review_mode'], 'FULL_DOUBLE_READ')  # reviewer scope is chosen independently of depth
        self.assertEqual({gate: row['decision'] for gate, row in packet['gate_results'].items()},
                         {'G0': 'PENDING', 'G1': 'PENDING', 'G2': 'PENDING', 'G3': 'PENDING'})
        self.assertEqual((packet['units'], packet['claims'], packet['reviews'], packet['scope_exclusions']), ([], [], [], []))
        self.assertEqual(packet['paper_status'], 'IN_PROGRESS')
        self.assertEqual(packet['research_target']['target_id'], 'agent-methodology-review')
        self.assertEqual(packet['promotion']['from_depth'], 'L1')
        self.assertEqual(packet['promotion']['trigger'], {'kind': 'DECISION', 'ref': 'D02'})
        # Deterministic work is reused: same bytes, same frozen pages, no second extraction.
        self.assertTrue(result['reused']['native_extraction'])
        self.assertEqual((run/'source_elements/manifest.json').read_bytes(), screening_manifest)
        self.assertEqual(result['run_assessment']['next_action']['kind'], 'SOURCE_INVENTORY')
        usage = resources.summary(self.ws)
        self.assertEqual((usage['pdf_extraction_calls'], usage['extractions_reused']), (1, 1))
        # Reading notes travel as leads only.
        leads = (run/'handoffs/screening/leads.md').read_text(encoding='utf8')
        self.assertIn('leads only', leads)
        self.assertIn('Table 2 lists 82% task success', leads)
        self.assertIn('4.2 Ablations', leads)
        record = self.record(pid)
        self.assertEqual(record['upgrade_history'][-1]['to'], 'L3')
        self.assertIs(record['upgrade_history'][-1]['completion_inherited'], False)
        self.assertEqual(record['upgrade_history'][-1]['reused']['leads_from_pass_ids'], ['L0-01', 'L1-01'])
        status = store.status(self.ws, pid)
        self.assertEqual((status['tier'], status['l3_state'], status['independent_review']), ('SKIMMED', 'IN_PROGRESS', 'PENDING'))
        self.assertEqual(status['next_action']['kind'], 'CONTINUE_L3_RUN')
        self.assertEqual(inspect_run(run, require_review=False)[0]['code'], 'EMPTY_INVENTORY')
        self.expect('ALREADY_PROMOTED', promotion.promote, self.ws, pid, self.base/'second', 'owner')

    def test_promotion_needs_a_decision_or_the_user(self):
        pid = self.skimmed(route=decision('REMAIN_AT_L1', refs=('S-INTRO',)), topic_relevance='MEDIUM')
        self.expect('UPGRADE_NOT_AUTHORIZED', promotion.promote, self.ws, pid, self.base/'run', 'owner')
        self.assertFalse((self.base/'run').exists())
        store.request_depth(self.ws, pid, 'L3', 'Please read this one completely.')
        run, result = self.promote(pid)
        self.assertEqual(control.read(run/'paper_packet.json')['promotion']['trigger']['kind'], 'USER_REQUEST')
        self.assertFalse(result['reused']['native_extraction'])
        self.assertEqual(result['run_assessment']['next_action']['kind'], 'EXTRACT_ELEMENTS')

    def test_user_request_for_complete_reading_skips_screening(self):
        pid = store.add_record(self.ws, {'title': 'A paper to verify'}, 'L3', 'Full verified reading.')['paper_id']
        run, result = self.promote(pid, source=self.pdf())
        self.assertIsNone(result['from_depth'])
        self.assertEqual(control.read(run/'paper_packet.json')['promotion']['trigger']['kind'], 'USER_REQUEST')
        self.assertEqual(store.status(self.ws, pid)['tier'], 'UNSCREENED')

    def test_same_version_evidence_is_reused_and_another_version_is_not(self):
        pid = self.core_paper()
        before = store.status(self.ws, pid)
        self.assertEqual(before['effective_depth'], 'L1')
        self.assertFalse(promotion.attach_source(self.ws, pid, self.pdf())['attached'])  # identical bytes: nothing repeated
        self.assertTrue(promotion.extract(self.ws, pid, parser=FakeParser())['reused'])
        changed = self.attach(pid, b'\n% revised version')
        self.assertEqual(changed['stale_pass_ids'], ['L1-01'])
        status = store.status(self.ws, pid)
        self.assertEqual((status['effective_depth'], status['tier']), ('L0', 'METADATA_SCREENED'))
        self.assertEqual(status['routing']['stale_reason'], 'SOURCE_VERSION_CHANGED')
        self.assertEqual(status['next_action']['kind'], 'REEXAMINE_NEW_VERSION')
        self.assertEqual(status['coverage']['examined_by_kind'], {'ABSTRACT': 1, 'TITLE': 1})
        # The skim decision was made on other bytes; it no longer authorizes complete reading.
        self.expect('UPGRADE_NOT_AUTHORIZED', promotion.promote, self.ws, pid, self.base/'run', 'owner')
        store.request_depth(self.ws, pid, 'L3', 'Read the revised version completely.')
        run, result = self.promote(pid)
        self.assertEqual(result['from_depth'], 'L0')
        self.assertFalse(result['reused']['native_extraction'])
        self.assertFalse((run/'source_elements').exists())
        leads = (run/'handoffs/screening/leads.md').read_text(encoding='utf8')
        self.assertIn('VERSION_DIFFERENCE', leads)
        self.assertNotIn('Table 2 lists 82% task success', leads)
        self.assertEqual(control.read(run/'paper_packet.json')['sources'][0]['sha256'], changed['sha256'])

    def test_new_version_can_be_skimmed_again_at_the_depth_already_authorized(self):
        pid = self.core_paper(extract=False)
        self.attach(pid, b'\n% revised version')
        skim = self.l1(pid, decision('PROMOTE_TO_L3', refs=('S-INTRO',)), topic_relevance='HIGH', research_utility='HIGH')
        status = store.submit(self.ws, skim)
        self.assertEqual(status['effective_depth'], 'L1')
        history = self.record(pid)['upgrade_history'][-1]
        self.assertEqual(history['trigger'], {'kind': 'REEXAMINE_NEW_VERSION', 'ref': 'L1-01'})
        self.assertEqual([row['status'] for row in self.record(pid)['passes']], ['CURRENT', 'STALE_SOURCE_VERSION', 'CURRENT'])

    def test_altered_extraction_is_not_adopted(self):
        pid = self.core_paper()
        page = next((self.ws/'papers'/pid/'versions').glob('*/source_elements/page-0001.json'))
        page.write_text(page.read_text(encoding='utf8').replace('Native evidence', 'Edited evidence'), encoding='utf8')
        run, result = self.promote(pid)
        self.assertFalse(result['reused']['native_extraction'])
        self.assertIn('not reused', result['reused']['native_extraction_note'])
        self.assertFalse((run/'source_elements').exists())
        self.assertEqual(result['run_assessment']['next_action']['kind'], 'EXTRACT_ELEMENTS')

    def test_refused_or_failed_promotion_leaves_no_trace(self):
        pid = self.skimmed(route=decision('REMAIN_AT_L1', refs=('S-INTRO',)), topic_relevance='MEDIUM')
        before = (self.ws/'papers'/pid/'screening.json').read_bytes()
        self.expect('UPGRADE_NOT_AUTHORIZED', promotion.promote, self.ws, pid, self.base/'run', 'owner',
                    source=self.pdf(b'\n% another version'))
        self.assertEqual((self.ws/'papers'/pid/'screening.json').read_bytes(), before)  # the new file was not attached
        core = self.core_paper()
        before = (self.ws/'papers'/core/'screening.json').read_bytes()
        original = promotion.render_leads
        promotion.render_leads = lambda *args: (_ for _ in ()).throw(OSError('disk full'))
        self.addCleanup(setattr, promotion, 'render_leads', original)
        with self.assertRaises(OSError):
            promotion.promote(self.ws, core, self.base/'run', 'owner')
        self.assertFalse((self.base/'run').exists())
        self.assertEqual((self.ws/'papers'/core/'screening.json').read_bytes(), before)
        promotion.render_leads = original
        self.promote(core)
        existing = self.base/'taken'
        existing.mkdir()
        other = self.core_paper()
        self.expect('RUN_EXISTS', promotion.promote, self.ws, other, existing, 'owner')
        self.assertEqual(list(existing.iterdir()), [])

    def test_new_source_version_after_promotion_gets_its_own_run(self):
        pid = self.core_paper()
        first, _ = self.promote(pid, name='run-v1')
        self.attach(pid, b'\n% revised version')
        status = store.status(self.ws, pid)
        self.assertEqual((status['l3_state'], status['tier']), ('OTHER_SOURCE_VERSION', 'METADATA_SCREENED'))
        store.request_depth(self.ws, pid, 'L3', 'Read the revised version completely.')
        second, _ = self.promote(pid, name='run-v2')
        record = self.record(pid)
        self.assertEqual(record['l3']['run_path'].split('/')[-1], 'run-v2')
        self.assertEqual([row['run_path'].split('/')[-1] for row in record['l3_history']], ['run-v1'])
        self.assertEqual(store.status(self.ws, pid)['l3_state'], 'IN_PROGRESS')
        self.assertTrue((first/'paper_packet.json').is_file())  # the earlier run is kept, untouched

    def test_text_snapshot_supports_a_skim_but_not_complete_reading(self):
        pid = self.add()
        store.request_depth(self.ws, pid, 'L3', 'Verify it.')
        snapshot = self.base/'paper.html'
        snapshot.write_text('<html>saved page</html>', encoding='utf8')
        self.assertEqual(promotion.attach_source(self.ws, pid, snapshot)['kind'], 'TEXT_SNAPSHOT')
        self.expect('FULL_TEXT_REQUIRED', promotion.promote, self.ws, pid, self.base/'run', 'owner')
        self.expect('FULL_TEXT_REQUIRED', promotion.extract, self.ws, pid)
        binary = self.base/'paper.bin'
        binary.write_bytes(b'\x00\x01')
        self.expect('INVALID_SOURCE', promotion.attach_source, self.ws, pid, binary)


class NoShortcutTests(PromotionFixture):
    """Earlier screening must not let unread content through COMPLETE_PAPER acceptance."""

    def setUp(self):
        super().setUp()
        self.pid = self.core_paper()
        self.run, _ = self.promote(self.pid)
        (self.run/'01_scope_gaps.md').write_text('Checked the one-page source against the inventory.', encoding='utf8')

    def handoff_error(self, payload):
        with self.assertRaises(RunError) as context:
            self.merge(self.run, payload)
        self.assertEqual(context.exception.code, 'INVALID_HANDOFF')
        return str(context.exception)

    def test_screening_notes_cannot_pass_a_gate_or_check_a_unit(self):
        self.sync(self.run)
        leads = 'handoffs/screening/leads.md'
        message = self.handoff_error({'writer_id': 'owner', 'gate_results': {'G0': {
            'decision': 'PASS', 'evidence_refs': [leads, 'handoffs/screening/screening_record.json'], 'open_items': []}}})
        self.assertIn('SCREENING_NOTE_NOT_EVIDENCE', message)
        self.merge(self.run, {'writer_id': 'owner', 'gate_results': {'G0': {
            'decision': 'PASS', 'evidence_refs': ['01_inventory.json', '01_scope_gaps.md'], 'open_items': []}}})
        for state in ['CHECKED', 'NON_INFORMATIVE', 'UNDERSTOOD']:
            message = self.handoff_error({'writer_id': 'owner', 'units': [{
                'unit_id': 'S2', 'read_state': state, 'understanding_note': 'Already covered by the earlier skim.',
                'evidence_refs': [leads]}]})
            self.assertIn('SCREENING_NOTE_NOT_EVIDENCE', message, state)
        packet = control.read(self.run/'paper_packet.json')
        self.assertEqual({unit['read_state'] for unit in packet['units']}, {'INVENTORIED'})

    def test_lead_references_are_recognized_however_the_path_is_spelled(self):
        import os
        self.sync(self.run)
        spellings = ['handoffs//screening/leads.md', 'handoffs/./screening/leads.md', './handoffs/screening/leads.md',
                     'handoffs/screening/../screening/leads.md', 'evidence/../handoffs/screening/leads.md',
'handoffs\\screening\\leads.md',
                     str(self.run/'handoffs'/'screening'/'leads.md')]
        if os.name == 'nt':
            spellings += ['Handoffs/Screening/LEADS.md']
        for ref in spellings:
            message = self.handoff_error({'writer_id': 'owner', 'gate_results': {'G0': {
                'decision': 'PASS', 'evidence_refs': [ref], 'open_items': []}}})
            self.assertIn('SCREENING_NOTE_NOT_EVIDENCE', message, ref)
            packet = control.read(self.run/'paper_packet.json')
            packet['scope_exclusions'] = [{'unit_id': 'S2', 'user_authorization_ref': ref}]
            self.assertIn('PROMOTION_SCOPE_ABUSE', {error['code'] for error in promotion_errors(self.run, packet)}, ref)

    def test_removing_the_promotion_field_does_not_switch_the_checks_off(self):
        self.sync(self.run)
        packet = control.read(self.run/'paper_packet.json')
        del packet['promotion']
        control.write(self.run/'paper_packet.json', packet)
        self.assertIn('PROMOTION_RECORD_INVALID', {error['code'] for error in inspect_run(self.run, require_review=False)})
        self.assertIn('PROMOTION_RECORD_INVALID', self.handoff_error({'writer_id': 'owner', 'gate_results': {'G0': {
            'decision': 'PASS', 'evidence_refs': ['01_inventory.json', '01_scope_gaps.md'], 'open_items': []}}}))

    def test_unread_units_block_complete_paper_gates_whatever_they_are_called(self):
        self.sync(self.run)
        self.merge(self.run, {'writer_id': 'owner', 'gate_results': {'G0': {
            'decision': 'PASS', 'evidence_refs': ['01_inventory.json', '01_scope_gaps.md'], 'open_items': []}}})
        gate = lambda name: {'writer_id': 'owner', 'gate_results': {name: {
            'decision': 'PASS', 'evidence_refs': ['01_scope_gaps.md'], 'open_items': []}}}
        self.assertIn('Complete actual unit reading', self.handoff_error(gate('G1')))
        # Relabelling unread content does not remove it from a complete-paper scope.
        assessment = self.merge(self.run, {'writer_id': 'owner', 'units': [{
            'unit_id': 'S2', 'read_state': 'OUT_OF_SCOPE', 'understanding_note': 'The router judged the appendix irrelevant.'}]})
        self.assertEqual(assessment['next_action']['kind'], 'READ_AND_RECORD_UNITS')
        self.assertIn('S2', assessment['next_action']['unit_ids'])
        self.assertIn('Complete actual unit reading', self.handoff_error(gate('G1')))
        self.assertIn('Complete actual unit reading', self.handoff_error(gate('G2')))
        codes = {(error['code'], error['item']) for error in inspect_run(self.run, require_review=False)}
        self.assertIn(('UNIT_INCOMPLETE', 'S2'), codes)
        self.assertIn(('GATE_PENDING', 'G1'), codes)

    def test_a_routing_decision_is_not_user_authorization_to_narrow_scope(self):
        self.sync(self.run)
        packet = control.read(self.run/'paper_packet.json')
        packet['scope_mode'] = 'USER_DEFINED_SCOPE'
        packet['units'][1]['read_state'] = 'OUT_OF_SCOPE'
        packet['scope_exclusions'] = [{'unit_id': 'S2', 'reason': 'Screening routed this paper to targeted reading only.',
                                       'scope_revision': packet['scope_revision'],
                                       'user_authorization_ref': 'handoffs/screening/screening_record.json'}]
        control.write(self.run/'paper_packet.json', packet)
        codes = {(error['code'], error['item']) for error in inspect_run(self.run, require_review=False)}
        self.assertIn(('PROMOTION_SCOPE_ABUSE', 'S2'), codes)
        self.assertIn('PROMOTION_SCOPE_ABUSE', self.handoff_error({'writer_id': 'owner', 'gate_results': {'G0': {
            'decision': 'PASS', 'evidence_refs': ['01_inventory.json', '01_scope_gaps.md'], 'open_items': []}}}))

    def test_upgrade_history_and_source_binding_cannot_be_rewritten(self):
        record = self.run/'handoffs/screening/promotion.json'
        data = json.loads(record.read_text(encoding='utf8'))
        data['from_depth'] = 'L2'
        record.write_text(json.dumps(data), encoding='utf8')
        self.assertIn('PROMOTION_RECORD_CHANGED', {error['code'] for error in inspect_run(self.run, require_review=False)})
        packet = control.read(self.run/'paper_packet.json')
        packet['sources'][0]['sha256'] = '0' * 64
        self.assertIn('PROMOTION_SOURCE_MISMATCH', {error['code'] for error in promotion_errors(self.run, packet)})

    def test_acceptance_cannot_be_fabricated_without_an_independent_reviewer(self):
        self.sync(self.run)
        self.assertIn('independent review supplies G3', self.handoff_error({'writer_id': 'owner', 'gate_results': {'G3': {
            'decision': 'PASS', 'evidence_refs': ['01_scope_gaps.md'], 'open_items': []}}}))
        review = json.loads((ROOT/'shared/review-record.template.json').read_text(encoding='utf8'))
        review.update({'template_only': False, 'review_id': 'R1', 'decision': 'VERIFIED_FOR_SCOPE',
                       'gate_decisions': {gate: 'PASS' for gate in ['G0', 'G1', 'G2', 'G3']}})
        for reviewer in ['owner', 'independent-reviewer']:
            with self.assertRaises(RunError) as context:
                control.ingest_review(self.run, {**review, 'reviewer_id': reviewer})
            self.assertIn(context.exception.code, {'PREFLIGHT_REQUIRED', 'INVALID_REVIEW', 'INVALID_REVIEW_COVERAGE'})
        with self.assertRaises(RunError) as context:
            control.ingest_review(self.run, {**review, 'reviewer_id': 'owner', 'decision': 'REVISION_REQUIRED',
                                             'gate_decisions': {gate: 'FAIL' for gate in ['G0', 'G1', 'G2', 'G3']}})
        self.assertEqual(context.exception.code, 'INVALID_REVIEW')
        self.assertIn('distinct', str(context.exception))
        packet = control.read(self.run/'paper_packet.json')
        self.assertEqual((packet['reviews'], packet['gate_results']['G3']['decision']), ([], 'PENDING'))
        self.assertEqual(control.assess(self.run)['paper_accepted'], False)
        tiers = {row['paper_id']: row for row in store.evidence_tiers(self.ws)['papers']}
        self.assertEqual((tiers[self.pid]['tier'], tiers[self.pid]['l3_state']), ('SKIMMED', 'IN_PROGRESS'))
        result = store.check_synthesis(self.ws, [{'synthesis_claim_id': 'SC1', 'text': 'Claimed as verified.',
                                                 'evidence_basis': 'ACCEPTED', 'strength': 'CONCLUSION',
                                                 'support': [{'paper_id': self.pid, 'claim_id': 'C1'}]}])
        self.assertEqual([error['code'] for error in result['errors']], ['SHALLOW_EVIDENCE_MISLABELED'])


class ContractCompatibilityTests(PromotionFixture):
    def test_plain_complete_reading_runs_are_unchanged(self):
        run = self.base/'plain'
        assessment = control.initialize(run, self.pdf(), 'owner', 'en')
        packet = control.read(run/'paper_packet.json')
        self.assertNotIn('promotion', packet)
        self.assertNotIn('promotion', control.read(run/'task.json'))
        self.assertEqual(packet['skill_revision'], '2.10')
        self.assertEqual((packet['scope_mode'], packet['review_mode']), ('COMPLETE_PAPER', 'KEY_CLAIMS'))
        self.assertEqual(assessment['next_action']['kind'], 'EXTRACT_ELEMENTS')
        self.assertEqual(promotion_errors(run, packet), [])
        template = json.loads((ROOT/'shared/packet.template.json').read_text(encoding='utf8'))
        self.assertNotIn('promotion', template)
        self.assertFalse(any('screening' in key or 'depth' in key for key in template))

    def test_legacy_accepted_run_keeps_its_acceptance_and_can_be_linked(self):
        fixture = run_fixtures.ReadingRunControlTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        before = {path.relative_to(fixture.root).as_posix(): path.read_bytes() for path in fixture.root.rglob('*') if path.is_file()}
        self.assertEqual(control.assess(fixture.root)['terminal_decision'], 'ACCEPTED')
        self.assertEqual(inspect_run(fixture.root), [])
        pid = self.add('A previously accepted paper')
        status = store.link_run(self.ws, pid, fixture.root)
        self.assertEqual((status['tier'], status['l3_state']), ('VERIFIED_COMPLETE', 'ACCEPTED'))
        self.assertEqual(self.record(pid)['upgrade_history'][-1]['trigger']['kind'], 'LINKED_EXISTING_RUN')
        after = {path.relative_to(fixture.root).as_posix(): path.read_bytes() for path in fixture.root.rglob('*') if path.is_file()}
        self.assertEqual(before, after)  # linking and tiering never write into the run

    def test_promotion_record_of_another_version_is_refused(self):
        pid = self.core_paper()
        run, _ = self.promote(pid)
        packet = control.read(run/'paper_packet.json')
        packet['promotion']['schema_version'] = 2
        self.assertEqual([error['code'] for error in promotion_errors(run, packet)], ['PROMOTION_RECORD_INVALID'])


class ResourceAndProfileTests(PromotionFixture):
    def test_ledger_records_measured_work_and_refuses_estimates(self):
        pid = self.core_paper()
        promotion.read_pages(self.ws, pid, [1])
        promotion.read_pages(self.ws, pid, [1])
        promotion.read_pages(self.ws, pid, [1], view='locator')
        self.assertIn('Native evidence', promotion.read_pages(self.ws, pid, [1]))
        usage = resources.summary(self.ws)
        self.assertEqual(usage['page_reads'], {'calls': 4, 'distinct_page_views': 2, 'repeated_page_reads': 2})
        self.assertEqual((usage['pdf_extraction_calls'], usage['pages_extracted']), (1, 1))
        self.assertIsNotNone(usage['helper_duration_s'])
        self.assertIsNone(usage['reported_model_calls'])
        self.assertEqual(usage['tokens']['input'], None)
        self.assertTrue(any('not a count of zero' in line for line in usage['unavailable']))
        self.expect('USAGE_SOURCE_REQUIRED', resources.log_usage, self.ws, 'MODEL_CALL', pid, 'L1', tokens_in=1200)
        resources.log_usage(self.ws, 'MODEL_CALL', pid, 'L1', tokens_in=1200, tokens_out=300, measured_by='API usage field')
        resources.log_usage(self.ws, 'MODEL_CALL', pid, 'L0')
        resources.log_usage(self.ws, 'REVIEWER_CALL', pid, 'L3')
        usage = resources.summary(self.ws, pid)
        self.assertEqual(usage['reported_model_calls'], {'total': 2, 'by_depth': {'L0': 1, 'L1': 1}})
        self.assertEqual(usage['reported_reviewer_calls'], {'total': 1, 'by_depth': {'L3': 1}, 'below_L3': 0})
        self.assertEqual((usage['tokens']['input'], usage['tokens']['calls_with_input_count'], usage['tokens']['reported_calls']), (1200, 1, 3))
        self.assertTrue(any('partial' in line for line in usage['unavailable']))
        self.expect('EXTRACTION_REQUIRED', promotion.read_pages, self.ws, self.skimmed(topic_relevance='MEDIUM'), [1])

    def test_profiles_change_presentation_not_evidence_status(self):
        metadata = self.add('A metadata-only paper')
        store.submit(self.ws, {**self.l0(metadata, **NONE), 'decision': decision('EXCLUDE_FOR_TARGET')})
        self.assertTrue(profiles.plan(self.ws, metadata, 'PAPER_CARD')['allowed'])
        for name in ['QUICK_SUMMARY', 'TECHNICAL_EXPLANATION', 'PEER_REVIEW_STYLE', 'FULL_READING_REPORT', 'REPRODUCTION_CHECKLIST']:
            self.assertFalse(profiles.plan(self.ws, metadata, name)['allowed'], name)
        card = profiles.render_card(self.ws, metadata)
        text = (self.ws/card['file']).read_text(encoding='utf8')
        self.assertIn('basis=METADATA tier=METADATA_SCREENED review=NONE', text)
        self.assertIn('The paper body was not read', text)
        self.assertIn('EXCLUDE_FOR_TARGET (ROUTER_RULES; a triage decision, not a review)', text)
        skim = self.skimmed(topic_relevance='MEDIUM')
        plan = profiles.plan(self.ws, skim, 'GROUP_MEETING')
        self.assertTrue(plan['allowed'])
        self.assertFalse(profiles.plan(self.ws, skim, 'PEER_REVIEW_STYLE')['allowed'])
        slides = self.base/'slides.md'
        slides.write_text('# Group meeting\n\nThis paper is fully verified.\n', encoding='utf8')
        self.expect('EVIDENCE_BANNER_MISSING', profiles.register, self.ws, skim, 'GROUP_MEETING', slides)
        slides.write_text(plan['banner']['marker'] + '\n\n> ' + plan['banner']['statement'] + '\n\n# Group meeting\n', encoding='utf8')
        profiles.register(self.ws, skim, 'GROUP_MEETING', slides)
        self.assertTrue(profiles.check(self.ws, skim, 'GROUP_MEETING')['current'])
        self.assertIn('not a complete reading', plan['banner']['statement'])
        self.expect('PROFILE_NOT_SUPPORTED', profiles.register, self.ws, skim, 'REPRODUCTION_CHECKLIST', slides)
        # Deeper reading changes the evidence; the old presentation is flagged, not silently relabelled.
        store.route(self.ws, skim, decision('PROMOTE_TO_L2', by='AGENT_JUDGMENT', refs=('S-INTRO',), focus=['3.2 Coordination']))
        store.submit(self.ws, self.l2(skim))
        self.assertEqual(profiles.check(self.ws, skim, 'GROUP_MEETING')['errors'][0]['code'], 'OUTPUT_STALE')

    def test_new_presentation_of_an_accepted_reading_does_not_reopen_review(self):
        fixture = run_fixtures.ReadingRunControlTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        pid = self.add('An accepted complete reading')
        store.link_run(self.ws, pid, fixture.root)
        plan = profiles.plan(self.ws, pid, 'PEER_REVIEW_STYLE')
        self.assertTrue(plan['allowed'])
        self.assertEqual((plan['evidence_status']['reading_basis'], plan['evidence_status']['independent_review']),
                         ('COMPLETE_READING', 'ACCEPTED'))
        text = plan['banner']['marker'] + '\n\n' + plan['banner']['statement'] + '\n\n# Review-style notes\n'
        inside = fixture.root/'peer_review.md'
        inside.write_text(text, encoding='utf8')
        self.expect('OUTPUT_INSIDE_RUN', profiles.register, self.ws, pid, 'PEER_REVIEW_STYLE', inside)
        inside.unlink()
        outside = self.base/'peer_review.md'
        outside.write_text(text, encoding='utf8')
        profiles.register(self.ws, pid, 'PEER_REVIEW_STYLE', outside)
        self.assertEqual(control.assess(fixture.root)['terminal_decision'], 'ACCEPTED')
        self.assertTrue(profiles.check(self.ws, pid, 'PEER_REVIEW_STYLE')['current'])
        fixture.packet['claims'][0]['allowed_use'] = 'HOLD'  # the science changed after acceptance
        fixture.save()
        self.assertEqual(profiles.check(self.ws, pid, 'PEER_REVIEW_STYLE')['errors'][0]['code'], 'OUTPUT_STALE')
        self.assertFalse(profiles.plan(self.ws, pid, 'PEER_REVIEW_STYLE')['evidence_status']['independent_review'] == 'ACCEPTED')

    def test_card_goes_stale_when_what_it_shows_changes(self):
        pid = self.add('A metadata-only paper')
        store.submit(self.ws, {**self.l0(pid, topic_relevance='LOW'), 'decision': decision('BACKGROUND_ONLY')})
        profiles.render_card(self.ws, pid)
        self.assertTrue(profiles.check(self.ws, pid, 'PAPER_CARD')['current'])
        store.route(self.ws, pid, decision('PROMOTE_TO_L1', by='AGENT_JUDGMENT'))
        self.assertEqual(profiles.check(self.ws, pid, 'PAPER_CARD')['errors'][0]['code'], 'OUTPUT_STALE')
        profiles.render_card(self.ws, pid)
        store.set_target(self.ws, {**json.loads(json.dumps(store.load_corpus(self.ws)['research_target'])), 'revision': 2,
                                   'purpose': 'A different purpose.'})
        self.assertEqual(profiles.check(self.ws, pid, 'PAPER_CARD')['errors'][0]['code'], 'OUTPUT_STALE')
        self.expect('INVALID_ARGUMENT', profiles.check, self.ws, '../..', 'PAPER_CARD')
        self.assertFalse((self.ws.parent/'outputs').exists() or (self.ws/'outputs'/'..').resolve() != self.ws)


class BehaviourEvaluationTests(PromotionFixture):
    def test_router_cases_are_reported_as_simulated(self):
        cases = json.loads((ROOT/'evals/adaptive/router_cases.json').read_text(encoding='utf8'))['cases']
        result = evaluation.evaluate_router(cases)
        self.assertEqual((result['evaluation_tier'], result['real_paper_e2e']), ('SIMULATED_FLOW', 'NOT_RUN'))
        self.assertEqual(result['misrouted_case_ids'], [])
        self.assertEqual(result['missed_core_case_ids'], [])
        self.assertEqual(result['core_papers_deferred'], ['R10'])
        broken = copy.deepcopy(cases[2])
        broken['acceptable_decisions'] = ['EXCLUDE_FOR_TARGET']
        self.assertEqual(evaluation.evaluate_router([broken])['routing_accuracy'], 0.0)
        missed = evaluation.score_decisions([{'case_id': 'X', 'decision': 'BACKGROUND_ONLY', 'is_core': True,
                                              'acceptable_decisions': ['PROMOTE_TO_L3']}])
        self.assertEqual((missed['core_paper_miss_rate'], missed['routing_accuracy']), (1.0, 0.0))

    def test_recorded_output_is_scored_against_gold_without_inventing_measurements(self):
        core = self.core_paper()
        shallow = self.add('A marginal paper')
        store.submit(self.ws, {**self.l0(shallow, topic_relevance='LOW'), 'decision': decision('BACKGROUND_ONLY')})
        sha = self.record(core)['full_text']['current_sha256']
        gold = {'evaluation_tier': 'REAL_PAPER_E2E', 'papers': [
            {'paper_id': core, 'is_core': True, 'acceptable_decisions': ['PROMOTE_TO_L3'], 'source_sha256': sha,
             'statements': [{'path': 'card.headline_evidence[0]', 'expected_attribution': 'REPORTED_OBSERVATION'},
                            {'path': 'card.core_method', 'expected_attribution': 'REPORTED_OBSERVATION'}],
             'unsupported_statements': ['card.potential_limitations[0]']},
            {'paper_id': shallow, 'is_core': True, 'acceptable_decisions': ['PROMOTE_TO_L1'],
             'statements': [{'path': 'screening.potential_value[0]', 'expected_attribution': 'AUTHOR_CLAIM'}]}]}
        result = evaluation.evaluate_records(self.ws, gold)
        self.assertEqual(result['evaluation_tier'], 'SIMULATED_FLOW')  # one gold paper has no bound source bytes
        self.assertIn(shallow, result['tier_note'])
        self.assertEqual((result['routing_accuracy'], result['core_paper_miss_rate']), (0.5, 0.5))
        self.assertEqual(result['evidence_attribution_accuracy'], round(2 / 3, 4))
        self.assertEqual((result['unsupported_claim_rate'], result['recorded_statements']), (round(1 / 7, 4), 7))
        self.assertIsNone(result['computational_cost']['tokens']['input'])
        self.assertIsNone(result['reviewer_utilization']['reported_reviewer_calls'])
        gold['papers'] = gold['papers'][:1]
        self.assertEqual(evaluation.evaluate_records(self.ws, gold)['evaluation_tier'], 'REAL_PAPER_E2E')
        with self.assertRaises(ValueError):
            evaluation.evaluate_records(self.ws, {'evaluation_tier': 'STATIC_UNIT', 'papers': []})


if __name__ == '__main__':
    import unittest
    unittest.main()
