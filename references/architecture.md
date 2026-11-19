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
| [Depth guide](../en/triage/README.md) and en/triage/L0–L2 | Reading below complete depth; loaded instead of the stage tree |
| [Adaptive depth](adaptive-depth.md), [screening contract](screening-contract.md), [batch screening](corpus-screening.md), [output profiles](output-profiles.md) | Depth, relevance, routing, upgrade, screening records, presentation and the resource ledger |
| references/ | Shared detailed contracts |
| shared/ | Unfinished schemas and examples, not executed evidence |
| scripts/ | Deterministic helpers and tests, no model launcher |

## Progressive loading

The [stage guide](../en/README.md) owns the loading routes. This architecture reference, historical plans and human reference translations are not startup requirements. Read prose by verified section/subsection via the [section reading guide](section-reading.md); read detailed evidence by object ID or source locator. Keep the complete sources accessible.

Depth selects the tree. L0–L2 load the depth guide, one depth prompt and the contract sections that prompt names; they do not load stages 00–09. L3 loads the stage guide as before and reads nothing from the adaptive layer except, in a promoted run, the reuse rules.

## Runtime, validation and synthesis

Current contract: 2.10. One skill entrypoint routes to stage responsibilities. One Owner normally performs 01–07 and one distinct reviewer performs 08. Python manages records; the host performs reading, delegation and continuation.


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
          → reading_element_locators.py (optional read-only navigation projection)
  → reading_report_assets.py (optional inspected-image gallery)
      → reading_run_records.py (shared I/O)
```

The controller continues to re-export record helpers for existing callers. Standalone checker and gallery entrypoints remain available. Imports needed only during validation may be deferred to avoid circular initialization. No public command or data schema is changed by this module split.

```text
init → extract-elements (source-bound native pages)
 → verify source outline + locate objects → inventory/sync/G0
 → read-section by unit ID and cursor in outline order (or read source sections directly)
 → reconcile section-coverage leads; inspect original pixels / detailed object evidence
 → validate-handoff/merge → act on returned assessment (repeat)
 → G1/G2 → report/targets/assets/readability → preflight/review-plan
 → actual independent review → snapshot/ingest-review
    ├─ accepted → next + read-only checker → delivery
    └─ failed → batch repair/regenerate → repair-scan/repair-ready
                → preflight/review-delta → same reviewer → new decision
```

The adaptive layer sits beside this run controller, not inside it:

```text
Host
  → reading_triage_control.py (CLI for the screening workspace)
      → reading_corpus.py (workspace, import, de-duplication, queue, counts, exports, evidence tiers)
          → reading_triage.py (screening record, pass validation, relevance assessment, routing rules and guardrails)
      → reading_promotion.py (full-text versions, extraction reuse, promote)
          → reading_pdf_elements.py / reading_outline.py / reading_crop.py (same helpers, source descriptor supplied by the workspace)
          → reading_run_control.py initialize/commit (opens an ordinary run)
      → reading_output_profiles.py (profile plan, evidence banner, output binding)
      → reading_resources.py (measured helper work, host-reported usage)
  → reading_run_control.py / reading_run_check.py
      → reading_promotion_contracts.py (checks applied only to packets that carry `promotion`)
  → eval_adaptive_reading.py (behavioural scoring; not part of a reading task)
```

```text
import/add → L0 pass → recommend/route
   ├─ EXCLUDE_FOR_TARGET / BACKGROUND_ONLY / DEFER_FOR_EVIDENCE (recorded, target-bound)
   └─ PROMOTE_TO_L1 → attach-source → L1 pass (card + decision)
         ├─ REMAIN_AT_L1
         ├─ PROMOTE_TO_L2 → L2 pass (focus, local claims) → REMAIN_AT_L2 or PROMOTE_TO_L3
         └─ PROMOTE_TO_L3 → promote → init … G0–G3 in the run (unchanged flow above)
user depth request → any depth directly; routing cannot go below it
```

The screening record is canonical for depths L0–L2 and the packet for L3. The only link is the promotion record; neither side mirrors the other's state.

`next` selects missing work from current evidence/state, not a numeric agent schedule. CONTINUE requires host action; repair, interruption and stale evidence can reopen earlier work.

Passing records cannot authenticate the actions they describe. Both modes require full Owner reading; only FULL_DOUBLE_READ denotes complete independent double reading.

For the formal, fully verified corpus route, run 00–08 per paper, then 09 preserves all target-paper states and uses G3-approved claims within allowed_use. New comparisons retain paper/claim/version/source and comparability conditions and receive stage-08 review. The controller remains per-paper; the host maintains synthesis scope and coordination under 09. There is no aggregate acceptance CLI and per-paper acceptance does not approve new synthesis. A screening workspace reports each paper's evidence tier from its actual state and checks that synthesis claims do not present lower tiers as accepted evidence; that check is structural and grants nothing.

## Automated checks and semantic work

| Gate | Automated checks | Actual semantic work |
|---|---|---|
| G0 | Inventory, IDs, references and hashes | Establish source identity, scope and omissions against all pages |
| G1 | Unit records and native/visual evidence contracts | Read every unit and understand conditions and relationships |
| G2 | Links, gate evidence and restrictions | Check comparisons, inference limits, negative results and anomalies |
| G3 | Mode coverage, identity fields, snapshots and passage index | Independently judge source accuracy, completeness and readability |
