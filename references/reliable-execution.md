# Reliable execution (revision 2.7)

Use the section for the current action via the [stage guide](../en/README.md). For delegated review, read the capability and host-lifetime rules before dispatch, not after the reviewer starts. Structural checks do not establish understanding, viewing or independence.

## Keep the team and records small

Start with one Owner/reader and one distinct source-first reviewer. The Owner can perform stages 01–07; stages are responsibilities, not a requirement to launch a separate agent for each. Add a specialist only for a concrete source difficulty or independent question that the current pair cannot efficiently cover. A short, legible paper normally needs no extra specialist readers. Do not have every role independently recreate all methods, experiments and claims.

The packet is the canonical scientific record. Give every source object, comparison, claim and issue one stable ID. Reuse those IDs in updates. A composite figure has a FIGURE parent and PANEL children with reciprocal parent_id/children. Repeated presentations of the same experiment share a comparison_id; if duplicate records must be preserved, link same_as to actual IDs and count the evidence once. Distinct independent runs are not duplicates merely because they use the same units. Inventory decisions still require source inspection; code cannot identify an omitted parent or infer whether two experiments are genuinely the same.

Prefer canonical handoffs over custom scripts rewriting many files. Do not maintain additional current methods/experiment/claim JSON mirrors unless another tool genuinely needs them. Immutable raw handoffs and prior decisions remain history; the generated notebook and index come from the current packet. Correct current claims and dependent report/target/visual text, while retaining an explicit correction trail. A repair is complete only after this whole dependency chain has been rechecked. For revision 2.5, follow [repair synchronization](repair-synchronization.md): the controller requires per-file inspection evidence and invalidates readiness when current files change. Store new reviewer-only outputs under reviews/.

## Verify image capability before relying on a reviewer

When mode-required graphical/raster/conflict objects need pixels, before expensive independent review give the intended reviewer one such source page/image, source identity and stage-08 requirements, without draft conclusions. A new native-only text/validated-table source uses independent structured inspection instead of a fabricated image probe. In its own clean context it actually opens the image and records visible labels, relationships and limitations with the tool outcome. File existence, a successful Read return, a caption, OCR or another reader's description is not evidence that pixels were displayed to that reviewer.

If the tool returns filtered, unavailable or undisplayed image content, set direct_pixels_available=false. Try at most one materially different already-available local viewing method, or a genuinely separate capable independent reviewer, within existing authorization. Do not repeat the same unavailable channel, install tools, upload sources or rename the writer as reviewer. This is a capability check, not a source anomaly.

Keep Pass A (source-first inventory) and Pass B (draft comparison) in the same actual reviewer session where supported. Resume that same agent rather than silently replacing its context under the same name. If a new session is necessary, disclose the change, establish source-first independence and directly recheck image capability there. Earlier session viewing does not become viewing in the new session. Record the actual host-exposed agent/session identifier; if none is exposed, use HOST_NOT_EXPOSED and explain the identity limitation rather than inventing an identifier.

Capture an exposed stable host ID before the first decision where possible. If old decisions truthfully recorded HOST_NOT_EXPOSED and a stable ID becomes available later, do not rewrite history or infer continuity from a route name. For the existing strict continuation validator, conservatively retain no unprovable coverage and directly recheck the current required units and claims. Explain the changed identity assurance in continuation.replacement_reason, distinguishing identity uncertainty from an actual reviewer replacement; save a new actual decision and snapshot. This recovery requires real reinspection, not new labels on old observations.

Check the host's child-task lifetime before dispatch. If ending the parent turn/process stops its reviewer, use a supported foreground continuation or keep the parent active with bounded result/status waits until the actual decision is saved and ingested. A final "waiting for reviewer" message is not a handoff to a durable worker. If the host reports a stopped task, inspect partial outputs and resume it; never count queued dispatch or stale activity as completed review.

For new 2.4 runs, acceptance requires a reviewer-authored visual_inspection object:

```json
{
  "reviewer_session_id": "actual-host-session-or-agent-id",
  "visual_inspection": {
    "status": "COMPLETE",
    "direct_pixels_available": true,
    "session_id": "actual-host-session-or-agent-id",
    "blocked_unit_ids": [],
    "tool_evidence_refs": ["reviewer_source_observations.md"],
    "units": [
      {
        "unit_id": "F1",
        "actually_viewed": true,
        "artifact_refs": ["evidence/figure-1.png"],
        "observations": "Source-specific visible marks, labels, relationships and restrictions."
      }
    ]
  }
}
```

Enumerate every independently required pixel unit, including necessary composite parent/panel context. New native-acquisition runs may exclude only complete validated native tables under the native contract and must record independent structured_inspection for them. FULL_DOUBLE_READ still checks every source unit; legacy runs retain their prior all-visual requirement. KEY_CLAIMS uses its computed required scope. Do not copy the writer's visual flags. Save your actual tool outcome/observation evidence locally. COMPLETE is permitted only after direct viewing; BLOCKED cannot accompany accepted G3. If no independent pixel units remain after the valid native-table exception, use status=NOT_APPLICABLE and units=[] with source-derived reasoning and actual structured evidence where required. The controller and checker reject incomplete/blocked visual contracts for new runs. They still cannot authenticate viewing or reviewer identity: contradictory disclosures are workflow errors requiring correction, not wording to hide behind a true flag.

If independently required direct viewing remains unavailable, finish all accessible reading, records and reporting, retain G3 PENDING/FAIL and record an actual CAPABILITY_BLOCK using EXECUTION.md. Include the actual failed attempts, evidence paths, affected action REQUEST_REVIEW and restart action. Do not produce acceptance merely with a footnote about unavailable pixels. An honest capability-blocked result is an observed outcome, not successful full reading.

## Generate and validate handoffs before mutation

Use the installed helper through Python. All commands below take the actual run directory; use shell file redirection or a file-writing tool appropriate to the platform for saved JSON, preserving UTF-8.

```text
python "<skill>/scripts/reading_run_control.py" handoff-template "<run>" --writer "<actual-writer>" --units F1 F1-a
python "<skill>/scripts/reading_run_control.py" validate-handoff "<run>" --file "<handoff.json>"
python "<skill>/scripts/reading_run_control.py" merge "<run>" --file "<handoff.json>"
python "<skill>/scripts/reading_run_control.py" review-template "<run>" --writer "<actual-reviewer>"
```

Templates contain unfinished fields and are not evidence. Handoff templates omit inventory identity/labels/locators to avoid accidental changes; merge retains those from inventory. Fill source-specific explanations and actual visual_review records. Collections units/methods_taxonomy/experiments/claims/issues are arrays of objects. gate_results is an object, {} when unused, never []; only the actual Owner supplies evidenced G0–G2, never G3. Review gate_decisions are plain PASS/FAIL/PENDING strings; overall decision is separate. The reviewer populates its own snapshot after actual inspection. Do not relabel a negative decision or delete valid repairs merely to satisfy a schema.

After inspection, fill and save the review draft including visual_inspection, then run `python "<skill>/scripts/reading_run_control.py" snapshot "<run>" --file "<review-draft.json>"`. Copy all four returned snapshot fields into the new actual decision: reviewed_scope_revision, reviewed_source_hashes, reviewed_content_sha256 and reviewed_visual_evidence_sha256. The fourth binds reviewer observations, session and reviewer-only image/tool/checklist evidence bytes. Do not use the decision or mutable state file as its own evidence; keep source-first observations stable. Changed reviewer evidence requires actual reinspection and a fresh decision, just as changed scientific content does.

validate-handoff runs the merge validation without writing any file. Correct reported shape/reference defects before merge; preserve the original raw return if an adapter is needed. Validation rejects dangling parent/panel and same_as references but cannot determine semantic completeness. Apply targeted edits to current canonical records through a new validated handoff; do not repeatedly run a partially successful mutation script. Use full source-specific field replacements when repairing a sentence, not chained global substring substitutions. Reread the exact changed prose, quantities, negations and units after replacement.

## Check concerns before asking the user to judge them

For each proposed source anomaly, establish the exact source locations, quantities, population/conditions, namespace and inference being compared. Problem numbers, tool IDs and panel labels can be different namespaces. Check definitions and explicit exclusions before calling statements contradictory. Different rounding/display precisions are not automatically discrepancies: reproduce the calculation with explicit decimal values and stated or clearly labeled candidate rules. Check both displayed and unrounded values; no implementation detail should be invented to explain a normal result.

Keep estimates separate from measured outcomes. Excluded overhead does not prove an unvalidated estimate bounds an actual duration. Tool-encoded prior knowledge does not prove the model contains no domain knowledge. Partial prompts/logs are not complete traces, but their presence must not be described as absence. A qualitative author assertion is not a measured ablation. These are comparison/inference checks, not a checklist demanding that every paper have these experiments.

If the supposed contradiction comes from the reader's arithmetic, namespace confusion, locator or inference, record a corrected WORKFLOW_ERROR or an explained concern and withdraw the user-adjudication request. Do not inflate low-impact citation/format observations into scientific defects or create a quota of anomalies. User review is for genuine unresolved source concerns with narrowly restricted claims.

## Test the actual report surface, then freeze once

Use the user's requested language for explanations and captions; preserve original labels/quotes as needed. Keep the reader-facing report focused on findings, mechanisms, evidence and target relevance. Put long hashes, machine IDs, execution history and JSON in linked evidence records rather than front-loading them. Prefer selected original panels and compact two-column evidence tables/cards. Mermaid needs a readable static diagram or concise prose fallback on a surface that does not render it; showing only source code is not a successful diagram.

If local tools permit a rendered preview, inspect the top, middle and bottom through the final paragraph/file links, at a useful width. Capture the document height or deliberately scroll/capture the complete end; a fixed tall viewport or a blank lower crop does not prove coverage. Record exactly which final sections were actually visible. Inspect relevant crops at legible resolution. A failed or unavailable renderer gets an honest disclosure, not a claim from asset existence. Do not install dependencies or start a server just to satisfy this check.

Finish text, assets, target answers, metadata and G0–G2 before the reviewer snapshots. Use neutral report wording pointing to the packet/latest review so approval need not rewrite the inspected report. Reviewer reinspection checks exact repairs and their dependencies, preserves failed decisions, then takes its own new snapshot. The writer ingests the actual decision and follows the returned assessment; run `next` plus the read-only checker before final delivery. Do not rewrite scientific files after approval or refresh an old token.

## Unassisted trial boundary

When the user requests a minimally supervised trial, provide only the updated skill, source, explicit target, new output directory and execution permissions. Keep prior reports, specific known paper anomalies and expected verdicts out of the test prompt. Observe status without editing the run, injecting repairs, supplying a replacement reviewer from the supervising host, or modifying the frozen skill. The executing agent may perform the skill's own repair/review loop within authorization. Preserve its actual completion or capability-blocked outcome; report failure as failure rather than silently rescuing the trial.

## Efficient reinspection

Read [Efficient independent reinspection](efficient-reinspection.md) before dispatching repair review. Reuse the actual independent reviewer and its own source-first evidence. A new decision needs a new review ID and fresh snapshot, not a fresh agent. Reinspect changes and their affected dependencies while retaining the same reviewer's verified unchanged coverage; expand the review when source, scope or reliability changes. Never invent resumed identity, viewing or approval.
