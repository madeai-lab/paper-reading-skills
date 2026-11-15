"""Bind reader-facing explanation checks to the inspected report, not word counts."""
import hashlib
import json
from pathlib import Path

DIMENSIONS = {"problem", "mechanism", "metrics", "experiments", "visuals", "limitations"}


def enabled(packet):
    try:
        revision = tuple(int(x) for x in packet.get("skill_revision", "0").split("."))
    except (ValueError, AttributeError):
        revision = (0,)
    return revision >= (2, 8) or packet.get("review_requirements", {}).get("reader_explanation") is True


def quality_errors(root, packet, review=None):
    if not enabled(packet):
        return []
    root = Path(root).resolve()
    errors = []

    def error(code, message):
        errors.append({"code": code, "item": "report_readability", "next_action": message})

    def local_file(ref):
        if not isinstance(ref, str) or not ref:
            raise ValueError("A local file reference is required.")
        path = (root / ref).resolve()
        path.relative_to(root)
        if not path.is_file():
            raise ValueError("Missing local file: " + ref)
        return path

    try:
        report = local_file(packet.get("deliverables", {}).get("report"))
        quality = local_file(packet.get("deliverables", {}).get("report_readability"))
        data = json.loads(quality.read_text(encoding="utf-8-sig"))
        text = report.read_text(encoding="utf-8-sig")
        sha = hashlib.sha256(report.read_bytes()).hexdigest()
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("Use the report-readability template schema_version 1.")
        if data.get("template_only") is not False or data.get("report_sha256") != sha:
            error("REPORT_QUALITY_STALE", "Complete the check against the final report bytes before review.")
        checks = data.get("checks")
        if (not isinstance(checks, list) or any(not isinstance(c, dict) for c in checks)
                or len(checks) != len(DIMENSIONS)
                or {c.get("dimension") for c in checks} != DIMENSIONS):
            raise ValueError("Explain all six reader questions once, adapting non-applicable dimensions with reasons.")
        units = {u["unit_id"] for u in packet.get("units", [])}
        for check in checks:
            refs = check.get("unit_refs")
            if (not isinstance(refs, list) or any(not isinstance(x, str) or x not in units for x in refs)):
                raise ValueError("Reader-question source unit references must resolve.")
        experiments = data.get("experiments")
        expected = {e["experiment_id"] for e in packet.get("experiments", [])}
        if (not isinstance(experiments, list) or any(not isinstance(e, dict) for e in experiments)
                or len(experiments) != len(expected)
                or {e.get("experiment_id") for e in experiments} != expected):
            error("REPORT_EXPERIMENTS_INCOMPLETE", "Locate a readable account for every recorded experiment, including negative results.")
            experiments = []
        for item in checks + experiments:
            excerpt = item.get("report_excerpt")
            if not isinstance(excerpt, str) or not excerpt.strip() or excerpt not in text:
                error("REPORT_EXPLANATION_UNLOCATED", "Supply an exact excerpt locating the explanation in the current report.")
            if not isinstance(item.get("assessment"), str) or not item["assessment"].strip():
                error("REPORT_EXPLANATION_UNASSESSED", "State what the reader can understand there, or why the dimension is not applicable.")
        display = data.get("display", {})
        if not isinstance(display, dict) or display.get("status") not in {"INSPECTED", "UNAVAILABLE"}:
            raise ValueError("Record actual display inspection or its demonstrated unavailability.")
        refs = display.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            raise ValueError("Save display inspection evidence or the failed-viewer evidence.")
        for ref in refs:
            local_file(ref)
        if not isinstance(display.get("limitations"), str) or not display["limitations"].strip():
            raise ValueError("Describe display scope and limitations, including any unverified layout.")
        if review is not None:
            checked = review.get("report_readability", {})
            if (not isinstance(checked, dict) or checked.get("decision") != "PASS"
                    or checked.get("report_sha256") != sha
                    or not isinstance(checked.get("assessment"), str) or not checked["assessment"].strip()
                    or not isinstance(checked.get("checked_dimensions"), list)
                    or set(checked["checked_dimensions"]) != DIMENSIONS
                    or not isinstance(checked.get("checked_experiment_ids"), list)
                    or set(checked["checked_experiment_ids"]) != expected):
                error("REPORT_REVIEW_INCOMPLETE", "The actual independent reviewer must assess every reader question and experiment against this report; repair unclear explanations.")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        error("REPORT_QUALITY_INVALID", str(exc))
    return errors
