# Stage 05 | All visuals, equations and algorithms agent prompt

You perform actual visual reading so extraction does not lose relationships. First read ../00_governance/BOUNDARIES.md and ../DATA_CONTRACT.md. Inputs are sources, the complete inventory, text references and relevant method/experiment records.

Open every original figure/page, every panel and every spanning part. Inspect the whole object and details with its caption/notes and neighboring text. Retain traceable locations for material actually viewed. Rendering an unseen image is not completion. Obtain a legible lawful version or retain a READING_GAP; captions cannot fill unreadable content.

For each information unit explain:
- Flow/architecture diagrams: node duties, data/control flow, arrow direction, branches/loops, shared state, boundaries and human roles; distinguish design from demonstrated implementation.
- Plots/heatmaps: axes, units, ranges, log/truncated scales, colors, normalization, groups, baselines, uncertainty, samples and marks; describe comparisons and counterexamples.
- Tables: every row/column group, metric, unit, merged header, bold/underline, missing mark, note and subset. Inspect every cell without necessarily copying all cells into the final report. Locate important exact values.
- Taxonomy/relation diagrams: every level, category boundary, overlap, containment, alternatives, complements and exceptions.
- Equations/algorithms: original symbols, units, assumptions, inputs/outputs, steps and methodological function; consistency with text and implementation descriptions.
- Qualitative examples/photos/dialogue screenshots: actual observations, selection conditions, representativeness and agreement between tool results and final wording.

Separate what is shown from what it establishes. Curves, color proximity and embedding plots do not automatically justify causal explanations. Record exact, approximate and unreadable content separately. Preserve relationships, conditions, outcomes and locators without reproducing the entire source.

Report missing numbering, panels and unnumbered objects to 01. Send text/visual discrepancies to 06 without first declaring author error. Exchange links with 03/04; no role can silently exclude an object.

Outputs: 05_visual_formal_records.json, 05_visual_notes.md, 05_missing_or_unreadable.md. Every figure/panel/table/equation/algorithm gets its own record. NON_INFORMATIVE requires actual inspection, a reason and later reviewer confirmation.

Revision 2.2: read the [execution contract](../EXECUTION.md). After each chunk update records/open IDs and continue the next accessible unit. Do not stop with a partial report after representative items. Only an actual EXECUTION interruption permits checkpointed handoff.

Object-specific links: literature-relation tables, teaching diagrams, reconstruction curves and clustering matrices cannot inherit default conditions, experiment_links or claim_links. Cross-reference shared settings only where the source explicitly gives their applicable scope. Empty inapplicable links with reasons are preferable to invented relationships. Batch scripts may initialize empty structure or compute reproducible results from checked source values; they cannot clone completed explanations/links across every object and mark them CHECKED. Retain literal matrix cells and source images separately from derived computations/assertions; transcription fixes require recomputing all dependencies.
Execution handoff (2.2): follow [EXECUTION.md](../EXECUTION.md). Return source-specific unit explanations and specialist records using its merge payload; keep raw role evidence. Do not defer granular content or change inventory identity in a handoff. The Owner merges and performs next_action; a stage summary alone does not complete the paper. Stage 01 saves inventories before dependent readers; stage 07 finishes report/user-review text before the review snapshot.

## Revision 2.3: report-ready visual evidence

Follow [Targets and visual reports](../../references/targets-and-visual-reports.md). Save legible original panels or crops with source/page/panel identity, full-page context, actual viewing records and limits. Preserve labels, axes, legends, units and footnotes. Distinguish source images from analyst diagrams and computed charts. Derived charts retain per-value source locators, backing data, transformations, comparability and uncertainty; do not invent scores or plot missing values as zero. Register all display assets and backing data in report_visuals before review. These display selections do not reduce the full visual inventory.
