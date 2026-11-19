# Screening data contract (schema 1)

Records of the adaptive layer. They live in a screening workspace, separate from any complete-reading run. The run contract in [DATA_CONTRACT.md](../en/DATA_CONTRACT.md) is unchanged; the only link between the two is the promotion record below. Field names are English; prose may use the requested language.

## Workspace

```text
<workspace>/
  corpus.json                      target, protocol, paper IDs, import log
  records/I01-<file>               imported record files, unchanged
  papers/P0001/screening.json      the screening record (canonical for this paper)
  papers/P0001/handoffs/<sha>.json raw submitted passes (history)
  papers/P0001/versions/<sha16>/   source.pdf, source_elements/, evidence/ for one source version
  resource_log.jsonl               measured helper work and host-reported usage
  exports/                         derived logs and matrices; regenerate, never hand-edit
  outputs/P0001/                   derived presentations with their evidence binding
```

`corpus.json`: `corpus_schema_version` (1), `corpus_id`, `owner_id`, `protocol {mode, exclusion_criteria, criteria_history, depth_ceiling}`, `research_target` (the existing [versioned target](targets-and-visual-reports.md#explicit-research-target)), `target_history`, `paper_ids`, `imports`. Status tables, queues and counts are computed from the screening records; none is stored as a mirror.

## Screening record

`screening_schema_version` (1), `record_kind: SCREENING_RECORD`, `paper_id`, then:

| Field | Content |
|---|---|
| `identity` | title, authors, year, venue, doi, arxiv_id, url, `paper_type`, field, `identity_state` (METADATA_ONLY or VERIFIED_AGAINST_SOURCE) |
| `source_records` | Every imported record merged into this paper: `record_id`, `origin {import_id, file, locator}`, normalized `identifiers`, canonical `fields`, `original` values, hash. Several records are versions or duplicates of one paper |
| `possible_duplicate_of` | Papers with the same title and conflicting identifiers; flagged, not merged |
| `full_text` | `access_state`, `missing_reason`, `current_sha256`, `versions[]` with kind, path and extraction state, `version_events` |
| `depth` | `user_requested` (a floor) and `ceiling {depth, user_instruction, at}` (a limit; `depth: null` lifts a workspace-wide limit for this paper), each with the user's words; `depth_requests` logs every change. Effective depth is derived from valid passes |
| `passes[]` | One entry per submitted pass: depth, writer, time, target binding, source hash, status (CURRENT, SUPERSEDED, STALE_SOURCE_VERSION), `examined`, `not_examined`, `uncertainty_flags`, `conflicts`, and `screening`, `card` or `targeted` |
| `assessments[]` | [Relevance assessments](adaptive-depth.md#relevance-assessment) with their target binding and pass; `kind: REASSESSMENT` marks a judgement made without new reading |
| `decisions[]` | Every routing decision, including superseded ones, with `basis` RATINGS or STATED_CRITERION |
| `applicability[]` | Per target revision: for each focus of the targeted pass, whether it applies, to which questions, and why |
| `upgrade_history[]` | from, to, time, trigger, source hash, what was reused, `completion_inherited: false` |
| `l3`, `l3_history` | Link to the complete-reading run for the current source version, with `source_sha256` and `identity_binding` (SOURCE_HASH_MATCH or ASSERTED_BY_OWNER); earlier runs for other versions |
| `independent_review` | Always `NONE`. Review status of a linked run is read from that run |

Unknown schema versions are refused and never rewritten.

## Passes

A pass is a JSON object submitted with `validate` and then `submit`. Allowed top-level keys: `writer_id`, `paper_id`, `depth`, `paper_type`, `field`, `identity_check`, `examined`, `not_examined`, `uncertainty_flags`, `conflicts`, `screening`, `card`, `targeted`, `assessment`, `decision`, `notes_refs`. Use `handoff-template` for a scaffold; the [L0](../shared/screening-handoff.L0.example.json), [L1](../shared/screening-handoff.L1.example.json) and [L2](../shared/screening-handoff.L2.example.json) examples are illustrations, not evidence.

**Examined items.** `item_id`, `kind`, `label`, `read_level` (SKIMMED or READ_IN_FULL), optional `note`.

- TITLE, ABSTRACT and METADATA cite `source_ref` (the imported record). An abstract read inside the paper is still kind ABSTRACT with a locator; it is never body evidence.
- SECTION, TABLE, EQUATION, ALGORITHM, APPENDIX, SUPPLEMENT, FIGURE and OTHER_VISUAL need a `locator` with `physical_page`, `section` or `object_label`. Never guess a page. Only the locator fields of the run contract are kept.
- A figure is either `actually_viewed: true` with existing `artifact_refs`, or `caption_only: true`. A caption is not the figure.
- `artifact_refs` and `notes_refs` are files inside this paper's workspace directory; absolute paths and paths leaving it are refused. Any body item may carry `artifact_refs` when its text was checked against a rendered image, for example a formula with glyph conflicts.
- Keep the files you write (target, passes, decisions) outside the workspace directory or in a subfolder you create after `init`; `init` itself needs a directory that does not exist yet.

**Statements.** `{text, attribution, from_items}` with the four attribution types of B09. A statement whose items are metadata, an abstract or a caption cannot be `REPORTED_OBSERVATION`. All screening and skim statements are stored `NOT_VERIFIED`.

**By depth.**

- L0: `screening {full_text_read: false, potential_value[]}`. Only metadata items. `evidence_adequacy` is UNKNOWN.
- L1 under policy 2: record identity, examined and unexamined content, `card.research_problem`, `card.core_method` and a sourced decision addressing relevance and next destination. Include other statements only when examined. Legacy L1: `identity_check {state, basis}`, at least one body item, a nonempty `not_examined`, and `card {research_problem, claimed_contributions[], core_method, headline_evidence[], potential_limitations[]}`. Surveys add `taxonomy_or_scope` and may have no headline evidence. On legacy policy only, empirical papers record headline evidence or flag `HEADLINE_EVIDENCE_NOT_FOUND`. The pass ends with a `decision`.
- L2: link questions to the bound target if there is one. Under policy 2 a general paper explanation uses focus descriptions and empty question IDs with a null target; do not manufacture a target. `targeted {focus[], local_claims[], scope_statement}`. Each focus names target question IDs and items read in full. Each local claim has `evidence_state` SUPPORTED, LIMITED, CONTRADICTED or UNDETERMINED, judged only on items read in full: SUPPORTED and LIMITED need `supporting_items`, CONTRADICTED needs `conflicting_items`, UNDETERMINED needs `missing_evidence`. A local claim attributed as REPORTED_OBSERVATION names the items it was observed in, whatever its evidence state.

**Assessment.** Every rated dimension cites at least one examined item in `refs`; `target_links` and `evidenced_points` keep their defined fields only.

**Conflicts.** `{conflict_id, kind, description, items, status: OPEN|EXPLAINED, explanation}`. `kind` is `CONTENT` (examined parts of the paper disagree; the default) or `VERSION_DIFFERENCE` (an imported record and the attached file describe different versions). Leave a conflict OPEN when it could not be checked; an open version difference restricts use and is settled by obtaining the other version, so it does not send the paper to deeper reading. A deeper pass that restates a `conflict_id` replaces its status, so a conflict opened by a skim can be closed by the targeted pass that checked it. Check extraction, definitions and versions before recording one, as for any [source concern](reliable-execution.md#check-concerns-before-asking-the-user-to-judge-them).

A screening pass cannot contain `gate_results`, `gate_decisions`, G0–G3, review or reviewer fields, `read_state`, `paper_status`, or acceptance values such as `VERIFIED_FOR_SCOPE` or `CHECKED`.

## Reassessment

A reassessment is submitted with `reassess` ([example](../shared/reassessment.example.json), scaffold: `reassess-template`). Allowed keys: `writer_id`, `paper_id`, `assessment`, `decision`, `focus_applicability`. It judges [what depends on the target](adaptive-depth.md#when-the-research-target-changes) on the items already examined and is refused if it carries reading fields. When a targeted pass was read for another target revision, every focus needs a row `{focus_id, applies, question_ids, note}`.

## Decisions

`{decision, decided_by, basis, reasons[], source_refs[], focus[], evidence_needed[], decision_changers[], exclusion_criterion, criterion_evidence[], user_instruction}`. `basis` defaults to RATINGS; [STATED_CRITERION](adaptive-depth.md#exclusion-by-a-stated-criterion) needs the stated criterion and `criterion_evidence [{text, from_items}]`, and the decision stores the hash of the criterion's wording. See the [example](../shared/routing-decision.example.json) and the [guardrails](adaptive-depth.md#routing). `source_refs` name examined items, imported records or `assessment:<id>`. A `USER` decision needs `user_instruction`; never simulate one. In a SYSTEMATIC_REVIEW workspace an exclusion cites a stated criterion.

## Permitted use before complete reading

For `SCOPED_L2` use in a methods review, see the [Stage 09 requirements and receipt format](../en/09_cross_paper_synthesis/PROMPT.md). The table below describes the earlier `SCREENING_LIMITED` / `ACCEPTED` representations, which remain supported.

| Tier | Source | Use in a synthesis |
|---|---|---|
| VERIFIED_COMPLETE / VERIFIED_USER_SCOPE | Accepted run, current review | Claims within USE or acknowledged CONDITIONAL; HOLD excluded |
| TARGETED_READ | L2 | Candidate comparison citing a SUPPORTED or LIMITED local claim, with a stated limitation; CONTRADICTED and UNDETERMINED are background only |
| SKIMMED | L1 | Bounded background: what the authors state and what was seen |
| METADATA_SCREENED | L0 | Background mention only |
| UNSCREENED | — | None |

A run that is open but not accepted contributes nothing above its screening tier, and neither does a run that reads another source version than the one the record now names (`l3_state: OTHER_SOURCE_VERSION`).

## Promotion record

`promote` writes into the new run, under the existing raw-history directory:

- `handoffs/screening/promotion.json`: corpus and paper IDs, time, `from_depth`, trigger, target binding, review mode, source hash, `screening_record_sha256` and `leads_sha256`, what was reused, what was not inherited. This record is the authority for the upgrade.
- `handoffs/screening/screening_record.json` and `leads.md`: the earlier notes as leads.
- `handoffs/screening/claim_leads.json`: one row per earlier statement `{lead_id, from, text, attribution_at_screening, evidence_state_at_screening, where_to_check[], status: TO_VERIFY}`. It is a checklist, not a handoff; nothing in it can be merged.
- `evidence/screening/*.png`: crops rendered from the same bytes; the promotion record gives each crop's page, box and scale when a render receipt exists.

The run's `paper_packet.json` and `task.json` gain one optional field: `promotion {schema_version: 1, corpus_id, paper_id, from_depth, trigger, promotion_ref, promotion_sha256, source_sha256, extraction_reused}`. Checks tied to it apply only to such runs, recognized by the field or by the promotion record `promote` wrote; removing the field does not switch them off. References are compared by the file they resolve to, so a differently spelled path to a screening note is still a screening note.

| Check | Code |
|---|---|
| Packet binding missing or of another version | `PROMOTION_RECORD_INVALID` |
| `task.json` and packet bindings differ, or the binding contradicts the record | `PROMOTION_RECORDS_DISAGREE` |
| Promotion record or screening snapshot altered | `PROMOTION_RECORD_CHANGED` |
| Cited decision or user request absent, superseded, or made on another source version or target | `PROMOTION_BASIS_STALE` |
| Run source differs from the promoted version | `PROMOTION_SOURCE_MISMATCH` |
| Run never carried the promoted target revision (change targets with `set-target`) | `PROMOTION_TARGET_MISMATCH` |
| Unit or gate resting on screening notes; notes used as scope authorization | `SCREENING_NOTE_NOT_EVIDENCE`, `PROMOTION_SCOPE_ABUSE` |

A run with no promotion in its packet, its task file or its history directory was never promoted and is asked for none of this.

## Compatibility

- Complete-reading runs keep contract 2.10. `init`, every existing command, the templates and the snapshot rules are unchanged. A run created without `promote` has no new field.
- Active, frozen and accepted runs are never migrated. `link-run` records a pointer to an existing run and reads its state; it writes nothing into the run. It refuses a run already linked to another paper, a run promoted for another paper, and a run whose source differs from the attached full text. Without attached full text the link is recorded as ASSERTED_BY_OWNER.
- Screening records and corpus files carry their own schema version. Helpers refuse other versions.
- `USER_DEFINED_SCOPE` remains a user decision with evidenced authorization. Screening and routing never create scope exclusions.
