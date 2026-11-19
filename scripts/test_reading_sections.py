"""Section reading is keyed by inventory identity; pages account for the text, not the schedule."""
import hashlib
import json
from pathlib import Path
import unittest

import reading_sections as sections
from reading_pdf_elements import ElementError
import test_reading_pdf_elements as native
from test_reading_locators import TextPage
import test_reading_run_control as runs


class SectionReadingTests(unittest.TestCase):
    root: Path
    packet: dict
    setUp = native.NativeElementTests.setUp
    save = native.NativeElementTests.save
    module = native.NativeElementTests.module
    extract = native.NativeElementTests.extract
    cli = runs.ReadingRunControlTests.cli

    def fixture(self, lines):
        pages = []
        for rows in lines:
            p = TextPage()
            p.native_lines = rows
            pages.append(p)
        self.packet['sources'][0]['page_count'] = len(pages)
        self.save()
        self.extract(native.FakeParser(pages))

    def unit(self, uid, *locs, kind='SECTION'):
        self.packet['units'].append({'unit_id': uid, 'source_id':'S1', 'kind':kind,
                                     'label':uid, 'locators':list(locs), 'read_state':'INVENTORIED'})
        self.save()

    @staticmethod
    def loc(n, **body):
        return {'physical_page':n, 'body':body}

    @staticmethod
    def words(result):
        return [w for s in result['segments'] for w in s['text'].split()]

    def test_section_crosses_six_pages_and_stops_before_next_heading(self):
        self.fixture([[(0,10,'Title 2 Methods a')]] + [[(0,10,f'body{i}')] for i in range(2,6)]
                     + [[(0,10,'end 3 Results measurements')]])
        self.unit('M', self.loc(1,start_at='2 Methods'), *(self.loc(i) for i in range(2,6)),
                  self.loc(6,stop_before='3 Results'))
        self.unit('R',self.loc(6,start_at='3 Results'))
        code, result = self.cli('read-section','--id','M')
        self.assertEqual(code,0,result)
        self.assertEqual(self.words(result), '2 Methods a body2 body3 body4 body5 end'.split())
        self.assertEqual([s['physical_page'] for s in result['segments']],list(range(1,7)))
        self.assertEqual(result['segments'][0]['first_word_id'],'p0001-w00002')
        self.assertEqual(result['segments'][-1]['last_word_id'],'p0006-w00001')
        for seg in result['segments']:
            self.assertTrue((self.root/seg['page_ref']).is_file())
        self.assertIsNone(result['next_cursor'])
        self.assertEqual(self.words(sections.read_section(self.root,'R')),['3','Results','measurements'])
        code,audit=self.cli('section-coverage','--source-id','S1')
        self.assertEqual(code,0,audit)
        self.assertEqual(audit['partial_pages'],[1])  # front matter is not Methods
        self.assertFalse(audit['overlap_pages'])

    def test_regions_define_column_order_without_copying_the_next_section(self):
        self.fixture([[(0,10,'Intro LEFT'), (200,10,'RIGHT first'), (0,30,'last left'),
                       (200,30,'Discussion OTHER')]])
        self.unit('I', self.loc(1,bbox=[0,0,150,800]),self.loc(1,bbox=[150,0,500,800],stop_before='Discussion'))
        self.unit('D', self.loc(1,bbox=[150,0,500,800],start_at='Discussion'))
        self.assertEqual(self.words(sections.read_section(self.root,'I')), 'Intro LEFT last left RIGHT first'.split())
        self.assertEqual(sections.section_coverage(self.root,'S1')['partial_pages'],[])

    def test_gap_overlap_unmapped_no_text_and_unbound_are_distinct(self):
        self.fixture([[(0,10,'A B C')],[(0,10,'D')],[],[(0,10,'X Y')]])
        self.unit('A',self.loc(1,stop_before='C'),self.loc(4))
        self.unit('B',self.loc(1,start_at='B',stop_before='C'))
        self.unit('parent',{'physical_page':1})
        self.unit('FIG',{'physical_page':2},kind='FIGURE')
        audit=sections.section_coverage(self.root,'S1')
        self.assertEqual((audit['partial_pages'],audit['overlap_pages'],audit['unmapped_pages'],
                          audit['no_native_text_pages'],audit['unbound_sections']),([1],[1],[2],[3],['parent']))
        self.assertFalse(audit['reading_state_changed'])
        with self.assertRaisesRegex(ElementError,'not a section boundary'):
            sections.read_section(self.root,'parent')

    def test_invalid_mapping_is_not_counted_partially(self):
        self.fixture([[(0,10,'Methods A Methods B')]])
        self.unit('ambiguous',self.loc(1,start_at='Methods'))
        self.unit('missing',self.loc(1,start_at='Absent'))
        self.unit('reversed',self.loc(1,start_at='B',stop_before='A'))
        self.unit('bad-region',self.loc(1,bbox=[0,0,600,800]))
        self.unit('unknown-field',self.loc(1,offset=50))
        self.unit('repeat-within-unit',self.loc(1),self.loc(1))
        self.unit('wrong-source-page',self.loc(9))
        self.unit('bad-locator','not a locator object')
        for u in self.packet['units']:
            with self.subTest(unit=u['unit_id']), self.assertRaises(ElementError) as err:
                sections.read_section(self.root,u['unit_id'])
            self.assertEqual(err.exception.code,'INVALID_SECTION_MAP')
        audit=sections.section_coverage(self.root,'S1')
        self.assertEqual(set(audit['invalid_sections']),{u['unit_id'] for u in self.packet['units']})
        self.assertEqual(audit['unmapped_pages'],[1])

    def test_cursor_is_lossless_bounded_source_bound_and_read_only(self):
        expected=['词'+str(i) for i in range(110)]
        self.fixture([[(0,10,' '.join(expected[:50]))],[(0,10,' '.join(expected[50:]))]])
        self.unit('A',self.loc(1),self.loc(2)); self.unit('B',self.loc(1))
        def snapshot():
            return {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        before=snapshot(); result=sections.read_section(self.root,'A',max_chars=650); words=self.words(result)
        first=result['next_cursor']; self.assertIsNotNone(first);seen=set()
        while True:
            self.assertLessEqual(len(json.dumps(result,ensure_ascii=True,separators=(',',':')))+1,650)
            self.assertFalse(result['reading_state_changed'])
            cursor=result['next_cursor']
            if cursor is None: break
            self.assertNotIn(cursor,seen); seen.add(cursor)
            result=sections.read_section(self.root,'A',cursor,650);words.extend(self.words(result))
        self.assertEqual(words,expected)
        self.assertEqual(snapshot(),before)
        for wrong in (first,'not-a-cursor'):
            with self.assertRaises(ElementError) as err: sections.read_section(self.root,'B',wrong)
            self.assertEqual(err.exception.code,'INVALID_SECTION_CURSOR')
        self.packet['units'][0]['locators'][0]=self.loc(1,start_at=expected[2]);self.save()
        with self.assertRaises(ElementError) as err: sections.read_section(self.root,'A',first)
        self.assertEqual(err.exception.code,'INVALID_SECTION_CURSOR')
        with self.assertRaises(ElementError) as err: sections.read_section(self.root,'A',max_chars=10)
        self.assertEqual(err.exception.code,'ELEMENT_READ_LIMIT')

    def test_supplement_binds_its_own_words_and_page_reference(self):
        main, supplement = TextPage(), TextPage()
        main.native_lines = [(0, 10, 'Main source')]
        supplement.native_lines = [(0, 10, 'Supplement source')]

        class Parser:
            __version__ = 'test'

            def open(self, path):
                return native.FakePDF([supplement if path.name == 'supp.pdf' else main])

        (self.root/'supp.pdf').write_bytes((self.root/'source.pdf').read_bytes())
        self.packet['sources'].append(dict(self.packet['sources'][0], source_id='SUP', local_path='supp.pdf'))
        self.save()
        self.extract(Parser())
        self.unit('supp-section',self.loc(1),kind='APPENDIX')
        self.packet['units'][0]['source_id'] = 'SUP'
        self.save()
        result = sections.read_section(self.root,'supp-section')
        self.assertEqual(result['source_id'],'SUP')
        self.assertEqual(self.words(result),['Supplement','source'])
        self.assertIn('SUP-',result['segments'][0]['page_ref'])
        self.assertEqual(sections.section_coverage(self.root,'SUP')['unmapped_pages'],[])
        self.assertEqual(sections.section_coverage(self.root,'S1')['unmapped_pages'],[1])

    def test_foreign_source_and_tamper_fail_closed(self):
        self.fixture([[(0,10,'Bound paper')]])
        self.unit('A',self.loc(1)); self.unit('img',self.loc(1),kind='FIGURE')
        for uid in ('img','unknown'):
            with self.assertRaises(ElementError) as err: sections.read_section(self.root,uid)
            self.assertEqual(err.exception.code,'INVALID_SECTION')
        with self.assertRaises(ElementError): sections.section_coverage(self.root,'supplement')
        (self.root/'source_elements/page-0001.json').write_text('{}',encoding='utf8')
        for fn,arg in [(sections.read_section,'A'),(sections.section_coverage,'S1')]:
            with self.assertRaises(ElementError) as err: fn(self.root,arg)
            self.assertEqual(err.exception.code,'ELEMENTS_INVALID')


if __name__ == '__main__': unittest.main()
