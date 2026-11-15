# Stage 01 | Sources and complete-inventory agent prompt

You establish a source-first scope baseline, not a claim that the paper is understood. First read ../00_governance/BOUNDARIES.md and ../DATA_CONTRACT.md. Inputs are a populated task JSON, the selected paper version and source locations.

For new native-acquisition runs, first follow [Native PDF elements](../../references/native-elements.md): extract source-bound page elements and read every page through bounded slices. Open the source and verify title, authors, identifier and version. Record actual PDF pages, web structure, appendices and supplement relations. Compute local hashes rather than inventing them. Reject links to unrelated or merely similarly named articles. Inventory each referenced Supplementary Note/Figure/Table and establish availability; unavailable does not mean nonexistent.

Inventory from sources:
- Every section/subsection level and page range, including introduction, related work, methods, results, discussion and appendices.
- Every figure, panel, table, equation, algorithm and unnumbered information-bearing illustration, with textual references.
- Every experiment, case, ablation, sensitivity analysis and failure/negative-result clue.
- Every taxonomy level; spanning objects, numbering gaps/duplicates and composite objects.
- Scope boundaries for code, raw data and externally cited papers; do not expand into experimental replication on your own.

Inspect native page elements/layouts or web blocks directly; actually open graphical/raster regions and parsing conflicts. Do not rasterize ordinary text pages by default. Searching for Fig/Table or reading a contents page alone cannot establish the inventory. Reconcile object lists, body references, appendix numbering and objects actually present on pages.

Give every unit a stable ID and parent/child links. Keep units INVENTORIED until comprehension is established; do not invent understanding_note content. G0 may permit limited work on available sources, but required missing sources stay on the inventory.

Outputs: 01_sources.json, 01_inventory.json, 01_scope_gaps.md. Recommend G0 with evidence; inventory completion does not pass G1 or G3. Repair omissions discovered later, increment scope_revision and preserve the change record.

Follow the shared loop in [EXECUTION.md](../EXECUTION.md) and [file ownership/loading routes](../../references/architecture.md). Keep the stage-specific checks above; perform next after each batch. Finishing this responsibility is not paper acceptance.
