# L2 | Research reading

Deliver an explanation someone can use, not a certificate about the whole paper. Start directly at L2 for “explain the method and contributions”, “精读这篇”, or “what can I use in my review?”; do not pay for separate L0 and L1 passes first. In a new screening workspace, `add --depth L2 --user-instruction "<actual request>"` (or `request-depth` for an existing candidate) records that interpretation. Attach the right version. Bind section-only instructions [before body access](../../references/adaptive-depth.md#what-the-user-asked-bounds-the-work).

**Work backwards from intended statements.** For an explanation without an external research target, leave `research_target` null. Use the actual question or a paper-specific explanatory question as the focus `description`, with `question_ids: []`. For a bound target, link its real question IDs. State the handful of questions the deliverable needs; do not turn these into an inventory of all possible questions.

| I intend to say… | Read together before saying it |
|---|---|
| “The authors propose X” | The relevant passage; attribute the proposal. Do not turn it into an observed effect. |
| “This method coordinates components in this way” | Definitions, mechanism and necessary context; inspect an architecture diagram if it uniquely shows the information flow. |
| “A outperformed B” | The result itself, metric/direction, comparator, population or split, budget and relevant notes. If conditions differ, qualify the comparison. |
| “X caused the improvement” | The relevant control or ablation, what actually varied and alternative explanations. Without isolation, report the configuration result and leave the attribution open. |

For each statement retain its locator(s), attribution, scope/conditions, contrary evidence and limits. Follow references to a relevant exception, negative result or failed comparison within the authorized scope; do not search only for support. Use the [figure ladder](../../references/research-work.md#figure-ladder) instead of routinely deriving numbers. On a genuine contradiction check definitions, versions and extraction; retain OPEN if unresolved.

**Stop** when each intended statement is supported at its stated strength or left LIMITED, CONTRADICTED or UNDETERMINED with the missing evidence named. “Not found in the sections read” is not “absent from the paper”. If answering would require unauthorized material, give the smallest proposed next read and wait. High importance alone requires neither whole-paper reading nor a reviewer.

Submit `targeted.focus`, `local_claims`, `scope_statement`, examined and unexamined content via the [pass contract](../../references/screening-contract.md#passes). A sourced `REMAIN_AT_L2` records a completed research task, not a failed L3. Deliver a readable explanation with source/version, conclusions and their boundaries. For [synthesis](../09_cross_paper_synthesis/PROMPT.md), a main-line conclusion needs a distinct source-based check of that particular use, not a second reading of the paper. A target change calls for reassessment, not new reading permission.
