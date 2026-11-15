"""Regression checks for incomplete and stale cross-file repairs."""
import copy
import json
import unittest

import reading_repair_sync as sync
import reading_run_control as control
from reading_run_check import inspect_run
import test_reading_run_control as fixtures


class RepairSyncTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.ReadingRunControlTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.root = fixture.root
        self.packet = fixture.packet
        self.packet['review_requirements'] = {'repair_dependency_sync': True}
        fixture.save()
        self.review = fixture.failed_review()
        control.ingest_review(self.root, self.review)
        self.packet = control.read(self.root/'paper_packet.json')
        self.request = control.requests(self.review, 'owner')[0]

    def scan(self, **kwargs):
        return sync.scan(self.root, self.packet, self.request, 'R1', **kwargs)

    def complete(self, report):
        for row in report['files']:
            row.update(disposition='CHECKED_UNCHANGED', reason='Checked source meaning and current claim restrictions.')
        return report

    def save_report(self, report):
        path = self.root/'repair_sync'/'R1-01.json'
        control.write(path, report)
        return path

    def test_scan_includes_unlinked_notes_and_manual_notebook_but_preserves_history(self):
        (self.root/'evidence').mkdir()
        (self.root/'evidence'/'reading_notes.md').write_text('F1 concern pending', encoding='utf8')
        (self.root/'full_notebook.md').write_text('F1 old manual explanation', encoding='utf8')
        (self.root/'handoffs').mkdir(exist_ok=True)
        raw=self.root/'handoffs'/'raw.json'
        raw.write_text('{"old": "F1 concern pending"}', encoding='utf8')
        before=raw.read_bytes()
        report=self.scan()
        names={r['path'] for r in report['files']}
        self.assertTrue({'evidence/reading_notes.md','full_notebook.md','paper_packet.json'} <= names)
        self.assertNotIn('handoffs/raw.json', names)
        self.assertEqual(raw.read_bytes(), before)

    def test_ready_requires_dependency_report_without_mutating_state(self):
        before=(self.root/'execution_state.json').read_bytes()
        with self.assertRaises(control.RunError) as caught:
            control.repair_ready(self.root, 'R1-01', 'notes.md')
        self.assertEqual(caught.exception.code, 'REPAIR_SYNC_REQUIRED')
        self.assertEqual(before,(self.root/'execution_state.json').read_bytes())

    def test_omitted_associated_file_is_rejected(self):
        report=self.complete(self.scan())
        report['files']=[r for r in report['files'] if r['path']!='notes.md']
        with self.assertRaisesRegex(ValueError, 'omitted'):
            sync.validate(self.root,self.packet,self.request,'R1',report)

    def test_declared_old_pending_wording_blocks_ready(self):
        (self.root/'notes.md').write_text('ISS-01 requires user confirmation', encoding='utf8')
        report=self.complete(self.scan(terms=['ISS-01'], obsolete=['requires user confirmation']))
        with self.assertRaisesRegex(control.RunError, 'Obsolete current wording'):
            control.repair_ready(self.root,'R1-01','notes.md',self.save_report(report))

    def test_historical_old_wording_needs_exact_location_and_reason(self):
        (self.root/'notes.md').write_text('Correction history: formerly requires user confirmation', encoding='utf8')
        report=self.complete(self.scan(obsolete=['requires user confirmation']))
        report['historical_occurrences']=[{'path':'notes.md','line':1,
            'literal':'requires user confirmation','reason':'Explicitly labelled prior, withdrawn interpretation.'}]
        sync.validate(self.root,self.packet,self.request,'R1',report)
        report['historical_occurrences'][0]['line']=2
        with self.assertRaises(ValueError):
            sync.validate(self.root,self.packet,self.request,'R1',report)

    def test_ready_seal_reopens_when_notes_change(self):
        report=self.complete(self.scan())
        control.repair_ready(self.root,'R1-01','notes.md',self.save_report(report))
        self.assertNotEqual(control.assess(self.root)['next_action']['kind'],'REPAIR')
        (self.root/'notes.md').write_text('Stale interpretation reintroduced',encoding='utf8')
        self.assertEqual(control.assess(self.root)['next_action']['kind'],'REPAIR')

    def test_new_unlinked_file_reopens_ready_repair(self):
        control.repair_ready(self.root,'R1-01','notes.md',self.save_report(self.complete(self.scan())))
        (self.root/'extra_notes.md').write_text('Unreconciled claim',encoding='utf8')
        self.assertEqual(control.assess(self.root)['next_action']['kind'],'REPAIR')

    def test_tampered_sync_report_reopens_repair(self):
        path=self.save_report(self.complete(self.scan()))
        control.repair_ready(self.root,'R1-01','notes.md',path)
        report=control.read(path)
        report['files'][0]['reason']='Changed after ready'
        control.write(path,report)
        self.assertEqual(control.assess(self.root)['next_action']['kind'],'REPAIR')

    def test_changed_claim_invalidates_ready_even_if_text_files_unchanged(self):
        control.repair_ready(self.root,'R1-01','notes.md',self.save_report(self.complete(self.scan())))
        packet=control.read(self.root/'paper_packet.json')
        packet['claims'][0]['allowed_use']='HOLD'
        control.write(self.root/'paper_packet.json',packet)
        self.assertEqual(control.assess(self.root)['next_action']['kind'],'REPAIR')

    def test_unlinked_note_changes_review_fingerprint_for_new_runs(self):
        before=control.content_fingerprint(self.root,self.packet)
        (self.root/'extra_notes.md').write_text('Additional current interpretation',encoding='utf8')
        self.assertNotEqual(before,control.content_fingerprint(self.root,self.packet))

    def test_accepted_review_cannot_skip_dependency_sync(self):
        accepted=copy.deepcopy(self.review)
        accepted.update(review_id='R2',decision='VERIFIED_FOR_SCOPE',repair_requests=[],
                        gate_decisions={g:'PASS' for g in ['G0','G1','G2','G3']})
        with self.assertRaises(control.RunError) as caught:
            control.ingest_review(self.root,accepted)
        self.assertEqual(caught.exception.code,'REPAIR_SYNC_REQUIRED')

    def test_corrected_report_with_stale_associated_notes_cannot_advance(self):
        (self.root/'report.md').write_text('ISS-01 is explained; no user adjudication is pending.',encoding='utf8')
        (self.root/'evidence').mkdir()
        notes=self.root/'evidence'/'reading_notes_02_06.md'
        notes.write_text('ISS-01 still awaits user adjudication.',encoding='utf8')
        report=self.complete(self.scan(terms=['ISS-01'], obsolete=['still awaits user adjudication']))
        with self.assertRaises(control.RunError):
            control.repair_ready(self.root,'R1-01','notes.md',self.save_report(report))
        notes.write_text('ISS-01 is explained; citation namespaces differ.',encoding='utf8')
        report=self.complete(self.scan(terms=['ISS-01'], obsolete=['still awaits user adjudication']))
        control.repair_ready(self.root,'R1-01','notes.md',self.save_report(report))
        self.assertNotEqual(control.assess(self.root)['next_action']['kind'],'REPAIR')

    def test_actual_accepted_review_after_sync_passes_checker_then_note_edit_invalidates_it(self):
        control.merge_handoff(self.root,{'writer_id':'owner','gate_results':{
            'G2':{'decision':'PASS','evidence_refs':['notes.md'],'open_items':[]}}})
        self.packet=control.read(self.root/'paper_packet.json')
        control.repair_ready(self.root,'R1-01','notes.md',self.save_report(self.complete(self.scan())))
        packet=control.read(self.root/'paper_packet.json')
        accepted=copy.deepcopy(self.fixture.packet['reviews'][0])
        accepted.update(review_id='R2',reviewed_content_sha256=control.content_fingerprint(self.root,packet))
        result=control.ingest_review(self.root,accepted)
        self.assertEqual(result['terminal_decision'],'ACCEPTED',result)
        self.assertEqual(inspect_run(self.root),[])
        (self.root/'notes.md').write_text('Stale claim reintroduced after review',encoding='utf8')
        codes={row['code'] for row in inspect_run(self.root)}
        self.assertTrue({'REVIEW_CONTENT_STALE','REPAIR_SYNC_REQUIRED'} <= codes)

    def test_deleted_file_and_changed_report_identity_are_rejected(self):
        report=self.complete(self.scan())
        report['review_id']='old-review'
        with self.assertRaisesRegex(ValueError,'identity'):
            sync.validate(self.root,self.packet,self.request,'R1',report)
        report['review_id']='R1'
        (self.root/'notes.md').unlink()
        with self.assertRaisesRegex(ValueError,'file set'):
            sync.validate(self.root,self.packet,self.request,'R1',report)

    def test_unfinished_scan_is_not_ready_evidence(self):
        with self.assertRaisesRegex(control.RunError,'Inspect and explain'):
            control.repair_ready(self.root,'R1-01','notes.md',self.save_report(self.scan()))


if __name__=='__main__':
    unittest.main()
