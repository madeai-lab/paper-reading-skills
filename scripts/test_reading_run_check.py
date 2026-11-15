"""Exercise the local preflight against incomplete and misleading run records."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name('reading_run_check.py')


class ReadingRunCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ['source.pdf', 'notes.md', 'page.png', 'source_check.md',
                     'review.md', 'report.md', 'index.md', 'issues.md']:
            (self.root / name).write_bytes(b'%PDF-fixture' if name.endswith('.pdf') else b'evidence fixture')
        unit = {'unit_id':'F1','source_id':'S1','kind':'FIGURE','read_state':'CHECKED',
                'understanding_note':'Shows the two paths, their conditions, and a shared output.',
                'evidence_refs':['notes.md'], 'locators':[{'physical_page':1}],
                'visual_review':{'required':True,'actually_viewed':True,'artifact_refs':['page.png']}}
        self.packet = {'template_only':False, 'task_id':'T1','paper_id':'P1',
            'scope_mode':'COMPLETE_PAPER','scope_revision':1,
            'owner_id':'owner','writer_ids':['owner','reader'],
            'paper_status':'VERIFIED_FOR_SCOPE',
            'sources':[{'source_id':'S1','local_path':'source.pdf','required_for_scope':True,
                        'access_state':'AVAILABLE','sha256':hashlib.sha256(b'%PDF-fixture').hexdigest()}],
            'units':[unit], 'claims':[{'claim_id':'C1','allowed_use':'USE','supporting_units':['F1']}],
            'issues':[], 'gate_results':{g:{'decision':'PASS','evidence_refs':['review.md']} for g in ['G0','G1','G2','G3']},
            'reviews':[{'reviewer_id':'reviewer','decision':'VERIFIED_FOR_SCOPE',
                        'source_first_inventory_ref':'source_check.md',
                        'checked_unit_ids':['F1'],'checked_claim_ids':['C1'],
                        'gate_decisions':{'G0':'PASS','G1':'PASS','G2':'PASS','G3':'PASS'},
                        'reviewed_scope_revision':1,
                        'reviewed_source_hashes':{'S1':hashlib.sha256(b'%PDF-fixture').hexdigest()},
                        'unresolved_reading_gaps':[],'repair_requests':[]}],
            'deliverables':{'full_notebook':'notes.md','report':'report.md','material_index':'index.md',
                            'user_review':'issues.md','independent_review':'review.md'}}
        self.inventory = [copy.deepcopy(unit)]

    def run_check(self):
        (self.root/'paper_packet.json').write_text(json.dumps(self.packet),encoding='utf8')
        (self.root/'01_inventory.json').write_text(json.dumps(self.inventory),encoding='utf8')
        result = subprocess.run([sys.executable,str(SCRIPT),str(self.root)],capture_output=True,text=True,encoding='utf8')
        self.assertTrue(result.stdout.strip().startswith('{'), 'Checker must return JSON; implementation is missing or crashed: '+result.stderr)
        return result.returncode, json.loads(result.stdout)

    def assert_rejected(self, expected_code):
        code, body = self.run_check()
        self.assertEqual(code,1)
        self.assertIn(expected_code,{x['code'] for x in body['errors']})

    def test_complete_records_pass_only_a_structural_check(self):
        code,body=self.run_check()
        self.assertEqual(code,0)
        self.assertTrue(body['structural_check_passed'])
        self.assertFalse(body['semantic_verification_automated'])

    def test_unread_unit_cannot_hide_behind_passed_gates(self):
        self.packet['units'][0]['read_state']='READ'
        self.assert_rejected('UNIT_INCOMPLETE')

    def test_removing_an_inventoried_unit_is_detected(self):
        self.inventory.append({'unit_id':'F2'})
        self.assert_rejected('INVENTORY_UNIT_MISSING')

    def test_rendering_without_actual_viewing_is_incomplete(self):
        self.packet['units'][0]['visual_review']['actually_viewed']=False
        self.assert_rejected('VISUAL_NOT_VIEWED')

    def test_claimed_visual_reading_needs_a_real_artifact(self):
        self.packet['units'][0]['visual_review']['artifact_refs']=['missing.png']
        self.assert_rejected('EVIDENCE_MISSING')

    def test_writer_cannot_approve_own_work(self):
        self.packet['reviews'][0]['reviewer_id']='reader'
        self.assert_rejected('REVIEW_NOT_INDEPENDENT')

    def test_review_cannot_omit_units(self):
        self.packet['reviews'][0]['checked_unit_ids']=[]
        self.assert_rejected('REVIEW_COVERAGE_MISSING')

    def test_open_workflow_error_blocks_finalization(self):
        self.packet['issues']=[{'issue_id':'I1','kind':'WORKFLOW_ERROR','status':'OPEN'}]
        self.assert_rejected('OPEN_READING_OR_WORKFLOW_GAP')

    def test_source_anomaly_is_allowed_only_with_restricted_claims(self):
        self.packet['paper_status']='VERIFIED_WITH_USER_REVIEW'
        self.packet['reviews'][0]['decision']='VERIFIED_WITH_USER_REVIEW'
        self.packet['issues']=[{'issue_id':'I1','kind':'SOURCE_ANOMALY','status':'USER_REVIEW','affected_claims':['C1'],'user_decision':None}]
        self.assert_rejected('ANOMALY_CLAIM_UNRESTRICTED')
        self.packet['claims'][0]['allowed_use']='CONDITIONAL'
        self.assertEqual(self.run_check()[0],0)

    def test_changed_source_invalidates_preflight(self):
        (self.root/'source.pdf').write_bytes(b'%PDF-new-version')
        self.assert_rejected('SOURCE_CHANGED')

    def test_empty_inventory_never_proves_full_coverage(self):
        self.inventory=[]
        self.packet['units']=[]
        self.assert_rejected('EMPTY_INVENTORY')

    def test_pending_gate_still_requires_work(self):
        self.packet['gate_results']['G3']['decision']='PENDING'
        self.assert_rejected('GATE_PENDING')

    def test_failed_review_gate_cannot_be_overridden_by_packet(self):
        self.packet['reviews'][0]['gate_decisions']['G3']='FAIL'
        self.assert_rejected('REVIEW_GATE_CONFLICT')

    def test_visual_type_cannot_disable_required_viewing(self):
        self.packet['units'][0]['visual_review']={'required':False,'actually_viewed':False}
        self.assert_rejected('VISUAL_NOT_VIEWED')

    def test_unknown_source_reference_is_rejected(self):
        self.packet['units'][0]['source_id']='UNKNOWN'
        self.assert_rejected('UNIT_SOURCE_MISSING')

    def test_new_scope_cannot_reuse_old_review(self):
        self.packet['scope_revision']=2
        self.assert_rejected('REVIEW_STALE')

    def test_updating_source_hash_does_not_refresh_review(self):
        (self.root/'source.pdf').write_bytes(b'%PDF-changed')
        self.packet['sources'][0]['sha256']=hashlib.sha256(b'%PDF-changed').hexdigest()
        self.assert_rejected('REVIEW_STALE')

    def test_user_narrowing_retains_excluded_unit_without_full_paper_claim(self):
        self.packet['scope_mode']='USER_DEFINED_SCOPE'
        self.packet['scope_revision']=2
        self.packet['reviews'][0]['reviewed_scope_revision']=2
        self.inventory.append({'unit_id':'F2'})
        self.packet['units'].append({'unit_id':'F2','source_id':'S1','read_state':'OUT_OF_SCOPE'})
        self.packet['scope_exclusions']=[{'unit_id':'F2','reason':'User requested figure1 only',
                                         'user_authorization_ref':'notes.md','scope_revision':2}]
        self.packet['reviews'][0]['checked_unit_ids'].append('F2')
        self.assertEqual(self.run_check()[0],0)
        self.packet['scope_mode']='COMPLETE_PAPER'
        self.assert_rejected('SCOPE_EXCLUSION_INVALID')

    def test_review_template_does_not_count_as_executed_review(self):
        self.packet['reviews'][0]['template_only']=True
        self.assert_rejected('REVIEW_TEMPLATE_NOT_EXECUTED')

    def test_checker_does_not_mutate_sources_or_records(self):
        self.run_check()
        before={x.name:x.read_bytes() for x in self.root.iterdir()}
        result=subprocess.run([sys.executable,str(SCRIPT),str(self.root)],capture_output=True)
        self.assertEqual(result.returncode,0)
        self.assertEqual(before,{x.name:x.read_bytes() for x in self.root.iterdir()})


if __name__ == '__main__':
    unittest.main()
