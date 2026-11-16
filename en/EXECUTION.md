# Execution and terminal decisions — current contract 2.9

## Initialize and inventory

Use one Owner for stages 01–07 and one distinct reviewer for 08. Reserve review capacity early; specialists address concrete difficulties. Read [boundaries](00_governance/BOUNDARIES.md), [data contract](DATA_CONTRACT.md) and [loading routes](../references/architecture.md). Default new runs to KEY_CLAIMS; preserve requested FULL_DOUBLE_READ and never migrate active/frozen runs.

```text
python "<skill>/scripts/reading_run_control.py" init "<new-run>" --source "<paper.pdf>" --owner "<actual-owner>" --language en --review-mode KEY_CLAIMS
python "<skill>/scripts/reading_run_control.py" extract-elements "<run>"
python "<skill>/scripts/reading_run_control.py" read-elements "<run>" --source-id SRC-01 --pages 1 2 --max-chars 18000
```

The directory must not exist. init copies/hashes the source and creates unfinished records. Bind only an explicit research target using init --target or set-target --file; otherwise leave null. Changed content under the same target_id requires a higher revision. Targets add questions, never filter source coverage.

Follow [Native elements](../references/native-elements.md): use an already provisioned pdfplumber interpreter, extract once and continuously read every page through bounded slices; use --bbox for regions. Missing dependencies do not authorize installation, OCR or uploads. Read native text, labels and complete tables structurally first; actually view graphics, bitmaps and formula/parsing conflicts as required. Extraction does not advance read_state.

Inspect identity, page joins, all objects, appendices and supplements. Save 01_sources.json, 01_inventory.json and scope evidence. sync, then merge an evidenced G0 before dependent readers start. Preserve missing material and new discoveries instead of removing difficult units.

## Read, hand off and verify locally

Load current stage-01–06 prompts. Read all units continuously and save content, relationships, conditions, limits and actual evidence. Identity/locator edits belong in inventory. Use handoff-template --writer --units, fill actual content, validate-handoff --file, then merge --file. Merge preserves raw history and generates notebook/index; do not maintain handwritten current mirrors. DATA_CONTRACT.md defines fields and ownership.

Run next after each batch and perform next_action. CONTINUE means work now, not end with a plan. Owner closes evidenced G1/G2 after actual coverage and method–experiment–visual–claim checks. Counts cannot replace understanding; READ/UNDERSTOOD never automatically becomes CHECKED. Repair READING_GAP/WORKFLOW_ERROR. Preserve SOURCE_ANOMALY evidence, alternative explanations and HOLD/CONDITIONAL claims without requiring a user truth verdict before continuing.

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
