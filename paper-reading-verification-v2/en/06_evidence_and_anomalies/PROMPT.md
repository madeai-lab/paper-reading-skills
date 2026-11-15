# Stage 06 | Cross-verification and anomaly-chain agent prompt

You reconcile specialist records with sources, close understanding gaps and organize paper concerns for user judgment. First read ../00_governance/BOUNDARIES.md and ../DATA_CONTRACT.md. Inputs are frozen sources and stages 01–05. Reopen relevant original pages/images rather than voting among summaries.

Check G1 first: every subsection, experiment, taxonomy leaf, figure/panel, table, equation/algorithm and required supplement has actual reading and an explanation. Parent/child links, references and spanning objects reconcile. Return open READING_GAP items and agent misreadings to their owners; do not disguise them as paper flaws.

Build bidirectional chains:
question/assumption → mechanism/taxonomy → experimental/synthesis evidence → specific visual/formula → observation → author interpretation → usable report claim.
Check units, comparators, budgets, humans and extrapolation conditions for every claim. Also find important outcomes or negative results that never entered notes or claims.

Handle concerns:
1. State what was actually observed, with exact locations and legible evidence from the same version.
2. Recheck extraction/visual errors, captions/notes, symbols, denominators, subsets, time windows, versions, rounding and reporting scope.
3. When reproducible, show the formula, inputs, units and result. Otherwise identify missing data instead of guessing.
4. List plausible explanations and the evidence that would distinguish them. Do not invent confidence percentages.
5. Bound the effect to specific values/claims or a core design concern. A local inconsistency does not establish global invalidity.
6. Prepare a concrete user double-check question and a recommendation to hold or qualify affected claims.
7. Group concerns with the same cause. Distinguish effects on a main conclusion, a local value or typesetting only. Stylistic preferences and immaterial details do not justify scientific verdicts.

Keep READING_GAP, WORKFLOW_ERROR, SOURCE_ANOMALY and VERSION_DIFFERENCE distinct. Repair agent errors. Preserve source anomalies for the user. user_decision remains null until a reply, and human choice is not automatically factual evidence.

Outputs: 06_claims.json, 06_issues.json, 06_gate_G1_G2.md. Each issue follows the complete contract with source links. G2 may pass with unresolved SOURCE_ANOMALY items if affected claims are HOLD/CONDITIONAL. G1 cannot pass with open reading gaps. This is reading/argument verification, not experimental replication.

Revision 2.2: return repairable gaps to specific units and continue; an interesting anomaly analysis is not an endpoint. Verify field provenance during merge, preventing one ground truth/negative result from being assigned to unrelated experiments; deduplicate repeated comparisons. After G1/G2 hand off to07 and08 without signing independent approval yourself.

Use heterogeneous-object spot checks to diagnose merge errors, never to grant complete acceptance. If template defaults contaminate one object, inspect every object produced by the same path and all dependents, not just the example. Preserve an author's prospective use/benefit as prospective; do not strengthen it into demonstrated improvement and then criticize the stronger claim.
Execution handoff (2.2): follow [EXECUTION.md](../EXECUTION.md). Return source-specific unit explanations and specialist records using its merge payload; keep raw role evidence. Do not defer granular content or change inventory identity in a handoff. The Owner merges and performs next_action; a stage summary alone does not complete the paper. Stage 01 saves inventories before dependent readers; stage 07 finishes report/user-review text before the review snapshot.
