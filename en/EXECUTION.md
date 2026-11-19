# Execution and terminal decisions — current contract 2.10

## Initialize and inventory

Use the [stage guide](README.md) for the current action's prerequisites. Reserve a distinct reviewer early. Default new runs to KEY_CLAIMS; preserve requested FULL_DOUBLE_READ and never migrate active/frozen runs.

```text
python "<skill>/scripts/reading_run_control.py" init "<new-run>" --source "<paper.pdf>" --owner "<actual-owner>" --language en --review-mode KEY_CLAIMS
python "<skill>/scripts/reading_run_control.py" extract-elements "<run>"
```

The directory must not exist. init copies/hashes the source and creates unfinished records. Bind only an explicit research target using init --target or set-target --file; otherwise leave null. Changed content under the same target_id requires a higher revision. Targets add questions, never filter source coverage.

For native PDFs, follow [Native elements](../references/native-elements.md) to extract once with an already provisioned pdfplumber interpreter. Verify source identity, section/subsection headings and their boundaries, all objects, appendices and supplements. Save 01_sources.json, 01_inventory.json and scope evidence; sync the inventory and use `section-coverage "<run>" --source-id SRC-01` to locate mapping gaps or overlaps. A flagged page calls for targeted inspection, not another full-text pass. Merge an evidenced G0 before dependent readers start. Preserve missing material and new discoveries instead of removing difficult units.

Register supplements you already hold before the first extraction: PDFs as `PDF` sources and CSV/TSV/XLSX/JSON/MD/TXT files as [DATA_FILE sources](DATA_CONTRACT.md#1-locators-and-units) with provenance and actual hashes. In a 2.10+ run, a supplement acquired later stays in this run. Register it, inventory its units and sync, then run:

```text
python "<skill>/scripts/reading_run_control.py" extract-elements "<run>" --append
```

The assessment reports ELEMENTS_APPEND_REQUIRED until you do. The append binds only the new sources and preserves all earlier pages and the previous manifest ([details](../references/native-elements.md#add-sources-acquired-after-extraction-210)). Checked units on earlier sources keep their evidence; dependent claims, the report and review snapshots must still absorb the new material. Runs initialized before 2.10 keep their original continuation-run route.

## Read, hand off and verify locally

Load the prompt for the current responsibility. Follow [section reading](../references/section-reading.md#02-read-and-reconcile): use `read-section "<run>" --id S2` and its continuation for mapped prose, or read sections directly from the source when no mapping/helper applies. Read every unit; save content, relationships, conditions, limits and actual evidence. For a figure/table, use `read-elements --view locator` on its page to navigate, then inspect the original object or detailed native table as required. For a DATA_FILE unit use `read-data "<run>" --source-id <id>` with `--sheet/--rows/--fields`, `--json-pointer` or `--lines`, and record `content_reading.mode: DATA_FILE` with the same locators ([data files](../references/native-elements.md#data-file-supplements-210)). Locator previews, structure views and coverage diagnostics never advance read state. Missing dependencies do not authorize installation, OCR or uploads.

Identity/locator edits belong in inventory. Use `handoff-template --writer ... --units ...`, fill actual content, `validate-handoff --file ...`, then `merge --file ...`. Validation is read-only; its success is not a merge. Merge preserves raw history and generates notebook/index. Use the canonical records rather than maintaining parallel transcripts.

Owner closes evidenced G1/G2 after actual coverage and method–experiment–visual–claim checks. Counts cannot replace understanding; READ/UNDERSTOOD never automatically becomes CHECKED. Repair READING_GAP/WORKFLOW_ERROR. Preserve SOURCE_ANOMALY evidence, alternatives and HOLD/CONDITIONAL claims without requiring a user truth verdict before continuing.

## Use the current assessment

A successful `init`, `sync`, `merge`, `repair-ready` or `ingest-review` already returns the assessment that `next` would compute. On `CONTINUE`, perform its `next_action` now; do not call `next` again on unchanged state. Send progress, not a plan in place of work. Errors are not assessments: address the error rather than continuing from an older result.

On resume, after manual edits, or when the result was lost or lacks an assessment and you need a routing decision, run `next`. Sync inventory changes first. For example, `extract-elements` returns extraction metadata, not a reading decision. Do not substitute an earlier assessment for preflight, repair validation or the final `next` and read-only checker.

## Finish the narrative before dispatch

Load 07, [Targets and visual reports](../references/targets-and-visual-reports.md) and [Reader explanations](../references/reader-explanations.md). Write report.md/user_review.md and answer every explicit target question in target_analysis.json. reading_report_assets.py generates galleries only from actually inspected images. Register derived data, transformations and limits. Explain mechanisms, terms, metrics and every experiment without requiring internal JSON.

Use shared/report-readability.template.json for report_readability.json, bound to final report SHA256. Locate all six explanation dimensions and every experiment with exact report excerpts and assessments. Actually inspect final display at top, middle and end, images and links; save evidence. A demonstrated unavailable viewer uses UNAVAILABLE and failure evidence; this does not waive source viewing.

New 2.9 runs also index exact localized headings in ordered `sections`, following Reader explanations. Link registered evidence outputs; only an explicitly bound target gets target comparison. The same reviewer judges explanation depth and records `checked_section_roles`/`presentation_assessment`. A missing reviewer summary can be linked at its agreed path before first review, but must exist for final acceptance.

Stabilize all text, assets, G0–G2 and records before preflight and review-plan. Inspect ready_for_review, not only the exit code. The controller computes ordinary sampling; every current claim and dependency is mandatory. Reviewer also checks semantic claim-registry completeness.

## Independent decision and repair

Load 08. Use an actual reviewer distinct from all writers, with fresh/no-history initial context where supported. Supply sources/08 requirements first; withhold drafts until the reviewer's source-first map exists. Probe required image access early. KEY_CLAIMS is not full double reading; FULL_DOUBLE_READ checks all units. The same reviewer assesses narrative explanation in the existing round.

After actual inspection the reviewer saves its draft/observations and runs snapshot --file <draft>, copying all four reviewed_* fields into a new real decision. Freeze inspected content during review. Owner immediately runs ingest-review --file, preserving negative decisions too.

REVISION_REQUIRED/MATERIAL_BLOCKED returns concrete repairs. Repair canonical records, claims, notes, narrative, targets and visual dependencies together; regenerate once. Follow [Repair synchronization](../references/repair-synchronization.md): complete each repair-scan's per-file dispositions, then repair-ready --id --evidence --sync-file. Readiness is not approval; later changes invalidate it.

Pass preflight and send review-delta to the same actual reviewer under [Efficient reinspection](../references/efficient-reinspection.md). New decisions need new IDs/snapshots; retain only that reviewer's verified unchanged coverage. A replacement discloses the change and directly checks claims it accepts, without inheriting viewing. Two recurring workflow failures require generation/synchronization repair before dispatch; record workflow-failure/workflow-repaired evidence. Use escalate-review with evidence when systemic problems require broader coverage, never downgrade a user-selected mode.

## Deliver or preserve genuine interruption

Run next and reading_run_check.py before delivery. ACCEPTED requires current actual independent acceptance, complete Owner reading and consistent records. State mode, independent extent and claim-use restrictions separately. Do not edit scientific text after acceptance or refresh an old token. Scripts neither launch models nor authenticate understanding, viewing or independence.

Only a user stop, imposed platform/resource limit, or demonstrated material/capability block after accessible work permits unfinished delivery. In execution_state record stop_reason=USER_STOP|RESOURCE_LIMIT|MATERIAL_BLOCK|CAPABILITY_BLOCK, restart_action and interruption observed_constraint, attempts, evidence_refs, affected_unit_ids and affected_repair_ids where needed. Capability blocks use affected_action=REQUEST_REVIEW and retain G3 PENDING. Subjective elapsed time, temporary capacity, pending review or a useful report is not a stop condition. INTERRUPTED_WITH_EVIDENCE explicitly means unfinished and promises no automatic background continuation.

Without Python maintain equivalent records manually and disclose the missing check. Without independent capability finish accessible reading/reporting and retain pending review. A single paper omits 09. Requested synthesis preserves all paper states and claim restrictions; new synthesis assertions return to 08.
