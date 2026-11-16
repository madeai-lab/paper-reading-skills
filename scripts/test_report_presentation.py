"""Presentation regressions observed across the seven reading reports."""
import hashlib
import json
import unittest

from reading_report_quality import quality_errors
import test_reading_report_quality as legacy


class PresentationTests(unittest.TestCase):
    def setUp(self):
        helper = legacy.ReportQualityTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        self.h = helper
        self.h.packet['skill_revision'] = '2.9'
        self.roles = ['source_scope', 'summary', 'problem', 'approach',
                      'evidence', 'limitations', 'navigation']
        self.h.data['sections'] = [{'role': r, 'heading': '## ' + r} for r in self.roles]
        for key in ['full_notebook', 'material_index', 'user_review', 'independent_review']:
            ref = key + '.md'
            self.h.packet['deliverables'][key] = ref
            (self.h.root / ref).write_text('Existing evidence document.', encoding='utf-8')
        self.refresh()
        self.h.review['report_readability'].update(
            checked_section_roles=self.roles,
            presentation_assessment='Independently checked depth, target applicability and navigation.')

    def refresh(self, navigation=None):
        if navigation is None:
            navigation = '\n'.join(f'[{k}]({v})' for k, v in self.h.packet['deliverables'].items()
                                   if k not in {'report', 'report_readability'})
        text = '\n\n'.join(row['heading'] + '\n\n' + self.h.text
                           for row in self.h.data['sections']) + '\n\n' + navigation
        (self.h.root / 'report.md').write_text(text, encoding='utf-8')
        sha = hashlib.sha256((self.h.root / 'report.md').read_bytes()).hexdigest()
        self.h.data['report_sha256'] = sha
        self.h.review['report_readability']['report_sha256'] = sha

    def codes(self, review=True):
        return self.h.codes(self.h.review if review else None)

    def test_valid_general_report_needs_no_target_section(self):
        self.assertEqual(self.codes(), set())

    def test_29_cannot_reuse_28_without_sections(self):
        del self.h.data['sections']
        self.assertIn('REPORT_STRUCTURE_INVALID', self.codes())

    def test_target_requires_its_own_section_and_real_answer_link(self):
        self.h.packet['research_target'] = {'target_id': 'explicit-target'}
        self.assertIn('REPORT_STRUCTURE_INVALID', self.codes())
        self.h.data['sections'].insert(-1, {'role': 'target', 'heading': '## Target relevance'})
        self.h.packet['deliverables']['target_analysis'] = 'target_analysis.json'
        (self.h.root / 'target_analysis.json').write_text('{}', encoding='utf-8')
        self.refresh()
        self.h.review['report_readability']['checked_section_roles'] = [x['role'] for x in self.h.data['sections']]
        self.assertEqual(self.codes(), set())

    def test_filenames_in_code_are_not_navigation(self):
        self.refresh(navigation='`full_notebook.md material_index.md user_review.md independent_review.md`')
        self.assertIn('REPORT_NAVIGATION_INCOMPLETE', self.codes())

    def test_registered_path_must_match_real_file_and_link(self):
        self.h.packet['deliverables']['independent_review'] = 'wrong/independent_review.md'
        self.assertIn('REPORT_NAVIGATION_INCOMPLETE', self.codes())

    def test_first_review_may_link_planned_review_file(self):
        (self.h.root / 'independent_review.md').unlink()
        self.assertEqual(self.codes(review=False), set())
        self.assertIn('REPORT_NAVIGATION_INCOMPLETE', self.codes())

    def test_encoded_local_paths_and_fragments_resolve(self):
        (self.h.root / 'notes').mkdir()
        ref = 'notes/reading notes.md'
        (self.h.root / ref).write_text('Notes', encoding='utf-8')
        self.h.packet['deliverables']['full_notebook'] = ref
        self.refresh(navigation='[Notes](notes/reading%20notes.md#scope)\n'
                     '[Index](material_index.md) [Concerns](user_review.md) [Review](independent_review.md)')
        self.assertEqual(self.codes(), set())

    def test_broken_image_and_outside_run_are_rejected(self):
        self.refresh(navigation='![Missing](missing.png)\n[Outside](../outside.md)')
        self.assertIn('REPORT_LINK_INVALID', self.codes())

    def test_headings_and_links_inside_fences_cannot_satisfy_contract(self):
        report = self.h.root / 'report.md'
        report.write_text('```markdown\n' + report.read_text(encoding='utf-8') + '\n```', encoding='utf-8')
        self.assertIn('REPORT_STRUCTURE_INVALID', self.codes())
        self.assertIn('REPORT_NAVIGATION_INCOMPLETE', self.codes())

    def test_section_order_and_review_coverage_are_checked(self):
        self.h.data['sections'][0], self.h.data['sections'][1] = self.h.data['sections'][1], self.h.data['sections'][0]
        self.refresh()
        self.assertIn('REPORT_STRUCTURE_INVALID', self.codes())
        self.h.review['report_readability'].pop('presentation_assessment')
        self.assertIn('REPORT_PRESENTATION_REVIEW_INCOMPLETE', self.codes())

    def test_commented_links_and_absolute_file_urls_do_not_supply_navigation(self):
        self.refresh(navigation='<!-- [Notes](full_notebook.md) -->\n[File](file:///missing.md)')
        self.assertIn('REPORT_NAVIGATION_INCOMPLETE', self.codes())
        self.assertIn('REPORT_LINK_INVALID', self.codes())

    def test_navigation_must_be_in_final_navigation_section(self):
        text = (self.h.root / 'report.md').read_text(encoding='utf-8')
        links = text.split('## navigation', 1)[1].split(self.h.text, 1)[1]
        self.refresh(navigation='')
        report = self.h.root / 'report.md'
        report.write_text(links + report.read_text(encoding='utf-8'), encoding='utf-8')
        self.assertIn('REPORT_NAVIGATION_INCOMPLETE', self.codes())

    def test_flag_cannot_be_deleted_to_bypass_new_revision(self):
        self.h.packet['review_requirements'] = {}
        self.h.data['sections'] = []
        self.assertIn('REPORT_STRUCTURE_INVALID', self.codes())

    def test_28_is_not_migrated_by_new_template_fields(self):
        self.h.packet['skill_revision'] = '2.8'
        self.refresh(navigation='')
        self.h.data['sections'] = []
        self.assertEqual(self.codes(), set())


if __name__ == '__main__':
    unittest.main()
