# Version history

## Research-first reading policy 2

New tasks default to L2 for explanations, L1 for reading-value decisions, and L3 only on a complete-verification mandate. L2 may use a paper-local question without a corpus target. Stage 09 distinguishes bounded method/comparison evidence and independently checked local conclusions from whole-paper acceptance. Figure reconstruction is opt-in by need, even in L3. Short, version-bound handoffs, soft budget alerts and one default delta round limit optional work without changing any G0–G3 gate. Existing tasks are not migrated.

## Adaptive layer 1 — reading depth, screening and routing

The complete-reading run contract stays 2.10: `init`, every existing command, the templates, G0–G3, both review modes and the snapshot rules are unchanged, and no active, frozen or accepted run is migrated. This entry adds a separately versioned layer beside it.

Reading depth is now an explicit choice: L0 metadata screening, L1 evidence-aware skim, L2 targeted reading and L3 complete verified reading. L0–L2 produce screening records in a workspace driven by `reading_triage_control.py`. A record lists the items actually examined and the content not examined, keeps author statements apart from observations, and cannot hold a gate, a review or an acceptance state. Depth and independent review scope are separate: `KEY_CLAIMS` and `FULL_DOUBLE_READ` exist only at L3 and are chosen when a run is opened.

With a bound research target, a pass rates seven dimensions separately (topic, method, transferability, evidence adequacy, novelty potential, applicability, utility) with a basis, an evidence level and references. Composite scores are refused. `recommend` applies a transparent rule baseline; `route` records a decision with reasons and its decider. Guardrails apply to every non-user decision: an explicit user depth request is a floor, missing evidence defers rather than excludes, low novelty never excludes, and a router climbs one authorized step. Decisions are bound to a target revision and a source version and are suspended when either changes.

`promote` opens an ordinary complete-reading run for a screened paper. It reuses the same source bytes, adopts the validated native extraction instead of extracting again, copies rendered crops and stores earlier notes under `handoffs/screening/` as leads. No read state, gate, review, claim or scope exclusion is inherited. The packet records an optional `promotion` field; only such runs are checked against it: screening notes cannot be the sole evidence of a unit or gate and are never user authorization for a scope exclusion.

Batch screening imports CSV, TSV, JSON, BibTeX and XLSX records, merges duplicates by DOI, arXiv ID or exact normalized title, keeps versions traceable and flags conflicting identifiers instead of merging. `queue`, `flow` and `export` derive the reading queue, screening counts, decision log and comparison matrix from the records. `tiers` and `check-synthesis` let stage 09 separate accepted complete readings from targeted, skimmed and metadata-only papers.

Output profiles (`PAPER_CARD`, `QUICK_SUMMARY`, `GROUP_MEETING`, `TECHNICAL_EXPLANATION`, `PEER_REVIEW_STYLE`, `REPRODUCTION_CHECKLIST`) present existing evidence with a mandatory evidence banner and are registered outside the run, so a change of presentation does not reopen review. A resource ledger records measured helper work and host-reported model, reviewer and token usage; unreported quantities stay empty.

Consistency corrections before first use. The promotion record under `handoffs/screening/` is the authority for an upgrade; the packet binding and its `task.json` copy must agree with it and with each other, the record names the screening snapshot it was decided on by hash, and a cited decision or user request that is absent, superseded, or made on another source version or target is refused at merge, preflight and acceptance. After a research-target change, what was read and where stays valid while relevance, routing, exclusion and the link between targeted-reading focus and target questions wait for `reassess`, which records the new judgement without claiming new reading; queue, exports and the synthesis check treat the old judgement as not current. An explicit violation of a criterion stated beforehand excludes a paper on that basis with quoted source evidence, so unknown ratings on unrelated dimensions no longer defer it forever; unknown ratings alone still never exclude. A user limit on depth ("abstract only", a time budget) is recorded with `limit-depth` or `init --max-depth`: deeper reading can be recommended and is not performed until the user asks. An open conflict no longer forces deeper reading of a paper with no other reason to be read, and a version difference between a record and the attached file is a separate kind of conflict. Helper entry points also run under an isolated interpreter (`-I`).

Not included: external novelty search, HTML or interactive reports, a model launcher, and a controlled cost comparison. Local tests cover record rules and simulated flows; `evals/adaptive/` holds routing cases and a scorer for real agent output. A small trial with agents on real papers was run to find process defects; it supports no accuracy figure. No cost saving has been measured or is claimed.

Small compatible changes to existing modules: `extract_elements`, `read_elements`, `analyze`/`run_outline` and `render_crop` accept an optional source descriptor so the screening workspace uses the same extraction path; `merge` and the read-only checker call the promotion checks only when a packet carries `promotion`.

## 2.10 — late supplements and data files

Runs initialized at 2.10 can bind sources acquired after the first extraction. `extract-elements --append` extracts only newly registered AVAILABLE sources into a new `source_elements/append-NNNN/` directory and preserves the previous manifest byte for byte under `source_elements/history/`. It then atomically replaces the schema-2 manifest, whose `history` chains each step by path and SHA-256. Validation rejects any rewritten earlier entry, page or snapshot. Unbound registered sources report ELEMENTS_APPEND_REQUIRED instead of a broken run, so required supplements no longer force a continuation run or re-adoption of earlier reading.

Non-PDF supplements (CSV, TSV, XLSX, JSON, Markdown, text) are `source_kind: DATA_FILE` sources with format, actual hash, `supplement_of` and provenance (published origin, run-local acquisition record, optional ZIP member verified byte for byte). Extraction never opens them as PDFs; it records a navigation-only structure, or an explicit parse conflict. `read-data` returns bounded content by sheet/rows/fields, JSON pointer or lines using the standard library only: no formula evaluation, macros, scripts, external links or conversion. Data units record `content_reading.mode: DATA_FILE`, and every locator must resolve. Only units with inspectable tabular cells can use the data-table structured route; a scalar pointer, title, or unresolved graphic is not a table inspection. An AVAILABLE required data file now satisfies source checks truthfully. Executable package content is never a source.

Corrections to this contract: an append publishes only a complete predecessor snapshot; a changed scope reopens previously passed gates without erasing historical decisions. Data structure summaries are checked against the bound bytes. A verified decoding conflict can be resolved by syncing the correct encoding for those same bytes. `read-data` preserves JSON number tokens and supports `--chars FIRST LAST` windows in a single long text value. Checks reuse acquisition validation only within the current read-only evaluation.

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
