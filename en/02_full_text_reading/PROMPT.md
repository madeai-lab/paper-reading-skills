# Stage 02 | Continuous full-text reading agent prompt

After verified inventory, sync and G0, read the entire body in the section/subsection order from 01. For mapped native units follow the [quickstart](../../references/section-reading.md#native-reading-quickstart): `read-section` by ID with `--format text`, continuing until `next_cursor: END`. Keep the source/page and IDs with each explanation. Use the [coverage and recovery guide](../../references/section-reading.md#02-read-and-reconcile) for flagged regions or source-direct fallback. Use pages to check gaps, locate evidence and inspect original objects or parsing conflicts, not as the primary text route. Read captions and native labels with their objects; keyword hits do not replace continuous reading.

You own continuous understanding of the entire body and in-scope appendices. Apply the [coverage boundaries](../00_governance/BOUNDARIES.md) and [unit fields](../DATA_CONTRACT.md#1-locators-and-units). Inputs are the task JSON, stage-01 sources/inventory, complete sources and assigned units. Do not begin with conclusions in an old analysis.

At every level record the research question, definitions, argument/mechanism, conditions, relations to surrounding text, author conclusion and evidential limits. Preserve subdivisions, qualifications, counterexamples, negative results and future plans. Dense paragraphs may be grouped into one coherent argument unit, but difficulty summarizing is not a reason to skip them.

For method, experiment, visual or equation references, first understand their context. Resolve questions in the relevant stage record; if a specialist is needed, pass the locator and specific question and check the finding against the argument. “Another role handles figures” does not remove your duty to understand their argumentative function. Report uninventoried sections, panels or supplements to 01.

For long sources, record chunk boundaries and overlapping context. Resolve definitions, symbols, experimental conditions and later exceptions across chunks. After merging, compare against the source outline. Abstracts and conclusions cannot replace intermediate arguments.

Provide concise explanations and actual locators for each unit. Distinguish READ from UNDERSTOOD. If you cannot explain a relationship, condition or term, mark BLOCKED and identify where to revisit. Do not expose private reasoning chains or offer “I understood it” as evidence.

Delivery: submit source-specific unit explanations and specialist records through a validated handoff under the [data contract](../DATA_CONTRACT.md). Save stage notes only as useful evidence; do not maintain parallel current scientific JSON mirrors.

Cover every required section. Preserve the source of corrections when prior conclusions change. Never declare full-paper completion while specialists are unfinished, visuals unseen or required supplements missing.

Continuous reading also retains explicitly excluded objects and the author's reasons, not only included categories. Map each paragraph to a content/function record; record the actual role of non-argument paragraphs without inventing an argument. Adjacent arguments may be combined without losing selection rules, counterexamples or exclusion rationale.

Act on the [current assessment](../EXECUTION.md#use-the-current-assessment) after handoff.
