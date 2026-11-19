"""Draft only: exercise the public navigation API against temporary frozen manifests."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
from threading import Barrier
import unittest

from reading_outline import draft_inventory, outline_json, outline_text, run_outline
from reading_pdf_elements import ElementError
from reading_sections import read_section
import test_reading_pdf_elements as native
from test_reading_locators import TextPage


def page(*rows, images=(), bold=()):
    p = TextPage()
    p.native_lines, p.images = rows, images
    p.chars = [dict(w, fontname='Bold' if w['top'] in bold else 'Regular', size=10)
               for w in p.extract_words()]
    return p


def image(left, top, width, height):
    return dict(x0=left, x1=left+width, top=top, bottom=top+height, width=width, height=height,
                srcsize=(width, height), name='bitmap', bits=8)


class OutlineTests(unittest.TestCase):
    root: Path
    packet: dict
    setUp = native.NativeElementTests.setUp
    save = native.NativeElementTests.save
    module = native.NativeElementTests.module
    extract = native.NativeElementTests.extract

    def freeze(self, *pages):
        self.packet['sources'][0]['page_count'] = len(pages)
        self.packet['gate_results'] = {'G0': {'decision': 'PENDING'}}
        self.save()
        self.extract(native.FakeParser(pages))

    def snapshot(self):
        return {p.relative_to(self.root): hashlib.sha256(p.read_bytes()).digest()
                for p in self.root.rglob('*') if p.is_file()}

    def read_words(self, uid):
        return [w for seg in read_section(self.root, uid)['segments'] for w in seg['text'].split()]

    def test_plain_nested_headings_require_active_parent_not_table_numbers_or_runins(self):
        self.freeze(page((20, 50, 'Paper title'), (20, 80, '2 Methods'), (20, 100, 'preamble'),
                         (20, 120, '2.1 Encoding'), (20, 140, 'body one'),
                         (20, 160, '2.1.1 Training'), (20, 180, 'body two'),
                         (20, 200, '33 Built Environment and Design'), (20, 220, '9.5 Orphan'),
                         (20, 240, 'AN EMPHASIZED LABEL'), bold=[200, 240]))
        before = self.snapshot()
        result, units, review = run_outline(self.root)
        self.assertIsNone(units)
        self.assertIsNone(review)
        self.assertEqual(before, self.snapshot())
        units, review = draft_inventory(result)
        self.assertEqual(review, [])
        self.assertEqual([u['unit_id'] for u in units], ['FRONT', 'S2', 'S2.1', 'S2.1.1'])
        self.assertEqual([u['parent_id'] for u in units], [None, None, 'S2', 'S2.1'])
        self.assertEqual(units[1]['children'], ['S2.1'])
        text = outline_text(result, units, review, 'tools/draft.json')
        for u in units:
            self.assertIn(u['unit_id']+' p1', text)
        structured = json.loads(json.dumps(outline_json(result)))
        self.assertFalse(structured['g0_assessed'])
        self.assertFalse(structured['reading_state_changed'])
        self.assertEqual([h['draft_unit_id'] for h in structured['headings'] if h['accepted']],
                         ['S2', 'S2.1', 'S2.1.1'])
        self.packet['units'] = units
        self.save()
        self.assertEqual(self.read_words('S2'), ['2', 'Methods', 'preamble'])
        self.assertEqual(self.read_words('S2.1.1'),
                         '2.1.1 Training body two 33 Built Environment and Design 9.5 Orphan AN EMPHASIZED LABEL'.split())

    def test_runin_and_repeated_headings_do_not_drop_running_prose(self):
        p = page((20, 50, '1 Introduction'), (20, 80, '1.1 Approach. This is ordinary prose'),
                 (20, 110, '2 Notes'), (20, 125, 'some details'), (20, 150, '2 Notes'), bold=[110, 150])
        for c in p.chars:
            if c['top'] == 80:
                c.update(size=14, fontname='Bold' if c['text'] in ('1.1', 'Approach.') else 'Regular')
        self.freeze(p)
        result, _, _ = run_outline(self.root)
        heads = outline_json(result)['headings']
        self.assertEqual([h['run_in'] for h in heads if h['run_in']], ['1.1 Approach.'])
        self.assertEqual([h['draft_unit_id'] for h in heads if h['accepted']], ['S1'])
        self.packet['units'], _ = draft_inventory(result)
        self.save()
        self.assertEqual(self.read_words('S1'), p.extract_text().split())

    def test_divider_is_not_runin_and_wrapped_title_stops_before_prose(self):
        p = page((20, 40, '1 | Findings'), (20, 60, '1.1 | Model'), (20, 70, 'Validation'),
                 (20, 90, 'body paragraph'), (20, 110, '1.2 | Caution. Plain prose follows'),
                 (20, 140, '2 | Ordinary table cells'), (20, 170, '2 | Discussion'), bold=[40, 60, 70, 110, 170])
        for glyph in p.chars:
            if glyph['text'] == '|' or glyph['text'] in ('Plain', 'prose', 'follows'):
                glyph['fontname'] = 'Regular'
        self.freeze(p)
        result, _, _ = run_outline(self.root)
        units, _ = draft_inventory(result)
        self.assertEqual([u['unit_id'] for u in units], ['S1', 'S1.1', 'S2'])
        self.assertEqual(units[1]['label'], '1.1 Model Validation')
        self.assertEqual(units[1]['parent_id'], 'S1')
        self.packet['units'] = units
        self.save()
        self.assertEqual(self.read_words('S1.1'),
                         '1.1 | Model Validation body paragraph 1.2 | Caution. Plain prose follows 2 | Ordinary table cells'.split())

    def test_full_width_abstract_then_two_columns_on_the_same_page(self):
        intro = ' '.join(['summary']*14)
        pairs = [(x, 380+12*i, f'{side} column passage {i}') for i in range(12)
                 for x, side in ((20, 'left'), (280, 'right'))]
        p = page((20, 60, 'Abstract'), *((20, 82+12*i, intro) for i in range(22)),
                 (20, 366, '1 | Methods'), (280, 366, '2 | Results'), *pairs, bold=[60, 366])
        self.freeze(p)
        result, _, _ = run_outline(self.root)
        self.packet['units'], _ = draft_inventory(result)
        self.save()
        self.assertEqual(self.read_words('S-ABSTRACT'), ('Abstract '+(intro+' ')*22).split())
        for uid, side, title in [('S1', 'left', 'Methods'), ('S2', 'right', 'Results')]:
            self.assertEqual(self.read_words(uid), [uid[1:], '|', title] +
                             ' '.join(f'{side} column passage {i}' for i in range(12)).split())

    def test_unbounded_abstract_keeps_page_hints_but_no_readable_body(self):
        self.freeze(page((20, 100, 'Abstract'), (20, 140, 'short summary'), bold=[100]),
                    page((20, 120, 'unrecognised boundary')), page((20, 160, 'more prose')))
        result, units, review = run_outline(self.root, out='tools/draft.json')
        self.assertTrue(any('abstract would cover 3 pages' in s for s in result['notes']))
        self.assertTrue(any('first body heading' in s for s in review))
        self.assertEqual([loc['physical_page'] for loc in units[0]['locators']], [1, 2, 3])
        self.assertFalse(any('body' in loc for loc in units[0]['locators']))
        self.packet['units'] = units
        self.save()
        with self.assertRaises(ElementError) as err:
            read_section(self.root, 'S-ABSTRACT')
        self.assertEqual(err.exception.code, 'SECTION_UNMAPPED')

    def test_ambiguous_boundary_does_not_publish_even_a_partial_section(self):
        repeat = ' '.join(['a'] * 18)
        self.freeze(page((20, 80, 'front page')),
                    page((20, 80, 'prose mentioning 2 Methods '+repeat), (20, 120, '2 Methods'), (20, 140, repeat)),
                    page((20, 80, 'more methods')))
        result, units, review = run_outline(self.root, out='tools/draft.json')
        self.assertEqual(units, json.loads((self.root/'tools/draft.json').read_text(encoding='utf-8')))
        self.assertEqual([u['unit_id'] for u in units], ['FRONT', 'S2'])
        self.assertTrue(any('no unique start_at' in msg for msg in review))
        self.assertTrue(any('no unique stop_before' in msg for msg in review))
        self.packet['units'] = units
        self.save()
        for u in units:
            self.assertGreater(len(u['locators']), 1)
            self.assertFalse(any('body' in loc for loc in u['locators']))
            self.assertTrue(any('Unresolved' in loc.get('paragraph_or_cell', '') for loc in u['locators']))
            with self.assertRaises(ElementError) as err:
                read_section(self.root, u['unit_id'])
            self.assertEqual(err.exception.code, 'SECTION_UNMAPPED')

    def test_unpaired_bitmaps_include_tiny_and_image_only_pages(self):
        p = page((20, 100, '1 Introduction'), (20, 150, 'FIGURE 1:'), (20, 159, 'next paragraph stays'),
                 images=[image(20, 110, 160, 36), image(310, 320, 2, 2)])
        self.freeze(p, page(images=[image(12, 14, 400, 600)]))
        result, _, _ = run_outline(self.root)
        data = outline_json(result)
        self.assertEqual(data['unpaired_bitmap_count'], 2)
        self.assertEqual([(b['page'], b['bbox']) for b in data['unpaired_bitmaps']],
                         [(1, [310, 320, 312, 322]), (2, [12, 14, 412, 614])])
        cap, = data['captions']
        self.assertTrue(cap['carved'])
        self.assertEqual(cap['object']['kind'], 'bitmap')
        units, review = draft_inventory(result)
        self.assertTrue(any('p2: 1 bitmap' in w for w in review))
        text = outline_text(result)
        for b in data['unpaired_bitmaps']:
            self.assertIn(f"p{b['page']} {b['element_id']} bbox=", text)
        self.packet['units'] = units
        self.save()
        self.assertEqual(self.read_words('S1'), '1 Introduction next paragraph stays'.split())

    def test_do_not_carve_body_between_caption_and_object(self):
        self.freeze(page((20, 50, '1 Introduction'), (20, 139, 'even short body text'), (20, 151, 'FIGURE 2:'),
                         images=[image(20, 90, 160, 45)]))
        result, _, _ = run_outline(self.root)
        cap, = outline_json(result)['captions']
        self.assertFalse(cap['carved'])
        units, _ = draft_inventory(result)
        self.assertNotIn('body', next(u for u in units if u['kind'] == 'FIGURE')['locators'][0])
        self.packet['units'] = units
        self.save()
        self.assertIn('even short body text FIGURE 2:', ' '.join(self.read_words('S1')))

    def test_two_columns_in_reading_order(self):
        pairs = [('left', 20), ('right', 280)]
        rows = [(x, 100 + 14*i, f'{label} paragraph number {i}') for i in range(10) for label, x in pairs]
        self.freeze(page(*rows))
        result, _, _ = run_outline(self.root)
        self.assertEqual(outline_json(result)['two_column_pages'], [1])
        self.packet['units'], _ = draft_inventory(result)
        self.save()
        expected = ' '.join(f'{side} paragraph number {i}' for side, _ in pairs for i in range(10))
        self.assertEqual(self.read_words('FRONT'), expected.split())

    def test_separate_source_drafts_have_disjoint_ids_and_local_hierarchies(self):
        (self.root/'supp.pdf').write_bytes((self.root/'source.pdf').read_bytes())
        self.packet['sources'].append(dict(self.packet['sources'][0], source_id='S1-extended', local_path='supp.pdf'))
        self.freeze(page((20, 20, 'Cover'), (20, 80, 'I. Introduction'), (20, 100, 'A. Methods'),
                         (20, 130, 'FIGURE 1:')))
        combined = set()
        for source in self.packet['sources']:
            sid = source['source_id']
            result, units, review = run_outline(self.root, sid, out=self.root/'tools'/(sid+'.json'))
            self.assertEqual((units, review), draft_inventory(result))
            ids = {u['unit_id'] for u in units}
            self.assertTrue(ids.isdisjoint(combined))
            combined.update(ids)
            for u in units:
                self.assertEqual(u['source_id'], sid)
                self.assertNotEqual(u['parent_id'], u['unit_id'])
                self.assertIn(u['parent_id'], ids | {None})
                self.assertTrue(set(u['children']) <= ids)
            self.assertIn(sid+'__F1', ids)
            self.assertIn(sid+'__SI-A', ids)

    def test_output_scope_no_overwrite_and_no_canonical_changes(self):
        self.freeze(page((20, 40, 'Body')))
        before = self.snapshot()
        for path in ('draft.json', '01_inventory.json', 'source_elements/new.json', '../evil.json',
                     'tools/../source_elements/evil.json', 'tools/new.txt', 'tools/.. /evil.json',
                     'tools/a:stream.json', 'tools/NUL.json', self.root.parent/'outside.json'):
            with self.subTest(path=path), self.assertRaises(ElementError):
                run_outline(self.root, out=path)
        self.assertEqual(self.snapshot(), before)
        rel = Path('tools/sub/draft.json')
        _, units, _ = run_outline(self.root, out=rel)
        self.assertEqual(json.loads((self.root/rel).read_text(encoding='utf-8')), units)
        with self.assertRaises(ElementError) as err:
            run_outline(self.root, out=self.root/rel)
        self.assertEqual(err.exception.code, 'DRAFT_EXISTS')
        after = self.snapshot()
        self.assertEqual(set(after)-set(before), {rel})
        self.assertEqual(before, {p: after[p] for p in before})

    def test_racing_writers_cannot_clobber_a_draft(self):
        self.freeze(page((20, 40, 'Body')))
        barrier = Barrier(2)
        def write():
            barrier.wait(timeout=10)
            try:
                return run_outline(self.root, out='tools/only-once.json')[1]
            except ElementError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: write(), range(2)))
        self.assertEqual(outcomes.count('DRAFT_EXISTS'), 1, outcomes)
        self.assertIn(json.loads((self.root/'tools/only-once.json').read_text(encoding='utf-8')), outcomes)

    def test_directory_link_to_frozen_artifacts_is_never_followed(self):
        self.freeze(page((20, 40, 'Body')))
        dest = self.root/'source_elements'
        link = self.root/'tools'
        if os.name == 'nt':
            import _winapi
            _winapi.CreateJunction(str(dest), str(link))  # does not require Windows symlink privilege
        else:
            link.symlink_to(dest, target_is_directory=True)
        with self.assertRaises(ElementError):
            run_outline(self.root, out='tools/leak.json')
        self.assertFalse((dest/'leak.json').exists())

    def test_existing_leaf_link_or_alias_never_overwrites_evidence(self):
        self.freeze(page((20, 40, 'Body')))
        canonical = self.root/'source_elements/manifest.json'
        before = canonical.read_bytes()
        tools = self.root/'tools'
        tools.mkdir()
        alias = tools/'alias.json'
        os.link(canonical, alias)
        with self.assertRaises(ElementError):
            run_outline(self.root, out=alias)
        self.assertEqual(canonical.read_bytes(), before)

    def test_dangling_leaf_symlink_is_not_followed(self):
        self.freeze(page((20, 40, 'Body')))
        target = self.root/'source_elements/never-created.json'
        alias = self.root/'tools/link.json'
        alias.parent.mkdir()
        try:
            alias.symlink_to(target)
        except OSError as exc:
            self.skipTest(f'Symlink creation unavailable: {exc}')
        with self.assertRaises(ElementError):
            run_outline(self.root, out=alias)
        self.assertFalse(target.exists())
        self.assertTrue(alias.is_symlink())

    def test_missing_or_changed_acquisition_never_publishes_a_draft(self):
        self.freeze(page((20, 40, 'Body')))
        with self.assertRaises(ElementError):
            run_outline(self.root, 'unknown', 'tools/foreign.json')
        (self.root/'source.pdf').write_bytes(b'changed')
        with self.assertRaises(ElementError) as err:
            run_outline(self.root, out='tools/changed.json')
        self.assertEqual(err.exception.code, 'ELEMENT_SOURCE_CHANGED')
        self.assertFalse((self.root/'tools').exists())


if __name__ == '__main__':
    unittest.main()
