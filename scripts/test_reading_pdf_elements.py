"""Exercise native PDF acquisition without treating extraction as understanding."""
import copy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

import reading_run_control as control
from reading_run_check import inspect_run
import test_reading_run_control as fixtures


def minimal_pdf():
    """A genuine one-page PDF with native text, a ruled table and a raster image."""
    content = (b'BT /F1 12 Tf 20 180 Td (Native evidence) Tj ET\n'
               b'BT /F1 10 Tf 20 140 Td (Item) Tj 60 0 Td (Value) Tj ET\n'
               b'BT /F1 10 Tf 20 120 Td (A) Tj 60 0 Td (10) Tj ET\n'
               b'BT /F1 10 Tf 20 100 Td (B) Tj 60 0 Td (20) Tj ET\n'
               b'10 150 m 110 150 l 110 90 l 10 90 l h S\n'
               b'10 130 m 110 130 l S 10 110 m 110 110 l S\n'
               b'70 150 m 70 90 l S\nq 30 0 0 30 140 20 cm /Im1 Do Q\n')
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] '
               b'/Resources << /Font << /F1 4 0 R >> /XObject << /Im1 6 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               b'<< /Length ' + str(len(content)).encode() + b' >>\nstream\n' + content + b'endstream',
               b'<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceGray '
               b'/BitsPerComponent 8 /Length 1 >>\nstream\n\x80\nendstream']
    output = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(str(number).encode() + b' 0 obj\n' + obj + b'\nendobj\n')
    start = len(output)
    output.extend(f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        output.extend(f'{offset:010} 00000 n \n'.encode())
    output.extend(f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode())
    return bytes(output)


class FakeTable:
    bbox = (10, 50, 110, 110)
    cells = [(10, 50, 70, 70), (70, 50, 110, 70),
             (10, 70, 70, 90), (70, 70, 110, 90),
             (10, 90, 70, 110), (70, 90, 110, 110)]
    rows = [SimpleNamespace(cells=cells[:2]), SimpleNamespace(cells=cells[2:4]),
            SimpleNamespace(cells=cells[4:])]

    def extract(self, **kwargs):
        return [['Item', 'Value'], ['A', '10'], ['B', '20']]


class FakePage:
    width = height = 200
    bbox = (0, 0, 200, 200)
    page_number = 1
    chars = [{'text': 'N', 'x0': 20, 'x1': 27, 'top': 10, 'bottom': 22,
              'fontname': 'Helvetica', 'size': 12}]
    images = [{'x0': 140, 'x1': 170, 'top': 150, 'bottom': 180,
               'width': 30, 'height': 30, 'srcsize': (1, 1),
               'name': 'Im1', 'bits': 8, 'stream': object()}]
    lines = [{'x0': 10, 'x1': 110, 'top': 50, 'bottom': 50, 'linewidth': 1}]
    rects = [{'x0': 10, 'x1': 110, 'top': 50, 'bottom': 110, 'linewidth': 1}]
    curves = []

    def extract_text(self, **kwargs):
        return 'Native evidence\nItem Value\nA 10\nB 20'

    def extract_words(self, **kwargs):
        return [{'text': text, 'x0': x, 'x1': x + 30, 'top': y, 'bottom': y + 10}
                for text, x, y in [('Native', 20, 10), ('evidence', 60, 10),
                                   ('Item', 20, 50), ('Value', 80, 50),
                                   ('A', 20, 70), ('10', 80, 70),
                                   ('B', 20, 90), ('20', 80, 90)]]

    def find_tables(self, **kwargs):
        return [FakeTable()]

    def extract_tables(self, **kwargs):
        return [FakeTable().extract()]

    def crop(self, *args, **kwargs):
        return self


class FakePDF:
    def __init__(self, pages=None, encrypted=False):
        self.pages = pages or [FakePage()]
        self.is_encrypted = encrypted
        self.doc = SimpleNamespace(is_extractable=not encrypted,
                                   is_encrypted=encrypted, encryption=True if encrypted else None)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeParser:
    __version__ = 'fixture-parser'

    def __init__(self, pages=None, encrypted=False):
        self.pages = pages
        self.encrypted = encrypted

    def open(self, *args, **kwargs):
        return FakePDF(self.pages, self.encrypted)


class NativeElementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root/'source.pdf'
        source.write_bytes(minimal_pdf())
        self.packet = {'skill_revision': '2.7', 'sources': [{
            'source_id': 'S1', 'local_path': 'source.pdf',
            'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'page_count': 1, 'access_state': 'AVAILABLE', 'required_for_scope': True}],
            'units': [], 'content_acquisition': {'method': 'PDFPLUMBER_NATIVE',
                                               'manifest_ref': 'source_elements/manifest.json'}}
        self.save()

    def save(self):
        (self.root/'paper_packet.json').write_text(json.dumps(self.packet), encoding='utf8')
        (self.root/'01_sources.json').write_text(json.dumps(self.packet['sources']), encoding='utf8')

    def module(self, name):
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError:
            self.fail('Native acquisition implementation is not available: ' + name)

    def extract(self, parser=None):
        return self.module('reading_pdf_elements').extract_elements(self.root, parser=parser or FakeParser())

    def page(self):
        return json.loads((self.root/'source_elements/page-0001.json').read_text(encoding='utf8'))

    def manifest(self):
        return json.loads((self.root/'source_elements/manifest.json').read_text(encoding='utf8'))

    def errors(self):
        return self.module('reading_element_contracts').element_errors(self.root, self.packet)

    def test_native_extraction_preserves_text_geometry_tables_and_images(self):
        original = (self.root/'source.pdf').read_bytes()
        self.extract()
        page = self.page()
        self.assertIn('Native evidence', page['text'])
        self.assertTrue(page['words'])
        self.assertTrue(page['tables'])
        self.assertTrue(page['images'])
        self.assertTrue(page['lines'])
        self.assertEqual((self.root/'source.pdf').read_bytes(), original)
        self.assertEqual(self.errors(), [])

    def test_bitmap_labels_are_not_invented_as_native_words(self):
        self.extract()
        self.assertNotIn('shoe', json.dumps(self.page()))
        self.assertNotIn('dress', json.dumps(self.page()))
        self.assertIs(self.manifest()['ocr_used'], False)

    def test_manifest_binds_source_and_all_pages(self):
        self.extract()
        manifest = self.manifest()
        self.assertEqual(manifest['sources'][0]['sha256'], self.packet['sources'][0]['sha256'])
        self.assertEqual(manifest['sources'][0]['page_count'], 1)
        self.assertTrue(manifest['sources'][0]['pages'])

    def test_existing_element_output_is_never_overwritten(self):
        self.extract()
        before = (self.root/'source_elements/manifest.json').read_bytes()
        with self.assertRaises(Exception) as caught:
            self.extract()
        self.assertEqual(getattr(caught.exception, 'code', None), 'ELEMENTS_EXIST')
        self.assertEqual((self.root/'source_elements/manifest.json').read_bytes(), before)

    def test_missing_pdfplumber_has_actionable_error_and_no_install(self):
        with patch.dict(sys.modules, {'pdfplumber': None}):
            with self.assertRaises(Exception) as caught:
                self.module('reading_pdf_elements').extract_elements(self.root)
        self.assertEqual(getattr(caught.exception, 'code', None), 'PDFPLUMBER_UNAVAILABLE')
        self.assertFalse((self.root/'source_elements/manifest.json').exists())

    def test_partial_extraction_failure_cannot_leave_success_manifest(self):
        class BrokenPage(FakePage):
            def extract_words(self, **kwargs):
                raise ValueError('Broken page text objects')
        with self.assertRaises(Exception):
            self.extract(FakeParser([FakePage(), BrokenPage()]))
        self.assertFalse((self.root/'source_elements/manifest.json').exists())

    def test_encrypted_source_is_not_extracted(self):
        with self.assertRaises(Exception):
            self.extract(FakeParser(encrypted=True))
        self.assertFalse((self.root/'source_elements/manifest.json').exists())

    def test_missing_manifest_blocks_new_contract(self):
        self.assertTrue(self.errors())

    def test_missing_mode_keeps_legacy_contract_unchanged(self):
        self.packet['skill_revision'] = '2.6'
        del self.packet['content_acquisition']
        self.assertEqual(self.errors(), [])

    def test_new_revision_cannot_bypass_elements_by_deleting_contract(self):
        del self.packet['content_acquisition']
        self.assertTrue(self.errors())

    def test_unknown_acquisition_method_fails_closed(self):
        self.packet['content_acquisition']['method'] = 'GUESS_FROM_IMAGES'
        self.assertTrue(self.errors())

    def test_tampered_page_invalidates_extraction(self):
        self.extract()
        p = self.root/'source_elements/page-0001.json'
        page = self.page()
        page['text'] = 'Changed interpretation'
        p.write_text(json.dumps(page), encoding='utf8')
        self.assertTrue(self.errors())

    def test_deleted_page_invalidates_extraction(self):
        self.extract()
        (self.root/'source_elements/page-0001.json').unlink()
        self.assertTrue(self.errors())

    def test_changed_pdf_cannot_reuse_native_elements(self):
        self.extract()
        (self.root/'source.pdf').write_bytes(minimal_pdf() + b'\nchanged')
        self.assertTrue(self.errors())

    def test_read_only_requested_page_returns_native_data(self):
        self.extract()
        before = (self.root/'source_elements/manifest.json').read_bytes()
        result = self.module('reading_pdf_elements').read_elements(self.root, [1])
        self.assertIn('Native evidence', json.dumps(result))
        self.assertEqual((self.root/'source_elements/manifest.json').read_bytes(), before)

    def test_out_of_range_page_is_rejected(self):
        self.extract()
        for pages in [[0], [2], [-1]]:
            with self.subTest(pages=pages), self.assertRaises(Exception):
                self.module('reading_pdf_elements').read_elements(self.root, pages)

    def test_bbox_read_does_not_return_outside_labels(self):
        self.extract()
        result = self.module('reading_pdf_elements').read_elements(self.root, [1], bbox=[10, 45, 115, 115])
        text = json.dumps(result)
        self.assertIn('Item', text)
        self.assertNotIn('Native evidence', text)

    def test_invalid_read_limit_is_rejected(self):
        self.extract()
        with self.assertRaises(Exception) as caught:
            self.module('reading_pdf_elements').read_elements(self.root, [1], max_chars=0)
        self.assertEqual(getattr(caught.exception, 'code', None), 'ELEMENT_READ_LIMIT')

    def test_long_read_is_rejected_instead_of_silently_truncated(self):
        self.extract()
        with self.assertRaises(Exception) as caught:
            self.module('reading_pdf_elements').read_elements(self.root, [1], max_chars=5)
        self.assertEqual(getattr(caught.exception, 'code', None), 'ELEMENT_READ_LIMIT')

    def test_inverted_bbox_is_rejected(self):
        self.extract()
        with self.assertRaises(Exception):
            self.module('reading_pdf_elements').read_elements(self.root, [1], bbox=[115, 115, 10, 45])

    def test_element_ids_are_deterministic_across_fresh_runs(self):
        self.extract()
        first = self.page()
        with tempfile.TemporaryDirectory() as other:
            target = Path(other)
            (target/'source.pdf').write_bytes((self.root/'source.pdf').read_bytes())
            (target/'paper_packet.json').write_text(json.dumps(self.packet), encoding='utf8')
            (target/'01_sources.json').write_text(json.dumps(self.packet['sources']), encoding='utf8')
            self.module('reading_pdf_elements').extract_elements(target, parser=FakeParser())
            second = json.loads((target/'source_elements/page-0001.json').read_text(encoding='utf8'))
        self.assertEqual(first, second)

    @unittest.skipUnless(importlib.util.find_spec('pdfplumber'), 'pdfplumber not installed in this interpreter')
    def test_real_pdf_native_text_table_and_raster_without_ocr(self):
        self.module('reading_pdf_elements').extract_elements(self.root)
        page = self.page()
        self.assertIn('Native evidence', page['text'])
        self.assertTrue(page['images'])
        self.assertTrue(page['tables'])
        self.assertIs(self.manifest()['ocr_used'], False)
        self.assertEqual(self.errors(), [])


class NativeTableEvidenceTests(unittest.TestCase):
    setUp = NativeElementTests.setUp
    save = NativeElementTests.save
    module = NativeElementTests.module
    extract = NativeElementTests.extract

    def native_table(self):
        return {'unit_id': 'T1', 'source_id': 'S1', 'kind': 'TABLE',
                'locators': [{'physical_page': 1}],
                'visual_review': {'required': True, 'actually_viewed': False, 'artifact_refs': []},
                'content_reading': {'mode': 'NATIVE_ELEMENTS',
                                    'page_refs': ['source_elements/page-0001.json'],
                                    'element_ids': ['p0001-t001'], 'conflict_resolution_refs': []}}

    def ready(self, unit):
        return self.module('reading_element_contracts').native_table_ready(self.root, self.packet, unit)

    def test_native_table_can_be_read_without_false_pixel_flag(self):
        self.extract()
        self.assertTrue(self.ready(self.native_table()))

    def test_native_word_label_is_not_full_table_evidence(self):
        self.extract()
        unit = self.native_table()
        unit['content_reading']['element_ids'] = ['p0001-w001']
        self.assertFalse(self.ready(unit))

    def test_chart_cannot_use_text_only_table_route(self):
        self.extract()
        for kind in ['FIGURE', 'PANEL', 'OTHER_VISUAL']:
            unit = self.native_table()
            unit['kind'] = kind
            with self.subTest(kind=kind):
                self.assertFalse(self.ready(unit))

    def test_table_locator_must_match_element_page(self):
        self.extract()
        unit = self.native_table()
        unit['locators'] = [{'physical_page': 2}]
        self.assertFalse(self.ready(unit))

    def test_unresolved_conflict_cannot_be_declared_native_complete(self):
        self.extract()
        unit = self.native_table()
        unit['content_reading']['unresolved_conflicts'] = ['merged header ambiguous']
        self.assertFalse(self.ready(unit))

    def test_missing_table_cells_cannot_be_declared_native_complete(self):
        self.extract()
        unit = self.native_table()
        unit['content_reading']['element_ids'] = ['p0001-t999']
        self.assertFalse(self.ready(unit))

    def test_table_source_identity_must_match_native_page(self):
        self.extract()
        unit = self.native_table()
        unit['source_id'] = 'another-source'
        self.assertFalse(self.ready(unit))

    def test_raster_overlap_prevents_text_only_table_completion(self):
        class OverlapPage(FakePage):
            images = [{'x0': 10, 'x1': 110, 'top': 50, 'bottom': 110,
                       'width': 100, 'height': 60, 'srcsize': (20, 12), 'name': 'TableScan'}]
        self.extract(FakeParser([OverlapPage()]))
        self.assertFalse(self.ready(self.native_table()))

    def test_ambiguous_merged_table_header_requires_resolution(self):
        class MergedTable(FakeTable):
            def extract(self, **kwargs):
                return [['Merged header', None], ['A', '10'], ['B', '20']]
        class MergedPage(FakePage):
            def find_tables(self, **kwargs):
                return [MergedTable()]
        self.extract(FakeParser([MergedPage()]))
        self.assertFalse(self.ready(self.native_table()))

    def test_independent_native_table_check_cannot_inherit_owner_flags(self):
        self.extract()
        self.packet['units'] = [self.native_table()]
        review = {'checked_unit_ids': ['T1']}
        errors = self.module('reading_element_contracts').structured_review_errors(self.root, self.packet, review)
        self.assertIn('REVIEW_NATIVE_INCOMPLETE', {x['code'] for x in errors})

    def test_independent_native_table_check_requires_own_existing_evidence(self):
        self.extract()
        self.packet['units'] = [self.native_table()]
        review = {'checked_unit_ids': ['T1'], 'structured_inspection': {
            'unit_ids': ['T1'], 'evidence_refs': ['reviews/missing.md']}}
        helper = self.module('reading_element_contracts').structured_review_errors
        self.assertTrue(helper(self.root, self.packet, review))
        (self.root/'reviews').mkdir()
        (self.root/'reviews/table-check.md').write_text('Reviewer checked header and A=10, B=20.', encoding='utf8')
        review['structured_inspection']['evidence_refs'] = ['reviews/table-check.md']
        self.assertEqual(helper(self.root, self.packet, review), [])

    def test_reviewer_native_evidence_mutation_changes_review_fingerprint(self):
        from reading_review_contracts import visual_fingerprint
        (self.root/'reviews').mkdir()
        path = self.root/'reviews/table-check.md'
        path.write_text('Independent original table observation.', encoding='utf8')
        review = {'reviewer_session_id': 'independent-session', 'structured_inspection': {
            'unit_ids': ['T1'], 'evidence_refs': ['reviews/table-check.md']}}
        before = visual_fingerprint(self.root, review)
        path.write_text('Changed table observation.', encoding='utf8')
        self.assertNotEqual(visual_fingerprint(self.root, review), before)

    def test_multipage_table_cannot_claim_completion_from_one_page(self):
        self.packet['sources'][0]['page_count'] = 2
        self.save()
        self.extract(FakeParser([FakePage(), FakePage()]))
        unit = self.native_table()
        unit['locators'] = [{'physical_page': 1}, {'physical_page': 2}]
        self.assertFalse(self.ready(unit))


class NativeAcquisitionIntegrationTests(unittest.TestCase):
    save = fixtures.ReadingRunControlTests.save
    cli = fixtures.ReadingRunControlTests.cli
    write_payload = fixtures.ReadingRunControlTests.write_payload

    def setUp(self):
        fixtures.ReadingRunControlTests.setUp(self)

    def test_old_visual_reading_rule_is_not_implicitly_relaxed(self):
        self.packet['units'][0]['visual_review']['actually_viewed'] = False
        self.save()
        self.assertIn('VISUAL_NOT_VIEWED', {x['code'] for x in inspect_run(self.root)})

    def test_missing_new_extraction_blocks_preflight_without_auto_reading(self):
        self.packet.update({'skill_revision': '2.7', 'content_acquisition': {
            'method': 'PDFPLUMBER_NATIVE', 'manifest_ref': 'source_elements/manifest.json'}})
        self.save()
        before = (self.root/'paper_packet.json').read_bytes()
        result = control.preflight(self.root)
        self.assertFalse(result['ready_for_review'])
        self.assertEqual((self.root/'paper_packet.json').read_bytes(), before)

    def prepare_native_table(self):
        self.packet.update({'skill_revision': '2.7', 'content_acquisition': {
            'method': 'PDFPLUMBER_NATIVE', 'manifest_ref': 'source_elements/manifest.json'}})
        unit = self.packet['units'][0]
        unit.update({'kind': 'TABLE', 'content_reading': {
            'mode': 'NATIVE_ELEMENTS', 'page_refs': ['source_elements/page-0001.json'],
            'element_ids': ['p0001-t001'], 'conflict_resolution_refs': []}})
        unit['visual_review'] = {'required': True, 'actually_viewed': False, 'artifact_refs': []}
        self.inventory = copy.deepcopy(self.packet['units'])
        self.save()
        self.module('reading_pdf_elements').extract_elements(self.root, parser=FakeParser())
        control.render(self.root, self.packet)
        self.save()

    module = NativeElementTests.module

    def test_complete_native_table_owner_does_not_need_false_pixel_flag(self):
        self.prepare_native_table()
        result = control.preflight(self.root)
        self.assertTrue(result['ready_for_review'], result['errors'])
        self.assertFalse(self.packet['units'][0]['visual_review']['actually_viewed'])

    def test_native_extraction_does_not_promote_an_unread_owner_table(self):
        self.prepare_native_table()
        self.packet['units'][0]['read_state'] = 'READ'
        self.save()
        result = control.preflight(self.root)
        self.assertFalse(result['ready_for_review'])
        self.assertIn('UNIT_INCOMPLETE', {x['code'] for x in result['errors']})

    def test_viewed_figure_still_needs_native_acquisition_provenance(self):
        self.prepare_native_table()
        self.packet['units'][0].update({'kind': 'FIGURE',
                                       'visual_review': {'required': True, 'actually_viewed': True,
                                                         'artifact_refs': ['page.png']}})
        self.packet['units'][0].pop('content_reading')
        self.inventory = copy.deepcopy(self.packet['units'])
        control.render(self.root, self.packet)
        self.save()
        result = control.preflight(self.root)
        self.assertFalse(result['ready_for_review'])

    def test_native_artifact_changes_reopen_fingerprint_unit_and_claim(self):
        from reading_element_contracts import element_errors
        from reading_review_modes import review_baseline, review_delta
        self.prepare_native_table()
        self.packet['review_mode'] = 'KEY_CLAIMS'
        self.packet['reviews'][-1]['review_id'] = 'R-native-baseline'
        (self.root/'evidence').mkdir()
        note = self.root/'evidence/native-resolution.md'
        note.write_text('Original native table resolution evidence.', encoding='utf8')
        self.packet['units'][0]['content_reading']['conflict_resolution_refs'] = ['evidence/native-resolution.md']
        control.render(self.root, self.packet)
        self.save()
        (self.root/'reviews').mkdir()
        baseline = review_baseline(self.root, self.packet)
        (self.root/'reviews/R-native-baseline.baseline.json').write_text(json.dumps(baseline), encoding='utf8')
        page_path = self.root/'source_elements/page-0001.json'
        manifest_path = self.root/'source_elements/manifest.json'
        page_bytes, manifest_bytes, note_bytes = page_path.read_bytes(), manifest_path.read_bytes(), note.read_bytes()
        original_fingerprint = control.content_fingerprint(self.root, self.packet)
        for changed_artifact in ['native-page', 'conflict-resolution']:
            page_path.write_bytes(page_bytes)
            manifest_path.write_bytes(manifest_bytes)
            note.write_bytes(note_bytes)
            if changed_artifact == 'native-page':
                page = json.loads(page_bytes)
                page['tables'][0]['rows'][1][1] = '99'
                page_path.write_text(json.dumps(page), encoding='utf8')
                manifest = json.loads(manifest_bytes)
                manifest['sources'][0]['pages'][0]['sha256'] = hashlib.sha256(page_path.read_bytes()).hexdigest()
                manifest_path.write_text(json.dumps(manifest), encoding='utf8')
            else:
                note.write_text('Changed resolution now contradicts the retained observation.', encoding='utf8')
            with self.subTest(changed_artifact=changed_artifact):
                self.assertEqual(element_errors(self.root, self.packet), [])
                delta = review_delta(self.root, self.packet)
                checks = {'fingerprint_changed': control.content_fingerprint(self.root, self.packet) != original_fingerprint,
                          'unit_reopened': 'F1' in delta['changed_unit_ids'],
                          'claim_reopened': 'C1' in delta['changed_claim_ids']}
                self.assertTrue(all(checks.values()), checks)


if __name__ == '__main__':
    unittest.main()
