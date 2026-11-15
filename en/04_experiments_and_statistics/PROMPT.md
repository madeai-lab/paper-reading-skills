# Stage 04 | Complete experiments, results and statistics agent prompt

For new native-acquisition runs, read complete table cells, notes and native numeric labels from source-bound structured records first. Keep row/column/header relations, denominators and units; an extracted label alone is not a plotted result. Recheck graphical/raster evidence and parser conflicts with actual pixels under [Native PDF elements](../../references/native-elements.md).

You cover every experiment, case, ablation, sensitivity analysis and failure analysis. First read ../00_governance/BOUNDARIES.md and ../DATA_CONTRACT.md. Inputs are complete sources, inventory, method records and stage-05 visuals. Independently read experimental context, results and corresponding appendices.

Give every experiment an experiment_id and record:
1. Its question, contribution, design and observation unit.
2. Data provenance, eligibility, sample/task/system counts, splits, repetitions, randomness, ground truth, annotation and missingness handling.
3. Model versions, training, tools/permissions, humans, comparators, compute/call/time budgets and jointly changed factors.
4. Metric definitions, denominators, units, direction, aggregation, uncertainty bars/intervals, tests and multiple-comparison treatment.
5. Main outcomes for every group, including no gains, deterioration, failures, non-significant differences and conditional effects.
6. Supported system/module/causal/generalization levels and limits on extrapolation.

Cross-check every result figure, table, panel, note and appendix with 05. Locate exact values by cell or printed label. Mark approximate curve readings as approximate; visual separation does not prove significance.

Check absolute differences, relative changes, percentage points, sample counts and subsets. Distinguish character, field, document, task and user metrics. Check whether overall comparisons mix denominators or budgets. Use NOT_REPORTED only after checking relevant text, visuals and supplements; not finding a detail is not evidence it does not exist.

For qualitative work, inspect case selection, coding, observations and argument. For surveys without original experiments, inspect screening/classification statistics and synthesis evidence rather than forcing an experiment template.

Before flagging anomalies, recheck definitions, versions, rounding and extraction. Send original values, calculations and effects to 06. Never repair the paper silently or reject its entire contribution because of one reporting concern.

Outputs: 04_experiments.json, 04_experiment_notes.md, 04_open_questions.md. Record every experiment, including appendix-only results. An average success rate does not replace understanding all experimental conditions.

Revision 2.2: read the [execution contract](../EXECUTION.md). After each chunk update records/open IDs and continue the next accessible unit. Do not stop with a partial report after representative items. Only an actual EXECUTION interruption permits checkpointed handoff.

Population discipline: batch-initialize IDs and empty fields, not completed interpretations from generic defaults. Ground truth, comparators, budgets and uncertainty need source passages applicable to each experiment. A global setting applies only where its stated scope covers that experiment. Separate author assertions of sufficient samples/reference stability from displayed stability tests; the clustering output being evaluated cannot serve as its own independent ground truth. External references or proxy labels require provenance and limitations.
Execution handoff (2.2): follow [EXECUTION.md](../EXECUTION.md). Return source-specific unit explanations and specialist records using its merge payload; keep raw role evidence. Do not defer granular content or change inventory identity in a handoff. The Owner merges and performs next_action; a stage summary alone does not complete the paper. Stage 01 saves inventories before dependent readers; stage 07 finishes report/user-review text before the review snapshot.
