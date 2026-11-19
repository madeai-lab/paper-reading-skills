"""Exercise the human CLI surfaces without requiring a model or a PDF backend."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import reading_sections
import test_reading_pdf_elements as native
from test_reading_locators import TextPage


class OwnerWorkflowTests(unittest.TestCase):
    root: Path
    packet: dict
    setUp = native.NativeElementTests.setUp
    save = native.NativeElementTests.save
    module = native.NativeElementTests.module
    extract = native.NativeElementTests.extract

    def make(self, pages, units=()):
        self.packet['sources'][0]['page_count'] = len(pages)
        self.packet['units'] = list(units)
        self.save()
        self.extract(native.FakeParser(pages))

    @staticmethod
    def page(lines):
        page = TextPage()
        page.native_lines = lines
        return page

    @staticmethod
    def unit(uid, kind, *locators):
        return dict(unit_id=uid, label='章 '+uid, source_id='S1', kind=kind, locators=list(locators))

    def cmd(self, op, *args, code=0):
        script = Path(__file__).with_name('reading_run_control.py')
        p = subprocess.run([sys.executable,'-B',str(script),op,str(self.root),*args],capture_output=True,
                           env={**os.environ,'PYTHONIOENCODING':'ascii'})
        self.assertEqual(p.returncode,code,(p.stdout,p.stderr))
        return p.stdout.decode('utf-8')

    def fingerprint(self):
        return {p.relative_to(self.root):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file()}

    def test_source_utf8_text_spot_check_does_not_include_geometry_or_outside_words(self):
        pg=self.page([(20,10,'Δ α'),(300,10,'outside')]);self.make([pg]);before=self.fingerprint()
        args=('--view','text','--source-id','S1','--pages','1')
        full=self.cmd('read-elements',*args); region=self.cmd('read-elements',*args,'--bbox','0','0','100','50')
        self.assertIn('Δ α', region);self.assertIn('outside',full);self.assertNotIn('outside',region)
        self.assertIn('p0001-text',region);self.assertNotIn('"chars"',region)
        err=json.loads(self.cmd('read-elements',*args,'--max-chars','1',code=1));self.assertEqual(err['error_code'],'ELEMENT_READ_LIMIT')
        self.assertEqual(self.fingerprint(),before)

    def test_plain_section_cursor_reassembles_actual_body_with_provenance(self):
        expected=['字'+str(i) for i in range(120)]
        pages=[self.page([(0,10,' '.join(expected[:60]))]),self.page([(0,10,' '.join(expected[60:]))])]
        unit=self.unit('Methods','SECTION',{'physical_page':1,'body':{}},{'physical_page':2,'body':{}})
        self.make(pages,[unit]); before=self.fingerprint();args=['--id','Methods','--format','text','--max-chars','290']
        collected=[];cursors=set();refs=set();chunk=self.cmd('read-section',*args)
        while True:
            self.assertLessEqual(len(chunk),290);blocks=chunk.strip().split('\n\n')
            self.assertIn('章 Methods',blocks[0]);self.assertTrue(blocks[-1].startswith('next_cursor: '))
            for meta,body in zip(blocks[1:-1:2],blocks[2:-1:2]):
                self.assertIn('flags=',meta);self.assertIn('-w',meta);refs.add(meta.split()[1]);collected.extend(body.split())
            cursor=blocks[-1].split()[-1]
            if cursor=='END':break
            self.assertNotIn(cursor,cursors);cursors.add(cursor);chunk=self.cmd('read-section',*args,'--cursor',cursor)
        self.assertEqual(collected,expected);self.assertTrue(cursors);self.assertEqual(len(refs),2)
        self.assertEqual(self.fingerprint(),before)
        self.assertIsNone(json.loads(self.cmd('read-section','--id','Methods'))['next_cursor'])

    def test_details_filter_counts_object_selectors_without_granting_reading(self):
        p1=self.page([(0,5,'HEADER'),(0,100,'Intro'),(0,200,'Figure 1'),(0,760,'FOOTER')]);p2=self.page([(0,200,'Elsewhere')]);
        self.make([p1,p2],[self.unit('S','SECTION',{'physical_page':1,'body':{'start_at':'Intro','stop_before':'Figure'}}),
                           self.unit('F','FIGURE',{'physical_page':1,'body':{'start_at':'Figure','stop_before':'FOOTER'}})])
        before=self.fingerprint(); args=['--source-id','S1','--details','--pages','1']
        audit=json.loads(self.cmd('section-coverage',*args)); self.assertEqual(audit['unmapped_pages'],[2]);self.assertEqual(audit['partial_pages'],[1])
        runs=audit['unmapped_runs']['1'];self.assertEqual([r['text'] for r in runs],['HEADER','FOOTER']);self.assertEqual([r['position'] for r in runs],['top margin','bottom margin'])
        for i,r in enumerate(runs):
            a=reading_sections.section_coverage(self.root,'S1',details=True,pages_filter=[1],limit=1,offset=i)
            self.assertEqual(a['unmapped_runs'][1],[r]);self.assertEqual(a['next_offset'],1 if i==0 else None)
        self.assertNotIn('unmapped_runs',json.loads(self.cmd('section-coverage','--source-id','S1')))
        self.assertFalse(audit['reading_state_changed']);self.assertEqual(self.fingerprint(),before)
        self.assertEqual(json.loads(self.cmd('section-coverage',*args[:-1],'3',code=1))['error_code'],'INVALID_ARGUMENT')

    def test_three_thin_rectangles_are_a_candidate_region_not_three_crop_targets(self):
        class RulesPage(TextPage):
            native_lines = [(38,57,'Table 2')]
            rects = [{'x0':38, 'x1':289, 'top':84, 'bottom':84.5}]
            curves = [{'x0':lo, 'x1':hi, 'top':106, 'bottom':106.5}
                      for lo, hi in [(38,100),(98,200),(198,289)]] + [
                          {'x0':38, 'x1':289, 'top':265, 'bottom':265.5}]

        self.make([RulesPage()])
        page=json.loads(self.cmd('read-elements','--pages','1','--view','locator'))['pages'][0]
        candidate,=page['objects']
        self.assertEqual((candidate['kind'],candidate['basis']),('drawing_region','parallel_rules'))
        self.assertEqual(candidate['bbox'],[38,84,289,265.5])
        self.assertNotIn('rows',candidate)

    def test_outline_command_is_not_sync_or_a_gate(self):
        self.make([self.page([(0,30,'1 Introduction'),(0,48,'First paragraph.'),(0,80,'2 Results'),(0,100,'New outcome.')])]);before=self.fingerprint()
        output=self.cmd('outline','--source-id','S1');self.assertIn('Introduction',output);self.assertEqual(self.fingerprint(),before)
        info=json.loads(self.cmd('outline','--source-id','S1','--out','tools/test.draft.json','--format','json'))
        draft=json.loads((self.root/'tools/test.draft.json').read_bytes());self.assertGreater(len(draft),0);self.assertFalse(info['reading_state_changed'])
        self.assertEqual(json.loads((self.root/'paper_packet.json').read_bytes())['units'],[])
        self.assertEqual(set(self.fingerprint())-set(before),{Path('tools/test.draft.json')})


if __name__=='__main__':unittest.main()
