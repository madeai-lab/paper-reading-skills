# English execution entry

[中文版](../zh-CN/README.md)

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

Stages 02–05 may run in parallel after G0 and must exchange discoveries. They begin independently from complete sources without waiting for other roles' records, then reconcile dependencies before 06. Each role writes to its own stage directory; the Owner merges them to avoid overwrites. Stage 07 follows 06. Stage 08 returns defects to their owning stage and rechecks repairs. Any new factual claim or comparison introduced by 09 also requires stage-08 review.

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

The shared [Reliable execution contract](../references/reliable-execution.md) is required. New runs bind review_requirements.direct_visual_inspection and require the reviewer's own visual_inspection/session/observation evidence for accepted G3. Use handoff-template and review-template to generate correct shapes; validate-handoff is read-only and precedes merge. Parent/panel links must be reciprocal and same_as references must resolve. Existing earlier runs are not silently migrated. Templates, viewing flags and structural checks cannot establish actual image access, independence or understanding. If reviewer image access remains unavailable after permitted local alternatives, finish accessible work and record a truthful capability block with G3 unaccepted.
