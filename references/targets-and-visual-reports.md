# Research targets and visual reports (revision 2.3)

Read this reference when configuring a research purpose or preparing/reviewing a report. It applies to the English instruction set; write deliverables in the user's requested language. The source-reading and independent-review requirements remain in force. New acquisitions follow [Native PDF elements](native-elements.md): body text/table cells/native labels use structured evidence first, while displayed image assets and graphical/raster/conflict content still require actual viewing. The table exception never grants a gallery image viewing flag.

## Explicit research target

`target_identity` identifies the paper. `research_target` describes why the user is reading it. Keep these distinct. Use the current user's explicit target/configuration; do not silently import a previous review direction from chat history, a legacy report, source documents or an example. If no target is supplied, leave it null and produce a general paper report. Ask only if an ambiguity changes the requested analysis; otherwise use the stated purpose and disclose assumptions.

The target can apply to a whole review, a chapter or one research question. Represent that scope in `purpose` and the questions rather than hard-coding a specific discipline. Questions are open questions; `hypotheses_to_test` are tentative, not instructions to confirm a desired conclusion. A target changes emphasis and additional analysis, never complete-paper coverage, evidence thresholds or permissions.

Use JSON and the standard-library controller:

```text
python "<skill>/scripts/reading_run_control.py" init "<new-run>" --source "<paper.pdf>" --owner "<owner>" --language en --target "<target.json>"
python "<skill>/scripts/reading_run_control.py" set-target "<run>" --file "<target.json>"
```

The controller validates and copies the explicit target into `task.json` and `paper_packet.json`. See [the example](../shared/research-target.example.json); it is an example, not a default. Required fields:

| Field | Contract |
| --- | --- |
| `schema_version` | `1` |
| `target_id`, `revision` | Stable target name and positive integer revision; changed content with the same ID requires a higher revision |
| `purpose` | Intended use and scope |
| `questions` | Nonempty array of `{id, text}`, unique question IDs |
| `comparison_dimensions` | Named comparison dimensions; empty is allowed |
| `hypotheses_to_test` | Tentative hypotheses; empty is allowed |
| `output_preferences` | Presentation preferences, such as language, audience, length or figure density; these never reduce reading coverage |

To return to general reporting, pass a JSON file containing `null` to `set-target`. Reading units and source scope remain intact. Existing reports, analyses and reviews remain historical evidence, not acceptance of the changed target. This revision uses one review envelope: changing a bound target or report requires actual reinspection. It does not implement separate portable approvals for each target. Do not rewrite an accepted legacy run merely to migrate it; use a new run/copy when experimenting.

## Separate paper findings from target analysis

Write the general `report.md` from complete evidence. Put target relevance in a clearly labeled section, linked to `target_analysis.json`. For every target question, retain an answer even when evidence is absent or contradicts the hypothesis. The analysis object contains:

```json
{
  "target_id": "agent-methodology-review",
  "target_revision": 1,
  "answers": [
    {
      "question_id": "Q1",
      "response": "Source-grounded answer or an explicit evidence gap.",
      "attribution": "ANALYST_INFERENCE",
      "supporting_claim_ids": ["CLM-01"],
      "unit_refs": ["U-01"],
      "evidence_state": "LIMITED",
      "limitations": "Conditions and what this evidence does not establish."
    }
  ]
}
```

Use the existing attribution vocabulary from B09 and support states from DATA_CONTRACT (`SUPPORTED`, `LIMITED`, `CONTRADICTED`, `UNDETERMINED`). IDs must resolve in the current packet. An unsupported answer may have empty reference arrays with an explanation; do not manufacture citations or treat `NOT_REPORTED` as evidence of absence. The controller checks target identity/revision and question coverage; the reviewer checks the actual answers, attribution and references. Reopen source reading for genuinely new claims, not just to restyle existing evidence.

## Reader-facing visual structure

New 2.9 reports use the common section roles/order in [Reader explanations](reader-explanations.md). In their target section compare the actual questions/dimensions using target, existing coverage, candidate difference/use and evidence still needed; do not impose one project's contribution list on general reading. Keep all question answers in the linked analysis. Partial material access remains visible in source scope and affected results; no presentation choice grants complete-paper acceptance.

Organize the report around the paper's question, mechanism, evidence and boundaries. Keep operational history and machine JSON in linked records. A short report still has complete evidence behind it. When useful, use:

1. A mechanism figure or a compact analyst-created Mermaid diagram, labeled as a reconstruction with unit references. Preserve feedback loops, tools and human decisions; do not invent causal arrows.
2. Original figure/panel crops beside their interpretation. Explain what the marks show, which conclusion they support and what they do not establish.
3. A compact results/evidence table preserving baselines, denominators, conditions, uncertainty and negative results. Use a chart only if it makes a quantitative relationship clearer.
4. A separate target mapping table: question, relevant evidence, possible use, limitation. Do not let target relevance substitute for scientific support.

Choose visuals by explanatory value; there is no fixed number of charts. A table may be the best visual for a qualitative paper. If the user requests original panels, embed them rather than giving only filenames. For a brief report link remaining panels through the complete notebook/gallery. Do not embed every PDF page indiscriminately.

Use standard Markdown images with meaningful alt text. Use relative, URL-encoded asset paths inside the saved report for portability; use absolute filesystem paths in the final Codex chat so local images render. Always link full resolution. Prefer a legible panel crop plus a link to the full page over a reduced whole-page screenshot. Keep axes, legends, panel labels, units, scale bars and relevant footnotes; label any crop and retain its full-page evidence. Cropping may use available deterministic local tools; no OCR, AI image reconstruction or new dependency is implied.

Actually open the selected source image/crop before recording viewing. Preserve `source_id`, physical page, object/panel and any source version in its unit. Never imply that embedding or generating an image establishes understanding.

### Local source-image gallery helper

Prepare a nonempty JSON array, with one record per displayed visual:

```json
[
  {
    "visual_id": "V1",
    "kind": "SOURCE_IMAGE",
    "title": "Original figure: mechanism",
    "unit_refs": ["U-01"],
    "artifact_refs": ["evidence/figure-01.png"],
    "caption": "Source identity, figure/panel and crop description.",
    "interpretation": "Observed relationship and supported claim.",
    "limitations": "What cannot be inferred from this panel.",
    "claim_refs": ["CLM-01"]
  }
]
```

Populate actual IDs/paths; the example is not evidence. Register each selected image in the corresponding unit's `visual_review.artifact_refs` after actually opening it, with `actually_viewed=true` and real locators. Run:

```text
python "<skill>/scripts/reading_report_assets.py" "<run>" --manifest "<visual-manifest.json>"
```

This checks local in-run image paths/extensions (PNG/JPEG/WebP), file existence, referenced units/claims and recorded viewing, generates `report_visuals.md` with inline images/full-resolution links/captions/interpretations/limits/locators, and registers `report_visuals` in the packet and deliverables. It does not decode image bytes or establish legibility; actually open images and the rendered report. It neither fetches images nor changes read states or grants approval. Copy selected image blocks into `report.md`, linking the gallery for the rest. A record claiming viewing is still subject to real tool evidence and independent review. This helper handles source images only; it is not a quantitative plotting engine.

### Derived diagrams, charts and tables

Label original evidence, analyst reconstruction and computed results distinctly. Use Mermaid for small explanatory structures, Markdown tables for mixed evidence, and available standard plotting tools for quantitative figures. Provide a static readable fallback if the delivery surface cannot render a diagram. Do not introduce a plotting dependency solely for decoration.

For each derived visual, save a record in `paper_packet.report_visuals` containing `visual_id`, `kind` (`ANALYST_DIAGRAM` or `DERIVED_CHART`), title/caption/interpretation/limitations, `unit_refs`, `claim_refs`, `artifact_refs`, and `evidence_refs`. For a quantitative chart add `data_ref` (also include it in `evidence_refs`), `transformations`, `comparability` and `uncertainty_policy`. The backing JSON/CSV records each plotted value with its unit, denominator, population/condition, baseline, source locator and exact-versus-estimated status. Register generated figures and backing data before the review snapshot. The gallery helper replaces source-image records while retaining derived visual records, rejecting colliding IDs. It does not validate the derived-chart schema or calculations; the actual reviewer checks them.

Preserve missing values as missing, not zero. Do not convert ordinal judgments into invented scores or average incomparable measures. Disclose normalization, excluded groups, estimation and calculations. State unavailable uncertainty rather than inventing error bars. Keep negative findings visible. A reconstructed diagram is an analyst interpretation, not an original figure or experimentally proven mechanism.

## Review and rendering checks

Before snapshotting, open the finished report in an available Markdown/document viewer and inspect its actual rendering: images resolve, labels are readable, captions match panels, wide tables remain usable, and target analysis is visibly separate. If the renderer is unavailable, verify assets/links locally and disclose that rendered layout remains unverified; do not claim a visual check from file existence. Rendering a PDF or starting a server is not required.

The reviewer checks the current target, every new target-specific assertion, visual provenance, backing data/calculations and finished display, in addition to existing source-first review. Captions and charts must preserve the same restrictions as claims. No presentation preference can weaken a gate.

Snapshots bind optional target/visual records, their registered assets/backing data, `report_visuals.md` and `target_analysis.json`. Simple inline Markdown image destinations in registered Markdown files are also hashed, including URL-encoded local paths; complex/reference-style Markdown and raw HTML images must use registered `artifact_refs` because the helper is not a full Markdown/HTML parser. For portable reports keep all assets inside the run. Any change to source interpretations, target, data, chart or caption requires real reinspection and a new review; never update a token in an old approval.

## Revision 2.8

Read [Reader explanations](reader-explanations.md). New reports must explain core mechanisms, metric interpretation and every experimental comparison, with a compact Owner passage index and the same independent reviewer's semantic judgment. The local preflight enforces current records and hashes, not prose quality. No extra agent, full rereading for styling, or migration of old runs is introduced.
