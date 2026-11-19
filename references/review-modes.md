# Review modes and bounded reinspection (revision 2.6)

Use the mode selected at initialization. Consult this contract when registering claims, preparing or conducting review, or resolving a mode/continuation question. Independent scope never reduces Owner reading or grants approval from a script result.

## Select and preserve the mode

New runs default to `KEY_CLAIMS`. Initialize with `--review-mode FULL_DOUBLE_READ` when complete independent double reading is requested. Record `review_mode` in the task, packet and actual review. A packet without an explicit mode retains earlier full-review requirements. Never migrate an active/frozen batch or relabel an old approval. Changing mode requires actual review of the new requirements.

In both modes the Owner continuously reads every in-scope unit, method, experiment, taxonomy leaf, appendix and required supplement. New native-acquisition runs follow [Native PDF elements](native-elements.md): text/tables/native labels are read from structured evidence first, graphical/raster/conflict objects receive actual visual inspection, and only verified complete native tables use the narrow table exception. Runs without native acquisition retain their previous direct-viewing requirements. G0-G2 and reading-gap rules are unchanged. Stages 01-07 are responsibilities normally performed by one Owner, not seven agents. Add a specialist only for a concrete unresolved difficulty.

## KEY_CLAIMS: independent evidence review

Before draft conclusions, the distinct reviewer saves a compact source-first structural map: source identity, page/section layout, methods/results, figures/tables, appendices/supplements and omission risks. Inspect source pages at readable scale where needed and probe actual image capability. This is an independent starting point, not a second complete notebook or a claim that all content was independently reread.

Every current packet claim is mandatory for independent verification. The controller computes `key_claim_ids`; the Owner cannot exempt a claim through a manual key list. Register substantive report-summary/conclusion assertions, every target answer and synthesis-bound assertion, quantitative comparisons, causal/superiority/generalization/novelty/absence claims, decisive conditions/negative results and user-facing source anomalies as claims. Ordinary descriptive detail may remain in units. The reviewer independently checks registry completeness; IDs cannot establish semantic completeness.

`review-plan` computes required claim and unit IDs, including claim supporting units, experiment unit references, issue dependencies, unit dependencies and necessary parent context. Additional mandatory units may be registered in `review_requirements.key_unit_ids`. Follow each claim through its full original evidence chain, comparators, calculations, qualifications and contradictory evidence. Directly inspect required graphical/raster/conflict objects; independently read validated native-table evidence through the structured-inspection contract. Writer flags, captions or contextless crops do not substitute for either actual check.

Compare the complete Owner inventory with the source-first map. Also inspect the reproducible stratified ordinary-unit sample from `review-plan`: `min(N, max(5, ceil(0.20*N)))` of N non-key units, distributed across actual source sections and object types. The computed minimum is not an upper bound; the reviewer may expand it. Independently justify exclusions and NON_INFORMATIVE labels instead of using them to evade reading.

One substantive error triggers examination of its type and dependencies. The same substantive error in two distinct units triggers checking that whole type. Widespread omission, unreliable evidence, mismatched versions or systematic misunderstanding requires FULL_DOUBLE_READ or an unresolved failure. Complete all claims and required expanded checks before acceptance. Do not call sampled ordinary coverage complete independent rereading.

## FULL_DOUBLE_READ

The reviewer first establishes a complete independent source inventory, then checks every in-scope unit, important claim, informative visual/panel, experiment and taxonomy node against Owner records. Preserve full checked-ID coverage and the source-appropriate evidence requirements, including real pixels for graphical/raster/conflict objects and independent structured inspection for validated native tables. Cost or a short report does not authorize downgrading a requested full double read.

## Preflight and one repair transaction

Finish scientific records, generated notebook/index, report, targets, visual assets and repair dependencies, then run the read-only `preflight` before dispatch. Resolve encoding, missing paths/evidence, invalid links, incomplete claim registration and stale repair readiness locally. Regenerate and verify content stability. Structural readiness is not scientific acceptance. Generated notebook/index files are generator-owned; avoid hand-maintained mirrors and volatile acceptance wording in reports.

The reviewer completes the planned review and returns all currently known findings together. Each repair identifies location, discrepancy, effect, affected IDs and an observable closure condition. Formatting preferences alone do not trigger another scientific round. Source anomalies retain evidence and claim-use restrictions; the Owner does not repair the paper.

Repair all findings/dependencies as one batch, regenerate once and pass preflight. Give the same actual reviewer the previous decision, unresolved repairs, before/after diff, changed IDs/locations, evidence paths and verification results. Use `review-delta` to locate changed artifacts and records; hashes locate changes, not prove correctness. Give paths instead of resending the entire packet, contract or chat.

The same reviewer retains only its own verified unchanged coverage and directly reinspects changed claims/units, their dependency closure and new evidence. Record `continuation.previous_review_id`, `retained_unit_ids` and `rechecked_unit_ids` truthfully. The reviewer may expand inspection. New decisions need new IDs and fresh snapshots, not new agents. Preserve checkpoints, observation evidence and failed decisions under `reviews/`.

Partition `checked_unit_ids` into disjoint retained/rechecked lists. Also record `continuation.rechecked_claim_ids` for changed or affected claims and `continuation.inspected_changed_files` for every path returned by `review-delta`. A replacement directly rechecks every current claim. The controller saves an immutable `<review_id>.baseline.json` beside each ingested decision. If it is missing, delta requires fresh coverage without retained flags. Delta follows changed evidence through unit dependencies and affected claims; the reviewer determines the remaining semantic dependency boundary.

If the reviewer cannot resume, save the actual failure and stop duplicate attempts or empty waiting. A replacement discloses `replacement_reason` and directly verifies every current claim and repair it accepts. Predecessor notes are attributed evidence, not replacement viewing; retained coverage requires the same actual reviewer session. Missing reliable evidence expands inspection, while replacement alone does not require rereading every ordinary unit.

If the same workflow defect recurs in two repair transactions, suspend reviewer dispatch and diagnose generation/synchronization. Keep unresolved status. A retry count or exhausted budget never grants acceptance. Resume after one stable preflighted batch.

Use `workflow-failure "<run>" --id <category> --evidence <note>` to record each observed recurring pipeline failure. Two recorded failures of the same category block preflight. After actual repair, `workflow-repaired` with the same category and an evidence note clears that category's dispatch block; all other preflight checks still apply. This is pipeline bookkeeping, never scientific approval. For systemic evidence problems use `escalate-review "<run>" --evidence <note>` to upgrade a new KEY_CLAIMS run to FULL_DOUBLE_READ. There is no downgrade command or automatic legacy migration.

## Delivery contract

Record the computed `coverage_label` and `review_mode` in the actual decision. `coverage_check` contains `source_structure_checked`, `owner_coverage_checked`, `omissions` and local `evidence_refs`; accepted review requires actual checks with no unresolved omissions. Report complete Owner reading separately from independent review extent. KEY_CLAIMS means complete reading plus independent verification of all registered claims and disclosed ordinary-unit sampling/expansion. Only actual FULL_DOUBLE_READ coverage is complete independent double reading. Preserve HOLD/CONDITIONAL claims and source concerns in both modes. Scripts cannot authenticate viewing, independence, understanding or semantic completeness.

Labels are `COMPLETE_READING_KEY_CLAIMS_CHECKED` and `COMPLETE_INDEPENDENT_DOUBLE_READ`, respectively. `preflight` returns `ready_for_review` and detailed errors; callers must inspect that field rather than treating successful command execution as readiness. Neither label overrides a partial source scope, blocked material or unresolved scientific use restrictions.
