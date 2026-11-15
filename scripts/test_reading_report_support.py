"""Exercise target binding and source-image report delivery with local fixtures."""
import copy
import unittest

import reading_run_control as control
import test_reading_run_control as fixtures


class ReadingReportSupportTests(unittest.TestCase):
    setUp = fixtures.ReadingRunControlTests.setUp
    save = fixtures.ReadingRunControlTests.save
    cli = fixtures.ReadingRunControlTests.cli
    write_payload = fixtures.ReadingRunControlTests.write_payload

    def target(self):
        return {"schema_version": 1, "target_id": "review", "revision": 1,
                "purpose": "Compare coordination mechanisms",
                "questions": [{"id": "Q1", "text": "Which mechanisms have controls?"}],
                "comparison_dimensions": ["coordination", "human_involvement"],
                "hypotheses_to_test": [], "output_preferences": {"language": "en"}}

    def test_target_changes_invalidate_approval_without_resetting_reading(self):
        before = copy.deepcopy(self.packet["units"])
        path = self.write_payload("target-input.json", self.target())
        code, result = self.cli("set-target", "--file", path)
        self.assertEqual(code, 0, result)
        packet = control.read(self.root/"paper_packet.json")
        self.assertEqual(packet["research_target"]["target_id"], "review")
        self.assertEqual(packet["units"], before)
        self.assertFalse(result["paper_accepted"])
        self.assertEqual(control.read(self.root/"task.json")["research_target"], self.target())
        self.assertEqual(packet["scope_revision"], self.packet["scope_revision"])

    def test_target_rejects_duplicate_question_ids_before_writing(self):
        target = self.target()
        target["questions"].append(target["questions"][0])
        before = (self.root/"paper_packet.json").read_bytes()
        code, result = self.cli("set-target", "--file", self.write_payload("bad.json", target))
        self.assertEqual(code, 1)
        self.assertEqual(result["error_code"], "INVALID_TARGET")
        self.assertEqual((self.root/"paper_packet.json").read_bytes(), before)

    def test_changed_target_needs_new_revision_and_null_clears_active_analysis(self):
        target = self.target()
        control.set_target(self.root, target)
        changed = copy.deepcopy(target)
        changed['purpose'] = 'Compare human oversight'
        with self.assertRaises(control.RunError):
            control.set_target(self.root, changed)
        changed['revision'] = 2
        control.set_target(self.root, changed)
        control.set_target(self.root, None)
        packet = control.read(self.root/'paper_packet.json')
        self.assertIsNone(packet['research_target'])
        self.assertNotIn('target_analysis', packet['deliverables'])
        with self.assertRaises(control.RunError):
            control.set_target(self.root, target)

    def test_readonly_checker_rejects_changed_target_snapshot(self):
        from reading_run_check import inspect_run
        self.packet['research_target'] = self.target()
        self.save()
        self.assertIn('REVIEW_CONTENT_STALE', {e['code'] for e in inspect_run(self.root)})

    def test_gallery_preserves_manual_report_and_packet_on_failure(self):
        import reading_report_assets as assets
        (self.root/'panel.png').write_bytes(b'fixture')
        unit = self.packet['units'][0]
        unit['visual_review'] = {'actually_viewed': True, 'artifact_refs': ['panel.png']}
        self.save()
        report = self.root/'report_visuals.md'
        report.write_text('# Report visual evidence\nManual work', encoding='utf8')
        before = (self.root/'paper_packet.json').read_bytes()
        record = {'visual_id': 'V1', 'kind': 'SOURCE_IMAGE', 'title': 'Panel',
                  'unit_refs': [unit['unit_id']], 'artifact_refs': ['panel.png'],
                  'caption': 'Caption', 'interpretation': 'Meaning', 'limitations': 'Limit', 'claim_refs': []}
        with self.assertRaises(control.RunError):
            assets.build_gallery(self.root, [record])
        self.assertEqual((self.root/'paper_packet.json').read_bytes(), before)
        self.assertIn('Manual work', report.read_text(encoding='utf8'))

    def test_gallery_regeneration_preserves_derived_visual_provenance(self):
        import reading_report_assets as assets
        (self.root/'panel.png').write_bytes(b'fixture')
        unit = self.packet['units'][0]
        unit['visual_review'] = {'actually_viewed': True, 'artifact_refs': ['panel.png']}
        derived = {'visual_id': 'D1', 'kind': 'DERIVED_CHART', 'evidence_refs': ['notes.md']}
        self.packet['report_visuals'] = [derived]
        self.save()
        record = {'visual_id': 'V1', 'kind': 'SOURCE_IMAGE', 'title': 'Panel',
                  'unit_refs': [unit['unit_id']], 'artifact_refs': ['panel.png'],
                  'caption': 'Caption', 'interpretation': 'Meaning', 'limitations': 'Limit', 'claim_refs': []}
        assets.build_gallery(self.root, [record])
        self.assertIn(derived, control.read(self.root/'paper_packet.json')['report_visuals'])

    def test_optional_displayed_asset_bytes_are_review_bound(self):
        image = self.root/"panel.png"
        image.write_bytes(b"original image fixture")
        self.packet["report_visuals"] = [{"visual_id": "V1", "artifact_refs": ["panel.png"]}]
        original = control.content_fingerprint(self.root, self.packet)
        image.write_bytes(b"changed image fixture")
        self.assertNotEqual(control.content_fingerprint(self.root, self.packet), original)

    def test_gallery_embeds_local_image_with_unit_location_and_limit(self):
        import reading_report_assets as assets
        (self.root/"panel.png").write_bytes(b"fixture")
        unit = self.packet["units"][0]
        unit["visual_review"] = {"actually_viewed": True, "artifact_refs": ["panel.png"]}
        self.save()
        manifest = [{"visual_id": "V1", "kind": "SOURCE_IMAGE", "title": "Mechanism",
                     "unit_refs": [unit["unit_id"]], "artifact_refs": ["panel.png"],
                     "caption": "Observed mechanism", "interpretation": "Supports a bounded claim",
                     "limitations": "No causal comparison", "claim_refs": []}]
        result = assets.build_gallery(self.root, manifest)
        output = (self.root/result["path"]).read_text(encoding="utf8")
        self.assertIn("![Mechanism](panel.png)", output)
        self.assertIn("No causal comparison", output)
        self.assertIn(unit["unit_id"], output)
        self.assertIn("Source locators", output)
        packet = control.read(self.root/"paper_packet.json")
        self.assertEqual(packet["report_visuals"], manifest)
        self.assertEqual(packet["deliverables"]["report_visuals"], result["path"])

    def test_inline_markdown_image_bytes_are_bound_even_without_manifest(self):
        (self.root/'inline panel.png').write_bytes(b'original')
        report = self.root/self.packet['deliverables']['report']
        report.write_text('![Panel](inline%20panel.png)', encoding='utf8')
        original = control.content_fingerprint(self.root, self.packet)
        (self.root/'inline panel.png').write_bytes(b'changed')
        self.assertNotEqual(control.content_fingerprint(self.root, self.packet), original)

    def test_init_target_and_missing_analysis_return_action(self):
        source = self.root/'new-source.pdf'
        source.write_bytes(b'%PDF-fixture')
        new = self.root/'new-run'
        control.initialize(new, source, 'owner', 'en', self.target())
        self.assertEqual(control.read(new/'task.json')['research_target'], self.target())
        self.cli('set-target', '--file', self.write_payload('target.json', self.target()))
        _, result = self.cli('next')
        self.assertEqual(result['next_action']['kind'], 'WRITE_TARGET_ANALYSIS')

    def test_gallery_rejects_unviewed_or_external_images(self):
        import reading_report_assets as assets
        for ref in ["https://example.org/panel.png", "../outside.png"]:
            manifest = [{"visual_id": "V1", "kind": "SOURCE_IMAGE", "title": "Panel",
                         "unit_refs": [self.packet["units"][0]["unit_id"]], "artifact_refs": [ref],
                         "caption": "Caption", "interpretation": "Meaning", "limitations": "Limit",
                         "claim_refs": []}]
            with self.assertRaises(control.RunError):
                assets.build_gallery(self.root, manifest)
        (self.root/"panel.png").write_bytes(b"fixture")
        manifest[0]["artifact_refs"] = ["panel.png"]
        self.packet["units"][0]["visual_review"] = {"actually_viewed": False}
        self.save()
        with self.assertRaises(control.RunError):
            assets.build_gallery(self.root, manifest)


if __name__ == "__main__":
    unittest.main()
