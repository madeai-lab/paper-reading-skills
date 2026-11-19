# Stage 01 | Sources and complete-inventory agent prompt

You establish a source-first scope baseline, not a claim that the paper is understood. Use the [coverage boundaries](../00_governance/BOUNDARIES.md) and [locator/unit fields](../DATA_CONTRACT.md#1-locators-and-units). Inputs are a populated task JSON, the selected paper version and source locations.

Open the source and verify title, authors, identifier and version. For new native-acquisition runs, [extract native elements once](../../references/native-elements.md#extract-once-read-bounded-source-slices). Verify the outline and transitions as described in [section reading](../../references/section-reading.md#01-map-the-source-outline); bind native body locators where applicable. Inventory is not a preliminary page-by-page reading pass. Record physical pages for coverage and location, or web headings/blocks, and identify appendices and supplement relations. Compute local hashes rather than inventing them. Reject links to unrelated or merely similarly named articles. Inventory each referenced Supplementary Note/Figure/Table and establish availability; unavailable does not mean nonexistent.

Inventory from sources:
- Every section/subsection level in source order, with source locators, including introduction, related work, methods, results, discussion and appendices.
- Every figure, panel, table, equation, algorithm and unnumbered information-bearing illustration, with textual references.
- Every experiment, case, ablation, sensitivity analysis and failure/negative-result clue.
- Every taxonomy level; spanning objects, numbering gaps/duplicates and composite objects.
- Scope boundaries for code, raw data and externally cited papers; do not expand into experimental replication on your own.

Use `read-elements --view locator` to find candidate table, bitmap and drawing regions on relevant pages. Cross-check them against the original layout, captions and body references; missing or overlapping boxes do not remove units. Inspect native page elements/layouts or web blocks directly; actually open graphical/raster regions and parsing conflicts. Do not rasterize ordinary text pages by default. Searching for Fig/Table or reading a contents page alone cannot establish the inventory. Reconcile object lists, body references, appendix numbering and objects actually present on pages.

Give every unit a stable ID and parent/child links. Keep units INVENTORIED until comprehension is established; do not invent understanding_note content. G0 may permit limited work on available sources, but required missing sources stay on the inventory.

Outputs: 01_sources.json, 01_inventory.json, 01_scope_gaps.md. Recommend G0 with evidence; inventory completion does not pass G1 or G3. Repair omissions discovered later, increment scope_revision and preserve the change record.

Use the [handoff and assessment loop](../EXECUTION.md#read-hand-off-and-verify-locally) to submit G0.
