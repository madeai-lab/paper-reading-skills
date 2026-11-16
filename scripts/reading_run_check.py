"""Read-only structural preflight for a paper-reading run; never judges understanding."""
import argparse
import hashlib
import json
from pathlib import Path
from reading_review_contracts import structure_errors, visual_review_errors
from reading_review_modes import coverage_errors
from reading_report_quality import quality_errors
from reading_element_contracts import element_errors, native_unit_errors, native_table_ready

VERIFIED = {"VERIFIED_FOR_SCOPE", "VERIFIED_WITH_USER_REVIEW"}


def inspect_run(root, require_review=True):
    root = Path(root).resolve()
    errors = []

    def error(code, item, action):
        errors.append({"code": code, "item": item, "next_action": action})

    def read_json(name):
        try:
            return json.loads((root / name).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            error("RECORD_UNREADABLE", name, str(exc))
            return None

    def evidence(ref, item):
        if not isinstance(ref, str) or not ref.strip():
            error("EVIDENCE_MISSING", item, "Record an existing local evidence path.")
            return
        target = (root / ref.split("#", 1)[0]).resolve()
        if not target.is_file() or not target.stat().st_size:
            error("EVIDENCE_MISSING", item, "Restore or correct evidence: " + ref)

    packet = read_json("paper_packet.json")
    inventory = read_json("01_inventory.json")
    if not isinstance(packet, dict) or not isinstance(inventory, list):
        error("RECORD_FORMAT", "run", "Use an object packet and an array inventory.")
        return errors
    if packet.get("template_only") is not False:
        error("TEMPLATE_NOT_EXECUTED", "packet", "Populate actual records; do not accept a template.")
    if not inventory or not packet.get("units"):
        error("EMPTY_INVENTORY", "units", "Inventory the source before claiming complete coverage.")
    units = packet.get("units", [])
    errors.extend(structure_errors(packet))
    errors.extend(element_errors(root, packet))
    errors.extend(native_unit_errors(root, packet))
    errors.extend(quality_errors(root, packet))
    ids = [u.get("unit_id") for u in units]
    if len(set(ids)) != len(ids) or None in ids:
        error("UNIT_ID_INVALID", "units", "Assign unique, non-null unit IDs.")
    baseline = {u.get("unit_id") for u in inventory}
    for missing in baseline - set(ids):
        error("INVENTORY_UNIT_MISSING", missing, "Restore the inventoried unit and complete it.")
    for added in set(ids) - baseline:
        error("INVENTORY_NOT_SYNCED", added, "Add discovered units to the inventory and revise scope.")
    source_hashes = {s.get("source_id"): s.get("sha256") for s in packet.get("sources", [])}
    source_ids = set(source_hashes)
    excluded = set()
    for entry in packet.get("scope_exclusions", []):
        uid = entry.get("unit_id")
        if (packet.get("scope_mode") != "USER_DEFINED_SCOPE" or uid not in ids
                or not entry.get("reason") or entry.get("scope_revision") != packet.get("scope_revision")):
            error("SCOPE_EXCLUSION_INVALID", uid, "Only an explicit user scope change permits a retained OUT_OF_SCOPE unit.")
        else:
            excluded.add(uid)
        evidence(entry.get("user_authorization_ref"), uid)
    for source in packet.get("sources", []):
        if source.get("required_for_scope") and source.get("access_state") != "AVAILABLE":
            error("SOURCE_UNAVAILABLE", source.get("source_id"), "Acquire the required material lawfully or retain a material block.")
        if source.get("local_path"):
            path = (root / source["local_path"]).resolve()
            if not path.is_file():
                error("EVIDENCE_MISSING", source.get("source_id"), "Restore the original source.")
            else:
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                if not source.get("sha256") or digest.hexdigest() != source["sha256"]:
                    error("SOURCE_CHANGED", source.get("source_id"), "Freeze the actual version and recheck dependent work.")
    if not packet.get("sources"):
        error("SOURCE_MISSING", "sources", "Freeze the source identity and scope.")
    for unit in units:
        uid = unit.get("unit_id")
        if unit.get("source_id") not in source_ids:
            error("UNIT_SOURCE_MISSING", uid, "Reference a frozen source in this packet.")
        if uid in excluded and unit.get("read_state") == "OUT_OF_SCOPE":
            continue
        if unit.get("read_state") not in {"CHECKED", "NON_INFORMATIVE"}:
            error("UNIT_INCOMPLETE", uid, "Read, explain and check this unit; flags alone are insufficient.")
        if not unit.get("understanding_note") or not unit.get("locators"):
            error("UNIT_EXPLANATION_MISSING", uid, "Supply source locators and an inspectable explanation.")
        if not unit.get("evidence_refs"):
            error("EVIDENCE_MISSING", uid, "Link the actual notebook or source evidence.")
        for ref in unit.get("evidence_refs", []):
            evidence(ref, uid)
        visual = unit.get("visual_review", {})
        if (visual.get("required") or unit.get("kind") in {"FIGURE", "PANEL", "TABLE", "OTHER_VISUAL"}) and not native_table_ready(root, packet, unit):
            if visual.get("actually_viewed") is not True:
                error("VISUAL_NOT_VIEWED", uid, "Actually open and inspect the original visual.")
            if not visual.get("artifact_refs"):
                error("EVIDENCE_MISSING", uid, "Link the visual actually inspected.")
            for ref in visual.get("artifact_refs", []):
                evidence(ref, uid)
    if require_review and packet.get("paper_status") not in VERIFIED:
        error("PAPER_NOT_ACCEPTED", "paper_status", "Continue work or record a concrete interruption; do not mark complete.")
    for gate in ["G0", "G1", "G2", "G3"]:
        if gate == 'G3' and not require_review:
            continue
        record = packet.get("gate_results", {}).get(gate, {})
        if record.get("decision") != "PASS":
            error("GATE_PENDING", gate, "Complete and review this gate.")
        if not record.get("evidence_refs"):
            error("EVIDENCE_MISSING", gate, "Link the actual gate decision.")
        for ref in record.get("evidence_refs", []):
            evidence(ref, gate)
    claims = {c.get("claim_id"): c for c in packet.get("claims", [])}
    for claim in claims.values():
        for uid in claim.get("supporting_units", []):
            if uid not in ids:
                error("CLAIM_UNIT_MISSING", claim.get("claim_id"), "Repair the claim-to-source-unit reference.")
            if uid in excluded and claim.get("allowed_use") != "HOLD":
                error("CLAIM_OUT_OF_SCOPE", claim.get("claim_id"), "Hold claims relying on excluded unread units.")
    for issue in packet.get("issues", []):
        opened = issue.get("status") not in {"CORRECTED", "EXPLAINED"}
        if opened and issue.get("kind") in {"READING_GAP", "WORKFLOW_ERROR"}:
            error("OPEN_READING_OR_WORKFLOW_GAP", issue.get("issue_id"), "Repair the agent error or close the reading gap.")
        if opened and issue.get("kind") in {"SOURCE_ANOMALY", "VERSION_DIFFERENCE"}:
            if require_review and packet.get("paper_status") != "VERIFIED_WITH_USER_REVIEW":
                error("ANOMALY_STATUS", issue.get("issue_id"), "Preserve the user-review state.")
            for cid in issue.get("affected_claims", []):
                if claims.get(cid, {}).get("allowed_use") not in {"HOLD", "CONDITIONAL"}:
                    error("ANOMALY_CLAIM_UNRESTRICTED", cid, "Hold or qualify the affected claim.")
    reviews = packet.get("reviews", [])
    if packet.get('review_requirements', {}).get('repair_dependency_sync'):
        from reading_run_control import requests
        from reading_repair_sync import progress_current
        state = read_json('execution_state.json') or {}
        # Ingestion validates every active repair seal before acceptance. A later
        # actual acceptance closes that failed round; its archive is not a live
        # repair task. Current-content changes still invalidate the review hash.
        failed = reviews[-1] if reviews and reviews[-1].get('decision') in {
            'REVISION_REQUIRED', 'MATERIAL_BLOCKED'} else None
        if failed:
            for request in requests(failed, packet.get('owner_id')):
                if not progress_current(root, packet, state, request, failed.get('review_id')):
                    error('REPAIR_SYNC_REQUIRED', request['repair_id'],
                          'Rescan current dependencies, inspect every disposition and obtain fresh review.')
    if not require_review:
        reviews = []
    if require_review and not reviews:
        error("REVIEW_MISSING", "G3", "Obtain independent source-first review.")
    elif reviews:
        review = reviews[-1]
        errors.extend(visual_review_errors(root, packet, review))
        if review.get("template_only") is True:
            error("REVIEW_TEMPLATE_NOT_EXECUTED", "G3", "Replace the review template with an actual current review.")
        writers = set(packet.get("writer_ids", [])) | {packet.get("owner_id")}
        if not packet.get("owner_id") or not packet.get("writer_ids"):
            error("WRITER_IDENTITY_MISSING", "G3", "Record the Owner and all actual writing agents.")
        if not review.get("reviewer_id") or review.get("reviewer_id") in writers:
            error("REVIEW_NOT_INDEPENDENT", "G3", "Use a distinct actual reviewer, not a renamed writing agent.")
        if review.get("decision") not in VERIFIED or review.get("decision") != packet.get("paper_status"):
            error("REVIEW_NOT_ACCEPTED", "G3", "Reconcile the actual review decision and final state.")
        if any(review.get("gate_decisions", {}).get(g) != "PASS" for g in ["G0", "G1", "G2", "G3"]):
            error("REVIEW_GATE_CONFLICT", "G3", "The actual review must confirm every claimed passed gate.")
        if (review.get("reviewed_scope_revision") != packet.get("scope_revision")
                or review.get("reviewed_source_hashes") != source_hashes):
            error("REVIEW_STALE", "G3", "Re-review this scope and source version; record reviewed_scope_revision and reviewed_source_hashes independently.")
        if review.get('reviewed_content_sha256'):
            # Import lazily: the controller also uses this structural preflight.
            from reading_run_control import content_fingerprint
            if review['reviewed_content_sha256'] != content_fingerprint(root, packet):
                error('REVIEW_CONTENT_STALE', 'G3', 'Reinspect changed report, target, records and visual assets; obtain a new actual review.')
        evidence(review.get("source_first_inventory_ref"), "source-first review")
        errors.extend(coverage_errors(root, packet, review))
        errors.extend(quality_errors(root, packet, review))
        if review.get("unresolved_reading_gaps") or review.get("repair_requests"):
            error("REVIEW_REPAIRS_OPEN", "G3", "Complete requested repairs and obtain re-review.")
    deliverables = packet.get("deliverables", {})
    for key in ["full_notebook", "report", "material_index", "user_review", "independent_review"]:
        if key == 'independent_review' and not require_review:
            continue
        evidence(deliverables.get(key), key)
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    try:
        errors = inspect_run(args.run_directory)
    except (OSError, TypeError, AttributeError, KeyError, ValueError) as exc:
        errors = [{"code": "RECORD_FORMAT", "item": "run", "next_action": str(exc)}]
    print(json.dumps({"structural_check_passed": not errors,
                      "semantic_verification_automated": False,
                      "warning": "Paths, IDs, hashes and self-reported flags do not prove actual viewing, independence, or understanding.",
                      "errors": errors}, ensure_ascii=True, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

