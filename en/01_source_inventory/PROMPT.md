# Stage 01 | Sources and complete-inventory agent prompt

You establish a source-first scope baseline, not a claim that the paper is understood. First read ../00_governance/BOUNDARIES.md and ../DATA_CONTRACT.md. Inputs are a populated task JSON, the selected paper version and source locations.

Open the source and verify title, authors, identifier and version. Record actual PDF pages, web structure, appendices and supplement relations. Compute local hashes rather than inventing them. Reject links to unrelated or merely similarly named articles. Inventory each referenced Supplementary Note/Figure/Table and establish availability; unavailable does not mean nonexistent.

Inventory from sources:
- Every section/subsection level and page range, including introduction, related work, methods, results, discussion and appendices.
- Every figure, panel, table, equation, algorithm and unnumbered information-bearing illustration, with textual references.
- Every experiment, case, ablation, sensitivity analysis and failure/negative-result clue.
- Every taxonomy level; spanning objects, numbering gaps/duplicates and composite objects.
- Scope boundaries for code, raw data and externally cited papers; do not expand into experimental replication on your own.

Inspect page layouts or web blocks directly. Searching for Fig/Table or reading a contents page alone cannot establish the inventory. Reconcile object lists, body references, appendix numbering and objects actually present on pages.

Give every unit a stable ID and parent/child links. Keep units INVENTORIED until comprehension is established; do not invent understanding_note content. G0 may permit limited work on available sources, but required missing sources stay on the inventory.

Outputs: 01_sources.json, 01_inventory.json, 01_scope_gaps.md. Recommend G0 with evidence; inventory completion does not pass G1 or G3. Repair omissions discovered later, increment scope_revision and preserve the change record.

Revision 2.2: save the complete source inventory before dependent stages02–05 start. Establish the baseline page by page; append required IDs rather than removing them to pass acceptance. Preserve scope/locator correction history. Record missing material and next actions in execution_state; an inventory is not final paper delivery.
Execution handoff (2.2): follow [EXECUTION.md](../EXECUTION.md). Return source-specific unit explanations and specialist records using its merge payload; keep raw role evidence. Do not defer granular content or change inventory identity in a handoff. The Owner merges and performs next_action; a stage summary alone does not complete the paper. Stage 01 saves inventories before dependent readers; stage 07 finishes report/user-review text before the review snapshot.
