"""Verify mode boundaries without treating structural checks as paper understanding."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import reading_run_control as control
from reading_run_check import inspect_run
from reading_review_contracts import visual_review_errors, visual_fingerprint
from reading_review_modes import (continuation_errors, coverage_errors, review_baseline,
                                  review_delta, review_mode, review_plan)
import test_reading_run_control as fixtures


class ReviewPlanTests(unittest.TestCase):
    def packet(self, ordinary=30):
        units = [{'unit_id': 'K1', 'kind': 'SECTION', 'dependencies': []}]
        units += [{'unit_id': 'U%02d' % n, 'kind': 'SECTION', 'dependencies': []}
                  for n in range(ordinary)]
        return {'review_mode': 'KEY_CLAIMS', 'units': units,
                'claims': [{'claim_id': 'C1', 'supporting_units': ['K1']}],
                'experiments': [], 'issues': [], 'review_requirements': {}}

    def test_missing_mode_preserves_full_double_read(self):
        self.assertEqual(review_mode({}), 'FULL_DOUBLE_READ')

    def test_unknown_mode_fails_closed(self):
        packet = self.packet()
        packet['review_mode'] = 'KEY_CLAIM'
        with self.assertRaises((ValueError, TypeError)):
            review_plan(packet)

    def test_small_ordinary_set_is_completely_sampled(self):
        for count in range(6):
            with self.subTest(count=count):
                plan = review_plan(self.packet(count))
                self.assertEqual(len(plan['sampled_unit_ids']), count)
                self.assertEqual(len(plan['required_unit_ids']), count + 1)

    def test_sample_is_deterministic_and_twenty_percent_above_minimum(self):
        packet = self.packet(30)
        plan = review_plan(packet)
        self.assertEqual(plan, review_plan(copy.deepcopy(packet)))
        self.assertEqual(len(plan['sampled_unit_ids']), 6)
        self.assertEqual(set(plan['key_claim_ids']), {'C1'})
        self.assertEqual(set(plan['key_unit_ids']), {'K1'})
        self.assertNotIn('K1', plan['sampled_unit_ids'])
        self.assertEqual(set(plan['required_unit_ids']),
                         {'K1'} | set(plan['sampled_unit_ids']))

    def test_sample_covers_each_present_ordinary_kind(self):
        packet = self.packet(30)
        for i, kind in enumerate(['APPENDIX', 'TABLE', 'EQUATION', 'ALGORITHM']):
            packet['units'][i + 1]['kind'] = kind
        plan = review_plan(packet)
        kinds = {u['kind'] for u in packet['units']
                 if u['unit_id'] in plan['sampled_unit_ids']}
        self.assertEqual(kinds, {'SECTION', 'APPENDIX', 'TABLE', 'EQUATION', 'ALGORITHM'})

    def test_all_claims_are_key_even_when_owner_supplies_subset(self):
        packet = self.packet()
        packet['claims'].append({'claim_id': 'C2', 'supporting_units': ['U00']})
        packet['review_requirements']['key_claim_ids'] = ['C1']
        plan = review_plan(packet)
        self.assertEqual(set(plan['key_claim_ids']), {'C1', 'C2'})
        self.assertIn('U00', plan['key_unit_ids'])

    def test_key_unit_closure_includes_dependencies_and_parent_context(self):
        packet = self.packet()
        packet['units'][0].update({'kind': 'PANEL', 'parent_id': 'U00',
                                   'dependencies': ['U01']})
        packet['units'][1].update({'kind': 'FIGURE', 'children': ['K1']})
        packet['units'][2]['dependencies'] = ['U02']
        plan = review_plan(packet)
        self.assertTrue({'K1', 'U00', 'U01', 'U02'} <= set(plan['key_unit_ids']))

    def test_related_experiment_units_cannot_escape_key_coverage(self):
        packet = self.packet()
        packet['claims'][0]['experiment_refs'] = ['E1']
        packet['experiments'] = [{'experiment_id': 'E1', 'unit_refs': ['U00'],
                                  'claim_refs': ['C1']}]
        self.assertIn('U00', review_plan(packet)['key_unit_ids'])

    def test_explicit_extra_key_unit_is_mandatory(self):
        packet = self.packet()
        packet['review_requirements']['key_unit_ids'] = ['U29']
        self.assertIn('U29', review_plan(packet)['key_unit_ids'])

    def test_unknown_claim_support_and_dependency_are_rejected(self):
        for key in ['supporting_units', 'dependencies']:
            packet = self.packet()
            if key == 'supporting_units':
                packet['claims'][0][key] = ['missing']
            else:
                packet['units'][0][key] = ['missing']
            with self.subTest(key=key), self.assertRaises((ValueError, TypeError)):
                review_plan(packet)

    def test_full_double_read_requires_every_unit(self):
        packet = self.packet()
        packet['review_mode'] = 'FULL_DOUBLE_READ'
        plan = review_plan(packet)
        self.assertEqual(set(plan['required_unit_ids']),
                         {u['unit_id'] for u in packet['units']})
        self.assertEqual(plan['coverage_label'], 'COMPLETE_INDEPENDENT_DOUBLE_READ')

    def test_legacy_coverage_does_not_add_new_experiment_reference_validation(self):
        packet = self.packet()
        del packet['review_mode']
        packet['claims'][0]['experiment_refs'] = ['E-missing']
        review = {'checked_unit_ids': [u['unit_id'] for u in packet['units']],
                  'checked_claim_ids': ['C1']}
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(coverage_errors(Path(directory), packet, review), [])


class ReviewModeIntegrationTests(unittest.TestCase):
    save = fixtures.ReadingRunControlTests.save
    cli = fixtures.ReadingRunControlTests.cli
    write_payload = fixtures.ReadingRunControlTests.write_payload

    def setUp(self):
        fixtures.ReadingRunControlTests.setUp(self)
        self.packet.update({'skill_revision': '2.6', 'review_mode': 'KEY_CLAIMS',
                            'review_requirements': {'direct_visual_inspection': True}})
        original = self.packet['units'][0]
        for i in range(2, 32):
            unit = copy.deepcopy(original)
            unit['unit_id'] = 'F%d' % i
            self.packet['units'].append(unit)
        self.inventory = copy.deepcopy(self.packet['units'])
        self.plan = review_plan(self.packet)
        review = self.packet['reviews'][0]
        review.update({'review_id': 'R-key', 'review_mode': 'KEY_CLAIMS',
                       'coverage_label': 'COMPLETE_READING_KEY_CLAIMS_CHECKED',
                       'reviewer_session_id': 'reviewer-session',
                       'coverage_check': {'source_structure_checked': True,
                                          'owner_coverage_checked': True,
                                          'omissions': [],
                                          'evidence_refs': ['source_check.md']},
                       'checked_unit_ids': self.plan['required_unit_ids'],
                       'checked_claim_ids': self.plan['key_claim_ids'],
                       'visual_inspection': {
                           'status': 'COMPLETE', 'direct_pixels_available': True,
                           'session_id': 'reviewer-session', 'blocked_unit_ids': [],
                           'tool_evidence_refs': ['source_check.md'],
                           'units': [{'unit_id': uid, 'actually_viewed': True,
                                      'artifact_refs': ['page.png'],
                                      'observations': 'The two branches converge at the output.'}
                                     for uid in self.plan['required_unit_ids']]}})
        self.seal()

    def seal(self):
        control.render(self.root, self.packet)
        self.save()
        review = self.packet['reviews'][0]
        review['reviewed_content_sha256'] = control.content_fingerprint(self.root, self.packet)
        review['reviewed_visual_evidence_sha256'] = visual_fingerprint(self.root, review)
        self.save()

    def test_key_mode_accepts_bounded_review_after_complete_owner_reading(self):
        review = self.packet['reviews'][0]
        self.assertLess(len(review['checked_unit_ids']), len(self.packet['units']))
        self.assertEqual(coverage_errors(self.root, self.packet, review), [])
        self.assertEqual(visual_review_errors(self.root, self.packet, review), [])
        self.assertEqual(inspect_run(self.root), [])

    def test_unsampled_owner_unit_must_still_be_read(self):
        ordinary = next(u for u in self.packet['units']
                        if u['unit_id'] not in self.plan['required_unit_ids'])
        ordinary['read_state'] = 'READ'
        self.seal()
        self.assertIn('UNIT_INCOMPLETE', {e['code'] for e in inspect_run(self.root)})

    def test_unsampled_owner_visual_must_still_be_viewed(self):
        ordinary = next(u for u in self.packet['units']
                        if u['unit_id'] not in self.plan['required_unit_ids'])
        ordinary['visual_review']['actually_viewed'] = False
        self.seal()
        self.assertIn('VISUAL_NOT_VIEWED', {e['code'] for e in inspect_run(self.root)})

    def test_key_claim_omission_is_rejected(self):
        review = copy.deepcopy(self.packet['reviews'][0])
        review['checked_claim_ids'] = []
        self.assertTrue(coverage_errors(self.root, self.packet, review))

    def test_supporting_unit_omission_is_rejected(self):
        review = copy.deepcopy(self.packet['reviews'][0])
        review['checked_unit_ids'].remove('F1')
        self.assertTrue(coverage_errors(self.root, self.packet, review))

    def test_required_visual_omission_is_rejected(self):
        review = copy.deepcopy(self.packet['reviews'][0])
        review['visual_inspection']['units'] = [
            u for u in review['visual_inspection']['units'] if u['unit_id'] != 'F1']
        review['reviewed_visual_evidence_sha256'] = visual_fingerprint(self.root, review)
        self.assertTrue(visual_review_errors(self.root, self.packet, review))

    def test_full_mode_cannot_reuse_key_mode_label_or_partial_coverage(self):
        self.packet['review_mode'] = 'FULL_DOUBLE_READ'
        review = self.packet['reviews'][0]
        self.assertTrue(coverage_errors(self.root, self.packet, review))

    def test_key_mode_cannot_claim_full_double_read_label(self):
        review = copy.deepcopy(self.packet['reviews'][0])
        review['coverage_label'] = 'COMPLETE_INDEPENDENT_DOUBLE_READ'
        self.assertTrue(coverage_errors(self.root, self.packet, review))

    def test_coverage_map_and_actual_evidence_are_required(self):
        for field, value in [('source_structure_checked', False),
                             ('owner_coverage_checked', False),
                             ('omissions', ['missing appendix']),
                             ('evidence_refs', ['missing.md'])]:
            review = copy.deepcopy(self.packet['reviews'][0])
            review['coverage_check'][field] = value
            with self.subTest(field=field):
                self.assertTrue(coverage_errors(self.root, self.packet, review))

    def test_init_defaults_to_key_mode_and_preserves_explicit_full_mode(self):
        script = Path(control.__file__)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / 'input.pdf'
            source.write_bytes(b'%PDF-test-input')
            for mode in [None, 'FULL_DOUBLE_READ']:
                run = base / ('default' if mode is None else 'strict')
                command = [sys.executable, str(script), 'init', str(run),
                           '--source', str(source), '--owner', 'owner']
                if mode:
                    command += ['--review-mode', mode]
                result = subprocess.run(command, capture_output=True, text=True, encoding='utf8')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                packet = json.loads((run / 'paper_packet.json').read_text(encoding='utf8'))
                self.assertEqual(packet['review_mode'], mode or 'KEY_CLAIMS')
                task = json.loads((run / 'task.json').read_text(encoding='utf8'))
                self.assertEqual(task['review_mode'], packet['review_mode'])

    def test_legacy_review_template_cannot_advertise_new_default(self):
        del self.packet['review_mode']
        self.save()
        code, body = self.cli('review-template', '--writer', 'independent')
        self.assertEqual(code, 0, body)
        self.assertEqual(body['review_mode'], 'FULL_DOUBLE_READ')


class ReviewPreflightTests(unittest.TestCase):
    save = ReviewModeIntegrationTests.save
    cli = ReviewModeIntegrationTests.cli
    write_payload = ReviewModeIntegrationTests.write_payload
    seal = ReviewModeIntegrationTests.seal

    def setUp(self):
        ReviewModeIntegrationTests.setUp(self)
        self.packet['reviews'] = []
        self.packet['paper_status'] = 'IN_PROGRESS'
        self.packet['gate_results']['G3'] = {'decision': 'PENDING',
                                             'evidence_refs': [], 'open_items': []}
        self.state['paper_status'] = 'IN_PROGRESS'
        control.render(self.root, self.packet)
        self.save()
        (self.root / 'task.json').write_text(json.dumps({'review_mode': 'KEY_CLAIMS'}),
                                              encoding='utf8')

    def snapshot_files(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def test_preflight_requires_no_existing_review_or_passed_g3(self):
        result = control.preflight(self.root)
        self.assertTrue(result['ready_for_review'], result)
        self.assertEqual(result['errors'], [])

    def test_cli_preflight_is_read_only(self):
        before = self.snapshot_files()
        code, result = self.cli('preflight')
        self.assertEqual(code, 0, result)
        self.assertTrue(result['ready_for_review'], result)
        self.assertEqual(self.snapshot_files(), before)

    def test_stale_generated_notebook_blocks_preflight(self):
        path = self.root / self.packet['deliverables']['full_notebook']
        path.write_text(path.read_text(encoding='utf8') + '\nAn unsynchronized manual addition.\n',
                        encoding='utf8')
        result = control.preflight(self.root)
        self.assertFalse(result['ready_for_review'], result)
        self.assertTrue(result['errors'])

    def test_non_utf8_current_text_blocks_before_review(self):
        (self.root / 'extracted.txt').write_bytes(b'page text\xff')
        result = control.preflight(self.root)
        self.assertFalse(result['ready_for_review'], result)
        self.assertTrue(result['errors'])

    def test_missing_report_or_claims_blocks_preflight(self):
        for failure in ['report', 'claims']:
            with self.subTest(failure=failure):
                packet = copy.deepcopy(self.packet)
                if failure == 'report':
                    packet['deliverables']['report'] = 'missing-report.md'
                else:
                    packet['claims'] = []
                (self.root / 'paper_packet.json').write_text(json.dumps(packet), encoding='utf8')
                self.assertFalse(control.preflight(self.root)['ready_for_review'])
        self.save()

    def test_unknown_claim_support_blocks_preflight(self):
        self.packet['claims'][0]['supporting_units'] = ['unknown-unit']
        self.save()
        self.assertFalse(control.preflight(self.root)['ready_for_review'])

    def test_next_returns_preflight_action_for_owner_controlled_defect(self):
        (self.root / 'bad.txt').write_bytes(b'\xff')
        _, result = self.cli('next')
        self.assertEqual(result['next_action']['kind'], 'PREFLIGHT_REVIEW')
        self.assertFalse(result['paper_accepted'])

    def test_task_mode_cannot_be_silently_changed_in_packet(self):
        self.packet['review_mode'] = 'FULL_DOUBLE_READ'
        self.save()
        self.assertFalse(control.preflight(self.root)['ready_for_review'])

    def test_sync_does_not_upgrade_legacy_revision_or_add_mode(self):
        del self.packet['review_mode']
        self.packet['skill_revision'] = '2.2'
        self.state['skill_revision'] = '2.2'
        (self.root / 'task.json').write_text(json.dumps({'skill_revision': '2.2'}),
                                              encoding='utf8')
        self.save()
        code, result = self.cli('sync')
        self.assertEqual(code, 0, result)
        packet = json.loads((self.root / 'paper_packet.json').read_text(encoding='utf8'))
        state = json.loads((self.root / 'execution_state.json').read_text(encoding='utf8'))
        self.assertNotIn('review_mode', packet)
        self.assertEqual(packet['skill_revision'], '2.2')
        self.assertEqual(state['skill_revision'], '2.2')


class ReviewContinuationTests(unittest.TestCase):
    save = ReviewModeIntegrationTests.save
    cli = ReviewModeIntegrationTests.cli
    write_payload = ReviewModeIntegrationTests.write_payload
    seal = ReviewModeIntegrationTests.seal

    def setUp(self):
        ReviewModeIntegrationTests.setUp(self)
        baseline = review_baseline(self.root, self.packet)
        directory = self.root / 'reviews'
        directory.mkdir(exist_ok=True)
        (directory / 'R-key.baseline.json').write_text(json.dumps(baseline), encoding='utf8')

    def next_review(self):
        review = copy.deepcopy(self.packet['reviews'][0])
        review['review_id'] = 'R-next'
        delta = review_delta(self.root, self.packet)
        review['continuation'] = {
            'previous_review_id': 'R-key',
            'retained_unit_ids': review['checked_unit_ids'][:],
            'rechecked_unit_ids': [],
            'inspected_changed_files': delta['changed_files'],
            'rechecked_claim_ids': delta['changed_claim_ids'],
            'replacement_reason': None}
        return review

    def test_unchanged_continuation_retains_same_reviewers_actual_coverage(self):
        review = self.next_review()
        self.assertEqual(continuation_errors(self.root, self.packet, review), [])

    def test_baseline_in_reviews_does_not_change_scientific_delta(self):
        delta = review_delta(self.root, self.packet)
        self.assertEqual(delta['changed_files'], [])
        self.assertEqual(delta['changed_unit_ids'], [])
        self.assertEqual(delta['changed_claim_ids'], [])

    def test_delta_includes_changed_report_and_deleted_current_artifact(self):
        report = self.root / self.packet['deliverables']['report']
        report.write_text('Revised scientific report.', encoding='utf8')
        (self.root / 'page.png').unlink()
        delta = review_delta(self.root, self.packet)
        self.assertIn(self.packet['deliverables']['report'], delta['changed_files'])
        self.assertIn('page.png', delta['changed_files'])
        self.assertTrue(delta['changed_unit_ids'])

    def test_changed_unit_cannot_be_retained(self):
        self.packet['units'][0]['understanding_note'] = 'Revised interpretation and conditions.'
        review = self.next_review()
        self.assertTrue(continuation_errors(self.root, self.packet, review))
        review['continuation']['retained_unit_ids'].remove('F1')
        review['continuation']['rechecked_unit_ids'] = ['F1']
        self.assertEqual(continuation_errors(self.root, self.packet, review), [])

    def test_every_changed_artifact_must_be_inspected(self):
        report = self.root / self.packet['deliverables']['report']
        report.write_text('Revised scientific report.', encoding='utf8')
        review = self.next_review()
        review['continuation']['inspected_changed_files'] = []
        self.assertTrue(continuation_errors(self.root, self.packet, review))

    def test_changed_claim_must_be_rechecked(self):
        self.packet['claims'][0]['text'] = 'A corrected comparison under explicit conditions.'
        review = self.next_review()
        review['continuation']['rechecked_claim_ids'] = []
        self.assertTrue(continuation_errors(self.root, self.packet, review))

    def test_replacement_cannot_retain_another_sessions_coverage(self):
        review = self.next_review()
        review['reviewer_session_id'] = 'replacement-session'
        review['continuation']['replacement_reason'] = 'Original host session was unavailable.'
        self.assertTrue(continuation_errors(self.root, self.packet, review))
        review['continuation']['retained_unit_ids'] = []
        review['continuation']['rechecked_unit_ids'] = review['checked_unit_ids'][:]
        review['continuation']['rechecked_claim_ids'] = review['checked_claim_ids'][:]
        self.assertEqual(continuation_errors(self.root, self.packet, review), [])

    def test_replacement_requires_disclosure_even_with_fresh_checks(self):
        review = self.next_review()
        review['reviewer_id'] = 'replacement-reviewer'
        review['continuation']['retained_unit_ids'] = []
        review['continuation']['rechecked_unit_ids'] = review['checked_unit_ids'][:]
        self.assertTrue(continuation_errors(self.root, self.packet, review))

    def test_checked_units_partition_cannot_overlap_or_omit(self):
        for broken in ['overlap', 'omission']:
            review = self.next_review()
            if broken == 'overlap':
                review['continuation']['rechecked_unit_ids'] = ['F1']
            else:
                review['continuation']['retained_unit_ids'].remove('F1')
            with self.subTest(broken=broken):
                self.assertTrue(continuation_errors(self.root, self.packet, review))

    def test_scope_or_source_change_invalidates_retained_coverage(self):
        for field in ['scope_revision', 'source_hashes']:
            packet = copy.deepcopy(self.packet)
            if field == 'scope_revision':
                packet[field] += 1
            else:
                packet['sources'][0]['sha256'] = 'new-source-hash'
            review = self.next_review()
            review['continuation']['inspected_changed_files'] = review_delta(self.root, packet)['changed_files']
            with self.subTest(field=field):
                self.assertTrue(continuation_errors(self.root, packet, review))

    def test_changed_dependency_reopens_supporting_unit_and_claim(self):
        dependency = next(uid for uid in self.plan['sampled_unit_ids'] if uid != 'F1')
        self.packet['units'][0]['dependencies'] = [dependency]
        baseline = review_baseline(self.root, self.packet)
        (self.root / 'reviews' / 'R-key.baseline.json').write_text(
            json.dumps(baseline), encoding='utf8')
        row = next(u for u in self.packet['units'] if u['unit_id'] == dependency)
        row['understanding_note'] = 'Changed evidence interpretation alters its dependent claim.'
        delta = review_delta(self.root, self.packet)
        self.assertIn('F1', delta['changed_unit_ids'])
        self.assertIn('C1', delta['changed_claim_ids'])
        review = self.next_review()
        review['continuation']['retained_unit_ids'].remove(dependency)
        review['continuation']['rechecked_unit_ids'] = [dependency]
        review['continuation']['rechecked_claim_ids'] = []
        self.assertTrue(continuation_errors(self.root, self.packet, review))

    def test_replacement_rechecks_every_key_claim_as_well_as_units(self):
        review = self.next_review()
        review['reviewer_session_id'] = 'new-session'
        review['continuation'].update({
            'replacement_reason': 'Original independent reviewer is unavailable.',
            'retained_unit_ids': [],
            'rechecked_unit_ids': review['checked_unit_ids'][:],
            'rechecked_claim_ids': []})
        self.assertTrue(continuation_errors(self.root, self.packet, review))

    def test_inline_report_image_changes_are_included_in_delta(self):
        report = self.root / self.packet['deliverables']['report']
        report.write_text('Report with evidence.\n\n![example](inline-only.png)\n', encoding='utf8')
        image = self.root / 'inline-only.png'
        image.write_bytes(b'original report image')
        baseline = review_baseline(self.root, self.packet)
        (self.root / 'reviews' / 'R-key.baseline.json').write_text(
            json.dumps(baseline), encoding='utf8')
        image.write_bytes(b'changed report image')
        self.assertIn('inline-only.png', review_delta(self.root, self.packet)['changed_files'])

    def test_changed_experiment_reopens_reverse_linked_claim_and_support(self):
        self.packet['experiments'] = [{'experiment_id': 'E1', 'claim_refs': ['C1'],
                                       'unit_refs': ['F13'], 'results': 'initial'}]
        self.packet['claims'][0].pop('experiment_refs', None)
        baseline = review_baseline(self.root, self.packet)
        (self.root / 'reviews' / 'R-key.baseline.json').write_text(
            json.dumps(baseline), encoding='utf8')
        self.packet['experiments'][0]['results'] = 'corrected comparison result'
        delta = review_delta(self.root, self.packet)
        self.assertIn('C1', delta['changed_claim_ids'])
        self.assertIn('F1', delta['changed_unit_ids'])

    def test_deleted_experiment_reopens_reverse_linked_claim_and_support(self):
        self.packet['experiments'] = [{'experiment_id': 'E1', 'claim_refs': ['C1'],
                                       'unit_refs': ['F13'], 'results': 'initial'}]
        self.packet['claims'][0].pop('experiment_refs', None)
        baseline = review_baseline(self.root, self.packet)
        (self.root / 'reviews' / 'R-key.baseline.json').write_text(
            json.dumps(baseline), encoding='utf8')
        self.packet['experiments'] = []
        delta = review_delta(self.root, self.packet)
        self.assertIn('C1', delta['changed_claim_ids'])
        self.assertIn('F1', delta['changed_unit_ids'])


if __name__ == '__main__':
    unittest.main()
