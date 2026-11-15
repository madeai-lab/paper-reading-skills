# Execution and terminal assessment (revision 2.2)

Calling this skill with a paper executes 00–08. Default to complete scope, without expanding into experimental replication. The local helper saves canonical records; it does not run models, create services, prove reading or prevent a host final response.

## 1. Initialize and inventory before dependent readers

Use python "<skill>/scripts/reading_run_control.py" init "<new-run>" --source "<paper.pdf>" --owner "<actual-owner-id>" --language en.
The new directory must not exist. This preserves a source copy/hash and creates task, assignment, state and packet JSON with gates PENDING. Fill discoverable identity fields yourself. Plan actual independent review capacity at startup.

Read stage 01, inspect the actual source/all pages and save:
- 01_sources.json: source array with actual identity, page_count, version, local_path and computed sha256.
- 01_inventory.json: full unit array with stable unit_id, kind, label, source_id, locators, parent_id, children and assigned_owner. Include informative unlettered regions, references needed to interpret the contribution and required missing supplements. Do not inventory every cited work as if its full text were available.
- Stage-01 evidence explaining identity, source completeness, page/chunk joins and coverage.

Run sync "<run>" after editing inventories, using the same helper path as above. Submit an Owner G0 decision through merge. G0 must be evidenced PASS before stages 02–05 start. New discoveries/corrections stay in inventory and invalidate affected reading/review. Never delete difficult units.

Give useful reading specialists complete sources, assigned IDs, role prompts and the data contract. Roles may be combined. Use a distinct reviewer in a fresh/no-history context where supported (for example fork_turns="none"), with sources/stage-08 prompt first; release finished readers to free capacity. Withhold drafts/conclusions until its independent checklist is saved. Do not rename the writer as reviewer.

## 2. Record each reading batch, then do the next action

Run next "<run>" after each chunk, handoff or repair. If terminal_decision=CONTINUE, perform next_action before another assessment. The returned IDs are bounded batches, not permission to omit the rest. Send progress messages while working.

Role handoff JSON contains writer_id and any of units, methods_taxonomy, experiments, claims, issues, gate_results. No other top-level keys are accepted. Units are partial updates by an already-inventoried unit_id; preserve inventory identity/kind/locators. Supply read_state, a source-specific understanding_note and existing evidence_refs. For informative visuals actually inspect the original image and record visual_review with artifact_refs/checks/limitations. Keep rich visual/formal explanations on the unit as well as in notes. READ/UNDERSTOOD never becomes CHECKED automatically. Assign CHECKED only after the required source/content cross-check, not because the helper accepted a payload.

Use merge "<run>" --file "<role-handoff.json>". It archives actual handoffs, merges per-unit explanations/specialist records and renders full_notebook.md/material_index.md. These generated files avoid manually duplicating the same reading records; generation is not understanding. A handoff saying “detail still being developed” is not finished evidence. Experiments require all DATA_CONTRACT fields with source-specific values or justified NOT_REPORTED/NOT_APPLICABLE states. Do not mechanically fill every field with NA.

Only Owner may merge G0–G2, each with decision (PASS/FAIL/PENDING), evidence_refs and open_items. Do not use status as the gate key. G1/G2 require actual complete unit checking and stage-06 semantic reconciliation; no flag-only repair. G3 comes only from the actual reviewer.

Read text continuously, retaining chunk joins; inspect every informative visual/panel/table/note, equation, experiment/negative result, taxonomy relation and appendix. Method references whose operational definition is absent must be identified as absent without pretending the cited paper was read. Each explanation preserves content, relationship, conditions and limits.

## 3. Review returns control to the Owner

Complete stages 06/07 and write report.md/user_review.md from full records. The report may say “pending independent review; current decision in paper_packet.json.” Finish its scientific text before review so acceptance need not change inspected content.

The distinct reviewer first makes its own source checklist, then compares the whole packet/notebook/report and original locations. Immediately before its decision, it runs snapshot "<run>" and copies reviewed_scope_revision, reviewed_source_hashes and reviewed_content_sha256 into a new actual review. This binds the inspected version, not identity or understanding. Do not change the inspected packet during a review; if changed, the reviewer rechecks affected content and takes a fresh snapshot. Review IDs use letters/numbers/underscore/dot/hyphen only. Preserve each new decision under a new review_id.

When review returns, Owner immediately runs ingest-review "<run>" --file "<actual-review.json>". Preserve its actual decision and failed gates. REVISION_REQUIRED means continue with the returned REPAIR actions:
1. Reinspect source and correct records, explanations and dependent claims. Retain evidence for each repair_id.
2. Run repair-ready "<run>" --id "<repair_id>" --evidence "<local-repair-note>" after actual repair.
3. Reconcile failed local gates with evidence, then send the repaired packet to the actual reviewer for reinspection. Repeat on further failures. READY_FOR_REVIEW is not approval.

Review findings stay in history. Do not overwrite an earlier review, insert acceptance yourself, copy a new snapshot into old approval, or stop just because the failed-review state has been saved. All current repair_requests must be closed by the reviewer. A new accepted review retains previous repair/closure evidence.

## 4. Final delivery or evidenced interruption

Run both next "<run>" and python "<skill>/scripts/reading_run_check.py" "<run>". Repair actual work or inconsistent records on failure, then reassess. Full delivery requires ACCEPTED plus real source-first semantic acceptance. Scripts check consistency/versioned evidence; they cannot detect every missing source object, prove viewing or authenticate an agent. Do not call them scientific certification.

Only user stop, an actual imposed platform/resource limit, demonstrated unavailable material, or genuinely missing independent capability permits an unfinished final checkpoint. Finish accessible work first for material/capability blocks. In execution_state use stop_reason USER_STOP, RESOURCE_LIMIT, MATERIAL_BLOCK or CAPABILITY_BLOCK, restart_action and interruption containing observed_constraint, attempts, evidence_refs and affected_unit_ids. Material-block units remain BLOCKED; record any affected_repair_ids. Capability-block applies to REQUEST_REVIEW after complete accessible reading/reporting; also record affected_action=REQUEST_REVIEW and actual unavailable-tool evidence. “Not yet reviewed,” temporary occupied slots and subjective elapsed time are not capability/resource blocks.

INTERRUPTED_WITH_EVIDENCE is explicitly unfinished, never accepted. A record cannot authenticate the constraint: check actual user/tool/platform evidence. Abrupt host interruption may prevent a helper call; preserve the smallest truthful checkpoint possible and do not imply background continuation.

Author concerns normally do not interrupt reading. Preserve an evidence chain, alternative explanations, affected HOLD/CONDITIONAL claims and a clear double-check question under VERIFIED_WITH_USER_REVIEW. User judgment is separate from scientific verification.

Without Python, keep equivalent canonical records manually and disclose the omitted automated checks; use actual review. Without genuine independent capability finish accessible work and retain G3 PENDING. Source boundaries and existing authorizations still apply.
