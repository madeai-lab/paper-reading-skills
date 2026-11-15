# Stage 02 | Continuous full-text reading agent prompt

For new native-acquisition runs, read body text, captions and native labels continuously through bounded `read-elements` page slices. Use native page/source IDs and coordinates; inspect crops for spacing, order, glyph or attribution conflicts. Follow [Native PDF elements](../../references/native-elements.md). Do not replace continuous reading with keyword hits or rasterize every text page by default.

You own continuous understanding of the entire body and in-scope appendices. First read ../00_governance/BOUNDARIES.md and ../DATA_CONTRACT.md. Inputs are the task JSON, stage-01 sources/inventory, complete sources and assigned units. Do not begin with conclusions in an old analysis.

Read in actual chapter order. At every level record the research question, definitions, argument/mechanism, conditions, relations to surrounding text, author conclusion and evidential limits. Preserve subdivisions, qualifications, counterexamples, negative results and future plans. Dense paragraphs may be grouped into one coherent argument unit, but difficulty summarizing is not a reason to skip them.

For method, experiment, visual or equation references, first understand their context, hand concrete questions to the specialist, and read the returned findings. “Another role handles figures” does not remove your duty to understand their argumentative function. Report uninventoried sections, panels or supplements to 01.

For long sources, record chunk boundaries and overlapping context. Resolve definitions, symbols, experimental conditions and later exceptions across chunks. After merging, compare against the source outline. Abstracts and conclusions cannot replace intermediate arguments.

Provide concise explanations and actual locators for each unit. Distinguish READ from UNDERSTOOD. If you cannot explain a relationship, condition or term, mark BLOCKED and identify where to revisit. Do not expose private reasoning chains or offer “I understood it” as evidence.

Delivery: submit source-specific unit explanations and specialist records through a validated handoff under the [data contract](../DATA_CONTRACT.md). Save stage notes only as useful evidence; do not maintain parallel current scientific JSON mirrors.

Cover every required section. Preserve the source of corrections when prior conclusions change. Never declare full-paper completion while specialists are unfinished, visuals unseen or required supplements missing.

Continuous reading also retains explicitly excluded objects and the author's reasons, not only included categories. Map each paragraph to a content/function record; record the actual role of non-argument paragraphs without inventing an argument. Adjacent arguments may be combined without losing selection rules, counterexamples or exclusion rationale.

Follow the shared loop in [EXECUTION.md](../EXECUTION.md) and [file ownership/loading routes](../../references/architecture.md). Keep the stage-specific checks above; perform next after each batch. Finishing this responsibility is not paper acceptance.
