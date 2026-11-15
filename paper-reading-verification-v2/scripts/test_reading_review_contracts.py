"""Regression fixtures for observed review, handoff and structural failures."""
import copy
import unittest

import reading_run_control as control
import test_reading_run_control as fixtures
from reading_run_check import inspect_run


class ReviewContractTests(unittest.TestCase):
    save = fixtures.ReadingRunControlTests.save
    cli = fixtures.ReadingRunControlTests.cli
    write_payload = fixtures.ReadingRunControlTests.write_payload

    def setUp(self):
        fixtures.ReadingRunControlTests.setUp(self)
        self.packet['skill_revision'] = '2.4'
        self.packet['review_requirements'] = {'direct_visual_inspection': True}
        review = self.packet['reviews'][0]
        review.update({'review_id': 'R-direct', 'reviewer_session_id': 'session-reviewer',
                       'visual_inspection': {
                           'status': 'COMPLETE', 'direct_pixels_available': True,
                           'session_id': 'session-reviewer', 'blocked_unit_ids': [],
                           'tool_evidence_refs': ['source_check.md'],
                           'units': [{'unit_id': 'F1', 'actually_viewed': True,
                                      'artifact_refs': ['page.png'],
                                      'observations': 'Two visible paths join at the shared output.'}]}})
        review['reviewed_content_sha256'] = control.content_fingerprint(self.root, self.packet)
        review['reviewed_visual_evidence_sha256'] = control.visual_fingerprint(self.root, review)
        self.save()

    def test_reviewer_with_blocked_pixels_cannot_accept(self):
        review = copy.deepcopy(self.packet['reviews'][0])
        review['review_id'] = 'R-blocked'
        review['visual_inspection']['direct_pixels_available'] = False
        code, body = self.cli('ingest-review', '--file', self.write_payload('blocked.json', review))
        self.assertEqual(code, 1)
        self.assertEqual(body['error_code'], 'INVALID_REVIEW_VISUAL')

    def test_reader_visual_records_cannot_replace_reviewer_evidence(self):
        review = copy.deepcopy(self.packet['reviews'][0])
        review['visual_inspection']['units'] = []
        code, body = self.cli('ingest-review', '--file', self.write_payload('inherited.json', review))
        self.assertEqual(code, 1)
        self.assertEqual(body['error_code'], 'INVALID_REVIEW_VISUAL')

    def test_direct_reviewer_can_accept_inspected_current_fixture(self):
        review = copy.deepcopy(self.packet['reviews'][0])
        code, body = self.cli('ingest-review', '--file', self.write_payload('direct.json', review))
        self.assertEqual(code, 0, body)
        self.assertEqual(body['terminal_decision'], 'ACCEPTED')

    def test_checker_rejects_contradictory_visual_status(self):
        self.packet['reviews'][0]['visual_inspection']['status'] = 'BLOCKED'
        self.save()
        self.assertIn('REVIEW_VISUAL_INCOMPLETE', {e['code'] for e in inspect_run(self.root)})

    def test_wrong_handoff_collection_type_is_actionable_and_nonmutating(self):
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        payload = self.write_payload('bad-shape.json', {'writer_id': 'reader', 'gate_results': []})
        code, body = self.cli('merge', '--file', payload)
        self.assertEqual(code, 1)
        self.assertEqual(body['error_code'], 'INVALID_HANDOFF')
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file() and p.name != 'bad-shape.json'}
        self.assertEqual(after, before)

    def test_handoff_template_and_dry_validation_do_not_write(self):
        code, template = self.cli('handoff-template', '--writer', 'reader', '--units', 'F1')
        self.assertEqual(code, 0, template)
        self.assertEqual(template['gate_results'], {})
        self.assertEqual(template['units'][0]['unit_id'], 'F1')
        self.assertNotIn('locators', template['units'][0])
        payload = {'writer_id': 'reader', 'units': [copy.deepcopy(self.packet['units'][0])]}
        before = (self.root/'paper_packet.json').read_bytes()
        code, body = self.cli('validate-handoff', '--file', self.write_payload('valid.json', payload))
        self.assertEqual(code, 0, body)
        self.assertTrue(body['valid'])
        self.assertEqual((self.root/'paper_packet.json').read_bytes(), before)

    def test_missing_panel_parent_is_detected(self):
        self.packet['units'][0].update({'kind': 'PANEL', 'parent_id': 'missing'})
        self.save()
        self.assertIn('UNIT_PARENT_INVALID', {e['code'] for e in inspect_run(self.root)})

    def test_experiment_same_as_must_resolve(self):
        self.packet['experiments'] = [{'experiment_id': 'E1', 'same_as': 'missing'}]
        self.save()
        self.assertIn('EXPERIMENT_LINK_INVALID', {e['code'] for e in inspect_run(self.root)})

    def test_failed_review_rejects_nested_gate_shapes_before_archiving(self):
        review = copy.deepcopy(self.packet['reviews'][0])
        review.update({'review_id': 'R-bad-shape', 'decision': 'REVISION_REQUIRED'})
        review['gate_decisions']['G2'] = {'decision': 'FAIL'}
        before = (self.root/'paper_packet.json').read_bytes()
        code, body = self.cli('ingest-review', '--file', self.write_payload('bad-review.json', review))
        self.assertEqual(code, 1)
        self.assertEqual(body['error_code'], 'INVALID_REVIEW')
        self.assertEqual((self.root/'paper_packet.json').read_bytes(), before)
        self.assertFalse((self.root/'reviews/R-bad-shape.json').exists())

    def test_reviewer_only_image_mutation_invalidates_acceptance(self):
        review = self.packet['reviews'][0]
        (self.root/'reviewer-page.png').write_bytes(b'original reviewer fixture')
        review['visual_inspection']['units'][0]['artifact_refs'] = ['reviewer-page.png']
        review['reviewed_visual_evidence_sha256'] = control.visual_fingerprint(self.root, review)
        self.save()
        (self.root/'reviewer-page.png').write_bytes(b'changed reviewer fixture')
        _, body = self.cli('next')
        self.assertFalse(body['paper_accepted'])
        self.assertIn('REVIEW_VISUAL_INCOMPLETE', {e['code'] for e in inspect_run(self.root)})

    def test_panel_self_parent_and_text_parent_are_invalid(self):
        from reading_review_contracts import structure_errors
        for parent_kind, self_parent in [('PANEL', True), ('SECTION', False)]:
            child = copy.deepcopy(self.packet['units'][0])
            child.update({'kind': 'PANEL', 'parent_id': 'F1' if self_parent else 'S0', 'children': ['F1'] if self_parent else []})
            self.packet['units'] = [child]
            if not self_parent:
                self.packet['units'].append({'unit_id': 'S0', 'kind': parent_kind, 'children': ['F1']})
            self.assertIn('UNIT_PARENT_INVALID', {e['code'] for e in structure_errors(self.packet)})


if __name__ == '__main__':
    unittest.main()
