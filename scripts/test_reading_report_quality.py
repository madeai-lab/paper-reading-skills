"""Regression checks for report explanations, version binding and legacy isolation."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from reading_report_quality import DIMENSIONS, quality_errors, section_roles
import reading_run_control as control
import test_reading_run_control as fixtures


class ReportQualityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.text = "The optimiser changes curve coordinates; the encoder stays fixed."
        (self.root / "report.md").write_text(self.text, encoding="utf-8")
        (self.root / "display.md").write_text("Viewer unavailable: actual error and inspection scope.", encoding="utf-8")
        self.packet = {"skill_revision": "2.8", "units": [{"unit_id": "U1"}],
                       "experiments": [{"experiment_id": "E1"}],
                       "deliverables": {"report": "report.md", "report_readability": "report_readability.json"}}
        self.data = {"schema_version": 1, "template_only": False,
                     "report_sha256": hashlib.sha256((self.root / "report.md").read_bytes()).hexdigest(),
                     "checks": [{"dimension": d, "report_excerpt": self.text,
                                 "assessment": "Fixture only; real reports need source-specific judgments.",
                                 "unit_refs": ["U1"]} for d in sorted(DIMENSIONS)],
                     "experiments": [{"experiment_id": "E1", "report_excerpt": self.text,
                                      "assessment": "Fixture comparison located."}],
                     "display": {"status": "UNAVAILABLE", "evidence_refs": ["display.md"],
                                 "limitations": "No rendered layout claim."}}
        self.review = {"report_readability": {"decision": "PASS", "report_sha256": self.data["report_sha256"],
                       "checked_dimensions": sorted(DIMENSIONS), "checked_experiment_ids": ["E1"],
                       "assessment": "Independent reader reconstruction checked."}}
        self.save()

    def save(self):
        (self.root / "report_readability.json").write_text(json.dumps(self.data), encoding="utf-8")

    def codes(self, review=None):
        self.save()
        return {e["code"] for e in quality_errors(self.root, self.packet, review)}

    def test_complete_shape_does_not_claim_automated_semantics(self):
        self.assertEqual(self.codes(self.review), set())
        # Repeated text passes shape checks deliberately; actual usefulness is reviewed.

    def test_missing_quality_prevents_new_run_acceptance(self):
        del self.packet["deliverables"]["report_readability"]
        self.assertIn("REPORT_QUALITY_INVALID", self.codes())

    def test_legacy_does_not_migrate(self):
        for revision in ["2.2", "2.6", "2.7"]:
            self.assertEqual(quality_errors(self.root, {"skill_revision": revision}), [])

    def test_deleting_new_flag_does_not_bypass_revision(self):
        self.packet["review_requirements"] = {}
        self.data["checks"] = []
        self.assertIn("REPORT_QUALITY_INVALID", self.codes())

    def test_report_edit_invalidates_owner_and_reviewer_checks(self):
        (self.root / "report.md").write_text(self.text + " changed", encoding="utf-8")
        self.assertTrue({"REPORT_QUALITY_STALE", "REPORT_REVIEW_INCOMPLETE"} <= self.codes(self.review))

    def test_refreshing_owner_hash_cannot_refresh_reviewer_approval(self):
        (self.root / "report.md").write_text(self.text + " changed", encoding="utf-8")
        self.data["report_sha256"] = hashlib.sha256((self.root / "report.md").read_bytes()).hexdigest()
        self.assertEqual(self.codes(self.review), {"REPORT_REVIEW_INCOMPLETE"})

    def test_all_experiments_required_even_negative_results(self):
        self.packet["experiments"].append({"experiment_id": "E-negative"})
        self.assertIn("REPORT_EXPERIMENTS_INCOMPLETE", self.codes())
        self.assertIn("REPORT_REVIEW_INCOMPLETE", self.codes(self.review))

    def test_empty_experiment_set_adapts_to_theory(self):
        self.packet["experiments"] = []
        self.data["experiments"] = []
        self.review["report_readability"]["checked_experiment_ids"] = []
        self.assertEqual(self.codes(self.review), set())

    def test_machine_ids_do_not_replace_report_excerpt(self):
        self.data["checks"][0]["report_excerpt"] = "U1 see notebook"
        self.assertIn("REPORT_EXPLANATION_UNLOCATED", self.codes())

    def test_unknown_unit_and_duplicate_dimension_fail(self):
        self.data["checks"][0]["unit_refs"] = ["unknown"]
        self.assertIn("REPORT_QUALITY_INVALID", self.codes())
        self.data["checks"][0] = copy.deepcopy(self.data["checks"][1])
        self.assertIn("REPORT_QUALITY_INVALID", self.codes())

    def test_display_requires_evidence_even_if_unavailable(self):
        self.data["display"]["evidence_refs"] = []
        self.assertIn("REPORT_QUALITY_INVALID", self.codes())

    def test_reference_cannot_escape_run(self):
        self.packet["deliverables"]["report"] = "../report.md"
        self.assertIn("REPORT_QUALITY_INVALID", self.codes())

    def test_template_and_missing_reviewer_cannot_approve(self):
        self.data["template_only"] = True
        self.assertIn("REPORT_QUALITY_STALE", self.codes())
        self.data["template_only"] = False
        self.assertIn("REPORT_REVIEW_INCOMPLETE", self.codes({}))
        self.review["report_readability"]["decision"] = "NEEDS_REPAIR"
        self.assertIn("REPORT_REVIEW_INCOMPLETE", self.codes(self.review))


class ReportQualityIntegrationTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.ReadingRunControlTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.f = fixture
        self.f.packet.setdefault("review_requirements", {})["reader_explanation"] = True
        self.f.save()

    def test_preflight_and_next_block_before_review(self):
        result = control.preflight(self.f.root)
        self.assertFalse(result["ready_for_review"])
        self.assertIn("REPORT_QUALITY_INVALID", {e["code"] for e in result["errors"]})
        self.assertNotEqual(control.assess(self.f.root)["terminal_decision"], "ACCEPTED")

    def test_accepted_review_cannot_bypass_reader_check(self):
        with self.assertRaises(control.RunError):
            control.ingest_review(self.f.root, self.f.packet["reviews"][0])

    def test_quality_file_is_snapshot_bound_without_repair_sync(self):
        self.f.packet["deliverables"]["report_readability"] = "quality.json"
        path = self.f.root / "quality.json"
        path.write_text('{"assessment":"first"}', encoding="utf-8")
        first = control.content_fingerprint(self.f.root, self.f.packet)
        path.write_text('{"assessment":"second"}', encoding="utf-8")
        self.assertNotEqual(first, control.content_fingerprint(self.f.root, self.f.packet))

    def test_display_image_bytes_are_snapshot_bound(self):
        self.f.packet["deliverables"]["report_readability"] = "quality.json"
        control.write(self.f.root / "quality.json", {"display": {"evidence_refs": ["display.png"]}})
        path = self.f.root / "display.png"
        path.write_bytes(b"first screenshot fixture")
        first = control.content_fingerprint(self.f.root, self.f.packet)
        path.write_bytes(b"changed screenshot fixture")
        self.assertNotEqual(first, control.content_fingerprint(self.f.root, self.f.packet))

    def test_failed_review_still_ingests_for_repair(self):
        review = self.f.failed_review()
        control.ingest_review(self.f.root, review)
        self.assertEqual(control.read(self.f.root / "paper_packet.json")["reviews"][-1]["decision"], "REVISION_REQUIRED")

    def test_complete_new_contract_can_reach_acceptance(self):
        helper = ReportQualityTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        helper.root = self.f.root
        helper.data["report_sha256"] = hashlib.sha256((self.f.root / "report.md").read_bytes()).hexdigest()
        for row in helper.data["checks"]:
            row.update(report_excerpt="evidence fixture", unit_refs=["F1"])
        helper.data["experiments"] = []
        (self.f.root / "display.md").write_text("Actual viewer fixture.", encoding="utf-8")
        helper.save()
        self.f.packet["deliverables"]["report_readability"] = "report_readability.json"
        review = self.f.packet["reviews"][0]
        review["report_readability"] = dict(helper.review["report_readability"],
            report_sha256=helper.data["report_sha256"], checked_experiment_ids=[])
        review["reviewed_content_sha256"] = control.content_fingerprint(self.f.root, self.f.packet)
        self.f.save()
        self.assertEqual(control.assess(self.f.root)["terminal_decision"], "ACCEPTED")

    def test_new_initialization_preserves_both_modes(self):
        for mode in ["KEY_CLAIMS", "FULL_DOUBLE_READ"]:
            root = self.f.root / mode
            control.initialize(root, self.f.root / "source.pdf", "owner", "en", mode=mode)
            packet = control.read(root / "paper_packet.json")
            self.assertEqual(packet["skill_revision"], "2.10")
            self.assertEqual(packet["review_mode"], mode)
            self.assertTrue(packet["review_requirements"]["reader_explanation"])
            self.assertTrue(packet["review_requirements"]["report_presentation"])
            self.assertEqual(packet["deliverables"]["report_readability"], "report_readability.json")

    def test_presentation_extension_can_reach_acceptance_with_registered_paths(self):
        helper = ReportQualityTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        helper.root = self.f.root
        # Exercise presentation integration separately from native-acquisition
        # fixtures, which already test the revision-gated 2.7+ source contract.
        self.f.packet['review_requirements']['report_presentation'] = True
        roles = section_roles(self.f.packet)
        helper.data['sections'] = [{'role': role, 'heading': '## ' + role} for role in roles]
        text = '\n\n'.join(row['heading'] + '\n\nevidence fixture' for row in helper.data['sections'])
        text += '\n\n' + '\n'.join(f'[{key}]({ref})' for key, ref in self.f.packet['deliverables'].items()
                                     if key in {'full_notebook', 'material_index', 'user_review', 'independent_review'})
        (self.f.root / 'report.md').write_text(text, encoding='utf-8')
        helper.data['report_sha256'] = hashlib.sha256((self.f.root / 'report.md').read_bytes()).hexdigest()
        for row in helper.data['checks']:
            row.update(report_excerpt='evidence fixture', unit_refs=['F1'])
        helper.data['experiments'] = []
        (self.f.root / 'display.md').write_text('Actual viewer failure fixture.', encoding='utf-8')
        helper.save()
        self.f.packet['deliverables']['report_readability'] = 'report_readability.json'
        review = self.f.packet['reviews'][0]
        review['report_readability'] = dict(helper.review['report_readability'],
            report_sha256=helper.data['report_sha256'], checked_experiment_ids=[],
            checked_section_roles=roles, presentation_assessment='Independent fixture assessment.')
        review['reviewed_content_sha256'] = control.content_fingerprint(self.f.root, self.f.packet)
        self.f.save()
        result = control.assess(self.f.root)
        self.assertEqual(result['terminal_decision'], 'ACCEPTED', result)


if __name__ == "__main__":
    unittest.main()
