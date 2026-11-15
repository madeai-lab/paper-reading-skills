# Reader-facing explanation and acceptance (revision 2.8)

This contract applies to newly initialized revision-2.8 runs in any requested output language and either review mode. Do not migrate active or frozen runs. Complete reading, native-element acquisition and all-claim verification remain required. This adds no reader or reviewer role and no routine full-paper rereading.

## What the report must explain

Write a connected account from research question to mechanism, evidence and usable conclusions. Define specialist terms before relying on them. Keep operational IDs, gate histories and machine records in linked appendices; a reader must not need JSON or the generated notebook to understand the argument. A short summary may precede the account, but cannot replace it. Do not meet this contract with a fixed word count, heading quota or mandatory keyword list.

Use these six reader questions, adapting to the actual paper:

| Dimension | Reader question and required explanation |
| --- | --- |
| `problem` | What problem is addressed, why does it matter, and what is the claimed contribution relative to the paper's described prior work? Separate source description from independently verified background. |
| `mechanism` | What enters and leaves the method, what state changes, and why does each central component exist? Explain symbols, objective terms, assumptions, feedback, initialization and failure modes where present. Separate training from inference, model from tool, and intended interaction from measured behavior. For theory/review papers explain derivation or taxonomy relationships instead. |
| `metrics` | What does each central metric measure, which direction means what, and what cannot be inferred? Explain denominators, units, comparators, proxy measures and uncertainty before interpreting results. If there is no quantitative evaluation, explain the actual evidence standard instead. |
| `experiments` | For every recorded experiment/case/ablation, what was varied, against what comparator, on which samples and budget, what was observed, and how far does that observation support the conclusion? Preserve negative results, shared samples, missing configurations, manual interventions and absent statistics. Do not compress all designs into opaque table cells. A clear table is allowed when it actually explains the comparisons. |
| `visuals` | For the useful displayed source visuals, what do axes, marks, colors, panels and uncertainty mean? Explain the observation and its limit beside each visual; provide legible crops/full-resolution links. Link the remaining figure index. For papers without informative visuals, explain that fact rather than inventing a figure. |
| `limitations` | What can be used confidently, conditionally, or not yet? Explain missing evidence and source anomalies with location, necessary calculation, alternatives and affected conclusions. Distinguish author caveats from analyst judgments. Keep decisive qualifications beside the result as well as in any final limitations section. |

The narrative need not transcribe every source panel. The complete notebook preserves full coverage. Neither a record count nor a notebook dump compensates for an unexplained mechanism or comparison in the report. Do not replace missing source details with plausible specifications. Derived explanations and examples must be labeled as such and any substantive new assertions registered in the existing claim set.

## Compact Owner record

After finishing the report, copy `shared/report-readability.template.json` to the run's `report_readability.json`, replace template values, and set `template_only=false`. The controller registers it as `deliverables.report_readability` in new runs. Use the SHA256 of the exact final report bytes in `report_sha256`.

The record is an explanation index, not a second report. Keep one short `assessment` and one exact `report_excerpt` for each of the six dimensions, with relevant `unit_refs`. The excerpt locates the explanation; it may be just its first sentence. Assessment states what the reader can reconstruct or gives a paper-specific non-applicability reason. Do not copy whole sections, use canned identical judgments, or claim a placeholder proves comprehension. List every packet `experiment_id` once in `experiments`, with an excerpt locating its readable design/result account and a short assessment. A theory paper with no recorded experiments uses an empty array and explains its evidence type under the experiments dimension.

Record `display.status=INSPECTED` only after actual viewing, otherwise `UNAVAILABLE` with demonstrated viewer failure evidence. Both require existing local `evidence_refs` and explicit `limitations` describing the surface, scope and remaining uncertainty. Save screenshots or inspection notes; file existence or generated HTML does not establish viewing. A demonstrated unavailable renderer does not waive source image requirements. Keep final status in packet/review; use neutral report provenance pointing to those records rather than leaving misleading "currently awaiting review" prose after acceptance or editing approved report text just to update status.

## Same-reviewer semantic check

The existing independent reviewer reads the finished narrative during the existing claim/evidence review. It checks whether a reader can reconstruct all six dimensions and each experiment without opening internal JSON. Independently assess source accuracy and explanation completeness; do not approve simply because the Owner supplied excerpts. Put a short actual judgment in review `report_readability.assessment`, its `decision=PASS|NEEDS_REPAIR`, the current `report_sha256`, all six `checked_dimensions` and all current `checked_experiment_ids`. Failed decisions may carry incomplete checks and must preserve concrete repair requests. Accepted decisions require PASS with complete coverage; Owner cannot grant this decision.

Unexplained inputs, loss terms, metrics, comparison groups or uncertainty are explanation defects even if facts appear elsewhere in the notebook. Return all concrete defects together, naming the relevant report passage and source dependencies. Follow the existing repair transaction and reuse this actual reviewer. Restyling unchanged, accurate content does not require a new full source read; newly added scientific explanations require affected-claim/source checks. A replacement reviewer follows the existing independence protocol. Preserve FULL_DOUBLE_READ when selected.

The local checker validates presence, coverage, in-report excerpts, references, hashes and the independent review record. It cannot determine whether the prose is useful, whether the reviewer actually understood it, or whether the claimed viewing occurred. No keyword/length score automatically grants semantic acceptance. Quality records and changed report bytes participate in existing snapshots and repair scans.
