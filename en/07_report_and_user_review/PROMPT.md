# Stage 07 | Reader-facing report and user-review packet

Read the [data contract](../DATA_CONTRACT.md), [boundaries](../00_governance/BOUNDARIES.md), [targets/visuals](../../references/targets-and-visual-reports.md) and [reader explanations](../../references/reader-explanations.md). Inputs are current 01–06 records and sources, not summaries alone.

The controller generates the complete notebook/material_index from packet. Confirm that every source unit, taxonomy leaf, experiment, visual, formalism and appendix has an explanation. Repair canonical records and regenerate instead of hand-editing generated outputs or adding mirrors.

Write a connected problem–mechanism–evidence–usable-conclusion narrative. Define terms; explain inputs/outputs, central components, symbols/objective terms and training versus runtime. Adapt theory/review papers to derivations or taxonomy relations. Explain metric meaning, units, denominators, direction and proxy limitations before results.

Explain every experiment/case/ablation: variation, comparator, samples/budget, actual observations and inference limits. Preserve manual intervention, shared samples, missing configurations, negative results and absent statistics. Clear tables are allowed; opaque short cells and machine-ID lookups do not replace explanations. Important numbers retain source, conditions and baseline.

Select useful actually inspected source panels with legible labels, reading guidance, source locations, full-resolution links and limits. Retain derived-chart data/transforms. Separate general findings from target inference; answer every target question, including unsupported/contrary evidence, in target_analysis.json. Register substantive new explanations as claims.

Lead user_review.md with genuine concerns changing use decisions. Preserve issue_id/version, A/B locations/images, calculations, eliminated/plausible explanations, affected/unaffected claims, HOLD/CONDITIONAL recommendations and precise double-check questions. Keep user_decision=null without an answer; local discrepancies do not invalidate a whole paper. State checked scope honestly when no concerns remain.

Complete report_readability.json from the template: six dimensions and all experiments, exact report excerpts, short assessments, valid unit links, final report hash and actual display evidence. Put machine JSON, hashes and workflow history in linked evidence, not narrative. Use neutral provenance pointing to packet/latest review rather than stale pending-review claims or post-approval status edits.

Finish all text, targets and assets and inspect final display, then pass preflight under [EXECUTION.md](../EXECUTION.md) and send to 08 for the same-round accuracy/explanation check. Owner cannot approve readability. No word-count, heading or keyword quota grants acceptance. A concise report still explains its argument; the notebook remains complete. DATA_CONTRACT.md defines output ownership.
