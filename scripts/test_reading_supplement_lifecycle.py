"""A late supplement changes the scope, not the historical evidence for the original paper."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import reading_run_control as ctl
import reading_pdf_elements as native
from test_reading_pdf_elements import minimal_pdf, FakeParser


class ScopeChangeTests(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        folder = Path(work.name)
        original = folder/'paper.pdf'
        original.write_bytes(minimal_pdf())
        self.root = folder/'run'
        ctl.initialize(self.root, original, 'writer', 'en')
        native.extract_elements(self.root, FakeParser())
        self.main = {'unit_id':'main', 'source_id':'SRC-01', 'label':'Main', 'kind':'SECTION',
                     'locators':[{'physical_page':1}]}
        self.save('01_inventory.json',[self.main]); self.sync()
        (self.root/'notes.md').write_text('Owner checked the printed table notes against the source.',encoding='utf8')
        self.handoff(units=[{'unit_id':'main','read_state':'CHECKED','understanding_note':'The example reports two labeled values, without uncertainty.',
                    'evidence_refs':['notes.md'],'content_reading':{'mode':'NATIVE_ELEMENTS',
                    'page_refs':['source_elements/page-0001.json'],'element_ids':['p0001-text']}}],
                    gate_results={g:self.pass_gate() for g in ['G0','G1','G2']})

    def save(self,name,data): ctl.write(self.root/name,data)
    def get(self,name): return ctl.read(self.root/name)
    def pass_gate(self): return {'decision':'PASS','evidence_refs':['notes.md'],'open_items':[]}
    def handoff(self, **data): return ctl.merge_handoff(self.root,{'writer_id':'writer',**data})
    def sync(self):
        packet = self.get('paper_packet.json'); state = self.get('execution_state.json')
        ctl.sync_inventory(self.root,packet,state)
        return ctl.commit(self.root,packet,state,'Synced registry and inventory.')

    def supplement(self, payload=b'study,outcome\nalpha,yes\n', fmt='CSV', suffix='csv'):
        path=self.root/('supp.'+suffix);path.write_bytes(payload)
        (self.root/'receipt.md').write_text('Publisher acquisition',encoding='utf8')
        src={'source_id':'SUP','source_kind':'DATA_FILE','format':fmt,'local_path':path.name,
             'sha256':ctl.digest(path),'page_count':None,'access_state':'AVAILABLE','required_for_scope':True,
             'supplement_of':'SRC-01','provenance':{'origin':'publisher','acquisition_ref':'receipt.md'}}
        self.save('01_sources.json', self.get('01_sources.json')+[src])
        return {'unit_id':'supp','source_id':'SUP','kind':'TABLE','label':'Study ledger',
                'locators':[{'rows':[2,2],'fields':['outcome']}]}

    def cli(self,args, check=True):
        r=subprocess.run([sys.executable,'-B',str(Path(ctl.__file__)),args[0],str(self.root),*args[1:]],
                         capture_output=True,encoding='utf8')
        if check:self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        return r

    def test_reopen_once_keep_old_units_and_require_fresh_gate_evidence(self):
        before=self.get('paper_packet.json'); rev=before['scope_revision']; old_unit=copy.deepcopy(before['units'][0]);gates=copy.deepcopy(before['gate_results'])
        unit=self.supplement(); self.save('01_inventory.json',[self.main,unit]); synced=self.sync()
        self.assertTrue(synced['next_action']['append']); p=self.get('paper_packet.json')
        self.assertEqual(p['scope_revision'],rev+1); self.assertEqual(p['units'][0],old_unit)
        for g in ('G0','G1','G2'):self.assertEqual(p['gate_results'][g]['decision'],'PENDING')
        history=self.get('execution_state.json')['scope_gate_history']; self.assertEqual(history[-1]['gate_results']['G0'],gates['G0'])
        native.extract_elements(self.root,append=True); self.assertEqual(self.sync()['next_action']['kind'],'SOURCE_INVENTORY')
        self.assertEqual(self.get('execution_state.json')['scope_gate_history'],history)
        self.assertEqual(self.get('paper_packet.json')['scope_revision'],rev+1)
        with self.assertRaisesRegex(ctl.RunError, 'different scope'):
            self.handoff(gate_results={'G0':dict(self.pass_gate(),scope_revision=rev)})
        step=self.handoff(gate_results={'G0':self.pass_gate()})['next_action']; self.assertNotIn('read-section',step['instruction'])
        route,=step['data_reads']; args=route['first_read_argv'];self.assertEqual(args[:4],['read-data','<run>','--source-id','SUP']);self.assertEqual(route['unit_id'],'supp')
        self.assertEqual(json.loads(self.cli([args[0],*args[2:]]).stdout)['rows'],[{'row':2,'values':['yes']}])
        step=self.handoff(units=[{'unit_id':'supp','read_state':'CHECKED','understanding_note':'The ledger codes alpha as yes.',
                 'evidence_refs':['supp.csv'],'content_reading':{'mode':'DATA_FILE'}}])['next_action']
        self.assertEqual((step['kind'],step['gate']),('VERIFY_LOCAL_GATE','G1'))
        with self.assertRaisesRegex(ctl.RunError,'Recheck G1'):self.handoff(gate_results={'G2':self.pass_gate()})
        self.assertEqual(self.handoff(gate_results={'G1':self.pass_gate()})['next_action']['gate'],'G2')
        self.handoff(gate_results={'G2':self.pass_gate()});p=self.get('paper_packet.json');self.assertEqual(p['gate_results']['G2']['scope_revision'],rev+1);self.assertEqual(p['gate_results']['G3']['decision'],'PENDING')

    def test_route_preserves_empty_json_pointer_and_nullable_tabular_selectors(self):
        units = [{'unit_id':'j', 'source_id':'J', 'locators':[{'json_pointer':''}]},
                 {'unit_id':'t', 'source_id':'T', 'locators':[{'rows':[3,3], 'sheet':None,
                                                               'fields':None, 'header_row':None}]}]
        sources = [{'source_id':sid, 'source_kind':'DATA_FILE', 'format':fmt}
                   for sid,fmt in [('J','JSON'),('T','CSV')]]
        json_route, csv_route = ctl._data_routes({'sources':sources}, units)
        self.assertEqual(json_route['first_read_argv'][-2:], ['--json-pointer',''])
        self.assertEqual(csv_route['first_read_argv'][4:], ['--rows','3','3','--header-row','0'])

    def test_new_required_source_without_unit_reopens_scope_and_blocks_g0(self):
        self.supplement();self.sync();native.extract_elements(self.root,append=True)
        with self.assertRaisesRegex(ctl.RunError,'SUP'):self.handoff(gate_results={'G0':self.pass_gate()})
        self.assertEqual(self.get('paper_packet.json')['gate_results']['G0']['decision'],'PENDING')

    def test_recovery_of_bound_codec_conflict_preserves_manifest(self):
        u=self.supplement('study,outcome\nalpha,Müller\n'.encode('cp1252'));self.save('01_inventory.json',[self.main,u]);self.sync();native.extract_elements(self.root,append=True)
        manifest=(self.root/'source_elements/manifest.json');frozen=manifest.read_bytes();self.handoff(gate_results={'G0':self.pass_gate()});rev=self.get('paper_packet.json')['scope_revision']
        src=self.get('01_sources.json');src[-1]['encoding']='cp1252';self.save('01_sources.json',src)
        self.assertEqual(self.sync()['next_action']['kind'],'SOURCE_INVENTORY');self.assertEqual(self.get('paper_packet.json')['scope_revision'],rev+1)
        self.assertEqual(json.loads(self.cli(['read-data','--source-id','SUP','--rows','2','2','--fields','outcome']).stdout)['rows'][0]['values'],['Müller']);self.assertEqual(frozen,manifest.read_bytes())
        self.assertEqual(self.get('paper_packet.json')['units'][0]['read_state'],'CHECKED')

    def test_accepted_state_is_reopened_without_editing_review_history(self):
        p=self.get('paper_packet.json');p['paper_status']='VERIFIED_FOR_SCOPE';p['gate_results']['G3']=self.pass_gate();old=[{'review_id':'previous','decision':'VERIFIED_FOR_SCOPE'}];p['reviews']=old;self.save('paper_packet.json',p)
        self.supplement();self.sync();p=self.get('paper_packet.json');self.assertEqual(p['paper_status'],'IN_PROGRESS');self.assertEqual(p['reviews'],old);self.assertEqual(p['gate_results']['G3']['decision'],'PENDING')

    def test_data_cli_limits_preserve_numeric_tokens_and_reconstruct_source_text(self):
        long='汉🌐'*9500; value='{"decimal":1.2300000000000000000001e-400,"big":1e400,"memo":'+json.dumps(long,ensure_ascii=False)+'}'
        self.supplement(value.encode('utf8'),'JSON','json');self.sync();native.extract_elements(self.root,append=True)
        for key,token in [('decimal','1.2300000000000000000001e-400'),('big','1e400')]:
            r=self.cli(['read-data','--source-id','SUP','--json-pointer','/'+key]);self.assertIn('"value":'+token,r.stdout)
        args=['read-data','--source-id','SUP','--json-pointer','/memo'];self.assertNotEqual(self.cli(args,check=False).returncode,0)
        chunks=[]
        for start in range(1,len(long)+1,1500):
            last=min(len(long),start+1499);v=json.loads(self.cli([*args,'--chars',str(start),str(last)]).stdout);chunks.append(v['value']);self.assertEqual(v['chars'],[start,last]);self.assertEqual(v['total_chars'],len(long));self.assertTrue(v['partial'])
        self.assertEqual(''.join(chunks),long)


if __name__=='__main__':unittest.main()
