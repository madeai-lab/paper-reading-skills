"""Bounded appendix reading: a target change must not authorize the rest of a shared page."""
import copy

import reading_corpus as store
import reading_promotion as promotion
from test_reading_pdf_elements import FakeParser
from test_reading_triage import Workspace, TARGET


class SectionScopeTests(Workspace):
    def setUp(self):
        super().setUp()
        self.pid = self.add()
        self.attach(self.pid)
        promotion.extract(self.ws, self.pid, parser=FakeParser())
        self.quote = 'Only read the appendix.'
        self.box = [20, 10, 50, 21]
        self.spec = {'source_sha256': self.record(self.pid)['full_text']['current_sha256'],
                     'regions': [{'physical_page': 1, 'bbox': self.box}]}
        store.set_scope(self.ws, self.pid, self.spec, self.quote)
        store.request_depth(self.ws, self.pid, 'L2', 'Read the appendix for the research question.')

    def test_target_change_preserves_exact_read_boundary(self):
        store.set_target(self.ws, {**TARGET, 'revision': 2, 'purpose': 'A new target needing main-text results'})
        status = store.status(self.ws, self.pid)
        self.assertEqual(status['reading_scope']['user_instruction'], self.quote)
        for pages, box in [([1], None), ([2], self.box), ([1, 2], self.box), ([1], [19, 10, 50, 21])]:
            self.expect('READING_SCOPE_LIMIT', promotion.read_pages, self.ws, self.pid, pages, bbox=box)
        for view in ['detail', 'locator']:
            self.expect('READING_SCOPE_LIMIT', promotion.read_pages, self.ws, self.pid, [1], view=view, bbox=self.box)
        self.expect('READING_SCOPE_LIMIT', promotion.find_text, self.ws, self.pid, ['secret'])
        self.expect('READING_SCOPE_LIMIT', promotion.outline, self.ws, self.pid)
        self.expect('READING_SCOPE_LIMIT', promotion.crop, self.ws, self.pid, 1, [19, 10, 50, 21], 'outside.png')
        text = promotion.read_pages(self.ws, self.pid, [1], bbox=self.box)
        self.assertIn('Native', text)
        self.assertNotIn('evidence', text)
        # A word straddling the requested boundary is not returned just because its centre fits.
        self.assertNotIn('Native', promotion.read_pages(self.ws, self.pid, [1], bbox=[21, 10, 50, 21]))

    def test_pass_preview_and_submission_require_bounded_evidence(self):
        payload = self.l2(self.pid)
        before = self.record(self.pid)
        for item in payload['examined']:
            item['locator']['bbox'] = self.box
        for invalid in [{'section': 'Appendix'}, {'physical_page': 1}, {'physical_page': 2, 'bbox': self.box},
                        {'physical_page': 1, 'bbox': [20, 10, 50, 22]}]:
            draft = copy.deepcopy(payload)
            draft['examined'][0]['locator'] = invalid
            self.expect('READING_SCOPE_LIMIT', store.recommend, self.ws, self.pid, draft)
            self.expect('READING_SCOPE_LIMIT', store.submit, self.ws, draft, True)
            self.expect('READING_SCOPE_LIMIT', store.submit, self.ws, draft)
        draft = copy.deepcopy(payload)
        draft['examined'][0]['artifact_refs'] = ['screening.json']
        self.expect('READING_SCOPE_LIMIT', store.submit, self.ws, draft)
        self.assertEqual(self.record(self.pid), before)
        store.submit(self.ws, payload)
        self.assertEqual(self.record(self.pid)['passes'][-1]['examined'][0]['locator']['bbox'], self.box)

    def test_version_and_depth_changes_do_not_widen_scope(self):
        store.request_depth(self.ws, self.pid, 'L3', 'Recommend full reading.')
        self.expect('READING_SCOPE_LIMIT', promotion.promote, self.ws, self.pid, self.base/'run', 'reader')
        release = {'source_sha256': self.spec['source_sha256'], 'whole_paper': True}
        self.expect('INVALID_READING_SCOPE', store.set_scope, self.ws, self.pid, release, self.quote)
        self.attach(self.pid, b' revised')
        self.expect('READING_SCOPE_STALE', promotion.read_pages, self.ws, self.pid, [1], bbox=self.box)
        self.expect('INVALID_READING_SCOPE', store.set_scope, self.ws, self.pid, release, 'Read the entire new version.')
        release['source_sha256'] = self.record(self.pid)['full_text']['current_sha256']
        store.set_scope(self.ws, self.pid, release, 'Read the entire new version.')
        self.assertIsNone(store.status(self.ws, self.pid)['reading_scope'])
        self.assertEqual(self.record(self.pid)['reading_scope_history'][-1]['user_instruction'], self.quote)
