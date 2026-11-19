# Stage guide — current contract 2.9

At startup load [00: Owner and coordination](00_governance/COORDINATOR_PROMPT.md) and initialize as described in [SKILL.md](../SKILL.md). On resume, use `next` to locate the current action instead of starting again. Links below are routes, not a startup reading list. Read the relevant sections when their action first applies. Reuse instructions already in context; after context loss or a specialist handoff, reload what that role needs.

| Action | Load before doing the work |
|---|---|
| Bind an explicit research target (even at init) | [Explicit research target](../references/targets-and-visual-reports.md#explicit-research-target). Otherwise leave it null. |
| Extract and inventory | [01: Sources](01_source_inventory/PROMPT.md), [boundaries](00_governance/BOUNDARIES.md) and [locator/unit fields](DATA_CONTRACT.md#1-locators-and-units). Load [section reading](../references/section-reading.md) here for mapping and reuse it in 02. For native PDFs use [Native PDF elements](../references/native-elements.md) for extraction and object inspection. |
| Submit the first handoff, including G0 | [Current records and handoffs](DATA_CONTRACT.md#current-records-handoffs-and-deliverables) and [handoff validation](../references/reliable-execution.md#generate-and-validate-handoffs-before-mutation). Use the [control loop](EXECUTION.md#use-the-current-assessment). |
| Read and cross-check | The current responsibility: [02: Full text](02_full_text_reading/PROMPT.md), [03: Methods and taxonomy](03_methods_and_taxonomy/PROMPT.md), [04: Experiments](04_experiments_and_statistics/PROMPT.md), [05: Visuals and formalism](05_visuals_and_formalism/PROMPT.md) or [06: Evidence and anomalies](06_evidence_and_anomalies/PROMPT.md). Load the matching [record fields](DATA_CONTRACT.md), not the whole notebook for each handoff. |
| Prepare the report | [07: Narrative and user review](07_report_and_user_review/PROMPT.md), [targets and visuals](../references/targets-and-visual-reports.md), [reader explanations](../references/reader-explanations.md) and the [display check](../references/reliable-execution.md#test-the-actual-report-surface-then-freeze-once). |
| Prepare or dispatch independent review | [08: Independent review](08_independent_acceptance/PROMPT.md), [review modes](../references/review-modes.md) and [reviewer capability and lifetime](../references/reliable-execution.md#verify-image-capability-before-relying-on-a-reviewer). Give the reviewer sources and requirements first; withhold drafts until its own source map exists. |
| Repair a failed review | [Repair synchronization](../references/repair-synchronization.md) and [efficient reinspection](../references/efficient-reinspection.md); return the delta to the same actual reviewer. |
| Synthesize across papers, only if requested | [09: Synthesis](09_cross_paper_synthesis/PROMPT.md); retain paper-specific scope, status and restrictions. |

[EXECUTION.md](EXECUTION.md) gives procedures by action. [Architecture](../references/architecture.md) explains implementation; [acceptance cases](ACCEPTANCE_CASES.md) are evaluation scenarios, not runtime prompts or completed trials.
