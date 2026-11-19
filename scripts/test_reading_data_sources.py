"""Non-PDF data supplements: real provenance, hashes and file + row/field locators; nothing executed."""
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import reading_data_sources as data
import reading_element_contracts as contracts
import reading_pdf_elements as native
import reading_run_control as control
from reading_pdf_elements import ElementError
from reading_run_check import inspect_run
import reading_sections as sections
from test_reading_pdf_elements import FakeParser, minimal_pdf
import test_reading_run_check as run_fixtures

SCRIPT = Path(__file__).with_name('reading_run_control.py')
MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
CSV = 'title,year,coding\r\nSmith 2020,2020,"A, B"\r\nLee 2021,2021,C\r\n'


def workbook(sheet, doctype=False):
    """A minimal genuine XLSX package written with zipfile; no spreadsheet application involved."""
    prefix = '<?xml version="1.0"?>' + ('<!DOCTYPE worksheet [<!ENTITY x "boom">]>' if doctype else '')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as package:
        package.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        package.writestr('xl/workbook.xml', f'<workbook xmlns="{MAIN}" xmlns:r="http://schemas.openxmlformats.org/'
                         'officeDocument/2006/relationships"><sheets><sheet name="Coding" sheetId="1" r:id="rId1"/>'
                         '</sheets></workbook>')
        package.writestr('xl/_rels/workbook.xml.rels',
                         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                         '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
                         '</Relationships>')
        package.writestr('xl/sharedStrings.xml', f'<sst xmlns="{MAIN}"><si><t>study</t></si><si><t>score</t></si>'
                         '<si><r><t>Smith </t></r><r><t>2020</t></r></si></sst>')
        package.writestr('xl/worksheets/sheet1.xml', prefix + sheet)
    return buffer.getvalue()


SHEET = (f'<worksheet xmlns="{MAIN}"><sheetData>'
         '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
         '<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2"><v>4</v></c></row>'
         '<row r="3"><c r="A3" t="inlineStr"><is><t>Lee 2021</t></is></c><c r="B3"><f>B2*2</f><v>999</v></c></row>'
         '</sheetData><mergeCells count="1"><mergeCell ref="A5:B5"/></mergeCells></worksheet>')


class DataRunFixture(unittest.TestCase):
    def make_run(self, revision='2.10'):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'source.pdf').write_bytes(minimal_pdf())
        (self.root/'supplements').mkdir()
        (self.root/'supplements/acquisition.json').write_text(json.dumps(
            {'url': 'https://publisher.example/article/s001.zip', 'http_status': 200}), encoding='utf8')
        self.packet = {'skill_revision': revision, 'units': [], 'sources': [{
            'source_id': 'S1', 'source_kind': 'PDF', 'local_path': 'source.pdf', 'access_state': 'AVAILABLE',
            'sha256': hashlib.sha256(minimal_pdf()).hexdigest(), 'page_count': None, 'required_for_scope': True}],
            'content_acquisition': {'method': 'PDFPLUMBER_NATIVE', 'manifest_ref': 'source_elements/manifest.json'}}
        self.save()

    def save(self):
        (self.root/'paper_packet.json').write_text(json.dumps(self.packet), encoding='utf8')

    def add(self, sid, name, content, fmt, **extra):
        path = self.root/'supplements'/name
        path.write_bytes(content if isinstance(content, bytes) else content.encode('utf8'))
        source = {'source_id': sid, 'source_kind': 'DATA_FILE', 'format': fmt, 'local_path': 'supplements/'+name,
                  'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'page_count': None,
                  'access_state': 'AVAILABLE', 'required_for_scope': True, 'supplement_of': 'S1',
                  'missing_reason': None, 'provenance': {'origin': 'https://doi.org/10.0000/example.s001',
                                                         'acquisition_ref': 'supplements/acquisition.json'}}
        source.update(extra)
        self.packet['sources'].append(source)
        self.save()
        return source

    def extract(self, append=False, parser=None):
        return native.extract_elements(self.root, parser=parser or FakeParser(), append=append)

    def manifest(self):
        return json.loads((self.root/'source_elements/manifest.json').read_text(encoding='utf8'))

    def codes(self):
        return [e['code'] for e in contracts.element_errors(self.root, self.packet)]

    def unit(self, uid, sid, kind='TABLE', locators=None, mode='DATA_FILE'):
        unit = {'unit_id': uid, 'source_id': sid, 'kind': kind, 'label': uid, 'read_state': 'CHECKED',
                'locators': locators if locators is not None else [{'rows': [1, 3], 'fields': ['title', 'coding']}],
                'understanding_note': 'Per-study coding rows with their stated categories.',
                'evidence_refs': ['supplements/acquisition.json'],
                'visual_review': {'required': True, 'actually_viewed': False, 'artifact_refs': []}}
        if mode:
            unit['content_reading'] = {'mode': mode, 'conflict_resolution_refs': []}
        self.packet['units'].append(unit)
        self.save()
        return unit


class DataSourceTests(DataRunFixture):
    def setUp(self):
        self.make_run()

    def test_initial_extraction_binds_data_files_without_pdf_parsing(self):
        self.add('SUP-CSV', 'coding.csv', CSV, 'CSV')
        opened = []

        class Recording(FakeParser):
            def open(self, path, *args, **kwargs):
                opened.append(Path(path).name)
                return super().open(path, *args, **kwargs)
        result = self.extract(parser=Recording())
        self.assertEqual(opened, ['source.pdf'])
        self.assertEqual((result['data_source_count'], result['code_executed']), (1, False))
        entry = self.manifest()['data_sources'][0]
        self.assertEqual({k: entry[k] for k in ['source_id', 'format', 'sha256', 'container']},
                         {'source_id': 'SUP-CSV', 'format': 'CSV', 'container': None,
                          'sha256': self.packet['sources'][1]['sha256']})
        table = entry['structure']['tables'][0]
        self.assertEqual((table['row_count'], table['row_1_values']), (3, ['title', 'year', 'coding']))
        self.assertEqual(self.manifest()['history'][0]['data_source_ids'], ['SUP-CSV'])
        self.assertEqual(self.codes(), [])
        self.assertEqual(list((self.root/'source_elements').glob('*SUP-CSV*')), [])

    def test_data_only_append_needs_no_pdf_parser_and_runs_from_the_cli(self):
        self.extract()
        self.add('SUP-CSV', 'coding.csv', CSV, 'CSV')
        self.assertEqual(self.codes(), ['ELEMENTS_APPEND_REQUIRED'])
        with patch.dict(sys.modules, {'pdfplumber': None}):
            result = native.extract_elements(self.root, append=True)
        self.assertEqual((result['appended_source_ids'], result['appended_data_source_ids'], result['page_count']),
                         ([], ['SUP-CSV'], 0))
        self.assertIsNone(self.manifest()['history'][1]['parser'])
        self.assertEqual(self.codes(), [])
        self.add('SUP-MD', 'checklist.md', '# PRISMA\nItem 1\n', 'MD')
        completed = subprocess.run([sys.executable, str(SCRIPT), 'extract-elements', str(self.root), '--append'],
                                   capture_output=True, text=True, encoding='utf8')
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['appended_data_source_ids'], ['SUP-MD'])
        self.assertEqual(self.codes(), [])

    def test_csv_rows_and_fields_resolve_with_quoted_values(self):
        self.add('SUP-CSV', 'coding.csv', CSV, 'CSV')
        self.extract()
        result = data.read_data(self.root, 'SUP-CSV', {'rows': [2, 3], 'fields': ['title', 'coding']})
        self.assertEqual(result['header'], ['title', 'coding'])
        self.assertEqual(result['rows'], [{'row': 2, 'values': ['Smith 2020', 'A, B']},
                                          {'row': 3, 'values': ['Lee 2021', 'C']}])
        self.assertEqual((result['reading_state_changed'], result['code_executed']), (False, False))
        summary = data.read_data(self.root, 'SUP-CSV')
        self.assertEqual((summary['view'], summary['purpose']), ('structure', 'NAVIGATION_ONLY'))

    def test_bad_locators_are_rejected_not_clipped(self):
        self.add('SUP-CSV', 'coding.csv', CSV, 'CSV')
        self.extract()
        for locator in [{'rows': [2, 9]}, {'rows': [0, 2]}, {'rows': [3, 2]}, {'rows': [1, 2], 'fields': ['missing']},
                        {'rows': [1, 2], 'sheet': 'Sheet1'}, {'lines': [1, 2]}, {'physical_page': 1},
                        {'rows': [1, 2], 'header_row': None, 'fields': ['title']}]:
            with self.subTest(locator=locator), self.assertRaises(data.DataError) as caught:
                data.read_data(self.root, 'SUP-CSV', locator)
            self.assertEqual(caught.exception.code, 'DATA_LOCATOR_INVALID')
        with self.assertRaises(data.DataError) as caught:
            data.read_data(self.root, 'SUP-CSV', {'rows': [1, 3]}, max_chars=20)
        self.assertEqual(caught.exception.code, 'DATA_READ_LIMIT')

    def test_xlsx_reports_stored_values_and_never_evaluates_formulas(self):
        self.add('SUP-XLSX', 'coding.xlsx', workbook(SHEET), 'XLSX')
        self.extract()
        table = self.manifest()['data_sources'][0]['structure']['tables'][0]
        self.assertEqual((table['sheet'], table['row_1_values']), ('Coding', ['study', 'score']))
        self.assertEqual(table['flags'], ['FORMULA_CACHED_VALUES', 'MERGED_CELLS'])
        result = data.read_data(self.root, 'SUP-XLSX', {'sheet': 'Coding', 'rows': [2, 3], 'fields': ['score', 'study']})
        self.assertEqual(result['rows'], [{'row': 2, 'values': ['4', 'Smith 2020']},
                                          {'row': 3, 'values': ['999', 'Lee 2021']}])
        self.assertIn('FORMULA_CACHED_VALUES', result['flags'])
        with self.assertRaises(data.DataError):
            data.read_data(self.root, 'SUP-XLSX', {'rows': [1, 2]})

    def test_xml_declarations_are_recorded_as_a_conflict_not_parsed(self):
        self.add('SUP-XLSX', 'coding.xlsx', workbook(SHEET, doctype=True), 'XLSX')
        self.extract()
        structure = self.manifest()['data_sources'][0]['structure']
        self.assertEqual((structure['parse_state'], structure['conflict']), ('CONFLICT', 'XLSX_STRUCTURE_CONFLICT'))
        self.assertEqual(self.codes(), [])
        with self.assertRaises(data.DataError) as caught:
            data.read_data(self.root, 'SUP-XLSX', {'sheet': 'Coding', 'rows': [1, 2]})
        self.assertEqual(caught.exception.code, 'DATA_PARSE_CONFLICT')

    def test_json_pointer_markdown_lines_and_duplicate_keys(self):
        self.add('SUP-JSON', 'index.json', '{"studies": [{"id": "S1", "a/b": 1}], "n": 1}', 'JSON')
        self.add('SUP-MD', 'readme.md', '# Package\r\nline two\r\nline three\r\n', 'MD')
        self.add('SUP-DUP', 'dup.json', '{"k": 1, "k": 2}', 'JSON')
        self.extract()
        self.assertEqual(data.read_data(self.root, 'SUP-JSON', {'json_pointer': '/studies/0/a~1b'})['value'], 1)
        self.assertEqual(data.read_data(self.root, 'SUP-MD', {'lines': [2, 3]})['text'], 'line two\nline three')
        structures = {d['source_id']: d['structure'] for d in self.manifest()['data_sources']}
        self.assertEqual((structures['SUP-JSON']['top_level'], structures['SUP-JSON']['keys']), ('object', ['studies', 'n']))
        self.assertEqual(structures['SUP-MD']['line_count'], 3)
        self.assertEqual(structures['SUP-DUP']['conflict'], 'JSON_DUPLICATE_KEY')
        for locator in [{'json_pointer': '/studies/1'}, {'json_pointer': 'studies'}, {'json_pointer': '/studies/01'}]:
            with self.subTest(locator=locator), self.assertRaises(data.DataError):
                data.read_data(self.root, 'SUP-JSON', locator)

    def test_declared_encoding_is_bound_and_undeclared_bytes_are_a_conflict(self):
        content = 'name,place\r\nM\xfcller,K\xf6ln\r\n'.encode('cp1252')
        self.add('SUP-RAW', 'raw.csv', content, 'CSV')
        self.add('SUP-1252', 'declared.csv', content, 'CSV', encoding='cp1252')
        self.extract()
        structures = {d['source_id']: d['structure'] for d in self.manifest()['data_sources']}
        self.assertEqual(structures['SUP-RAW']['conflict'], 'TEXT_DECODING_CONFLICT')
        self.assertEqual(data.read_data(self.root, 'SUP-1252', {'rows': [2, 2]})['rows'][0]['values'], ['M\xfcller', 'K\xf6ln'])
        self.packet['sources'][2]['encoding'] = 'latin-1'
        self.save()
        self.assertEqual(self.codes(), ['ELEMENT_SOURCE_CHANGED'])

    def test_non_utf8_source_is_hashed_as_data_not_read_as_an_owner_note(self):
        import reading_repair_sync as repair_sync
        from reading_run_records import content_fingerprint
        self.packet['review_requirements'] = {'repair_dependency_sync': True}
        source = self.add('SUP-1252', 'declared.md', 'M\xfcller\n![](not-an-asset.png)'.encode('cp1252'), 'MD', encoding='cp1252')
        self.extract()
        (self.root/'notes.md').write_text('See SUP-1252 row 2.', encoding='utf8')
        documents = repair_sync.current_documents(self.root, self.packet)
        self.assertNotIn(source['local_path'], documents)
        self.assertIn('notes.md', documents)
        from reading_review_modes import artifact_manifest
        self.assertIn(source['local_path'], artifact_manifest(self.root, self.packet))
        before = content_fingerprint(self.root, self.packet)
        (self.root/source['local_path']).write_bytes(b'name\nOther\n')
        self.assertNotEqual(content_fingerprint(self.root, self.packet), before)

    def test_utf16_workbook_xml_is_reported_as_a_representation_conflict(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(workbook(SHEET))) as original, zipfile.ZipFile(buffer, 'w') as output:
            for info in original.infolist():
                output.writestr(info, SHEET.encode('utf-16') if info.filename.endswith('sheet1.xml') else original.read(info))
        self.add('SUP-XLSX', 'utf16.xlsx', buffer.getvalue(), 'XLSX')
        self.extract()
        structure = self.manifest()['data_sources'][0]['structure']
        self.assertEqual(structure['conflict'], 'XLSX_STRUCTURE_CONFLICT')
        self.assertIn('UTF-8', structure['detail'])

    def test_sheet_coordinates_and_expanded_width_fail_closed(self):
        for invalid in [SHEET.replace('r="B2"', 'r="A2"'), SHEET.replace('r="B2"', 'r="B3"')]:
            with self.subTest(invalid=invalid):
                self.make_run()
                self.add('S4', 'coding.xlsx', workbook(invalid), 'XLSX')
                self.extract()
                self.assertEqual(self.manifest()['data_sources'][0]['structure']['conflict'], 'XLSX_STRUCTURE_CONFLICT')
        self.make_run()
        self.add('S4', 'coding.xlsx', workbook(SHEET.replace('r="B2"', 'r="Z2"')), 'XLSX')
        with patch.object(data, 'MAX_CELLS', 20), self.assertRaises(ElementError) as caught:
            self.extract()
        self.assertEqual(caught.exception.code, 'DATA_LIMIT')
        self.assertFalse((self.root/'source_elements').exists())

    def test_receipt_is_immutable_and_separate_from_the_data(self):
        self.add('S4', 'coding.csv', CSV, 'CSV')
        self.extract()
        (self.root/'supplements/acquisition.json').write_text('Changed origin', encoding='utf8')
        self.assertEqual(self.codes(), ['ELEMENT_SOURCE_CHANGED'])

    def test_code_macros_and_unsupported_formats_are_never_data_sources(self):
        for name, fmt in [('rebuild_analysis.py', 'PY'), ('analysis.ipynb', 'JSON'), ('book.xlsm', 'XLSX'),
                          ('build.sh', 'TXT')]:
            with self.subTest(name=name):
                self.make_run()
                self.add('SUP-X', name, 'print("never run")\n', fmt)
                with self.assertRaises(ElementError) as caught:
                    self.extract()
                self.assertEqual(caught.exception.code, 'DATA_SOURCE_INVALID')
                self.assertFalse((self.root/'source_elements').exists())

    def test_provenance_and_supplement_relation_are_required(self):
        for change in [{'provenance': None}, {'provenance': {'origin': '', 'acquisition_ref': 'supplements/acquisition.json'}},
                       {'provenance': {'origin': 'https://doi.org/x', 'acquisition_ref': 'supplements/missing.json'}},
                       {'supplement_of': None}, {'sha256': 'ABC'}, {'page_count': 3}, {'local_path': '../outside.csv'}]:
            with self.subTest(change=change):
                self.make_run()
                self.add('SUP-CSV', 'coding.csv', CSV, 'CSV', **change)
                with self.assertRaises(ElementError) as caught:
                    self.extract()
                self.assertEqual(caught.exception.code, 'DATA_SOURCE_INVALID')

    def test_archive_member_provenance_is_verified_byte_for_byte(self):
        archive = self.root/'supplements/s001.zip'
        with zipfile.ZipFile(archive, 'w') as package:
            package.writestr('tables/coding.csv', CSV)
            package.writestr('rebuild_analysis.py', 'raise SystemExit("never run")')
        container = {'local_path': 'supplements/s001.zip', 'member': 'tables/coding.csv',
                     'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
        source = self.add('SUP-CSV', 'coding.csv', CSV, 'CSV')
        source['provenance']['container'] = container
        self.save()
        self.extract()
        self.assertEqual(self.manifest()['data_sources'][0]['container'], container)
        self.assertEqual(self.codes(), [])
        archive.write_bytes(archive.read_bytes() + b'\0')
        self.assertEqual(self.codes(), ['ELEMENT_SOURCE_CHANGED'])
        with self.assertRaises(ElementError) as caught:
            sections.section_coverage(self.root, 'S1')
        self.assertEqual(caught.exception.code, 'ELEMENT_SOURCE_CHANGED')
        self.make_run()
        source = self.add('SUP-CSV', 'coding.csv', CSV.replace('C', 'D'), 'CSV')
        archive = self.root/'supplements/s001.zip'
        with zipfile.ZipFile(archive, 'w') as package:
            package.writestr('tables/coding.csv', CSV)
        source['provenance']['container'] = dict(container, sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
        self.save()
        with self.assertRaises(ElementError) as caught:
            self.extract()
        self.assertEqual(caught.exception.code, 'DATA_SOURCE_INVALID')

    def test_changed_data_bytes_or_identity_fail_closed(self):
        self.add('SUP-CSV', 'coding.csv', CSV, 'CSV')
        self.extract()
        (self.root/'supplements/coding.csv').write_text(CSV + 'New 2022,2022,D\r\n', encoding='utf8')
        self.assertEqual(self.codes(), ['ELEMENT_SOURCE_CHANGED'])

    def test_data_files_are_refused_in_runs_before_2_10(self):
        self.make_run(revision='2.9')
        self.add('SUP-CSV', 'coding.csv', CSV, 'CSV')
        with self.assertRaises(ElementError):
            self.extract()
        self.packet['sources'].pop()
        self.save()
        self.extract()
        self.add('SUP-CSV', 'coding.csv', CSV, 'CSV')
        self.assertEqual(self.codes(), ['DATA_SOURCE_UNSUPPORTED'])

    def test_documented_example_record_is_a_valid_bindable_source(self):
        example = json.loads((Path(__file__).resolve().parent.parent/'shared/data-source.example.json')
                             .read_text(encoding='utf8'))
        member = example['provenance']['container']['member']
        archive = self.root/example['provenance']['container']['local_path']
        with zipfile.ZipFile(archive, 'w') as package:
            package.writestr(member, CSV)
        (self.root/example['local_path']).write_text(CSV, encoding='utf8', newline='')
        example.update(supplement_of='S1', sha256=hashlib.sha256((self.root/example['local_path']).read_bytes()).hexdigest())
        example['provenance']['container']['sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.packet['sources'].append(example)
        self.save()
        self.extract()
        self.assertEqual(self.codes(), [])
        self.assertEqual(data.read_data(self.root, example['source_id'], {'rows': [2, 2], 'fields': ['title']})['rows'],
                         [{'row': 2, 'values': ['Smith 2020']}])

    def test_pdf_readers_point_data_sources_to_read_data(self):
        self.add('SUP-CSV', 'coding.csv', CSV, 'CSV')
        self.extract()
        self.unit('S4', 'SUP-CSV', kind='APPENDIX')
        for call in [lambda: native.read_elements(self.root, [1], source_id='SUP-CSV'),
                     lambda: sections.section_coverage(self.root, 'SUP-CSV'),
                     lambda: sections.read_section(self.root, 'S4')]:
            with self.assertRaises(ElementError) as caught:
                call()
            self.assertIn('read-data', str(caught.exception))

    def test_read_data_cli_returns_compact_bounded_json(self):
        self.add('SUP-CSV', 'coding.csv', CSV, 'CSV')
        self.extract()
        completed = subprocess.run([sys.executable, str(SCRIPT), 'read-data', str(self.root), '--source-id', 'SUP-CSV',
                                    '--rows', '2', '2', '--fields', 'coding'],
                                   capture_output=True, text=True, encoding='utf8')
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertNotIn('\n', completed.stdout.strip())
        self.assertEqual(json.loads(completed.stdout)['rows'], [{'row': 2, 'values': ['A, B']}])
        misuse = subprocess.run([sys.executable, str(SCRIPT), 'read-elements', str(self.root), '--rows', '1', '2'],
                                capture_output=True, text=True, encoding='utf8')
        self.assertEqual(misuse.returncode, 2)


class DataUnitTests(DataRunFixture):
    def setUp(self):
        self.make_run()
        self.add('SUP-CSV', 'coding.csv', CSV, 'CSV')
        self.extract()

    def test_cached_formula_and_merged_cells_require_resolution_evidence(self):
        self.add('WORKBOOK', 'screening.xlsx', workbook(SHEET), 'XLSX')
        self.extract(append=True)
        unit = self.unit('SCREENING', 'WORKBOOK', locators=[{'sheet': 'Coding', 'rows': [2, 3]}])
        self.assertFalse(contracts.structured_ready(self.root, self.packet, unit))
        (self.root/'interpretation.md').write_text('Checked merged headers and compared the stored score with the source.', encoding='utf8')
        unit['content_reading']['conflict_resolution_refs'] = ['interpretation.md']
        self.assertTrue(contracts.structured_ready(self.root, self.packet, unit))

    def test_data_table_uses_structured_route_instead_of_fabricated_viewing(self):
        unit = self.unit('T-S4', 'SUP-CSV')
        self.assertTrue(contracts.structured_ready(self.root, self.packet, unit))
        self.assertFalse(contracts.native_table_ready(self.root, self.packet, unit))
        self.assertEqual(contracts.native_unit_errors(self.root, self.packet), [])
        self.assertFalse(unit['visual_review']['actually_viewed'])

    def test_data_units_need_their_own_reading_record_and_resolving_locators(self):
        cases = {'missing mode': dict(mode=None), 'pdf mode': dict(mode='NATIVE_ELEMENTS'),
                 'no locators': dict(locators=[]), 'bad field': dict(locators=[{'rows': [1, 2], 'fields': ['x']}]),
                 'page locator': dict(locators=[{'physical_page': 1}]), 'figure kind': dict(kind='FIGURE')}
        for name, change in cases.items():
            with self.subTest(name):
                self.packet['units'] = []
                unit = self.unit('T-S4', 'SUP-CSV', **change)
                self.assertFalse(contracts.structured_ready(self.root, self.packet, unit))
                self.assertEqual([e['code'] for e in contracts.native_unit_errors(self.root, self.packet)],
                                 ['UNIT_DATA_EVIDENCE_MISSING'])

    def test_reviewer_must_record_its_own_structured_inspection_of_data_tables(self):
        unit = self.unit('T-S4', 'SUP-CSV')
        review: dict = {'checked_unit_ids': ['T-S4']}
        codes = [e['code'] for e in contracts.structured_review_errors(self.root, self.packet, review)]
        self.assertEqual(codes, ['REVIEW_NATIVE_INCOMPLETE'])
        (self.root/'reviewer-s4.md').write_text('Reviewer compared rows 2-3 with the paper.', encoding='utf8')
        review['structured_inspection'] = {'unit_ids': ['T-S4'], 'evidence_refs': ['reviewer-s4.md']}
        self.assertEqual(contracts.structured_review_errors(self.root, self.packet, review), [])
        from reading_review_modes import required_visual_ids
        self.packet['review_mode'] = 'FULL_DOUBLE_READ'
        self.assertNotIn(unit['unit_id'], required_visual_ids(self.packet, review, self.root))


class DataRunCheckTests(unittest.TestCase):
    """The read-only checker accepts an AVAILABLE required data supplement truthfully."""
    def setUp(self):
        fixture = run_fixtures.ReadingRunCheckTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root, self.packet = fixture.root, copy.deepcopy(fixture.packet)
        self.packet.update({'skill_revision': '2.10', 'content_acquisition': {
            'method': 'PDFPLUMBER_NATIVE', 'manifest_ref': 'source_elements/manifest.json'}})
        self.packet['units'][0]['content_reading'] = {'mode': 'VISUAL', 'element_ids': ['p0001-text'],
                                                      'page_refs': ['source_elements/page-0001.json']}
        (self.root/'acquisition.json').write_text('{"url": "https://publisher.example/esm.csv"}', encoding='utf8')
        (self.root/'esm.csv').write_bytes(CSV.encode('utf8'))
        self.packet['sources'].append({
            'source_id': 'ESM1', 'source_kind': 'DATA_FILE', 'format': 'CSV', 'local_path': 'esm.csv',
            'sha256': hashlib.sha256((self.root/'esm.csv').read_bytes()).hexdigest(), 'page_count': None,
            'access_state': 'AVAILABLE', 'required_for_scope': True, 'supplement_of': 'S1',
            'provenance': {'origin': 'https://link.springer.com/esm/MOESM1_ESM.csv', 'acquisition_ref': 'acquisition.json'}})
        self.unit = {'unit_id': 'ESM1-T', 'source_id': 'ESM1', 'kind': 'TABLE', 'label': 'Corpus ledger',
                     'read_state': 'CHECKED', 'locators': [{'rows': [1, 3], 'object_label': 'ESM 1'}],
                     'understanding_note': 'Corpus ledger rows listing each included study and coding.',
                     'evidence_refs': ['notes.md'], 'content_reading': {'mode': 'DATA_FILE'},
                     'visual_review': {'required': True, 'actually_viewed': False, 'artifact_refs': []}}
        self.packet['units'].append(self.unit)
        self.inventory = copy.deepcopy(self.packet['units'])
        self.write()
        native.extract_elements(self.root, parser=FakeParser())

    def write(self):
        (self.root/'paper_packet.json').write_text(json.dumps(self.packet), encoding='utf8')
        (self.root/'01_inventory.json').write_text(json.dumps(self.inventory), encoding='utf8')

    def relevant(self):
        return {(e['code'], e['item']) for e in inspect_run(self.root, require_review=False)
                if e['item'] in {'ESM1', 'ESM1-T', 'content_acquisition'}
                or e['code'] in {'SOURCE_UNAVAILABLE', 'UNIT_NATIVE_EVIDENCE_MISSING'}}

    def test_required_available_data_supplement_passes_source_and_unit_checks(self):
        self.assertEqual(self.relevant(), set())

    def test_hash_only_does_not_complete_a_required_supplement(self):
        self.packet['units'].pop()
        self.inventory.pop()
        self.write()
        self.assertIn(('SOURCE_NOT_INVENTORIED', 'ESM1'), self.relevant())

    def test_missing_data_reading_record_is_reported_for_that_unit(self):
        del self.packet['units'][1]['content_reading']
        self.write()
        # Without its data reading record the table falls back to the ordinary pixel-viewing rule.
        self.assertEqual(self.relevant(), {('UNIT_DATA_EVIDENCE_MISSING', 'ESM1-T'), ('VISUAL_NOT_VIEWED', 'ESM1-T'),
                                           ('EVIDENCE_MISSING', 'ESM1-T')})

    def test_changed_data_supplement_is_a_source_change(self):
        (self.root/'esm.csv').write_text(CSV + 'x,1,y\r\n', encoding='utf8')
        self.assertIn(('SOURCE_CHANGED', 'ESM1'), self.relevant())
        self.assertIn(('ELEMENT_SOURCE_CHANGED', 'content_acquisition'), self.relevant())

    def test_assessment_routes_a_newly_registered_supplement_to_append(self):
        state = {'template_only': False, 'owner_id': 'owner', 'writer_ids': ['owner'], 'stage': '02',
                 'paper_status': 'IN_PROGRESS', 'scope_revision': 1, 'open_unit_ids': [], 'next_actions': [],
                 'blockers': [], 'stop_reason': None, 'restart_action': None, 'history': [], 'repair_progress': {}}
        (self.root/'execution_state.json').write_text(json.dumps(state), encoding='utf8')
        (self.root/'readme.md').write_text('# Replication package\n', encoding='utf8')
        self.packet['sources'].append(dict(self.packet['sources'][1], source_id='ESM2', format='MD',
                                           local_path='readme.md',
                                           sha256=hashlib.sha256((self.root/'readme.md').read_bytes()).hexdigest()))
        self.write()
        result = control.assess(self.root)
        self.assertEqual(result['next_action']['kind'], 'EXTRACT_ELEMENTS')
        self.assertEqual(result['next_action']['errors'][0]['code'], 'ELEMENTS_APPEND_REQUIRED')
        self.assertIn('--append', result['next_action']['instruction'])


if __name__ == '__main__':
    unittest.main()
