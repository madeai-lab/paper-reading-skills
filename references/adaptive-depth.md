# Adaptive reading depth (new-task reading policy 2)

Read this when deciding how deeply to read a paper, when routing a screened paper, or when upgrading one. It adds depths below complete reading. It changes nothing in the complete-reading run contract (2.10), its gates or its review modes.

Order of priorities: evidence integrity, then honest completion language, then efficiency, then presentation.

## Four depths, two independent choices

| Depth | What is read | What it may claim | Record |
|---|---|---|---|
| L0 metadata screening | Title, abstract, identifiers, imported metadata | Identity, paper type, what the authors state, a routing step | Screening record |
| L1 evidence-aware skim | Selected parts of the paper: problem, method overview, key figure, headline results, conclusion, limitations | A sourced card; statements stay NOT_VERIFIED; examined and unexamined content listed | Screening record |
| L2 targeted reading | The content a research-target question needs, read in full with its context | Local claim → evidence links, valid inside the examined passages only | Screening record |
| L3 complete verified reading | Every in-scope unit | G0–G3, COMPLETE_PAPER, independent review | Run (`reading_run_control.py`) |

Reading depth and independent review scope are separate. `KEY_CLAIMS` and `FULL_DOUBLE_READ` exist only at L3 and are chosen when the run is opened, whatever depth the paper came from. L0–L2 do not dispatch paper reviewers. A main-line synthesis statement based on L2 needs a separate scoped check of that statement; neither the screening record nor a scoped receipt can pass a gate.

A depth describes work actually done. L2 completion does not mean the paper was verified. A skim that opened nothing but the abstract is L0.

## Relevance assessment

When a research target is bound, each pass rates seven dimensions separately, each with a rating (`NONE`, `LOW`, `MEDIUM`, `HIGH` or `UNKNOWN`), a written basis, an `evidence_level` and references to examined items:

| Dimension | What is judged |
|---|---|
| `topic_relevance` | Whether the paper's subject is the target's subject |
| `methodological_relevance` | Whether a method, mechanism or design in the paper bears on a target question, including one the paper uses without studying it |
| `transferability` | Whether that mechanism could be carried into the target's setting from the paper's own domain, judged on how it is stated, not on whether this paper tested the transfer |
| `evidence_adequacy` | How well this paper's own examined evidence supports what it says on the target questions |
| `novelty_potential` | How new the paper presents its contribution to be |
| `practical_applicability` | Whether conditions of use are reported: settings, costs, constraints, failure cases |
| `research_utility` | How much reading this paper would help answer the target questions overall |

Uncertainty is recorded next to them as a level and the missing information.

Keep relevance and evidence apart. A mechanism that bears on a target question but is used without an ablation, or evaluated only in another domain, is rated on `methodological_relevance` and `transferability` for what it is, and `LOW` on `evidence_adequacy`. Rating it `LOW` everywhere because the evidence is thin hides exactly the papers a cross-domain review wants to find; the missing evidence belongs in `decision_changers` and the uncertainty.

- No total, weighted or overall score is accepted. Queues compare dimensions one after another.
- `evidence_level` is `EXAMINED_SOURCE` only when body content was actually examined. An abstract is `AUTHOR_STATEMENT` or `METADATA_ONLY`.
- At L0 `evidence_adequacy` is always `UNKNOWN`: an abstract cannot establish experimental quality.
- `UNKNOWN` is not `NONE`. Use `UNKNOWN` when what you examined is silent or could not be examined, and name the missing information. Use `NONE` or `LOW` when what you examined shows the paper does not address the dimension, and say so in the basis ("the abstract describes X; no part of it concerns the target"). Rating `UNKNOWN` to stay safe defers a paper for evidence it will never contain.
- State the concrete link to target questions, the mechanisms worth study, which points are evidenced and which are only stated by the authors, why this depth is recommended, and which new evidence would change the decision.
- `novelty_potential` is a reading of the paper's own framing. It is not checked against outside literature (`novelty_externally_checked: false`). Novelty is not research value: an applied paper with no new architecture can be highly useful for method combination, deployment conditions, tool coordination or failure modes, and a novel idea can be irrelevant to the target.

Without a research target there is no relevance verdict. A paper can still be skimmed or promoted because the user asked.

## Routing

New workspaces and their papers carry `reading_policy: 2`; absence keeps the earlier routing rules. Existing workspaces, L3 runs, saved decisions and acceptance labels are not migrated. The host selects the new-task entry depth from the request; the helper recommends the **next** step on recorded evidence. It does not classify natural-language prompts.

Decisions: `PROMOTE_TO_L1`, `PROMOTE_TO_L2`, `PROMOTE_TO_L3`, `REMAIN_AT_L1`, `REMAIN_AT_L2`, `BACKGROUND_ONLY`, `DEFER_FOR_EVIDENCE`, `EXCLUDE_FOR_TARGET`. Each records `decided_by` (`ROUTER_RULES`, `AGENT_JUDGMENT` or `USER`), reasons, source references and the target it applies to. Every decision is stored with `independent_review: false`; a routing decision is never a review finding.

`recommend` applies a transparent rule baseline to the recorded ratings and returns a decision with its trace. The first matching row applies; the last three rows then adjust the result:

| Situation in the ratings | Recommendation |
|---|---|
| High research utility with high topic or methodological relevance | Research reading of the needed conclusions (via a skim if screening at L0); for a survey, locate the relevant taxonomy and selection rules. Not an automatic L3. |
| A method, transferable mechanism or deployment condition worth study, with research utility at least medium, paper not core | Targeted reading with a named focus |
| The same with low research utility (a passing remark, a mechanism the paper only touches) | No targeted reading; the mechanism stays on record in `mechanisms_worth_study` and the route follows the rows below |
| Topic or utility at least medium, nothing needing deeper reading | Skim, or stay at the current depth |
| Any deciding dimension unknown, at L0 with the full text attached | Skim: the paper in hand can settle it |
| Any deciding dimension unknown otherwise | `DEFER_FOR_EVIDENCE`, listing what is needed |
| Topic NONE and every other deciding dimension NONE or LOW | `EXCLUDE_FOR_TARGET` |
| Otherwise | `BACKGROUND_ONLY` |
| Open conflict in examined content, in a paper that is at least related | At least targeted reading of the conflicting items. In a paper with no other reason to be read, the conflict stays as a use restriction |
| Next depth needs the paper and full text is unavailable | `DEFER_FOR_EVIDENCE` |
| The user requested a deeper reading | That depth |

The deciding dimensions are topic, method, transferability, applicability and utility. Novelty and evidence adequacy never lower a route. Weak examined evidence adds a use restriction and is a reason to check, not to exclude.

Guardrails apply to every non-user decision, whether it follows the rules or the agent's own judgement:

1. An explicit user depth request is a floor. Routing may recommend more, never less. A request for L1 or L2 is met once that depth is reached. A request for complete reading keeps binding automatic routing, also after a run was opened, because only an accepted run meets it. Only the user can lower or withdraw a request, in the user's own recorded words; a `USER` decision does so and is logged in `depth_requests`.
2. Exclusion and `BACKGROUND_ONLY` need a current assessment with the pattern above and no unknown deciding dimension. Missing evidence is uncertainty and is deferred; a deferred paper stays in the queue with the evidence it waits for.
3. A router climbs L0→L1, L1→L2 or L3, L2→L3. Other jumps need the user.
4. `PROMOTE_TO_L2` names the sections, mechanisms or experiments to check.
5. `ROUTER_RULES` records the rule output unchanged. A different choice is `AGENT_JUDGMENT` with its own reasons; the rule output is kept beside it. The rules never propose a decision the guardrails refuse.
6. A decision applies to one target revision and one source version. When either changes, the decision is suspended and reported for reassessment. Examined coverage is kept; relevance, routing and exclusion are judged again.

## What the user asked bounds the work

A user instruction about depth works in both directions, and both are recorded with the user's words.

| The user said | Record | Effect |
|---|---|---|
| "Read this completely", "verify it" | `request-depth --depth L3` | A floor. Automatic routing cannot go below it. |
| "Quickly judge whether it is worth reading" | `request-depth --depth L1`, and `limit-depth --depth L1` when the user wants the judgement before anything more | Skim directly. A recommendation to read on is reported, not acted on. |
| "Only the abstract", "I have ten minutes" | `limit-depth --depth L0` (for all papers: `init --max-depth L0`, or `limit-depth` without `--paper`) | A ceiling. No pass above it is accepted and `promote` is refused. |
| "Go on", "read that one closely" | `request-depth` at the new depth | Raises the limit for that paper to the requested depth and authorizes the upgrade. A limit that already allowed the request is left as it was; complete reading beyond it still needs the user. |

For an explicit section limit, attach the PDF and **before reading** bind the user's words to verified PDF locators with `set-scope WS --paper ID --file scope.json --user-instruction "<exact instruction>"`. The file names `source_sha256` and `regions`, e.g. `[{"physical_page":24,"bbox":[89,503,524,689]}]` (illustrative, PDF points from the top left). Omit `bbox` **only** for an entirely authorized page. If the boundaries cannot be established from available locators, ask rather than opening a mixed page. No free-text parser infers permissions. A new target, request for depth or routing recommendation does not change these locators. Reassess from the authorized material; name what evidence outside it would answer the outstanding question and wait. Only on explicit user authorization replace the regions, or release the bound limit with `{"source_sha256":"…","whole_paper":true}` and the new user instruction.

The screening CLI checks `read-pages` and `render-crop` against these regions; use text view on partial pages. Whole-document `outline`/`find-text`, complete promotion/linking and detail/locator reads of partial pages are refused. `validate`, `submit` and pass preview require physical locators (including bbox on mixed pages); a section label alone is not evidence of containment. Scoped image references need source-bound crop receipts. `status.reading_scope` shows the current map; a change of source bytes requires remapping. Extraction still preprocesses the file and emits no body text to the reader. These checks do not mediate the host PDF viewer, shell, raw cache/filesystem access, external tools or direct edits to records; they do not authenticate a user's words or what a reader actually saw. Do not use those paths to read beyond the limit.

A recommendation and an upgrade are different things. `recommend` and `route` may record `PROMOTE_TO_…` above a ceiling; the paper then waits as `UPGRADE_NEEDS_USER`, and `recommend` marks `requires_user_approval`. Only the user's request turns the recommendation into reading. The later instruction wins: a limit set after a request for more withdraws that request, visibly in `depth_requests`.

## Exclusion by a stated criterion

Ratings decide most exclusions, and an unknown deciding dimension always defers. A paper that explicitly violates a criterion the workspace stated beforehand is a different case: waiting for unrelated unknowns would never end. Such a paper is excluded with `basis: STATED_CRITERION`:

- the criterion is one of the workspace's stated criteria (`init --file criteria.json`, later `set-criteria`), each worded as the condition that excludes;
- `criterion_evidence` states what the examined source says that violates it, with the examined items it comes from;
- it is recorded as `AGENT_JUDGMENT` or `USER`, never as `ROUTER_RULES`, and the rule output is kept beside it;
- a user depth request still outranks it.

Absence of information is not a violation. A criterion written for one paper is not a stated criterion. When the criteria are replaced, exclusions that cited a changed or removed wording are suspended (`CRITERION_CHANGED`) and decided again.

## When the research target changes

Two kinds of content are kept apart.

| Stays valid | Judged again for the new target |
|---|---|
| Source version, examined items and their locators, read levels, unexamined content | Relevance ratings and their basis |
| Card statements and local claims as statements about the source, with their attribution and evidence state | Routing decisions, including exclusions and their reasons |
| Conflicts and uncertainty flags | Which target question each targeted-reading focus serves, and so whether a local claim may be used as a candidate |
| Evidence tier (what depth of reading exists) | Derived outputs that show any of the above |

After `set-target`, affected papers are reported as `REASSESS_FOR_TARGET`. Local claims read for the old target are labelled `REASSESS_FOR_TARGET` in status, the matrix, the tiers export and the synthesis check; they remain citable as background about the source, not as candidates.

A changed target is not a new permission to read. Limits and scope instructions the user gave earlier stay in force; when the new target would need content beyond them, record the recommendation and ask.

`reassess` records the new judgement on existing coverage: a new assessment, a decision, and for a targeted pass a `focus_applicability` row per focus (`applies`, the current target's question IDs, a reason). It claims no reading and adds no pass. A focus judged not applicable leaves its claims as `SOURCE_NOTE_ONLY`. Read more, as a new pass, only when the new target needs content that was not examined.

## Upgrades and reuse

Allowed: L0→L1, L1→L2, L1→L3, L2→L3, and any upward step the user explicitly requests. Each needs a current promoting decision or the user request (policy 2 requires a complete-reading mandate to execute L3, not merely a recommendation), and is appended to `upgrade_history` with its trigger.

| Reused | Condition |
|---|---|
| Source file | Same bytes (SHA-256) |
| Native extraction | Same bytes and a manifest that still validates; adopted into the run instead of extracting again |
| Rendered crops | Copied as image files with their page, box and scale, so the Owner can match a crop to a unit instead of rendering it again; viewing in the new run is still required |
| Earlier examined items, card statements, local claims | Carried as leads in `handoffs/screening/`, never as read states or claims. `claim_leads.json` lists each statement with where it was read, marked TO_VERIFY: the Owner confirms, corrects or rejects each against the source and registers survivors as claims with the run's own units |

Never inherited: unit inventory and read states, G0–G3, independent review and its coverage, the claim registry, scope exclusions, report and readability records. READ or UNDERSTOOD never becomes CHECKED, at any depth.

An L3 run opened from L1 or L2 must meet COMPLETE_PAPER and G0–G3 from the beginning. In such a run:

- a unit or gate whose evidence consists only of screening notes is rejected;
- unread units stay open however they are labelled; `OUT_OF_SCOPE` and `NON_INFORMATIVE` keep their existing rules;
- a routing decision or screening note is not user authorization for `USER_DEFINED_SCOPE`;
- the promotion record and the source hash it names cannot be edited;
- the three places that mention the promotion must agree. The record `handoffs/screening/promotion.json` is the history and names, by hash, the screening snapshot it was decided on. The packet's `promotion` binds the run to that record. `task.json` carries a copy of the packet binding. A difference between task and packet, a binding that contradicts the record, a removed copy, a cited decision that was not the current one or was made on another source version or target, and a run that never carried the promoted target revision are all reported and block merges, preflight and acceptance.

A different source version invalidates coverage, assessments and decisions made on the other version. They remain as history and as `VERSION_DIFFERENCE` leads. A depth already authorized for the earlier version may be redone on the new one. A run speaks only for the bytes it reads: when another version is attached after promotion, the paper's tier no longer counts that run, and the new version can be promoted into its own run while the earlier one is kept in `l3_history`.

A refused promotion changes nothing, and a promotion that fails midway removes the run directory it had just created.

## Efficiency without a claim of savings

The layer avoids work that is not needed: no routine reviewer below L3, no second extraction of the same bytes, one prompt per depth, one record per paper with derived status tables, and presentation changes outside the reviewed run. Use the [resource ledger](output-profiles.md#resource-ledger) to record what was actually measured. No percentage saving is claimed; that needs a controlled comparison.
