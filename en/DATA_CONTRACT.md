# Handoff data contract — current contract 2.8

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

## Current records, handoffs and deliverables

paper_packet.json is the canonical current scientific record. 01_sources.json and 01_inventory.json own source identity and unit identity/locators; sync after changing them. A reading handoff cannot change unit identity, kind, hierarchy or locators. The packet also records owner_id, writer_ids, skill_revision, review_mode, research_target, content_acquisition, review_requirements and deliverables. execution_state.json owns stage, open_unit_ids, next_actions, blockers and repair progress, not a second scientific account.

Handoff top-level keys are limited to writer_id, units, methods_taxonomy, experiments, claims, issues and gate_results. Collections are arrays of objects; gate_results is an object. Use handoff-template, validate-handoff, then merge. Only Owner supplies evidenced G0–G2 with decision=PASS|FAIL|PENDING, evidence_refs and open_items. Only actual independent review supplies G3. READ/UNDERSTOOD never automatically becomes CHECKED.

| Artifact | Writer and purpose |
|---|---|
| paper_packet.json | Controller merges current units, methods, experiments, claims and issues |
| full_notebook.md, material_index.md | Controller-generated from packet; do not hand-edit; follow actual deliverables paths |
| report.md, user_review.md | Owner explains the paper and unresolved source concerns; state checked scope if none remain |
| report_readability.json | Owner passage/display index bound to final report bytes |
| target_analysis.json | Owner answers all current explicit target questions when a target exists |
| report_visuals.md | Gallery helper generates from registered inspected assets; retain derived-data provenance |
| reviews/, independent_review | Reviewer evidence and decisions; controller preserves actual decisions/history |
| handoffs/, repair_sync/ | Raw handoff history and per-request repair scans, never current note mirrors |

Former stage filenames such as 02_units.json, 04_experiments.json and 06_claims.json are not additional mandatory canonical files. Keep useful specialist evidence notes and reference them through evidence_refs; avoid parallel current numerical, claim or experiment accounts. Existing manual notebooks are preserved; the generator may select an alternative output path. Existing current notes participate in applicable repair scans/snapshots even if unlinked.

## Detailed field authorities

- [Native elements](../references/native-elements.md): content_acquisition, content_reading, structured_inspection, source/page/element binding and conflict evidence. Only complete validated native TABLE records qualify for the structured alternative.
- [Review modes](../references/review-modes.md): review_mode, coverage_label, coverage_check, mandatory IDs, sampling and continuation. Every current claim is mandatory; comparison_id/same_as prevent duplicate evidence counting.
- [Reliable execution](../references/reliable-execution.md): reviewer_session_id, visual_inspection and the four reviewed_* snapshot fields. The actual reviewer supplies these; review.gate_decisions uses plain gate strings.
- [Targets and visuals](../references/targets-and-visual-reports.md): explicit research_target, target_analysis, report_visuals and derived data provenance. Target purpose is distinct from paper identity and does not reduce coverage.
- [Reader explanations](../references/reader-explanations.md): six passage checks, all experiments, display evidence, report hash and the same reviewer's semantic judgment. Use the [template](../shared/report-readability.template.json); no word-count score grants approval.
- [Repair synchronization](../references/repair-synchronization.md) and [incremental review](../references/efficient-reinspection.md): repair_requests, repair_progress and per-file dispositions. READY_FOR_REVIEW is not acceptance.

Evidence paths resolve to existing local files, relative to the run or absolute. Keep page/object locations in locators and URLs in source_refs. Expand checked_unit_ids/checked_claim_ids into actual IDs. The last reviews entry is the current decision; template_only cannot be true. Use new review IDs and preserve failed decisions/closure evidence.

## Compatibility and completion

New 2.8 runs enable reader_explanation; new runs since 2.7 bind native acquisition; missing review_mode retains legacy full independent review. Never retrofit active/frozen runs or delete new-run fields to evade their contract. Only USER_DEFINED_SCOPE permits evidenced user-authorized OUT_OF_SCOPE exclusions; retain units and scope revision without claiming complete-paper coverage.

Changes to sources, locators, explanations, reports or evidence reopen affected dependencies and review. Four snapshot fields bind the actual inspected version; never refresh an old approval token. See [EXECUTION.md](EXECUTION.md) for the control loop and evidenced interruption. Scripts cannot prove reading, understanding, viewing, independence or complete source inventory.
