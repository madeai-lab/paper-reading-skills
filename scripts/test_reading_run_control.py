"""Test executable handoff and terminal decisions, not paper understanding."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_reading_run_check as fixtures
import reading_run_control as control

SCRIPT = Path(__file__).with_name("reading_run_control.py")


class ReadingRunControlTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.ReadingRunCheckTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.packet = copy.deepcopy(fixture.packet)
        self.inventory = copy.deepcopy(fixture.inventory)
        self.state = {
            "template_only": False, "skill_revision": "2.2", "owner_id": "owner",
            "writer_ids": ["owner", "reader"], "stage": "08", "paper_status": "VERIFIED_FOR_SCOPE",
            "scope_revision": 1, "open_unit_ids": [], "next_actions": [], "blockers": [],
            "stop_reason": None, "restart_action": None, "history": [], "repair_progress": {}
        }
        control.render(self.root,self.packet)
        self.save()
        self.packet['reviews'][0]['reviewed_content_sha256'] = control.content_fingerprint(self.root,self.packet)
        self.save()

    def save(self):
        for name, value in [("paper_packet.json",self.packet),("01_inventory.json",self.inventory),
                            ("execution_state.json",self.state)]:
            (self.root/name).write_text(json.dumps(value),encoding="utf8")

    def cli(self, command, *args):
        result = subprocess.run([sys.executable,str(SCRIPT),command,str(self.root),*args],
                                capture_output=True,text=True,encoding="utf8")
        self.assertTrue(result.stdout.strip().startswith("{"),
                        "Controller is missing or failed to return JSON: "+result.stderr)
        return result.returncode,json.loads(result.stdout)

    def write_payload(self, name, data):
        f=self.root/name
        f.write_text(json.dumps(data),encoding="utf8")
        return str(f)

    def failed_review(self):
        review=copy.deepcopy(self.packet["reviews"][0])
        review.update({"review_id":"R1","decision":"REVISION_REQUIRED",
                       "gate_decisions":{"G0":"PASS","G1":"PASS","G2":"FAIL","G3":"FAIL"},
                       "repair_requests":[{"repair_id":"R1-01","unit_ids":["F1"],
                                          "responsible_role":"reader","required_action":"Correct the arrow explanation against page1."}]})
        return review

    def test_accepted_current_records_allow_final_delivery(self):
        code,body=self.cli("next")
        self.assertEqual(code,0)
        self.assertEqual(body["terminal_decision"],"ACCEPTED")
        self.assertTrue(body["may_send_final"])

    def test_saved_failed_state_without_blockers_requires_work(self):
        self.packet["paper_status"]="IN_PROGRESS"
        self.packet["units"][0]["read_state"]="READ"
        self.packet["reviews"]=[]
        self.state["stage"]="08"
        self.state["paper_status"]="REVISION_REQUIRED"
        self.state["open_unit_ids"]=["F1"]
        self.save()
        code,body=self.cli("next")
        self.assertEqual(code,0)
        self.assertEqual(body["terminal_decision"],"CONTINUE")
        self.assertFalse(body["may_send_final"])
        self.assertIn("F1",body["next_action"]["unit_ids"])

    def test_review_ingestion_preserves_failure_and_assigns_repairs(self):
        f=self.write_payload("incoming-review.json",self.failed_review())
        code,body=self.cli("ingest-review","--file",f)
        self.assertEqual(code,0,body)
        packet=json.loads((self.root/"paper_packet.json").read_text(encoding="utf8"))
        self.assertEqual(packet["reviews"][-1]["decision"],"REVISION_REQUIRED")
        self.assertEqual(packet["gate_results"]["G3"]["decision"],"FAIL")
        _,body=self.cli("next")
        self.assertEqual(body["terminal_decision"],"CONTINUE")
        self.assertEqual(body["next_action"]["kind"],"REPAIR")
        self.assertEqual(body["next_action"]["repair_ids"],["R1-01"])

    def test_repair_evidence_cannot_self_approve_the_paper(self):
        f=self.write_payload("incoming-review.json",self.failed_review())
        code, assessment = self.cli("ingest-review", "--file", f)
        self.assertEqual(code, 0, assessment)
        self.assertEqual(assessment["next_action"]["kind"], "REPAIR")
        code, assessment = self.cli("repair-ready", "--id", "R1-01", "--evidence", "notes.md")
        self.assertEqual(code, 0, assessment)
        self.assertEqual(assessment["next_action"]["kind"], "VERIFY_LOCAL_GATE")
        f=self.write_payload("rechecked-g2.json",{"writer_id":"owner","gate_results":{
            "G2":{"decision":"PASS","evidence_refs":["notes.md"],"open_items":[]}}})
        code, assessment = self.cli("merge", "--file", f)
        self.assertEqual(code, 0, assessment)
        self.assertEqual(assessment["next_action"]["kind"], "REQUEST_REVIEW")
        self.assertFalse(assessment["may_send_final"])
        self.assertEqual((code, assessment), self.cli("next"))
        packet=json.loads((self.root/"paper_packet.json").read_text(encoding="utf8"))
        self.assertEqual(packet["reviews"][-1]["decision"],"REVISION_REQUIRED")

    def test_merge_rejects_demonstrated_generic_placeholder(self):
        unit={"unit_id":"F1","read_state":"CHECKED",
              "understanding_note":"See full_notebook.md; granular evidence still being developed."}
        f=self.write_payload("handoff.json",{"writer_id":"reader","units":[unit]})
        before=(self.root/"paper_packet.json").read_bytes()
        code,body=self.cli("merge","--file",f)
        self.assertEqual(code,1)
        self.assertEqual(body["error_code"],"INVALID_HANDOFF")
        self.assertEqual(before,(self.root/"paper_packet.json").read_bytes())

    def test_merge_never_promotes_understood_to_checked(self):
        unit={"unit_id":"F1","read_state":"UNDERSTOOD",
              "understanding_note":"Two labeled branches converge; the figure describes design, not measured accuracy.",
              "evidence_refs":["source.pdf"],"visual_review":{"required":True,"actually_viewed":True,"artifact_refs":["page.png"]}}
        f=self.write_payload("handoff.json",{"writer_id":"reader","units":[unit]})
        code,body=self.cli("merge","--file",f)
        self.assertEqual(code,0,body)
        packet=json.loads((self.root/"paper_packet.json").read_text(encoding="utf8"))
        self.assertEqual(packet["units"][0]["read_state"],"UNDERSTOOD")

    def test_merge_rejects_pointer_only_experiment_records(self):
        f=self.write_payload("handoff.json",{"writer_id":"reader","experiments":[
            {"experiment_id":"E1","unit_refs":["F1"],"evidence_refs":["notes.md"]}]})
        code,body=self.cli("merge","--file",f)
        self.assertEqual(code,1)
        self.assertEqual(body["error_code"],"INVALID_HANDOFF")

    def test_merge_rejects_status_instead_of_decision_gate(self):
        f=self.write_payload("handoff.json",{"writer_id":"owner","gate_results":{
            "G0":{"status":"PASS","evidence_refs":["notes.md"]}}})
        self.assertEqual(self.cli("merge","--file",f)[0],1)

    def test_owner_cannot_set_g3_through_handoff(self):
        f=self.write_payload("handoff.json",{"writer_id":"owner","gate_results":{
            "G3":{"decision":"PASS","evidence_refs":["notes.md"]}}})
        self.assertEqual(self.cli("merge","--file",f)[0],1)

    def test_ad_hoc_state_aliases_do_not_allow_ending(self):
        self.state={"phase":"REVISION_REQUIRED","open_ids":["F1"],"blockers":[]}
        self.save()
        _,body=self.cli("next")
        self.assertEqual(body["terminal_decision"],"CONTINUE")
        self.assertEqual(body["next_action"]["kind"],"REPAIR_STATE_SCHEMA")

    def test_unsubstantiated_stop_reason_is_not_interruption(self):
        self.packet["units"][0]["read_state"]="READ"
        self.state["stop_reason"]="time limit"
        self.save()
        _,body=self.cli("next")
        self.assertEqual(body["terminal_decision"],"CONTINUE")

    def test_explicit_user_pause_with_checkpoint_ends_without_acceptance(self):
        self.packet["units"][0]["read_state"]="READ"
        self.state.update({"stop_reason":"USER_STOP","restart_action":"Read F1",
                           "interruption":{"evidence_refs":["notes.md"],"affected_unit_ids":["F1"],
                                           "observed_constraint":"User explicitly requested pause.",
                                           "attempts":["Saved source version and open IDs."]}})
        self.save()
        _,body=self.cli("next")
        self.assertEqual(body["terminal_decision"],"INTERRUPTED_WITH_EVIDENCE")
        self.assertTrue(body["may_send_final"])
        self.assertFalse(body["paper_accepted"])

    def test_material_block_does_not_hide_other_accessible_units(self):
        self.packet["units"] += [{"unit_id":"F2","read_state":"READ","source_id":"S1","locators":[{"physical_page":1}]}]
        self.packet["units"][0]["read_state"]="BLOCKED"
        self.inventory.append({"unit_id":"F2"})
        self.state.update({"stop_reason":"MATERIAL_BLOCK","restart_action":"Acquire F1",
                           "interruption":{"evidence_refs":["notes.md"],"affected_unit_ids":["F1"],
                                           "observed_constraint":"Required page is damaged.",
                                           "attempts":["Opened original and available copy."]}})
        self.save()
        _,body=self.cli("next")
        self.assertEqual(body["terminal_decision"],"CONTINUE")
        self.assertIn("F2",body["next_action"]["unit_ids"])

    def test_changed_scope_reopens_actual_review(self):
        self.packet["scope_revision"]=2
        self.state["scope_revision"]=2
        self.save()
        _,body=self.cli("next")
        self.assertEqual(body["terminal_decision"],"CONTINUE")
        self.assertEqual(body["next_action"]["kind"],"REQUEST_REVIEW")

    def test_init_uses_canonical_shapes_and_keeps_source(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"new-run"
            source=self.root/"source.pdf"
            before=source.read_bytes()
            result=subprocess.run([sys.executable,str(SCRIPT),"init",str(out),"--source",str(source),"--owner","owner"],
                                  capture_output=True,text=True,encoding="utf8")
            self.assertTrue(result.stdout.startswith("{"),result.stderr)
            self.assertEqual(result.returncode,0,result.stdout)
            packet=json.loads((out/"paper_packet.json").read_text(encoding="utf8"))
            state=json.loads((out/"execution_state.json").read_text(encoding="utf8"))
            self.assertEqual(packet["gate_results"]["G0"]["decision"],"PENDING")
            self.assertEqual(state["stage"],"01")
            self.assertEqual(state["next_actions"][0]["kind"],"EXTRACT_ELEMENTS")
            self.assertEqual(packet['content_acquisition']['method'], 'PDFPLUMBER_NATIVE')
            self.assertEqual(source.read_bytes(),before)
            self.assertEqual((out/"source.pdf").read_bytes(),before)

    def test_init_refuses_to_overwrite_existing_run(self):
        before={f.name:f.read_bytes() for f in self.root.iterdir()}
        code,body=self.cli("init","--source",str(self.root/"source.pdf"),"--owner","owner")
        self.assertEqual(code,1)
        self.assertEqual(body["error_code"],"RUN_EXISTS")
        self.assertEqual(before,{f.name:f.read_bytes() for f in self.root.iterdir()})

    def test_handoff_cannot_change_source_identity_or_hide_visual_kind(self):
        f=self.write_payload("bad-kind.json",{"writer_id":"reader","units":[{
            "unit_id":"F1","kind":"SECTION","understanding_note":"An alleged nonvisual section.",
            "read_state":"CHECKED","visual_review":{"required":False,"actually_viewed":False}}]})
        self.assertEqual(self.cli("merge","--file",f)[0],1)

    def test_gate_zero_cannot_pass_an_empty_inventory(self):
        self.packet["units"]=[]
        self.inventory=[]
        self.save()
        f=self.write_payload("bad-g0.json",{"writer_id":"owner","gate_results":{
            "G0":{"decision":"PASS","evidence_refs":["notes.md"],"open_items":[]}}})
        self.assertEqual(self.cli("merge","--file",f)[0],1)

    def test_unknown_handoff_fields_are_not_silently_ignored(self):
        f=self.write_payload("unknown.json",{"writer_id":"reader","reviews":[self.failed_review()]})
        self.assertEqual(self.cli("merge","--file",f)[0],1)

    def test_raw_handoff_is_preserved(self):
        payload={"writer_id":"reader","units":[{"unit_id":"F1","read_state":"UNDERSTOOD",
            "understanding_note":"Two paths converge on an output; the diagram describes the design only."}]}
        f=self.write_payload("raw.json",payload)
        self.assertEqual(self.cli("merge","--file",f)[0],0)
        saved=list((self.root/"handoffs").glob("*.json"))
        self.assertTrue(saved)
        self.assertIn(payload,[json.loads(x.read_text(encoding="utf8")) for x in saved])

    def test_source_locator_change_reopens_unit_checking(self):
        self.assertEqual(self.cli("sync")[0],0)
        self.inventory[0]["locators"]=[{"physical_page":2}]
        (self.root/"01_inventory.json").write_text(json.dumps(self.inventory),encoding="utf8")
        self.assertEqual(self.cli("sync")[0],0)
        packet=json.loads((self.root/"paper_packet.json").read_text(encoding="utf8"))
        self.assertEqual(packet["scope_revision"],2)
        self.assertNotEqual(packet["units"][0]["read_state"],"CHECKED")

    def test_editing_explanation_requires_new_review(self):
        f=self.write_payload('edit.json',{'writer_id':'reader','units':[{
            'unit_id':'F1','understanding_note':'The source has a different relationship under a restricted condition.'}]})
        self.assertEqual(self.cli('merge','--file',f)[0],0)
        _,body=self.cli('next')
        self.assertEqual(body['next_action']['kind'],'REQUEST_REVIEW')
        self.assertFalse(body['may_send_final'])

    def test_direct_inventory_locator_edit_cannot_reuse_acceptance(self):
        self.inventory[0]['locators']=[{'physical_page':2}]
        self.save()
        _,body=self.cli('next')
        self.assertFalse(body['may_send_final'])

    def test_changed_report_or_evidence_cannot_reuse_acceptance(self):
        for file in ['report.md','page.png','notes.md']:
            with self.subTest(file=file):
                path=self.root/file
                before=path.read_bytes()
                path.write_bytes(b'changed reviewed content')
                _,body=self.cli('next')
                self.assertFalse(body['may_send_final'])
                path.write_bytes(before)

    def test_accepted_review_requires_actual_current_snapshot(self):
        review=copy.deepcopy(self.packet['reviews'][0])
        review.update({'review_id':'new-final','reviewed_content_sha256':'0'*64})
        f=self.write_payload('stale.json',review)
        self.assertEqual(self.cli('ingest-review','--file',f)[0],1)

    def test_capability_block_cannot_hide_accessible_review_repairs(self):
        self.packet['reviews']=[self.failed_review()]
        self.state.update({'stop_reason':'CAPABILITY_BLOCK','restart_action':'Get reviewer',
            'interruption':{'evidence_refs':['notes.md'],'affected_unit_ids':[],
                            'observed_constraint':'No reviewer available','attempts':['Checked available tools']}})
        self.save()
        _,body=self.cli('next')
        self.assertEqual(body['next_action']['kind'],'REPAIR')
        self.assertFalse(body['may_send_final'])

    def test_unsafe_review_ids_cannot_overwrite_other_archives(self):
        r=self.failed_review()
        r['review_id']='review/one'
        f=self.write_payload('unsafe.json',r)
        self.assertEqual(self.cli('ingest-review','--file',f)[0],1)

    def test_generated_notebook_cannot_write_outside_run(self):
        self.packet['deliverables']['full_notebook']='../outside.md'
        self.save()
        code,body=self.cli('sync')
        self.assertEqual(code,1)
        self.assertEqual(body['error_code'],'INVALID_PATH')

    def test_simultaneous_source_and_inventory_change_increments_once(self):
        self.assertEqual(self.cli('sync')[0],0)
        self.inventory[0]['locators']=[{'physical_page':2}]
        sources=copy.deepcopy(self.packet['sources'])
        sources[0]['sha256']='1'*64
        (self.root/'01_sources.json').write_text(json.dumps(sources),encoding='utf8')
        (self.root/'01_inventory.json').write_text(json.dumps(self.inventory),encoding='utf8')
        self.assertEqual(self.cli('sync')[0],0)
        packet=json.loads((self.root/'paper_packet.json').read_text(encoding='utf8'))
        self.assertEqual(packet['scope_revision'],2)

    def test_absolute_external_evidence_changes_invalidate_review(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'evidence.md'
            path.write_text('actual reviewed evidence',encoding='utf8')
            self.packet['units'][0]['evidence_refs'].append(str(path))
            self.save()
            self.packet['reviews'][0]['reviewed_content_sha256']=control.content_fingerprint(self.root,self.packet)
            self.save()
            self.assertTrue(self.cli('next')[1]['may_send_final'])
            path.write_text('different evidence',encoding='utf8')
            self.assertFalse(self.cli('next')[1]['may_send_final'])

    def test_nested_evidence_named_like_state_is_not_skipped(self):
        f=self.root/'evidence'/'execution_state.json'
        f.parent.mkdir()
        f.write_text('reviewed evidence',encoding='utf8')
        self.packet['units'][0]['evidence_refs'].append('evidence/execution_state.json')
        self.save()
        self.packet['reviews'][0]['reviewed_content_sha256']=control.content_fingerprint(self.root,self.packet)
        self.save()
        self.assertTrue(self.cli('next')[1]['may_send_final'])
        f.write_text('changed evidence',encoding='utf8')
        self.assertFalse(self.cli('next')[1]['may_send_final'])

    def test_new_failed_review_reopens_reused_repair_id(self):
        review=self.failed_review()
        f=self.write_payload('r1.json',review)
        self.assertEqual(self.cli('ingest-review','--file',f)[0],0)
        self.assertEqual(self.cli('repair-ready','--id','R1-01','--evidence','notes.md')[0],0)
        review['review_id']='R2'
        review['repair_requests'][0]['required_action']='New source discrepancy in the same unit; repair again.'
        f=self.write_payload('r2.json',review)
        code,body=self.cli('ingest-review','--file',f)
        self.assertEqual(code,0,body)
        self.assertEqual(body['next_action']['kind'],'REPAIR')

    def test_material_block_review_does_not_hide_repair_requests(self):
        review=self.failed_review()
        review['decision']='MATERIAL_BLOCKED'
        f=self.write_payload('blocked-review.json',review)
        code,body=self.cli('ingest-review','--file',f)
        self.assertEqual(code,0,body)
        self.assertEqual(body['next_action']['kind'],'REPAIR')

    def test_manual_notebook_and_fallback_are_preserved(self):
        self.packet['deliverables']['full_notebook']='manual.md'
        (self.root/'manual.md').write_text('Human manuscript',encoding='utf8')
        (self.root/'unit_notebook.md').write_text('Another human manuscript',encoding='utf8')
        self.save()
        self.assertEqual(self.cli('sync')[0],0)
        self.assertEqual((self.root/'manual.md').read_text(encoding='utf8'),'Human manuscript')
        self.assertEqual((self.root/'unit_notebook.md').read_text(encoding='utf8'),'Another human manuscript')

    def test_manual_material_index_is_preserved(self):
        path=self.root/'material_index.md'
        path.write_text('Handwritten source map',encoding='utf8')
        self.assertEqual(self.cli('sync')[0],0)
        self.assertEqual(path.read_text(encoding='utf8'),'Handwritten source map')

    def test_gate_only_evidence_change_invalidates_review(self):
        path=self.root/'gate-only.md'
        path.write_text('actual source completeness check',encoding='utf8')
        self.packet['gate_results']['G0']['evidence_refs']=['gate-only.md']
        self.save()
        self.packet['reviews'][0]['reviewed_content_sha256']=control.content_fingerprint(self.root,self.packet)
        self.save()
        self.assertTrue(self.cli('next')[1]['may_send_final'])
        path.write_text('changed coverage',encoding='utf8')
        self.assertFalse(self.cli('next')[1]['may_send_final'])

    def test_accessible_fourth_repair_precedes_three_blocked_repairs(self):
        review=self.failed_review()
        review['repair_requests']=[{'repair_id':f'R-{i}','unit_ids':['F1'],
            'required_action':f'Source-grounded repair {i}'} for i in range(4)]
        self.packet['reviews']=[review]
        self.state['interruption']={'affected_repair_ids':['R-0','R-1','R-2']}
        self.save()
        _,body=self.cli('next')
        self.assertEqual(body['next_action']['repair_ids'],['R-3'])

    def test_nested_notebook_index_link_retains_directory(self):
        self.packet['deliverables']['full_notebook']='notes/notebook.md'
        self.save()
        self.assertEqual(self.cli('sync')[0],0)
        packet=json.loads((self.root/'paper_packet.json').read_text(encoding='utf8'))
        index=(self.root/packet['deliverables']['material_index']).read_text(encoding='utf8')
        self.assertIn('(notes/notebook.md#f1)',index)


if __name__=="__main__":
    unittest.main()

