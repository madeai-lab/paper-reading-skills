"""Append newly acquired sources into an existing extraction without rewriting earlier evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import reading_element_contracts as contracts
import reading_pdf_elements as native
from reading_pdf_elements import ElementError
import reading_run_records as records
from test_reading_pdf_elements import FakePage, FakeParser, minimal_pdf


def tree(root):
    """Every file under source_elements/ with its bytes, to prove nothing earlier changed."""
    base = root/'source_elements'
    return {p.relative_to(base).as_posix(): p.read_bytes() for p in sorted(base.rglob('*')) if p.is_file()}


class SourceAppendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'source.pdf').write_bytes(minimal_pdf())
        self.packet = {'skill_revision': '2.10', 'units': [], 'sources': [self.pdf('S1', 'source.pdf')],
                       'content_acquisition': {'method': 'PDFPLUMBER_NATIVE',
                                               'manifest_ref': 'source_elements/manifest.json'}}
        self.save()

    def pdf(self, sid, name, payload=b''):
        path = self.root/name
        if not path.exists():
            path.write_bytes(minimal_pdf() + payload)
        return {'source_id': sid, 'source_kind': 'PDF', 'local_path': name, 'access_state': 'AVAILABLE',
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'page_count': None,
                'required_for_scope': True, 'supplement_of': None if sid == 'S1' else 'S1'}

    def save(self):
        (self.root/'paper_packet.json').write_text(json.dumps(self.packet), encoding='utf8')

    def register(self, sid, name):
        self.packet['sources'].append(self.pdf(sid, name, b'\n% ' + sid.encode()))
        self.save()

    def extract(self, append=False, parser=None):
        return native.extract_elements(self.root, parser=parser or FakeParser(), append=append)

    def manifest(self):
        return json.loads((self.root/'source_elements/manifest.json').read_text(encoding='utf8'))

    def errors(self):
        return contracts.element_errors(self.root, self.packet)

    def assert_code(self, code, call):
        with self.assertRaises(ElementError) as caught:
            call()
        self.assertEqual(caught.exception.code, code, str(caught.exception))
        return caught.exception

    def test_new_runs_record_schema_two_history_from_the_first_extraction(self):
        self.extract()
        manifest = self.manifest()
        self.assertEqual(manifest['schema_version'], 2)
        self.assertEqual(manifest['data_sources'], [])
        self.assertEqual(manifest['history'], [{
            'sequence': 1, 'operation': 'INITIAL', 'parser': manifest['parser'], 'source_ids': ['S1'],
            'data_source_ids': [], 'previous_manifest_ref': None, 'previous_manifest_sha256': None}])
        self.assertEqual(self.errors(), [])

    def test_rerunning_extraction_still_never_overwrites_and_names_the_append_route(self):
        self.extract()
        before = tree(self.root)
        error = self.assert_code('ELEMENTS_EXIST', self.extract)
        self.assertIn('--append', str(error))
        self.assertEqual(tree(self.root), before)

    def test_registered_supplement_is_reported_as_an_append_not_a_broken_run(self):
        self.extract()
        self.register('SUP', 'supplement.pdf')
        errors = self.errors()
        self.assertEqual([e['code'] for e in errors], ['ELEMENTS_APPEND_REQUIRED'])
        self.assertIn('SUP', errors[0]['next_action'])
        self.assert_code('ELEMENTS_APPEND_REQUIRED', lambda: native.read_elements(self.root, [1], source_id='S1'))

    def test_append_extracts_only_the_new_pdf_and_preserves_every_earlier_byte(self):
        self.extract()
        before, previous = tree(self.root), (self.root/'source_elements/manifest.json').read_bytes()
        self.register('SUP', 'supplement.pdf')
        opened = []

        class Recording(FakeParser):
            def open(self, path, *args, **kwargs):
                opened.append(Path(path).name)
                return super().open(path, *args, **kwargs)
        result = self.extract(append=True, parser=Recording())
        self.assertEqual(opened, ['supplement.pdf'])
        self.assertEqual((result['operation'], result['sequence'], result['appended_source_ids']), ('APPEND', 2, ['SUP']))
        after = tree(self.root)
        for name, data in before.items():
            if name != 'manifest.json':
                self.assertEqual(after[name], data, name)
        self.assertEqual(after['history/manifest-0001.json'], previous)
        manifest = self.manifest()
        self.assertEqual(manifest['sources'][0], json.loads(previous)['sources'][0])
        self.assertEqual(manifest['sources'][1]['pages'][0]['ref'], 'source_elements/append-0002/SUP-page-0001.json')
        self.assertEqual(manifest['history'][1], {
            'sequence': 2, 'operation': 'APPEND', 'parser': manifest['parser'], 'source_ids': ['SUP'],
            'data_source_ids': [], 'previous_manifest_ref': 'source_elements/history/manifest-0001.json',
            'previous_manifest_sha256': hashlib.sha256(previous).hexdigest()})
        self.assertEqual(self.errors(), [])
        self.assertEqual(native.read_elements(self.root, [1], source_id='SUP')['source_id'], 'SUP')

    def test_prior_checked_reading_stays_valid_without_readoption(self):
        self.extract()
        unit = {'unit_id': 'T1', 'source_id': 'S1', 'kind': 'TABLE', 'read_state': 'CHECKED',
                'locators': [{'physical_page': 1}],
                'content_reading': {'mode': 'NATIVE_ELEMENTS', 'page_refs': ['source_elements/page-0001.json'],
                                    'element_ids': ['p0001-t001'], 'conflict_resolution_refs': []}}
        self.packet['units'] = [unit]
        self.save()
        self.assertTrue(contracts.native_table_ready(self.root, self.packet, unit))
        self.register('SUP', 'supplement.pdf')
        self.extract(append=True)
        self.assertEqual(contracts.native_unit_errors(self.root, self.packet), [])
        self.assertTrue(contracts.native_table_ready(self.root, self.packet, unit))

    def test_append_invalidates_review_fingerprint(self):
        self.extract()
        (self.root/'01_inventory.json').write_text('[]', encoding='utf8')
        before = records.content_fingerprint(self.root, self.packet)
        self.register('SUP', 'supplement.pdf')
        self.extract(append=True)
        self.assertNotEqual(records.content_fingerprint(self.root, self.packet), before)

    def test_history_chains_across_several_appends(self):
        self.extract()
        for number, sid in enumerate(['SUP', 'SUP2'], 2):
            self.register(sid, sid.lower() + '.pdf')
            self.assertEqual(self.extract(append=True)['sequence'], number)
        manifest = self.manifest()
        self.assertEqual([h['source_ids'] for h in manifest['history']], [['S1'], ['SUP'], ['SUP2']])
        self.assertTrue((self.root/'source_elements/history/manifest-0002.json').is_file())
        self.assertEqual(self.errors(), [])

    def test_tampered_history_snapshot_fails_closed(self):
        self.extract()
        self.register('SUP', 'supplement.pdf')
        self.extract(append=True)
        snapshot = self.root/'source_elements/history/manifest-0001.json'
        snapshot.write_bytes(snapshot.read_bytes().replace(b'"S1"', b'"S9"'))
        self.assertEqual([e['code'] for e in self.errors()], ['ELEMENTS_INVALID'])

    def test_rewriting_an_earlier_page_and_its_manifest_hash_is_detected(self):
        self.extract()
        self.register('SUP', 'supplement.pdf')
        self.extract(append=True)
        page = self.root/'source_elements/page-0001.json'
        data = json.loads(page.read_text(encoding='utf8'))
        data['text'] = 'Rewritten after review'
        page.write_text(json.dumps(data), encoding='utf8')
        manifest = self.manifest()
        manifest['sources'][0]['pages'][0]['sha256'] = hashlib.sha256(page.read_bytes()).hexdigest()
        (self.root/'source_elements/manifest.json').write_text(json.dumps(manifest), encoding='utf8')
        errors = self.errors()
        self.assertEqual([e['code'] for e in errors], ['ELEMENTS_INVALID'])
        self.assertIn('earlier manifest evidence', errors[0]['next_action'])

    def test_append_is_not_offered_to_runs_before_2_10(self):
        self.packet['skill_revision'] = '2.9'
        self.save()
        self.extract()
        self.assertEqual(self.manifest()['schema_version'], 1)
        before = tree(self.root)
        self.register('SUP', 'supplement.pdf')
        self.assert_code('ELEMENTS_APPEND_UNSUPPORTED', lambda: self.extract(append=True))
        self.assertEqual(tree(self.root), before)
        self.assertEqual([e['code'] for e in self.errors()], ['ELEMENTS_INVALID'])

    def test_schema_cannot_be_swapped_to_evade_the_revision_contract(self):
        self.extract()
        self.packet['skill_revision'] = '2.9'
        self.assertEqual([e['code'] for e in self.errors()], ['ELEMENTS_INVALID'])

    def test_nothing_to_append_and_missing_first_extraction_are_explicit(self):
        self.assert_code('ELEMENTS_INVALID', lambda: self.extract(append=True))
        self.extract()
        self.assert_code('ELEMENTS_NOTHING_TO_APPEND', lambda: self.extract(append=True))

    def test_changed_bound_source_blocks_append_and_writes_nothing(self):
        self.extract()
        before = tree(self.root)
        (self.root/'source.pdf').write_bytes(minimal_pdf() + b'\nchanged')
        self.register('SUP', 'supplement.pdf')
        self.assert_code('ELEMENT_SOURCE_CHANGED', lambda: self.extract(append=True))
        self.assertEqual(tree(self.root), before)

    def test_failed_append_leaves_manifest_pages_and_history_untouched(self):
        self.extract()
        before = tree(self.root)
        self.register('SUP', 'supplement.pdf')

        class Broken(FakePage):
            def extract_words(self, **kwargs):
                raise ValueError('broken page')
        with self.assertRaises(ValueError):
            self.extract(append=True, parser=FakeParser([FakePage(), Broken()]))
        self.assertEqual(tree(self.root), before)
        self.assertEqual([p.name for p in self.root.iterdir() if p.name.startswith('.native-elements-')], [])

    def test_missing_pdfplumber_blocks_a_pdf_append_without_writing(self):
        self.extract()
        before = tree(self.root)
        self.register('SUP', 'supplement.pdf')
        with patch.dict(sys.modules, {'pdfplumber': None}):
            self.assert_code('PDFPLUMBER_UNAVAILABLE', lambda: native.extract_elements(self.root, append=True))
        self.assertEqual(tree(self.root), before)

    def test_interrupted_append_directory_is_neither_reused_nor_removed(self):
        self.extract()
        stray = self.root/'source_elements/append-0002'
        stray.mkdir()
        (stray/'SUP-page-0001.json').write_text('partial', encoding='utf8')
        self.register('SUP', 'supplement.pdf')
        self.extract(append=True)
        self.assertEqual((stray/'SUP-page-0001.json').read_text(encoding='utf8'), 'partial')
        self.assertEqual(self.manifest()['sources'][1]['pages'][0]['ref'],
                         'source_elements/append-0002-2/SUP-page-0001.json')
        self.assertEqual(self.errors(), [])

    def test_pending_append_cannot_overwrite_a_concurrent_publish(self):
        self.extract()
        before = tree(self.root)
        self.register('S2', 'late.pdf')
        (self.root/'.source-append.lock').mkdir()
        self.assert_code('ELEMENTS_APPEND_BUSY', lambda: self.extract(append=True))
        self.assertEqual(tree(self.root), before)

    def test_partial_snapshot_write_never_reaches_history_and_append_can_retry(self):
        self.extract()
        before = tree(self.root)
        self.register('S2', 'late.pdf')
        snapshot = self.root/'source_elements/history/manifest-0001.json'
        open_file = Path.open

        def open_with_fault(path, mode='r', *args, **kwargs):
            stream = open_file(path, mode, *args, **kwargs)
            if path.name == snapshot.name and mode == 'xb':
                write = stream.write

                def write_half(data):
                    self.assertEqual(data, before['manifest.json'])
                    count = write(data[:len(data)//2])
                    stream.flush()
                    self.assertFalse(snapshot.exists())  # No half-written public name, even mid-write.
                    if interrupted:
                        raise OSError('interrupted snapshot write')
                    return count

                stream.write = write_half
            return stream

        for interrupted in (True, False):
            with self.subTest(interrupted=interrupted):
                with patch.object(Path, 'open', open_with_fault):
                    if interrupted:
                        with self.assertRaisesRegex(OSError, 'interrupted snapshot write'):
                            self.extract(append=True)
                    else:
                        self.assert_code('ELEMENTS_INVALID', lambda: self.extract(append=True))
                self.assertEqual(tree(self.root), before)
                self.assertEqual([e['code'] for e in self.errors()], ['ELEMENTS_APPEND_REQUIRED'])

        self.assertEqual(self.extract(append=True)['sequence'], 2)
        self.assertEqual(snapshot.read_bytes(), before['manifest.json'])
        self.assertEqual(tree(self.root)['page-0001.json'], before['page-0001.json'])
        self.assertEqual(self.errors(), [])

    def test_snapshot_flush_to_disk_failure_publishes_nothing(self):
        self.extract()
        before = tree(self.root)
        self.register('S2', 'late.pdf')
        with patch.object(native.os, 'fsync', side_effect=OSError('snapshot sync failed')):
            with self.assertRaisesRegex(OSError, 'snapshot sync failed'):
                self.extract(append=True)
        self.assertEqual(tree(self.root), before)
        self.assertEqual(self.extract(append=True)['sequence'], 2)
        self.assertEqual(self.errors(), [])

    def test_snapshot_racing_publication_is_never_replaced(self):
        self.extract()
        before = tree(self.root)
        self.register('S2', 'late.pdf')
        operation = 'rename' if native.os.name == 'nt' else 'link'
        publish = getattr(native.os, operation)

        def race(staged, destination):
            if destination.name == 'manifest-0001.json':
                destination.write_bytes(b'conflicting history')
            return publish(staged, destination)

        with patch.object(native.os, operation, side_effect=race):
            self.assert_code('ELEMENTS_INVALID', lambda: self.extract(append=True))
        self.assertEqual(tree(self.root), {**before, 'history/manifest-0001.json': b'conflicting history'})

    def test_failed_publication_can_resume_without_overwriting_old_pages(self):
        self.extract()
        self.register('S2', 'late.pdf')
        before = tree(self.root)
        with patch.object(native.os, 'replace', side_effect=OSError('I/O error')), self.assertRaises(OSError):
            self.extract(append=True)
        after_failure = tree(self.root)
        for name, content in before.items():
            self.assertEqual(after_failure[name], content)
        self.assertEqual(after_failure['history/manifest-0001.json'], before['manifest.json'])
        self.assertEqual([e['code'] for e in self.errors()], ['ELEMENTS_APPEND_REQUIRED'])
        self.extract(append=True)
        self.assertEqual(self.errors(), [])
        self.assertEqual(tree(self.root)['history/manifest-0001.json'], before['manifest.json'])

    def test_duplicate_registered_ids_block_append_before_publication(self):
        self.extract()
        before = tree(self.root)
        self.register('s1', 'late.pdf')
        self.assert_code('ELEMENTS_INVALID', lambda: self.extract(append=True))
        self.assertEqual(tree(self.root), before)

    def test_legacy_partial_snapshot_requires_manual_inspection_and_is_never_overwritten(self):
        self.extract()
        history = self.root/'source_elements/history'
        history.mkdir()
        original = tree(self.root)['manifest.json']
        (history/'manifest-0001.json').write_bytes(original[:len(original)//2])
        before = tree(self.root)
        self.register('SUP', 'supplement.pdf')
        error = self.assert_code('ELEMENTS_INVALID', lambda: self.extract(append=True))
        self.assertIn('manifest-0001.json', str(error))
        self.assertIn('Manually quarantine', str(error))
        self.assertEqual(tree(self.root), before)


class MixedSourceWorkflowTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('pdfplumber'), 'requires already provisioned pdfplumber')
    def test_acquire_required_files_after_first_extraction_through_controller(self):
        script = Path(__file__).with_name('reading_run_control.py')
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)/'original.pdf'
            source.write_bytes(minimal_pdf())
            root = Path(temporary)/'run'

            def cli(command, *args):
                completed = subprocess.run([sys.executable, str(script), command, str(root), *args],
                                           capture_output=True, text=True, encoding='utf8')
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                return json.loads(completed.stdout)

            cli('init', '--source', str(source))
            catalog = root/'01_sources.json'
            sources = records.read(catalog)
            pdf = dict(sources[0], source_id='SI', supplement_of='SRC-01', local_path=None, sha256=None,
                       access_state='UNAVAILABLE', missing_reason='Not yet obtained.')
            sources.append(pdf)
            records.write(catalog, sources)
            cli('sync')
            cli('extract-elements')  # Read the paper; missing required SI still blocks acceptance.
            from reading_run_check import inspect_run
            self.assertIn('SOURCE_UNAVAILABLE', {e['code'] for e in inspect_run(root, require_review=False)})
            before = tree(root)

            (root/'si.pdf').write_bytes(minimal_pdf() + b'\n% supplemental material')
            pdf.update(local_path='si.pdf', sha256=records.digest(root/'si.pdf'), access_state='AVAILABLE', missing_reason=None)
            (root/'studies.csv').write_bytes(b'id,group\n42,case\n')
            records.write(root/'retrieval.json', {'url': 'https://example.org/studies.csv'})
            sources.append(dict(pdf, source_kind='DATA_FILE', source_id='S4', format='CSV', local_path='studies.csv',
                                sha256=records.digest(root/'studies.csv'), provenance={
                                    'origin': 'https://example.org/studies.csv', 'acquisition_ref': 'retrieval.json'}))
            records.write(catalog, sources)
            self.assertIn('ELEMENTS_APPEND_REQUIRED', {e['code'] for e in cli('sync')['next_action']['errors']})
            step = cli('extract-elements', '--append')
            self.assertEqual((step['appended_source_ids'], step['appended_data_source_ids']), (['SI'], ['S4']))
            self.assertEqual((root/step['previous_manifest_ref']).read_bytes(), before['manifest.json'])
            self.assertEqual(tree(root)['page-0001.json'], before['page-0001.json'])
            self.assertIn('Native evidence', cli('read-elements', '--source-id', 'SI', '--pages', '1')['pages'][0]['text'])
            self.assertEqual(cli('read-data', '--source-id', 'S4', '--rows', '2', '2', '--fields', 'group')['rows'],
                             [{'row': 2, 'values': ['case']}])


if __name__ == '__main__':
    unittest.main()
