# Execution entry — current contract 2.8

Read [EXECUTION.md](EXECUTION.md), [DATA_CONTRACT.md](DATA_CONTRACT.md), [boundaries](00_governance/BOUNDARIES.md) and the coordinator prompt. At startup also read [Native elements](../references/native-elements.md), [Review modes](../references/review-modes.md) and [Reliable execution](../references/reliable-execution.md). [Architecture](../references/architecture.md) defines loading routes, module calls and ownership.

One Owner normally performs 01–07 and a distinct actual reviewer performs 08; stages do not imply headcount. A paper uses 00–08; 09 is requested synthesis only. Owner always reads all source units. Default KEY_CLAIMS checks every claim/dependency and samples ordinary units; FULL_DOUBLE_READ retains complete independent rereading. Revision 2.8 requires readable mechanisms, metrics and every experiment, assessed by the same reviewer in the existing round. Active/frozen runs are not migrated.

| Stage | Prompt |
|---|---|
| 00 | [Ownership](00_governance/COORDINATOR_PROMPT.md) |
| 01 | [Sources and inventory](01_source_inventory/PROMPT.md) |
| 02 | [Continuous reading](02_full_text_reading/PROMPT.md) |
| 03 | [Methods and taxonomy](03_methods_and_taxonomy/PROMPT.md) |
| 04 | [Experiments and statistics](04_experiments_and_statistics/PROMPT.md) |
| 05 | [Visuals and formalism](05_visuals_and_formalism/PROMPT.md) |
| 06 | [Evidence and anomalies](06_evidence_and_anomalies/PROMPT.md) |
| 07 | [Narrative and report](07_report_and_user_review/PROMPT.md) |
| 08 | [Independent review](08_independent_acceptance/PROMPT.md) |
| 09 | [Requested synthesis](09_cross_paper_synthesis/PROMPT.md) |

After each reading/handoff/repair batch run next and perform its action. Continue to independent review after reporting and reuse the actual reviewer after repairs. Notebook/index are generated from packet; a concise report cannot narrow source coverage. [Acceptance cases](ACCEPTANCE_CASES.md) describe scenarios, not completed real trials. [History](../CHANGELOG.md) is separate from current instructions.

Load English instructions regardless of report language. Set `--language` for the requested deliverable language; it does not select another prompt tree.
