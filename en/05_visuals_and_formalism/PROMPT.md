# Stage 05 | All visuals, equations and algorithms agent prompt

You read all graphical/formal content using native evidence first where applicable, retaining actual pixel inspection for graphical/raster relationships and conflicts. Follow [Native PDF elements](../../references/native-elements.md) for new acquisition runs; legacy requirements remain unchanged. Apply the [coverage boundaries](../00_governance/BOUNDARIES.md) and [visual/formal fields](../DATA_CONTRACT.md#2-specialist-records). Inputs are sources, the complete inventory, text references and relevant method/experiment records.

For native runs, locate the object with `read-elements --view locator` before requesting glyph geometry or a large region. Follow its source/page/bbox back to the original; a label preview or candidate caption is not an observation. Open every original figure, every panel and every graphical/raster spanning part; do not rasterize ordinary text pages by default. Read native table cells/headers/notes and labels from source-bound structured evidence first. Only validated complete native TABLE units can use content_reading instead of pixel viewing, without falsely setting actually_viewed. Any unresolved table/layout/glyph conflict requires actual source reinspection or a reading gap. Inspect the whole object and details with its caption/notes and neighboring text. Retain traceable locations for material actually viewed. Rendering an unseen image is not completion. Obtain a legible lawful version or retain a READING_GAP; captions cannot fill unreadable content.

For each information unit explain:
- Flow/architecture diagrams: node duties, data/control flow, arrow direction, branches/loops, shared state, boundaries and human roles; distinguish design from demonstrated implementation.
- Plots/heatmaps: axes, units, ranges, log/truncated scales, colors, normalization, groups, baselines, uncertainty, samples and marks; describe comparisons and counterexamples.
- Tables: every row/column group, metric, unit, merged header, bold/underline, missing mark, note and subset. Inspect every cell without necessarily copying all cells into the final report. Locate important exact values.
- Taxonomy/relation diagrams: every level, category boundary, overlap, containment, alternatives, complements and exceptions.
- Equations/algorithms: original symbols, units, assumptions, inputs/outputs, steps and methodological function; consistency with text and implementation descriptions.
- Qualitative examples/photos/dialogue screenshots: actual observations, selection conditions, representativeness and agreement between tool results and final wording.

Separate what is shown from what it establishes. Curves, color proximity and embedding plots do not automatically justify causal explanations. Record exact, approximate and unreadable content separately. Preserve relationships, conditions, outcomes and locators without reproducing the entire source.

Report missing numbering, panels and unnumbered objects to 01. Send text/visual discrepancies to 06 without first declaring author error. Give 03/04 the `unit_id`, source locator, encoding, reading limits and any mismatch. Keep literal cells/pixels available as evidence rather than retyping whole tables into the handoff. This does not replace inspecting each cell/panel or explaining the relationships shown.

Delivery: submit source-specific unit explanations and specialist records through a validated handoff under the [data contract](../DATA_CONTRACT.md). Save stage notes only as useful evidence; do not maintain parallel current scientific JSON mirrors.

Every figure/panel/table/equation/algorithm gets its own record. NON_INFORMATIVE requires actual inspection, a reason and later reviewer confirmation.

Object-specific links: literature-relation tables, teaching diagrams, reconstruction curves and clustering matrices cannot inherit default conditions, experiment_links or claim_links. Cross-reference shared settings only where the source explicitly gives their applicable scope. Empty inapplicable links with reasons are preferable to invented relationships. Batch scripts may initialize empty structure or compute reproducible results from checked source values; they cannot clone completed explanations/links across every object and mark them CHECKED. Retain literal matrix cells/native page evidence and any actually viewed source images separately from derived computations/assertions; transcription fixes require recomputing all dependencies.

Act on the [current assessment](../EXECUTION.md#use-the-current-assessment) after handoff.
