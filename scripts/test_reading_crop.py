"""Test no-clobber crop publication and compare real rendered pixels to frozen locators."""
import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import reading_crop as crops
from reading_element_locators import locator_page
from reading_pdf_elements import ElementError, extract_elements, sha
import test_reading_pdf_elements as native


BACKEND = all(importlib.util.find_spec(n) is not None for n in ('pdfplumber', 'pypdfium2', 'PIL'))


def colors_pdf(angle=0, media='0 0 120 80', crop='12 8 110 74', extra=''):
    # Non-square page, asymmetric inherited CropBox and two rectangles. The small
    # blue patch in the upper-left of the red mark distinguishes all four rotations.
    stream = b'1 0 0 rg 20 45 30 20 re f\n0 0 1 rg 20 55 8 10 re f\n'
    crop_attr = f'/CropBox [{crop}]' if crop else ''
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               f'<< /Type /Pages /Kids [3 0 R] /Count 1 /MediaBox [{media}] {crop_attr} /Rotate {angle} >>'.encode(),
               f'<< /Type /Page /Parent 2 0 R /Resources << >> /Contents 4 0 R {extra} >>'.encode(),
               b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'endstream']
    pdf = bytearray(b'%PDF-1.6\n'); offsets = []
    for n, obj in enumerate(objects, 1):
        offsets.append(len(pdf)); pdf.extend(f'{n} 0 obj\n'.encode()+obj+b'\nendobj\n')
    start = len(pdf)
    pdf.extend(b'xref\n0 5\n0000000000 65535 f \n')
    for offset in offsets:
        pdf.extend(f'{offset:010} 00000 n \n'.encode())
    pdf.extend(f'trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode())
    return bytes(pdf)


class RunFixture(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)/'run'
        self.root.mkdir()
        self.sources = []

    def source(self, data, filename='source.pdf', sid='S1', page_count=1):
        (self.root/filename).write_bytes(data)
        self.sources.append({'source_id': sid, 'access_state': 'AVAILABLE', 'page_count': page_count,
                             'local_path': filename, 'sha256': hashlib.sha256(data).hexdigest()})
        self.packet = {'sources': self.sources, 'units': [{'read_state': 'INVENTORIED'}],
                       'content_acquisition': {'method': 'PDFPLUMBER_NATIVE', 'manifest_ref': 'source_elements/manifest.json'}}
        (self.root/'paper_packet.json').write_text(json.dumps(self.packet), encoding='utf8')
        (self.root/'execution_state.json').write_text('{"stage":"01"}', encoding='utf8')

    def render(self, **args):
        return crops.render_crop(self.root, **dict({'source_id': 'S1', 'page_num': 1, 'bbox': [0, 0, 40, 40],
                                                    'out': 'evidence/crop.png'}, **args))

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): sha(p) for p in self.root.rglob('*') if p.is_file()}


class CropGuardTests(RunFixture):
    def setUp(self):
        super().setUp()
        self.source(native.minimal_pdf())
        extract_elements(self.root, parser=native.FakeParser())

    def test_invalid_pages_bboxes_scales_never_reach_renderer(self):
        before = self.snapshot()
        bad = [{'page_num': p} for p in (False, 0, 1.0, 2, '1')]
        bad.extend({'bbox': b} for b in ([], None, '0000', [0, 1, 2], [0, 1, 2, 3, 4],
                   [0, 0, 201, 200], [-1, 0, 1, 1], [3, 0, 3, 4], [0, 3, 3, 2],
                   [True, 0, 1, 1], ['0', 0, 2, 2], [0, 0, 10**400, 1],
                   [float('nan'), 0, 1, 1], [0, 0, float('inf'), 1]))
        bad.extend({'scale': s} for s in (True, '2', 0.1, 0, -1, 9, float('nan'), float('inf')))
        bad.extend({'source_id': s} for s in ('unknown', '', None))
        with patch.object(crops, '_render', side_effect=AssertionError('bad input reached renderer')):
            for args in bad:
                with self.subTest(args=args), self.assertRaises(ElementError) as caught:
                    self.render(**args)
                self.assertEqual(caught.exception.code, 'INVALID_ARGUMENT')
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root/'evidence').exists())

    def test_output_policy_and_exclusive_publication(self):
        dest = self.root/'reviews/existing.png'; dest.parent.mkdir(); dest.write_bytes(b'owned')
        before = self.snapshot()
        for out in ('tools/new.png', 'evidence/../outside.png', 'reviews/dir/../../outside.png',
                    'reviews/CON.png', 'evidence/out.txt:stream.png', 'reviews/out.png.',
                    'C:out.png', r'\\server\share\new.png', 'reviews/file.jpg', dest):
            with self.subTest(out=out), self.assertRaises(ElementError):
                self.render(out=out)
        with self.assertRaises(ElementError) as err:
            self.render(out='reviews/existing.png')
        self.assertEqual(err.exception.code, 'CROP_EXISTS')
        # Even if the name was absent during validation, commit must not replace any later writer.
        def competing_writer(*unused):
            (self.root/'reviews/race.png').write_bytes(b'won'); return b'lost', [1, 1]
        with patch.object(crops, '_render', side_effect=competing_writer), self.assertRaises(ElementError):
            self.render(out='reviews/race.png')
        self.assertEqual(self.snapshot(), dict(before, **{'reviews/race.png': hashlib.sha256(b'won').hexdigest()}))

    def test_directory_link_escape_and_dangling_leaf(self):
        outside = self.root.parent/'outside'; outside.mkdir()
        link = self.root/'evidence'
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            if sys.platform != 'win32':
                self.skipTest('cannot create directory symlink on this filesystem')
            # Windows non-admin accounts can create a junction without symlink privileges.
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)], check=True, capture_output=True)
        with self.assertRaises(ElementError):
            self.render(out='evidence/deeper/out.png')
        self.assertFalse(list(outside.iterdir()))
        (self.root/'reviews').mkdir(); leaf = self.root/'reviews/link.png'
        try:
            leaf.symlink_to(outside/'missing.png')
        except OSError:
            return  # junction escape was still exercised
        with self.assertRaises(ElementError):
            self.render(out='reviews/link.png')
        self.assertFalse((outside/'missing.png').exists())

    def test_tamper_at_validation_or_after_validation_is_rejected(self):
        path = self.root/'source.pdf'; orig = path.read_bytes(); path.write_bytes(orig+b'!')
        with self.assertRaises(ElementError) as err:
            self.render()
        self.assertEqual(err.exception.code, 'ELEMENT_SOURCE_CHANGED'); path.write_bytes(orig)
        validated = crops._native
        def swap_after_validation(*args):
            result = validated(*args); path.write_bytes(orig+b' changed'); return result
        with patch.object(crops, '_native', side_effect=swap_after_validation), self.assertRaises(ElementError) as err:
            self.render()
        self.assertEqual(err.exception.code, 'ELEMENT_SOURCE_CHANGED'); path.write_bytes(orig)
        (self.root/'source_elements/page-0001.json').write_bytes(b'{}')
        with self.assertRaises(ElementError) as err:
            self.render()
        self.assertEqual(err.exception.code, 'ELEMENTS_INVALID')
        self.assertFalse((self.root/'evidence').exists())

    def test_missing_backend_does_not_mutate_run(self):
        before = self.snapshot()
        with patch.dict(sys.modules, {'pypdfium2': None}), self.assertRaises(ElementError) as err:
            self.render()
        self.assertEqual(err.exception.code, 'CROP_RENDERER_UNAVAILABLE')
        self.assertEqual(before, self.snapshot())


@unittest.skipUnless(BACKEND, 'requires a provisioned pdfplumber/PDFium/Pillow interpreter')
class CropPixelTests(RunFixture):
    def test_locator_round_trip_all_rotations_inherited_crop_and_provenance(self):
        from PIL import Image
        cases = [(0, [20, 15, 50, 35], (4, 4)), (90, [45, 20, 65, 50], (-5, 4)),
                 (180, [70, 45, 100, 65], (-5, -5)), (270, [15, 70, 35, 100], (4, -5))]
        for angle, _, _ in cases:
            self.source(colors_pdf(angle), f'r{angle}.pdf', f'S{angle}')
        extract_elements(self.root)
        for idx, (angle, box, blue_xy) in enumerate(cases):
            with self.subTest(rotation=angle):
                sid = f'S{angle}'
                ref = 'source_elements/'+('' if idx == 0 else sid+'-')+'page-0001.json'
                page = json.loads((self.root/ref).read_text(encoding='utf8'))
                locator = locator_page(page, ref)['objects'][0]['bbox']
                self.assertEqual(locator, box)
                before = self.snapshot(); out = f'reviews/nested/r{angle}.png'
                result = self.render(source_id=sid, bbox=locator, out=out)
                self.assertEqual(result['source_id'], sid); self.assertEqual(result['physical_page'], 1)
                self.assertEqual(result['source_sha256'], sha(self.root/f'r{angle}.pdf'))
                self.assertEqual(result['bbox'], box); self.assertEqual(result['path'], out)
                self.assertEqual(result['page_ref'], ref); self.assertIs(result['reading_state_changed'], False)
                self.assertNotIn('actually_viewed', result); self.assertIs(result['ocr_used'], False)
                with Image.open(self.root/out) as image:
                    self.assertEqual(image.format, 'PNG')
                    self.assertEqual(image.size, ((box[2]-box[0])*2, (box[3]-box[1])*2))
                    self.assertEqual(list(image.size), result['pixel_size'])
                    x, y = blue_xy[0] % image.width, blue_xy[1] % image.height
                    self.assertEqual(image.getpixel((x, y))[:3], (0, 0, 255))
                    self.assertEqual(image.getpixel((image.width-1-x, image.height-1-y))[:3], (255, 0, 0))
                self.assertEqual(result['image_sha256'], sha(self.root/out))
                self.assertEqual(self.snapshot(), dict(before, **{out: result['image_sha256']}))

    def test_requested_physical_page_not_first_page(self):
        import pypdfium2 as pdfium
        from PIL import Image
        with pdfium.PdfDocument.new() as doc, BytesIO() as data:
            for contents in [native.minimal_pdf(), colors_pdf()]:
                with pdfium.PdfDocument(contents) as part:
                    doc.import_pages(part)
            doc.save(data)
            self.source(data.getvalue(), page_count=2)
        extract_elements(self.root)
        result = self.render(page_num=2, bbox=[22, 18, 24, 20])
        self.assertEqual(result['physical_page'], 2)
        self.assertEqual(result['page_ref'], 'source_elements/page-0002.json')
        with Image.open(self.root/result['path']) as image:
            self.assertEqual(image.getcolors(), [(16, (0, 0, 255))])

    def test_validly_hashed_but_incompatible_frozen_geometry_fails_closed(self):
        self.source(colors_pdf()); extract_elements(self.root)
        path = self.root/'source_elements/page-0001.json'
        page = json.loads(path.read_bytes()); page['width'] += 1
        path.write_text(json.dumps(page), encoding='utf8')
        manifest = self.root/'source_elements/manifest.json'
        metadata = json.loads(manifest.read_bytes()); metadata['sources'][0]['pages'][0]['sha256'] = sha(path)
        manifest.write_text(json.dumps(metadata), encoding='utf8')
        before = self.snapshot()
        with self.assertRaises(ElementError) as err:
            self.render(bbox=[20, 15, 50, 35])
        self.assertEqual(err.exception.code, 'CROP_GEOMETRY_UNSUPPORTED')
        self.assertEqual(self.snapshot(), before)

    def test_fractional_bbox_rounds_outward_without_full_page_allocation(self):
        from PIL import Image
        self.source(colors_pdf(crop=None)); extract_elements(self.root)
        with patch.object(crops, 'MAX_PIXELS', 4):
            result = self.render(bbox=[23.1, 18.1, 24.1, 19.1], scale=1)
        self.assertEqual(result['pixel_size'], [2, 2])
        with Image.open(self.root/result['path']) as image:
            self.assertEqual(image.getcolors(), [(4, (0, 0, 255))])

    def test_refuse_outside_visible_box_and_preallocation_limits(self):
        self.source(colors_pdf()); extract_elements(self.root)
        before = self.snapshot()
        with self.assertRaises(ElementError) as err:
            self.render(bbox=[11, 10, 25, 25])
        self.assertEqual(err.exception.code, 'CROP_GEOMETRY_UNSUPPORTED')
        import pypdfium2 as pdfium
        for name, limit in [('MAX_PIXELS', 200), ('MAX_SIDE', 50)]:
            with patch.object(crops, name, limit), patch.object(pdfium.PdfPage, 'render') as raster:
                with self.assertRaises(ElementError) as err:
                    self.render(bbox=[20, 15, 50, 35])
                self.assertEqual(err.exception.code, 'CROP_LIMIT'); raster.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_offset_origin_and_nonstandard_units_are_explicitly_unsupported(self):
        self.source(colors_pdf(media='10 10 130 90', crop=None))
        self.source(colors_pdf(extra='/UserUnit 2'), 'unit.pdf', 'unit')
        extract_elements(self.root)
        before = self.snapshot()
        for sid in ('S1', 'unit'):
            with self.subTest(sid=sid), self.assertRaises(ElementError) as err:
                self.render(source_id=sid, bbox=[20, 20, 30, 30])
            self.assertEqual(err.exception.code, 'CROP_GEOMETRY_UNSUPPORTED')
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
