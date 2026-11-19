# Adaptive reading layer: status, limits and open work

Status on 2026-11-19 for adaptive layer 1. The runtime rules are in [adaptive depth](../references/adaptive-depth.md) and the [screening contract](../references/screening-contract.md); this note records what is and is not done.

## Limits of the earlier architecture that this layer addresses

- One depth. Every paper took the full Owner reading plus independent review, whatever its relevance to the research purpose.
- No record below complete reading. A quick look had no place to state what was examined, so it either became an unrecorded summary or an unfinished run.
- A research target added questions to a complete reading but could not help decide which papers to read.
- Synthesis accepted only G3-accepted packets or an "explicitly incomplete" label, with no vocabulary for targeted, skimmed and metadata-only papers.
- No candidate-set handling: no import, de-duplication, queue or screening log.
- A presentation change inside a run changed the reviewed content fingerprint and reopened review.
- Cost was not recorded anywhere.

## Mechanisms reused, and from where

Most mechanisms were taken from this repository's own contract rather than from other skills, to keep one consistent set of rules:

- Validate-then-submit passes with source-specific content, mirroring `validate-handoff` and `merge`.
- Version binding by SHA-256 and invalidation on change, mirroring review snapshots and B16.
- Append-only history with superseded entries kept, mirroring manifest history and review records.
- The existing versioned research target, attribution types (B09) and support states.
- Derived views instead of stored mirrors, following the canonical-record rule.

From outside the repository:

- Progressive loading by task, the general Agent Skills convention already used here: one depth prompt per depth, the stage tree only at L3.
- The PRISMA flow idea of counting records identified, merged, screened and excluded with reasons, enforced as a protocol only in `SYSTEMATIC_REVIEW` mode.
- Ordinal, per-criterion judgement without a composite score, as in multi-criteria screening forms.

No third-party skill repository was surveyed for this work. A comparison with other reading or review skills remains open.

## Implemented

Phase 1: depths L0–L3, screening records, relevance assessment, rule-based routing with guardrails, user override and depth floor, target and version invalidation, upgrade history, promotion with reuse of source, extraction and crops.

Phase 2: import from CSV, TSV, JSON, BibTeX and XLSX; de-duplication with version tracking; queue; flow counts; decision log and comparison matrix exports; evidence tiers and the synthesis claim check for stage 09; linking existing runs.

Phase 3, partly: output profiles with evidence banner and binding; resource ledger; behavioural evaluation cases and scorer.

## Not implemented

| Item | Why | What is needed |
|---|---|---|
| External novelty assessment | Needs literature search and a rule for what counts as prior work; unverifiable from the paper alone | A search-backed record with sources per novelty statement; until then `novelty_externally_checked` stays false |
| HTML and interactive reports | Optional presentation; adds dependencies | A profile renderer that reads the same records and banner |
| Automated semantic assessment of scoped L2 reviews | Stage 09 checks local bindings, writer separation and recorded verdict; it cannot authenticate understanding | Keep real source-based independent judgement |
| Instrumentation inside the run controller | Read-only run commands must stay read-only, and files added to a run change its fingerprint | A ledger outside the run keyed by run ID, or host-level telemetry |
| Fuzzy title matching and author-based de-duplication | Risk of silent wrong merges | A reviewed "possible duplicate" resolution command |
| Resolving `possible_duplicate_of` | Needs a person's decision | A merge or keep-separate command with a recorded reason |
| Reviving passes when an earlier source version is attached again | Rare; kept simple | Status restore when the hash matches a stale pass |
| Non-PDF full text for complete reading | The run requires a PDF source | Out of scope for this layer |
| Host-wide enforcement of section permissions | Screening helpers enforce explicitly mapped physical pages/rectangles; host viewers, raw files and arbitrary tools are outside that boundary | No general permission framework planned |
| A later pass at the same depth that extends an earlier one | Today the later pass replaces the earlier one and carried-over items must be restated | An `extends` link that keeps both passes valid and merges their views |
| Comparing two source versions | The second skim rests on the reader's memory of the first | A diff of extracted text by page between versions |
| Correcting bibliographic fields of an imported record | Only conflicts can be recorded today | An amend command with history |
| Figures mislabelled as tables, and tables missed, by `outline` | Inherited from the shared extraction heuristics | Outside this layer |
| Controlled cost comparison and any accuracy figure | The trial below is too small and has no comparison arm | See the benchmark plan |

## Verification actually performed

Four kinds of evidence exist. None substitutes for another.

**Code exists and local rules hold.** The suite passes with the default interpreter (tests needing pdfplumber skipped) and, with no skips, with the provisioned interpreter that has pdfplumber and pypdfium2. One exhaustive test checks every combination of the five deciding ratings at each depth: the rule output is always accepted by the guardrails, and no combination containing an unknown rating is excluded or demoted. Mutation checks disabled guards one at a time in a temporary copy; the tests failed for all but one equivalent mutant.

**Existing runs behave as before.** Eight real runs kept from earlier work (contract 2.9 and 2.10; two accepted, one interrupted, one awaiting revision, four in progress) were given nine read-only commands each with the scripts at HEAD and with the working tree. All 72 outputs were byte-identical and no file in those runs changed. This covers read-only assessment, preflight, review planning, snapshots and native reads; mutating commands are covered by the unchanged existing tests, not by this comparison.

**A real flow ran, once.** Agents given only the skill, natural-language tasks and files processed six real papers around one research purpose on 2026-11-19 and 20: batch screening of five candidates, an abstract-only request, a quick-judgement request, a source-version change, a research-target change, and one upgrade from targeted reading into a complete-reading run with a separate reviewer agent. Expectations were written before the agents started and kept outside their directories. The record is in the local `eval-runs/adaptive-e2e-20261119/` directory, which is not part of the repository.

**What that flow does and does not show.** It found process defects, listed in the changelog entry, and several were fixed and one of them retested. It is one run per scenario on a handful of papers, with the person who wrote the skill writing the expectations: it supports no accuracy figure, no miss rate and no statement about stability. Efficiency was observed only as counts (extraction calls, repeated page reads, reviewer calls by depth); there is no comparison arm, so no saving is claimed.
