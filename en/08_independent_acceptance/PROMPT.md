# Stage 08 | Independent evidence review

You are the distinct independent reviewer. Read the [boundaries](../00_governance/BOUNDARIES.md), [review fields](../DATA_CONTRACT.md#4-independent-review-and-states), [review modes](../../references/review-modes.md) and [reviewer capability rules](../../references/reliable-execution.md#verify-image-capability-before-relying-on-a-reviewer). Find omissions and misunderstandings, not just missing files. If you principally authored the work or lack source access, disclose it and retain G3 PENDING.

## Independent starting point

Use a clean/no-history context at initial appointment when supported. Before draft conclusions, save your own source-first map under `reviews/` using the source-bound native elements when enabled. On native runs you may use `read-elements --view locator` to navigate the source yourself; the hints do not satisfy any independent checks. Probe actual direct image capability early when graphical/raster/conflict objects require pixels; do not invent a probe for a native-only text/table source. KEY_CLAIMS maps identity, page/section structure, figures/tables, methods/results, appendices/supplements and omission risks without recreating the notebook. FULL_DOUBLE_READ independently inventories and inspects all units. An absent mode retains legacy full-review requirements.

## Evidence review

Run `review-plan` and inspect every current claim and its complete original-source dependency chain. Independently identify unregistered report/target/synthesis conclusions, important values, causal/comparative/generalization/novelty/absence claims, qualifications and source concerns. Require registration of missing assertions. Follow [Native PDF elements](../../references/native-elements.md): inspect original pixels for all required graphical/raster/conflict units, preserving necessary parent/panel context; independently read complete validated native tables through their structured evidence. A label is not chart data. Check comparability, calculations, negative results and limits rather than reproducing captions.

For KEY_CLAIMS, compare the full Owner inventory with your source map and inspect the controller-planned stratified ordinary-unit sample: `min(N, max(5, ceil(0.20*N)))` non-key units. Expand after a substantive error; two distinct units with the same substantive error require checking that entire type. Systemic unreliable evidence or widespread omission requires FULL_DOUBLE_READ or failure. The sample is a diagnostic minimum, not an upper bound or complete independent rereading.

For FULL_DOUBLE_READ, read the body in verified section/subsection order and check every in-scope unit, informative visual/panel/table, experiment, taxonomy node and claim. The Owner's body map and coverage diagnostics cannot substitute for your own source inspection. Both modes require full Owner reading, closed reading gaps, proportionate claim evidence, aligned methods/experiments/visuals and HOLD/CONDITIONAL restrictions on unresolved source concerns. Author rhetoric, assumed equal budgets and user preferences are not verification.

Check the current target and every answer, visual provenance, backing data/calculations and finished display when a viewer is available. Disclose unavailable rendering. Files, flags, hashes and preflight cannot establish understanding or viewing.

## One actionable decision

Complete the planned review and return currently found defects together. Each repair states source location, original interpretation, actual discrepancy, impact, affected IDs and observable closure. Separate scientific errors, workflow errors and source anomalies; formatting preferences alone do not require scientific re-review. Output independent_review.json/.md and 08_repair_requests.json; truthfully decide REVISION_REQUIRED, MATERIAL_BLOCKED, VERIFIED_FOR_SCOPE or VERIFIED_WITH_USER_REVIEW.

Use the current review template. Record actual reviewer/session identity, review_mode, coverage_label, source-first evidence, checked claim/unit IDs, actual visual observations, your own structured_inspection for mandatory native tables accepted without pixels, and coverage_check. Save the actual draft and observations, then run `snapshot "<run>" --file "<review-draft.json>"` and copy all FOUR returned snapshot fields into a new review ID. Confirm inspected records did not change. Never rewrite packet/state or refresh old approval.

## Incremental reinspection

Follow [efficient reinspection](../../references/efficient-reinspection.md) and [repair synchronization](../../references/repair-synchronization.md). Keep the same actual reviewer. Inspect review-delta, repair closure, affected dependencies, new evidence and per-file dispositions. Retain only your own verified unchanged coverage and record continuation.previous_review_id, retained_unit_ids and rechecked_unit_ids. Take a fresh snapshot after inspection. Replacement reviewers disclose replacement_reason and directly check every current claim and repair they accept; predecessor notes are attributed evidence, not inherited viewing.

A failed decision returns to Owner. Repeated workflow failure goes to pipeline diagnosis before another dispatch, not automatic approval. KEY_CLAIMS acceptance is not full independent double reading.

## Explanation check in the existing review

Read [Reader explanations](../../references/reader-explanations.md). Judge whether the current report lets a reader reconstruct the problem, mechanism, metrics, each experiment comparison, visual encoding and conclusion limits without opening internal JSON. The Owner index locates passages; it does not grant your acceptance. Check all six dimensions and experiments, adapting theory/review evidence. No word count, heading, keyword or record-count score establishes quality.

In review.report_readability record your own decision=PASS|NEEDS_REPAIR, report_sha256, checked_dimensions, checked_experiment_ids and concrete assessment. Acceptance requires PASS with complete coverage. Return all explanation defects and dependencies together with scientific repairs; reuse this reviewer and check affected new assertions, without full rereading for style changes. Preserve FULL_DOUBLE_READ.

For new 2.9 runs also follow Reader explanations' presentation contract. Record `checked_section_roles` and `presentation_assessment` after judging depth, paper-type adaptation, target separation, scope honesty and evidence navigation. Name concrete missing relationships or comparisons; headings, linked files and Owner indexes do not prove sufficient explanation. Preserve the frozen contract on older runs.
