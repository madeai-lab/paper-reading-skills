# Version history

## 2.10 — late supplements and data files

Runs initialized at 2.10 can bind sources acquired after the first extraction. `extract-elements --append` extracts only newly registered AVAILABLE sources into a new `source_elements/append-NNNN/` directory and preserves the previous manifest byte for byte under `source_elements/history/`. It then atomically replaces the schema-2 manifest, whose `history` chains each step by path and SHA-256. Validation rejects any rewritten earlier entry, page or snapshot. Unbound registered sources report ELEMENTS_APPEND_REQUIRED instead of a broken run, so required supplements no longer force a continuation run or re-adoption of earlier reading.

Non-PDF supplements (CSV, TSV, XLSX, JSON, Markdown, text) are `source_kind: DATA_FILE` sources with format, actual hash, `supplement_of` and provenance (published origin, run-local acquisition record, optional ZIP member verified byte for byte). Extraction never opens them as PDFs; it records a navigation-only structure, or an explicit parse conflict. `read-data` returns bounded content by sheet/rows/fields, JSON pointer or lines using the standard library only: no formula evaluation, macros, scripts, external links or conversion. Data units record `content_reading.mode: DATA_FILE`, and every locator must resolve. A resolving data TABLE uses the structured route instead of a fabricated pixel view, and needs the reviewer's own structured inspection. An AVAILABLE required data file now satisfies source checks truthfully. Executable package content is never a source.

Runs initialized at 2.7–2.9 keep schema-1 manifests, single extraction and their continuation-run route; append and DATA_FILE are refused there. Existing active or frozen runs are not migrated.

## 2.9 — consistent report delivery

New runs share ordered semantic report sections with localized headings and paper-specific depth. Explicit targets receive a separate coverage/difference/evidence-needed comparison; general reading has no invented target. The existing readability record indexes sections and the same reviewer assesses presentation alongside source accuracy. Local checks validate section locations, registered navigation, portable inline links/images and current reviewer coverage, without word-count or heading-based semantic approval. Active/frozen 2.8 runs retain their original contract.

Compatibility correction: a later actual accepted review closes the previous failed round's repair-sync obligations. Current-content fingerprint changes still invalidate acceptance, and active failures still require valid synchronization before review ingestion. This avoids an unrecoverable request for historical repair IDs after acceptance; it does not rewrite or synthesize review decisions.

Workflow-only update: load contracts at their point of use, act on the controller assessment already returned after a handoff, and exchange evidence locators rather than parallel table transcripts. CLI commands, data schemas, reading scope, the independent review and final delivery checks are unchanged.

Additive CLI view: `read-elements --view locator` returns lightweight figure/table navigation from existing frozen page records. Default detail reads, native evidence format and acceptance rules are unchanged.

Full body reading follows verified section/subsection order. `read-section` joins explicitly mapped native spans with bounded continuation; `section-coverage` checks physical-page assignments for gaps and overlaps without certifying understanding. Existing runs are not migrated.

Owner workflow helpers: `outline` proposes headings and optional inventory scaffolding before G0. Plain-text section reads preserve source anchors and continuation, detailed coverage identifies remaining word ranges, and `render-crop` produces a new local evidence image from a frozen source rectangle. No helper certifies reading, actual viewing or review. Existing default JSON reads are retained.

## 2.8 — reader-facing explanations

Imported the reusable update from the local paper-agent skill identified by the referenced chat. Reports explain problem, mechanism, metrics, every experiment, visuals and limitations. report_readability.json binds Owner passage checks to report bytes; the existing independent reviewer supplies the semantic decision. No additional reviewer or automatic full rereading is introduced. Existing runs remain unchanged.

Maintenance on 2026-11-16 consolidates current bilingual instructions, progressive loading, record ownership and module boundaries. Public CLI commands and data contracts stay at 2.8. Personal queues, trial outputs and historical validation reports from the source project are not imported. Local tests must be rerun here; results from another chat are not validation of this checkout.

## 2.7 — native source elements

Source-bound pdfplumber elements, bounded page/region reading, conflict evidence and a narrow complete-native-table structured-inspection alternative. Required graphics and bitmaps still need actual viewing.

## 2.6 — review scope and continuation

KEY_CLAIMS defaults to independent checking of all claims and their dependencies plus stratified ordinary sampling. FULL_DOUBLE_READ retains all-unit independent review. Preflight, delta review and same-reviewer continuation reduce unnecessary repeated work without claiming measured savings.

## 2.5 — repair synchronization

Per-file repair dispositions and content-sensitive readiness prevent stale current documents from bypassing reinspection.

## 2.4 — reliable execution

Reviewer pixel evidence, validated handoffs, reference integrity and complete report display inspection.

## 2.3 — explicit research targets and visual reports

Versioned targets, separate target analysis, original-panel galleries and derived-chart provenance.

## 2.2 and earlier

Canonical initialization, handoffs, next-action assessment, failed-review repair queues and review snapshots support the complete-reading boundary and independent acceptance. Commits for 2.2, 2.4 and 2.5 were reconstructed from available snapshots; no separate 2.3 snapshot was imported into this repository.

### English-only runtime instructions

Operational documents now load only the English prompt tree and references. Chinese human reference material was preserved outside this repository before removal from the runtime package. Report-language choices and existing run records are unchanged. This removes duplicate-language routing; no measured token-saving percentage is claimed.
