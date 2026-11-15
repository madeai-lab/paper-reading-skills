# Handoff data contract

## Revision 2.7 acquisition records

`content_acquisition` binds `method=PDFPLUMBER_NATIVE` and `manifest_ref=source_elements/manifest.json` for new runs only. The manifest binds the source hash, parser and detailed page-file hashes. Every checked new-run unit records `content_reading` with `mode=NATIVE_ELEMENTS|VISUAL|MIXED`, existing `page_refs`, exact `element_ids` and `conflict_resolution_refs`. IDs must resolve to the correct source/page/object; no unresolved parsing conflict may be hidden. Only a complete validated TABLE can substitute this for pixel viewing, preserving `actually_viewed=false` when appropriate. FIGURE/PANEL/OTHER_VISUAL remain actual-viewing objects. For required native tables accepted without pixels, the reviewer records its own `structured_inspection` with inspected `unit_ids` and local `evidence_refs`; other textual evidence still requires actual source/claim checking. Owner flags do not transfer. Read [Native PDF elements](../references/native-elements.md) for routing, evidence limits and commands. Extraction files and resolution evidence are snapshot-bound; changes reopen affected dependencies. Missing fields in earlier runs do not enable the exception or migrate the run.

## Revision 2.6: review mode

Read [Review modes](../references/review-modes.md) before applying earlier revision guidance. New runs default to KEY_CLAIMS; FULL_DOUBLE_READ retains complete independent double reading. Missing mode retains legacy full-review behavior. The Owner still covers all source units; stage-08 scope depends on the recorded mode. Existing active/frozen runs are never migrated.

Use the same task, source, unit, experiment, claim and issue IDs across stages. Field names remain English; prose may use the selected language. The [shared template](../shared/packet.template.json) is empty scaffolding, not completed evidence.

## 1. Locators and units

source: source_id, title, version, publication_status, local_path or url, sha256 actually computed for local files, page_count, access_state, supplement_of, required_for_scope, missing_reason.

unit: unit_id, kind, label, parent_id, children, source_id, locators, assigned_owner, read_state, information_role, understanding_note, evidence_refs, visual_review, dependencies.
Use SECTION, FIGURE, PANEL, TABLE, EQUATION, ALGORITHM, APPENDIX, OTHER_VISUAL or BIBLIOGRAPHY for kind. Give a parent figure and each panel separate IDs, such as P20-F04 and P20-F04-d. Do the same for nested sections, composite tables and unnumbered visuals.

locator: physical_page, printed_page, section, object_label, panel, paragraph_or_cell, image_path. Inapplicable fields may be null; never guess a page. An object spanning pages may have several locators.

read_state is INVENTORIED, READ, UNDERSTOOD, CHECKED, BLOCKED or NON_INFORMATIVE. Attach stage evidence when advancing a state and preserve other roles' findings. visual_review contains required, actually_viewed, artifact_refs, checks and limitations. Rendering alone cannot set actually_viewed.

understanding_note states content, relationships/mechanism, conditions/units, supported and unsupported interpretations. “Understood,” “see figure” or “correct” alone is insufficient. evidence_refs must identify actual sources and existing notes/images, not only an old report.

## 2. Specialist records

experiment: experiment_id, purpose, unit_refs, design, data_and_sampling, split, ground_truth, models_and_tools, comparators, budget, metrics, results, uncertainty, negative_results, failure_cases, limitations, claim_refs.
For numbers retain value, unit, denominator, population, time_or_condition and source_locator. Distinguish NOT_REPORTED, NOT_YET_FOUND and NOT_APPLICABLE with reasons rather than filling everything with NA.

method/taxonomy: each component/node has an ID, definition, inputs/outputs, relations, assumptions, training/runtime stage, assignment/mapping rules, exceptions and source locations. A parent-level sentence cannot replace its leaf nodes.

visual/formal record: unit_id, observed_content, encoding, relationships, conditions, text_links, experiment_links, claim_links, exact_vs_estimated, limitations, evidence_refs. For equations/algorithms also record symbols, assumptions, inputs/outputs, steps/derivation function and scope.

claim: claim_id, text, attribution, source_refs, supporting_units, experiment_refs, conditions, support_state, allowed_use, issue_refs. Use the four B09 attribution types. support_state is SUPPORTED, LIMITED, CONTRADICTED or UNDETERMINED. allowed_use is USE, CONDITIONAL or HOLD. Author emphasis alone does not justify SUPPORTED.

## 3. Issues and user decisions

issue: issue_id, kind, status, observations, source_refs, minimal_evidence, calculation, alternative_explanations, checks_performed, missing_evidence, affected_claims, impact, recommended_use, user_question, user_decision.
kind is READING_GAP, WORKFLOW_ERROR, SOURCE_ANOMALY or VERSION_DIFFERENCE. status is OPEN, CORRECTED, EXPLAINED or USER_REVIEW. user_decision must remain null until the user responds; never simulate approval.

The user-review packet uses the same issue_id and contains:
1. A one-sentence concern and source version.
2. Two or more relevant source locations with legible images or necessary paraphrases, stating what was actually observed.
3. A like-for-like comparison or calculation, or why calculation is inapplicable.
4. Explanations eliminated and still plausible, without invented probabilities.
5. Affected claims and whether other results are affected.
6. The exact conclusion to hold or qualify, and the material the user should double-check.
7. User choice and evidence status recorded separately. Human choice does not replace source evidence.

## 4. Independent review and states

review: review_id, reviewer_id, independence_disclosure, source_first_inventory_ref, checked_unit_ids, checked_claim_ids, findings, unresolved_reading_gaps, open_source_issues, gate_decisions, decision, repair_requests.
A reviewer who also authored the work, only saw an old summary, or could not independently inspect sources cannot claim independent review. Never invent a second agent or reviewer identity.

paper_packet contains task_id, paper_id, scope_mode, scope_revision, paper_status, sources, units, methods_taxonomy, experiments, claims, issues, reviews, gate_results and deliverables. The coordinator merges handoffs while preserving conflicts and role records. With COMPLETE_PAPER scope, all required units must be CHECKED before G1; only independently confirmed NON_INFORMATIVE items are exempt. Difficult information cannot be excluded.

Each gate_results entry records PASS, FAIL or PENDING, reasons and open items. Only the independent review decision grants G3 PASS. Do not reconstruct approvals from a report title or checked boxes without underlying evidence.

## 5. Final deliverables

- paper_packet.json: coordinator's merged index.
- full_notebook.md: complete unit-level reading notebook linking specialist records.
- report.md: readable report with explicit scope and status.
- material_index.md: sections, figures/panels, experiments, taxonomy, equations and appendices.
- user_review.md: unresolved SOURCE_ANOMALY chains. If none are found, state the review scope; do not invent concerns.
- independent_review.json / .md: independent review outcome.
- Other specialist JSON/Markdown files follow stage prompt names. Preserve source files/renderings only in authorized locations and respect source rights when sharing.

## 6. Revision 2.2 run records and checker

Also record owner_id, writer_ids (all actual writing agents) and skill_revision in paper_packet. Maintain stage, open IDs, next actions, blocker reasons/attempts/outcomes and repair history in execution_state.json using the [template](../shared/execution-state.template.json). Update on every handoff. Never remove inventoried IDs to satisfy the checker; append discoveries with scope revisions and retain locator-correction history.

The read-only checker expects 01_inventory.json as a unit array and paper_packet under this contract. Gate evidence_refs, unit evidence_refs, visual artifact_refs, source_first_inventory_ref and deliverables values use existing local path strings relative to the run directory or absolute. Keep source locators separately in locators and URLs in source_refs. The five deliverables keys are full_notebook, report, material_index, user_review and independent_review.

Expand checked_unit_ids and checked_claim_ids into actual ID lists rather than natural-language ranges. The last reviews entry is the actual current-revision decision. Explain NON_INFORMATIVE objects and include them in review. Use comparison_id/same_as for repeated presentation of one experimental comparison without double-counting evidence.

The script detects record inconsistencies. It cannot judge semantic understanding, authenticate reviewer identity or actual viewing, or detect a source object absent from the inventory. Actual work, source-first review and tool records establish those; exit code0 is not G3 evidence.

### Current review snapshot and narrowed scope

Reviews must include reviewed_scope_revision and reviewed_source_hashes (source_id to actual sha256), populated independently by the reviewer from inspected materials. Review gate_decisions must agree with every packet gate. Source/scope changes invalidate old review; the Owner must not copy new hashes into an old approval. Important interpretation/value/claim changes require B16 re-review. The helper binds recorded explanations and local evidence with reviewed_content_sha256; semantic adequacy still requires actual review.

Only explicit user narrowing permits scope_mode=USER_DEFINED_SCOPE while retaining original inventory IDs. Each scope_exclusions entry records unit_id, reason, a local user_authorization_ref containing actual user authorization and the current scope_revision. The retained unit uses read_state=OUT_OF_SCOPE without fabricated understanding. The reviewer checks exclusion evidence and lists its ID. The report prominently states PARTIAL_SCOPE and the actual subset, never full-paper completion. COMPLETE_PAPER permits no such exclusion. HOLD claims relying on excluded unread objects. The Owner cannot narrow scope to satisfy the checker.

repair_requests contains currently open requests only. Move repaired items into closed_repairs or retain previous reviews/history with closure evidence. The last review cannot have template_only=true; an empty template grants no acceptance.

### Executable handoffs and current-content snapshot

See [EXECUTION.md](EXECUTION.md) for helper commands. Use init/sync/merge rather than rebuilding canonical JSON. Gate objects use decision, evidence_refs, open_items; execution_state uses stage, open_unit_ids, next_actions (not phase/open_ids/next_action). A raw handoff has writer_id and only units/methods_taxonomy/experiments/claims/issues/gate_results as needed. The notebook is rendered from these records; put the complete source-specific explanation in the unit, not a promise of future detail. Preserve other roles' work and record unresolved conflicts as issues.

The reviewer independently runs snapshot after inspecting the final packet and copies reviewed_content_sha256 into its review along with reviewed_scope_revision and reviewed_source_hashes. It binds inventory, source inventory, recorded units/methods/experiments/claims/issues, local source/evidence files, notebook/index and report/user_review text. It excludes execution/review outputs to avoid circular hashes. A changed source locator, explanation, evidence or report requires reinspection and a new review. Snapshot tokens can be copied falsely, so actual tool sequence/identity remains necessary evidence. Older review records without this field are historical evidence, not current 2.2 acceptance.

repair_requests entries use repair_id, unit_ids, responsible_role and required_action with source/impact evidence. repair-ready stores READY_FOR_REVIEW and evidence_refs in state.repair_progress, never closes reviewer requests. Reviews are append-only by unique safe review_id. Use ingest-review, including failed decisions, so the Owner receives an executable repair queue. Current failed requests remain open until actual reinspection.

next returns CONTINUE, ACCEPTED or INTERRUPTED_WITH_EVIDENCE with may_send_final/paper_accepted. CONTINUE requires doing next_action, not a final answer listing it. The helper cannot force the host/model to continue. An interruption record must match an actual documented constraint; generated text alone is not evidence of one.

## Revision 2.3 extensions

The optional research_target and report_visuals packet fields, target_analysis.json, report_visuals.md and quantitative backing-data contracts are defined in [Targets and visual reports](../references/targets-and-visual-reports.md). research_target is distinct from bibliographic target_identity. The helper binds it at init --target or set-target --file; target changes preserve source units but invalidate acceptance of changed interpretation/report. Target-specific analysis remains separate from general source findings. Optional fields are omitted from legacy fingerprints when null/absent; existing runs are not automatically migrated or reapproved.

Register display images and derived-chart backing data with artifact_refs/evidence_refs. The snapshot also binds simple inline Markdown images; complex/reference-style or HTML images require explicit registration. Generated display and structural validation do not establish actual viewing, scientific understanding or semantic acceptance. Complete target analysis and visual output before the reviewer snapshots the packet.

## Revision 2.4

The shared [Reliable execution contract](../references/reliable-execution.md) is required. Graphical/raster/conflict objects require the reviewer's own visual_inspection/session/observation evidence for accepted G3; new native-acquisition runs may independently inspect validated complete tables under [Native PDF elements](../references/native-elements.md). Runs without that explicit acquisition contract retain their prior visual requirements. Use handoff-template and review-template; validate-handoff is read-only and precedes merge. Parent/panel links must be reciprocal and same_as references must resolve. Existing runs are not migrated. Templates and structural checks cannot establish actual inspection, independence or understanding. A blocked required image channel retains G3 unaccepted.

## Revision 2.6 review fields

`task.review_mode`, `packet.review_mode` and `review.review_mode` use KEY_CLAIMS or FULL_DOUBLE_READ. Missing packet mode means legacy FULL_DOUBLE_READ, not the new default. No active/frozen migration is implied. The controller computes all current claim IDs as mandatory key_claim_ids; `review_requirements.key_unit_ids` adds mandatory unit IDs. Claim supporting_units, experiment unit_refs, issue links and recursive unit dependencies/parent context determine required evidence units. All report/target/synthesis substantive assertions must be registered; the reviewer checks semantic completeness.

The review records the computed coverage_label, actual checked_unit_ids/checked_claim_ids and `coverage_check` with source_structure_checked=true, owner_coverage_checked=true, omissions=[], evidence_refs pointing to existing reviewer evidence. These true values require actual work. In KEY_CLAIMS checked IDs cover every current claim, required dependency unit and controller-planned stratified ordinary sample; direct reviewer visual records cover the required inspected visual units. FULL_DOUBLE_READ retains all-unit coverage using the native contract when explicitly enabled; legacy runs retain their previous all-unit/all-visual requirements. Owner coverage remains complete in every mode.

After an earlier review, `continuation` records previous_review_id, retained_unit_ids, rechecked_unit_ids and replacement_reason when relevant. Retained coverage requires the same actual reviewer_session_id and verified unchanged content. Rechecked IDs mean actual new inspection; replacements do not inherit predecessor viewing. A new review ID and all four fresh snapshot fields bind the actual current decision. State complete Owner reading and independent coverage mode separately; the same accepted state must not imply full independent double reading for KEY_CLAIMS.
