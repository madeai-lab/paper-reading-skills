"""Lossless JSON number transport and read-only character windows on registered data."""
from decimal import Decimal
from inspect import Parameter, signature
import json
import unittest

import reading_data_sources as data
import reading_element_contracts as contracts
from test_reading_data_sources import DataRunFixture, SHEET, workbook


class DataValueTests(DataRunFixture):
    def setUp(self):
        self.make_run()

    def assertBudget(self, sid, locator, **kwargs):
        result = data.read_data(self.root, sid, locator, **kwargs)
        payload = data.data_json(result)
        self.assertTrue(payload.isascii())
        self.assertNotIn('\n', payload)
        budget = len(payload) + 1  # CLI's terminating LF
        self.assertEqual(data.read_data(self.root, sid, locator, budget, **kwargs), result)
        with self.assertRaises(data.DataError) as caught:
            data.read_data(self.root, sid, locator, budget - 1, **kwargs)
        self.assertEqual(caught.exception.code, 'DATA_READ_LIMIT')
        return result, payload

    def test_nested_numbers_round_trip_as_original_unquoted_tokens(self):
        fractional = ['1e400', '1e-400', '0.12345678901234567890123456789012345000', '-0.0E+03']
        tokens = fractional + ['-0', '987', '9' * 4800]
        text = '{"measurements":[' + ','.join(tokens) + '],"literal":"1e400"}'
        self.add('J', 'data.json', text, 'JSON')
        self.add('N', 'scalar.json', fractional[0], 'JSON')
        self.extract()
        result, payload = self.assertBudget('J', {'json_pointer': ''})
        self.assertIn('"value":' + text, payload)
        parsed = json.loads(payload, parse_float=Decimal, parse_int=Decimal)['value']
        self.assertEqual(parsed['measurements'], [Decimal(t) for t in tokens])
        self.assertEqual(parsed['literal'], '1e400')
        self.assertIs(type(result['value']['measurements'][-2]), int)
        self.assertNotIsInstance(result['value']['measurements'][0], str)
        self.assertEqual(data.read_data(self.root, 'N')['structure']['top_level'], 'number')
        _, payload = self.assertBudget('N', {'json_pointer': ''})
        self.assertIn('"value":1e400', payload)

    def test_oversized_line_can_be_read_without_gaps_or_cache_mutation(self):
        prefix = 'x' * 17000
        suffix = '中\U0001f680é' + 'z' * 3000
        value = prefix + suffix
        locator = {'lines': [2, 2], 'section': 'Methods'}
        for fmt in ('TXT', 'MD'):
            self.add(fmt, 'notes.' + fmt.lower(), 'one\r\n' + value + '\r\nprivate next line', fmt)
        self.extract()
        for fmt in ('TXT', 'MD'):
            with self.subTest(fmt=fmt):
                with self.assertRaisesRegex(data.DataError, '--chars') as caught:
                    data.read_data(self.root, fmt, locator)
                self.assertEqual(caught.exception.code, 'DATA_READ_LIMIT')
                left = data.read_data(self.root, fmt, locator, chars=[1, len(prefix)])
                right, wire = self.assertBudget(fmt, locator, chars=[len(prefix) + 1, len(value)])
                self.assertEqual(left['text'] + right['text'], value)
                self.assertEqual((right['chars'], right['total_chars'], right['partial']),
                                 ([len(prefix) + 1, len(value)], len(value), True))
                self.assertEqual((right['locator'], right['lines']), (locator, [2, 2]))
                self.assertFalse(right['reading_state_changed'])
                self.assertNotIn('private next line', wire)
                self.assertIn('\\ud83d\\ude80', wire)

    def test_csv_tsv_and_xlsx_window_preserves_cell_coordinates(self):
        for fmt, sep in [('CSV', ','), ('TSV', '\t')]:
            text = 'preamble\r\nid{0}body\r\nsecret{0}"p,\nq\U0001f680林end"\r\n'.format(sep)
            self.add(fmt, 'table.' + fmt.lower(), text, fmt)
        self.add('XLSX', 'table.xlsx', workbook(SHEET.replace('Lee 2021', 'p,\nq\U0001f680林end')), 'XLSX')
        self.extract()
        for fmt in ('CSV', 'TSV', 'XLSX'):
            with self.subTest(fmt=fmt):
                locator = {'rows': [3, 3], 'header_row': 2, 'fields': ['body']}
                if fmt == 'XLSX':
                    locator.update(sheet='Coding', header_row=1, fields=['study'])
                result, payload = self.assertBudget(fmt, locator, chars=[3, 6])
                self.assertEqual(result['locator'], locator)
                self.assertEqual(result['rows'], [{'row': 3, 'values': ['\nq\U0001f680林']}])
                self.assertEqual(result['header'], locator['fields'])
                self.assertEqual(result['header_row'], locator['header_row'])
                self.assertEqual(result['sheet'], locator.get('sheet'))
                self.assertEqual((result['chars'], result['total_chars'], result['partial']), ([3, 6], 9, True))
                self.assertNotIn('secret', payload)
                full = data.read_data(self.root, fmt, locator)
                self.assertEqual(full['rows'][0]['values'], ['p,\nq\U0001f680林end'])
                self.assertNotIn('chars', full)
                if fmt == 'XLSX':
                    self.assertIn('FORMULA_CACHED_VALUES', result['flags'])

    def test_implicit_sole_column_with_missing_or_ambiguous_header(self):
        value = '中' * data.MAX_READ_CHARS
        self.add('C', 'no-header.csv', value + '\r\n', 'CSV')
        self.add('T', 'duplicate.tsv', 'dup\tdup\r\n' + value, 'TSV')
        sheet = SHEET.replace('Lee 2021', value).replace('<c r="B3"><f>B2*2</f><v>999</v></c>', '')
        self.add('X', 'table.xlsx', workbook(sheet), 'XLSX')
        self.extract()
        for sid, n, loc, header in [('C', 1, {'header_row': None}, None), ('T', 2, {}, ['dup']),
                                    ('X', 3, {'sheet': 'Coding'}, ['study'])]:
            with self.subTest(sid=sid):
                locator = dict(loc, rows=[n, n])
                result, _ = self.assertBudget(sid, locator, chars=[42, 45])
                self.assertEqual((result['locator'], result['column'], result['header']), (locator, 1, header))
                self.assertEqual((result['rows'], result['total_chars']), ([{'row': n, 'values': ['中中中中']}], len(value)))
                # A second slice still sees the original, not a modified cached row.
                self.assertEqual(data.read_data(self.root, sid, locator, chars=[100, 101])['total_chars'], len(value))
        # Default header row 1 is also selectable. Never include its unsliced value as header metadata.
        header_cell, _ = self.assertBudget('C', {'rows': [1, 1]}, chars=[1, 1])
        self.assertEqual((header_cell['header_row'], header_cell['rows'][0]['values']), (1, ['中']))
        self.assertNotIn('header', header_cell)
        with self.assertRaisesRegex(data.DataError, 'occurs 2 times'):
            data.read_data(self.root, 'T', {'rows': [2, 2], 'fields': ['dup']}, chars=[1, 1])

    def test_json_window_uses_decoded_unicode_and_original_pointer(self):
        value = 'A\U0001f680é"\n\\Z'
        locator = {'json_pointer': '/a~1b~0c/0'}
        self.add('J', 'values.json', json.dumps({'a/b~c': [value, 'not selected']}), 'JSON')
        self.extract()
        result, wire = self.assertBudget('J', locator, chars=[2, 4])
        self.assertEqual(result['json_pointer'], locator['json_pointer'])
        self.assertEqual(result['locator'], locator)
        self.assertEqual(result['value'], '\U0001f680é')
        self.assertNotIn('not selected', wire)
        self.assertEqual((result['total_chars'], result['partial']), (8, True))
        whole = data.read_data(self.root, 'J', locator, chars=[1, len(value)])
        self.assertEqual(whole['value'], value)
        self.assertFalse(whole['partial'])

    def test_invalid_or_ambiguous_character_ranges_never_clip(self):
        self.add('T', 'note.txt', 'one\ntwo\n', 'TXT')
        self.add('C', 'cells.csv', 'x,y\na,b\nragged\n', 'CSV')
        self.add('J', 'values.json', '["",1e-400,true,{},null,3]', 'JSON')
        self.extract()
        for coords in ([], [1], [1, 2, 3], [0, 1], [3, 2], [1, 4], [-1, 1], [True, 2], [1, 2.0], '12'):
            with self.subTest(coords=coords), self.assertRaises(data.DataError) as caught:
                data.read_data(self.root, 'T', {'lines': [1, 1]}, chars=coords)
            self.assertEqual(caught.exception.code, 'DATA_LOCATOR_INVALID')
        cases = [('T', None), ('T', {'lines': [1, 2]}), ('C', {'rows': [2, 3], 'fields': ['x']}),
                 ('C', {'rows': [2, 2]}), ('C', {'rows': [2, 2], 'fields': ['x', 'y']}),
                 ('C', {'rows': [3, 3], 'fields': ['y']})]
        cases += [('J', {'json_pointer': ptr}) for ptr in ('', '/0', '/1', '/2', '/3', '/4', '/5')]
        for sid, locator in cases:
            with self.subTest(sid=sid, locator=locator), self.assertRaises(data.DataError) as caught:
                data.read_data(self.root, sid, locator, chars=[1, 1])
            self.assertEqual(caught.exception.code, 'DATA_LOCATOR_INVALID')
        self.assertIs(signature(data.read_data).parameters['chars'].kind, Parameter.KEYWORD_ONLY)

    def test_window_is_not_a_unit_locator_and_checks_full_source_and_provenance(self):
        source = self.add('C', 'cells.csv', 'x\nyes\nunread', 'CSV')
        locator = {'rows': [2, 2], 'fields': ['x']}
        self.extract()
        unit = self.unit('U', 'C', locators=[dict(locator, chars=[1, 1])])
        self.assertFalse(contracts.structured_ready(self.root, self.packet, unit))
        result = data.read_data(self.root, 'C', locator, chars=[1, 1])
        self.assertFalse(result['reading_state_changed'])
        for path in (self.root/source['local_path'], self.root/source['provenance']['acquisition_ref']):
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(original[:-1] + b'!')
                with self.assertRaises(data.DataError) as caught:
                    data.read_data(self.root, 'C', locator, chars=[1, 1])
                self.assertEqual(caught.exception.code, 'ELEMENT_SOURCE_CHANGED')
                path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
