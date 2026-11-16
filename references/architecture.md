# Architecture and loading routes

All operational instructions are English. Reports and evidence prose still use the requested language; `--language` selects deliverable language, not another prompt tree.

## Authorities

| File or directory | Responsibility |
|---|---|
| [SKILL.md](../SKILL.md) | Activation, core constraints and loading routes |
| [Execution entry](../en/README.md) | Stage navigation |
| [EXECUTION.md](../en/EXECUTION.md) | Commands, continuation and terminal decisions |
| [DATA_CONTRACT.md](../en/DATA_CONTRACT.md) | Record ownership, handoffs and schema references |
| [Boundaries](../en/00_governance/BOUNDARIES.md) | Complete coverage and G0–G3 |
| [Coordinator](../en/00_governance/COORDINATOR_PROMPT.md) | Owner responsibility and review coordination |
| en/01–09 | Stage-specific responsibilities, not separate skills |
| references/ | Shared detailed contracts |
| shared/ | Unfinished schemas and examples, not executed evidence |
| scripts/ | Deterministic helpers and tests, no model launcher |

## Progressive loading

| When | Load |
|---|---|
| Startup | SKILL, execution entry, EXECUTION, DATA_CONTRACT, boundaries/coordinator; [Native elements](native-elements.md), [Review modes](review-modes.md), [Reliable execution](reliable-execution.md) |
| Reading | Current role prompt and source slices, not full notebooks repeatedly |
| Target or report | [Targets and visuals](targets-and-visual-reports.md), [Reader explanations](reader-explanations.md), 07 |
| Initial review | 08 and relevant evidence contracts; source-first map before drafts |
| Repair | [Repair synchronization](repair-synchronization.md), [Efficient reinspection](efficient-reinspection.md); compact deltas and paths to the same reviewer |
| Synthesis | 09, current paper packets/reviews/restrictions; new assertions return to 08 |

Do not load human reference translations, historical plans or whole source trees as routine runtime context.

## Runtime, validation and synthesis

Current contract: 2.9. One skill entrypoint routes to stage responsibilities. One Owner normally performs 01–07 and one distinct reviewer performs 08. Python manages records; the host performs reading, delegation and continuation.


User instructions govern scope. Role prompts cannot weaken shared boundaries. Detailed shared references are maintained in English. Resolve discrepancies against the shared contract and implementation instead of choosing a weaker rule. Changelog entries are history, not extra instructions; old runs retain their enabled contracts.


```text
Host Owner
  → reading_run_control.py (CLI, state assessment, merge/review/repair)
      → reading_run_records.py (I/O, source/content hashes, notebook/index)
      → reading_run_check.py (structural consistency)
      → reading_review_modes.py (mandatory coverage, sample, delta)
      → reading_review_contracts.py (structure and reviewer visual evidence)
      → reading_element_contracts.py (source-bound native evidence)
      → reading_report_quality.py (report passage/experiment/hash checks)
      → reading_repair_sync.py (current-file discovery and dispositions)
      → reading_pdf_elements.py (lazy extraction/read command import)
  → reading_report_assets.py (optional inspected-image gallery)
      → reading_run_records.py (shared I/O)
```

The controller continues to re-export record helpers for existing callers. Standalone checker and gallery entrypoints remain available. Imports needed only during validation may be deferred to avoid circular initialization. No public command or data schema is changed by this module split.

```text
init → extract-elements/read-elements → inventory/sync/G0
 → read + validate-handoff/merge + next (repeat)
 → G1/G2 → report/targets/assets/readability → preflight/review-plan
 → actual independent review → snapshot/ingest-review
    ├─ accepted → next + read-only checker → delivery
    └─ failed → batch repair/regenerate → repair-scan/repair-ready
                → preflight/review-delta → same reviewer → new decision
```

`next` selects missing work from current evidence/state, not a numeric agent schedule. CONTINUE requires host action; repair, interruption and stale evidence can reopen earlier work.

Passing records cannot authenticate the actions they describe. Both modes require full Owner reading; only FULL_DOUBLE_READ denotes complete independent double reading.

Run 00–08 per paper, then 09 preserves all target-paper states and uses G3-approved claims within allowed_use. New comparisons retain paper/claim/version/source and comparability conditions and receive stage-08 review. The controller remains per-paper; the host maintains synthesis scope and coordination under 09. There is no aggregate acceptance CLI and per-paper acceptance does not approve new synthesis.

## Automated checks and semantic work

| Gate | Automated checks | Actual semantic work |
|---|---|---|
| G0 | Inventory, IDs, references and hashes | Establish source identity, scope and omissions against all pages |
| G1 | Unit records and native/visual evidence contracts | Read every unit and understand conditions and relationships |
| G2 | Links, gate evidence and restrictions | Check comparisons, inference limits, negative results and anomalies |
| G3 | Mode coverage, identity fields, snapshots and passage index | Independently judge source accuracy, completeness and readability |
