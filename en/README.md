# English execution entry

[中文版](../zh-CN/README.md)

## Revision 2.7: native source elements

Read [Native PDF elements](../references/native-elements.md). New runs obtain body text, tables and native labels from source-bound pdfplumber records before using vision. Bitmaps, graphical relationships and parsing conflicts still need actual source inspection. Complete Owner reading and both review modes remain unchanged. Existing/frozen runs retain their prior rules.

## Revision 2.6: review mode

Read [Review modes](../references/review-modes.md) before applying earlier revision guidance. New runs default to KEY_CLAIMS; FULL_DOUBLE_READ retains complete independent double reading. Missing mode retains legacy full-review behavior. The Owner still covers all source units; stage-08 scope depends on the recorded mode. Existing active/frozen runs are never migrated.

Purpose: produce traceable understanding of a paper's text, experiments, visuals, detailed structure and relevant supplements. When a paper appears unreasonable, present an evidence chain the user can inspect.

## Execution order

| Stage | File | Role | Input and gate |
|---|---|---|---|
| 00 | [Boundaries](00_governance/BOUNDARIES.md), [Coordinator prompt](00_governance/COORDINATOR_PROMPT.md) | Coordinator | Freeze task, versions, scope and ownership |
| 01 | [Sources and inventory](01_source_inventory/PROMPT.md) | Source agent | Inspect original sources and inventory all units; G0 |
| 02 | [Continuous full-text reading](02_full_text_reading/PROMPT.md) | Text agent | Cover every body section and in-scope appendix continuously |
| 03 | [Methods and taxonomy](03_methods_and_taxonomy/PROMPT.md) | Methods agent | All mechanisms, assumptions, subclasses and relations |
| 04 | [Experiments and statistics](04_experiments_and_statistics/PROMPT.md) | Experiments agent | All experiments, cases, ablations, negative results and definitions |
| 05 | [Visuals and formalism](05_visuals_and_formalism/PROMPT.md) | Visual agent | Every figure/panel, table/note, equation, algorithm and text relation |
| 06 | [Cross-checks and anomalies](06_evidence_and_anomalies/PROMPT.md) | Verification agent | Link methods, experiments, visuals and claims; G1/G2 |
| 07 | [Report and user-review packet](07_report_and_user_review/PROMPT.md) | Writing agent | Complete notebook, readable report and issue presentation |
| 08 | [Independent acceptance](08_independent_acceptance/PROMPT.md) | Independent reviewer | Inspect sources before comparing deliverables; decide G3 |
| 09 | [Cross-paper synthesis](09_cross_paper_synthesis/PROMPT.md) | Synthesis agent | Use G3-accepted claims with their restrictions |

Stages 01–07 are responsibilities normally performed by one Owner. Add a specialist only for a concrete source difficulty; provide full source access and merge discoveries without overwrites. Stage 07 follows 06. Stage 08 returns defects to their owning stage and rechecks repairs. Any new factual claim or comparison introduced by 09 also requires stage-08 review.

Each agent first reads the [boundaries](00_governance/BOUNDARIES.md) and [handoff data contract](DATA_CONTRACT.md), then its role prompt. The coordinator supplies a populated task JSON, source root, assigned unit IDs, output directory and available handoffs. “You” in a prompt means the assigned agent, not the paper's author.

## Delivery principles

One Owner closes each paper's full scope. A visual agent must not assume the experiments agent read a panel, or vice versa. Long sources may be divided into chunks, but every chunk must be merged; context or page budgets cannot silently truncate the assignment.

A reader-facing summary may be concise. The underlying notebook must retain every information unit. Coverage, understanding and verification come before compression; a short target report must not narrow source reading.


Use the [acceptance scenarios](ACCEPTANCE_CASES.md) to detect omitted panels/supplements, mixed metrics and unsupported author-error verdicts. Static validation of this package is not evidence that real agent execution has been behaviorally validated.

## Revision 2.2: invocation starts execution

First read [execution and stopping conditions](EXECUTION.md). A skill and paper path suffice: create task/output records, execute 00–08, plan independent review and close repairs. A partial analysis is not a stopping condition. A single-paper task does not run 09.
Use the bundled local control helper in EXECUTION.md for canonical initialization, unit handoffs, failed-review repair queues and exact inspected-content snapshots. It never launches models or proves semantic acceptance. A CONTINUE assessment requires the Owner to do the returned work.

## Revision 2.3: configurable purpose and visual reports

Use [Targets and visual reports](../references/targets-and-visual-reports.md) for explicit research-target JSON, separate target analysis, original-panel galleries, derived-chart provenance and final rendering checks. A target controls additional questions and report emphasis, never complete source coverage or evidence thresholds. No target means a general paper report. Targets and displayed assets are bound to the current review snapshot.

## Revision 2.4

The shared [Reliable execution contract](../references/reliable-execution.md) is required. Graphical/raster/conflict objects require the reviewer's own visual_inspection/session/observation evidence for accepted G3; new native-acquisition runs may independently inspect validated complete tables under [Native PDF elements](../references/native-elements.md). Runs without that explicit acquisition contract retain their prior visual requirements. Use handoff-template and review-template; validate-handoff is read-only and precedes merge. Parent/panel links must be reciprocal and same_as references must resolve. Existing runs are not migrated. Templates and structural checks cannot establish actual inspection, independence or understanding. A blocked required image channel retains G3 unaccepted.
