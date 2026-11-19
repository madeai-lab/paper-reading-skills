"""A locator navigates frozen native evidence; it neither returns nor edits that evidence."""
from collections.abc import Sequence
import json
from pathlib import Path
import unittest

import reading_pdf_elements as elements
import test_reading_pdf_elements as native
import test_reading_run_control as runs


class TextPage:
    width, height = 500, 800
    bbox = (0, 0, width, height)
    # (left, top, text); words on each line use a fixed-width font.
    native_lines: Sequence[tuple[int, int, str]] = ()
    images: Sequence[dict] = ()
    chars = lines = rects = curves = ()

    def find_tables(self, **kwargs):
        return []

    def extract_text(self, **kwargs):
        return '\n'.join(text for _, _, text in self.native_lines)

    def extract_words(self, **kwargs):
        words = []
        for x, y, line in self.native_lines:
            for word in line.split():
                end = x + len(word) * 4
                words.append({'text': word, 'x0': x, 'x1': end, 'top': y, 'bottom': y + 8})
                x = end + 4
        return words


class LocatorTests(unittest.TestCase):
    # Borrow just the fixtures. Importing or subclassing their TestCase here would
    # make unittest discover the old tests a second time.
    root: Path
    packet: dict
    setUp = native.NativeElementTests.setUp
    save = native.NativeElementTests.save
    module = native.NativeElementTests.module
    extract = native.NativeElementTests.extract
    page = native.NativeElementTests.page
    cli = runs.ReadingRunControlTests.cli

    def locate(self, **kwargs):
        return elements.read_elements(self.root, [1], view='locator', **kwargs)

    def assert_compact(self, value):
        if isinstance(value, dict):
            self.assertFalse({'rows', 'cells', 'words', 'chars', 'path'} & value.keys(), value.keys())
            for child in value.values():
                self.assert_compact(child)
        elif isinstance(value, list):
            for child in value:
                self.assert_compact(child)

    def test_objects_point_to_native_records_without_returning_their_contents(self):
        class AmbiguousTable(native.FakeTable):
            def extract(self, **kwargs):
                return [['unique-cell-payload', None], ['A', '10'], ['B', '20']]

        class MixedPage(native.FakePage):
            curves = [{'x0': 10, 'top': 50, 'x1': 40, 'bottom': 70,
                       'path': [('m', (10, 50)), ('l', (40, 70))]}]

            def find_tables(self, **kwargs) -> list[native.FakeTable]:
                return [AmbiguousTable()]

        self.extract(native.FakeParser([MixedPage()]))
        saved = self.page()
        result = self.locate()
        self.assertEqual(result['view'], 'locator')
        self.assertEqual(result['source_id'], 'S1')
        self.assertEqual(result['source_ref'], self.packet['sources'][0]['local_path'])
        self.assertIs(result['reading_state_changed'], False)
        page, = result['pages']
        self.assertEqual(page['page'], 1)
        self.assertEqual(json.loads((self.root / page['page_ref']).read_bytes()), saved)
        self.assertEqual(page['bbox'], [0, 0, saved['width'], saved['height']])
        self.assertEqual(page['flags'], saved['flags'])
        self.assertEqual(page['caption_hints'], [])
        self.assertNotIn('native_text_preview', page)
        for kind, key in [('bitmap', 'images'), ('table', 'tables')]:
            obj, = [o for o in page['objects'] if o['kind'] == kind]
            record, = saved[key]
            self.assertEqual((obj['element_id'], obj['bbox']), (record['id'], record['bbox']))
            if kind == 'bitmap':
                self.assertEqual(obj['srcsize'], record['srcsize'])
            else:
                self.assertEqual(obj['row_count'], len(record['rows']))
                self.assertEqual(obj['flags'], record['flags'])
        self.assert_compact(result)
        self.assertNotIn('unique-cell-payload', json.dumps(result))
        self.assertNotIn('Native evidence', json.dumps(result))

    def test_bbox_separates_interior_text_from_adjacent_numbered_captions(self):
        class CaptionPage(TextPage):
            images = native.FakePage.images  # [140, 150, 170, 180]
            native_lines = [(140, 20, 'Table 99. Too far above'),
                            (140, 112, 'Figure notes'),  # no number
                            (124, 132, 'See Figure 7.'),  # 'See' lies outside the crop
                            (140, 153, 'ROI'),
                            (140, 182, 'Figure 2. Pulse'),
                            (140, 193, 'continuation of caption'),
                            (360, 182, 'Figure 8. Other column')]

        self.extract(native.FakeParser([CaptionPage()]))
        region = [138, 149, 225, 181]
        page, = self.locate(bbox=region)['pages']
        self.assert_compact(page)
        self.assertEqual(page['bbox'], region)
        self.assertEqual(page['native_text_preview'].strip(), 'ROI')
        self.assertIs(page['preview_shortened'], False)
        hint, = page['caption_hints']
        self.assertIn('Figure 2. Pulse', hint['text'])
        self.assertNotIn('continuation', hint['text'])
        self.assertNotIn('Other column', hint['text'])
        first = next(w for w in self.page()['words'] if w['text'] == 'Figure' and w['bbox'][:2] == [140, 182])
        self.assertEqual(hint['word_id'], first['id'])
        x0, y0, x1, y1 = hint['bbox']
        self.assertTrue(x0 <= first['bbox'][0] < x1 and y0 <= first['bbox'][1] < y1)
        for top, bottom in [(185, 189), (192, 200)]:  # caption intersects, then lies just above
            with self.subTest(top=top):
                hints = self.locate(bbox=[138, top, 225, bottom])['pages'][0]['caption_hints']
                self.assertIn(first['id'], [h['word_id'] for h in hints])

    def test_bbox_filters_objects_and_counts_zero_thickness_vector_lines(self):
        class VectorPage(native.FakePage):
            lines = [*native.FakePage.lines,
                     {'x0': 115, 'x1': 145, 'top': 20, 'bottom': 20},  # crosses left edge
                     {'x0': 143, 'x1': 143, 'top': 15, 'bottom': 30}]

        self.extract(native.FakeParser([VectorPage()]))
        page, = self.locate(bbox=[120, 10, 170, 45])['pages']
        counts = page['graphics_counts']
        self.assertEqual((counts['lines'], counts['rects'], counts['curves']), (2, 0, 0))
        self.assertTrue(page['objects'])
        for obj in page['objects']:
            self.assertEqual(obj['kind'], 'drawing_region')  # table, bitmap and their rules are outside
            x0, y0, x1, y1 = obj['bbox']
            self.assertTrue(x0 < 170 and x1 > 120 and y0 < 45 and y1 > 10)

    def test_captioned_horizontal_rules_suggest_regions_not_table_records(self):
        class RuledPage(native.FakePage):
            rects = curves = images = []
            lines = [{'x0': 10, 'x1': 160, 'top': y, 'bottom': y} for y in (12, 28, 56, 92, 105, 140)]

            def find_tables(self, **kwargs) -> list[native.FakeTable]:
                return []

            def extract_words(self, **kwargs):
                return [{'text': label, 'x0': 10, 'x1': 55, 'top': y, 'bottom': y + 7}
                        for label, y in [('Table 1.', 60), ('Table 2.', 146)]]

        self.extract(native.FakeParser([RuledPage()]))
        objects = self.locate()['pages'][0]['objects']
        self.assertEqual([o['bbox'] for o in objects], [[10, 12, 160, 56], [10, 92, 160, 140]])
        for o in objects:
            self.assertEqual((o['kind'], o['basis']), ('drawing_region', 'parallel_rules'))
            self.assertNotIn('element_id', o)
        # Inside the same grid, two rules without a caption aren't a new table.
        self.assertEqual(self.locate(bbox=[20, 0, 150, 30])['pages'][0]['objects'], [])

    def test_empty_and_bitmap_only_pages_do_not_invent_text_or_captions(self):
        blank, scan = TextPage(), TextPage()
        scan.images = native.FakePage.images
        self.packet['sources'][0]['page_count'] = 2
        self.save()
        self.extract(native.FakeParser([blank, scan]))
        pages = elements.read_elements(self.root, [1, 2], bbox=[0, 0, 200, 200], view='locator')['pages']
        first, second = pages
        self.assertEqual(first['objects'], [])
        bitmap, = second['objects']
        self.assertEqual(bitmap['kind'], 'bitmap')
        for page in pages:
            self.assertIn('NO_NATIVE_TEXT', page['flags'])
            self.assertEqual(page['caption_hints'], [])
            self.assertEqual(page['native_text_preview'], '')
            self.assertIs(page['preview_shortened'], False)

    def test_preview_reports_shortening_without_bypassing_max_chars(self):
        class DensePage(TextPage):
            native_lines = [(0, y, ' '.join(['native'] * 50)) for y in range(0, 800, 8)]
            width = 1500
            bbox = (0, 0, width, 800)

        self.extract(native.FakeParser([DensePage()]))
        region = list(DensePage.bbox)
        page, = self.locate(bbox=region)['pages']
        self.assertIs(page['preview_shortened'], True)
        self.assertIn('native', page['native_text_preview'])
        self.assertLess(len(page['native_text_preview']), len(DensePage().extract_text()))
        for limit in (0, 10, elements.MAX_READ_CHARS + 1):
            with self.subTest(limit=limit), self.assertRaises(elements.ElementError) as err:
                self.locate(bbox=region, max_chars=limit)
            self.assertEqual(err.exception.code, 'ELEMENT_READ_LIMIT')

    def test_pdf_hash_mismatch_blocks_locator_even_with_cached_pages(self):
        self.extract()
        source = self.root / 'source.pdf'
        source.write_bytes(source.read_bytes() + b'\nchanged')
        with self.assertRaises(elements.ElementError) as err:
            self.locate()
        self.assertEqual(err.exception.code, 'ELEMENT_SOURCE_CHANGED')

    def test_default_view_preserves_full_page_and_crop_detail_contracts(self):
        self.extract()
        saved = self.page()
        for bbox in (None, [10, 45, 115, 115]):
            with self.subTest(bbox=bbox):
                result = elements.read_elements(self.root, [1], bbox=bbox)
                self.assertEqual(result, elements.read_elements(self.root, [1], bbox=bbox, view='detail'))
                self.assertEqual(set(result), {'source_id', 'pages', 'ocr_used', 'truncated'})
                page, = result['pages']
                self.assertEqual(page['text'], saved['text'] if bbox is None else None)
                self.assertEqual(page['tables'][0]['rows'], saved['tables'][0]['rows'])
                if bbox is None:
                    self.assertEqual(page['images'], saved['images'])
                else:
                    self.assertIn('Item', [w['text'] for w in page['words']])
                    self.assertIn('chars', page)
                    self.assertEqual(page['images'], [])

    def test_cli_selects_requested_source_and_leaves_run_byte_identical(self):
        source = dict(self.packet['sources'][0], source_id='SUP', local_path='supplement.pdf')
        (self.root / source['local_path']).write_bytes((self.root / 'source.pdf').read_bytes())
        self.packet['sources'].append(source)
        self.packet['units'] = [{'unit_id': 'F1', 'read_state': 'UNREAD'}]
        self.save()
        (self.root / 'execution_state.json').write_text('{"status":"OPEN"}', encoding='utf8')
        mixed = native.FakePage()
        image, = mixed.images
        mixed.images = [dict(image, x0=0, x1=30, top=0, bottom=30), image]
        self.extract(native.FakeParser([mixed]))

        def snapshot():
            return {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

        before = snapshot()
        code, result = self.cli('read-elements', '--source-id', 'SUP', '--pages', '1', '--view', 'locator',
                                '--bbox', '135', '145', '175', '185')
        self.assertEqual(code, 0, result)
        self.assertEqual((result['view'], result['source_id'], result['source_ref']),
                         ('locator', 'SUP', source['local_path']))
        self.assertIs(result['reading_state_changed'], False)
        page, = result['pages']
        saved = json.loads((self.root / page['page_ref']).read_bytes())
        self.assertEqual(saved['source_id'], 'SUP')
        obj, = page['objects']
        self.assertEqual((obj['kind'], obj['element_id']), ('bitmap', saved['images'][1]['id']))
        self.assertEqual(snapshot(), before)


if __name__ == '__main__':
    unittest.main()
