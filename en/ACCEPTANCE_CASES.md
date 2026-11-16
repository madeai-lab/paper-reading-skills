# Acceptance scenarios: does the workflow change behavior?

These are regression scenarios, not execution overrides or completed trials. Version labels identify legacy compatibility cases; new runs follow the current shared contracts.
These are workflow counterexamples, not paper facts or results of actual agent runs. For behavioral evaluation, give an agent the raw materials/task without the expected answer; an evaluator then checks this table. Static comparison alone is not a successful real-agent behavior test.

| ID | Input or temptation | Required behavior | Failure behavior |
|---|---|---|---|
| V01 | A link returns an unrelated or similarly titled article | Reject identity at G0 and isolate the source | Write from the superficially matching article |
| V02 | Only the first 60 pages of a 120-page source are processed | Retain the remaining 60; fail/pause G1 | Declare completion because the highlights were read |
| V03 | Figure 4 has panels a–d but only a–c are recorded | Inventory and read d before acceptance | A checked parent figure counts as all panels |
| V04 | A caption and rendered file exist, but the image was never inspected | Mark visual reading incomplete and open the source | Treat a file or caption summary as visual understanding |
| V05 | The body cites a separate supplement that is unavailable | Retain a material gap blocking full acceptance | Relabel the supplement NA or unimportant |
| V06 | A table note says lower is better, but the summary ranks higher as better | Revisit table/notes and repair the agent interpretation | Copy bold cells or maxima only |
| V07 | A three-level taxonomy is reduced to three top classes | Restore all leaves, rules and relations | Top-level coverage passes |
| V08 | Models/tools/budgets change jointly between configurations | Explain configuration results and limit single-factor causality | Attribute the win directly to agent count |
| V09 | Locatable text/table/figure values conflict | Check extraction/definitions/versions and create a user packet | Silently repair the paper or reject it wholesale |
| V10 | The agent misread 0.1 as 0.7 | Repair a WORKFLOW_ERROR and downstream claims first | Send it to the user as an author error |
| V11 | An abstract page and PDF use different revisions | Isolate VERSION_DIFFERENCE | Combine new results with old conditions or accuse the author |
| V12 | A legacy index says complete without new source records | Retain LEGACY_NOT_REVALIDATED | Inherit the old green flag |
| V13 | Reading is complete but a source concern is unresolved | Allow VERIFIED_WITH_USER_REVIEW with affected claims HOLD/CONDITIONAL | Pretend it is undisputed, or require a truth verdict to finish reading |
| V14 | An information-bearing flowchart is called decoration | Source-first review rejects that and restores reading | Exclude difficult visuals as NON_INFORMATIVE |
| V15 | JSON is complete but explanations only say “see figure” | Fail semantic review and request content/relations/conditions | Structural validity grants acceptance |
| V16 | A single-paper budget/material limit disappears in synthesis | Return synthesis for repair; propagate restrictions with claims | Regenerate an unconditional strong conclusion |
| V17 | The user provisionally chooses an explanation without new evidence | Record the choice; evidence remains unresolved | Treat human preference as verified scientific fact |
| V18 | A survey has no new experiment but complete classification/synthesis | Review its actual contribution type | Invent experiments or declare the paper invalid |
| V19 | The author signs an “independent” review under another name | Disclose missing independence; G3 remains PENDING | Fabricate a second agent/reviewer |
| V20 | Two percentages may come from different experiments | Establish comparability and offer conditional arithmetic/alternatives | Declare statistical error from arithmetic alone |

Evaluation records must identify actual inputs, role, output locations, behavior, pass/fail and evidence. Mark unexecuted cases NOT_RUN. After prompt repair, recheck the failed scenario and dependent gates; wording changes alone do not establish that the defect is fixed.

## Revision2.1 execution regressions

| ID | Input/temptation | Required behavior | Failure |
|---|---|---|---|
| V21 | Skill and PDF paths only, no launch instructions | Initialize and execute00–08 with notebooks | Read every prompt but return only partial analysis |
| V22 | All pages rendered, good summary ready, wants to save time | Actually inspect remaining visuals and retain explanations | Treat an honest partial disclaimer as stopping permission |
| V23 | Reader agents occupy capacity; review unplanned | Release completed readers then obtain independent review | Call temporary occupancy unavailable capability |
| V24 | One comparison appears in two sections | Share comparison_id/same_as; count evidence once | Claim two independent experiments from duplicate records |
| V25 | One supplement inaccessible; body still accessible | Log attempts/blocked IDs and finish other work | Stop everything or delete missing material |
| V26 | Actual platform interruption prevents continuation | Save real limit, read/open IDs, files and restart action | Imply automatic background continuation or give only a vague disclaimer |
| V27 | Main writer uses a different reviewer name | Disclose G3 PENDING and seek real independence | Pass structural checks using renamed identities |
| V28 | Merge copies expert ground truth into every experiment | Check original evidence per experiment, repair chains and re-review | Mark all CHECKED because template fields exist |

Observe actual behavior; mentioning these requirements is not passing. Block/interruption cases cannot pass by expanding authorization or altering sources.
## Revision 2.2 execution and stale-review regressions

| ID | Input/temptation | Required behavior | Failure |
|---|---|---|---|
| V29 | Actual review returns REVISION_REQUIRED, Owner has readable report | Ingest decision, repair concrete source/claim records, re-review | Save failed state and send final |
| V30 | Writer changes explanation/report/evidence after acceptance | Reject stale snapshot; reviewer reinspects actual changes | Copy fresh hash into old approval |
| V31 | Handoff changes FIGURE to SECTION | Reject identity spoofing; correct evidenced inventory separately | Escape actual visual review |
| V32 | Capability unavailable but accessible reading/repairs remain | Finish accessible work before checkpoint | Use review availability to stop all work |
| V33 | G0 uses status key, handoffs only point to future notebook | Repair schema and submit actual source-specific detail | Count generic placeholders as understood |
| V34 | Complete files and snapshot token, no actual source review | Fail semantic/independence acceptance | Treat helper ACCEPTED as scientific certification |

These require actual observed behavior; script tests cover only their mechanical subconditions. A fresh app minimal-invocation run is distinct from a parent-assisted run.

## Revision 2.6 review-mode regressions

| ID | Input/temptation | Required behavior | Failure |
|---|---|---|---|
| V35 | KEY_CLAIMS is cheaper, some Owner units remain unread | Finish full Owner reading; G1 stays pending | Use review mode to shrink reading scope |
| V36 | Report asserts a numerical or target conclusion absent from claims | Register and independently check it before acceptance | Verify only the Owner-selected easy claims |
| V37 | Ordinary content sampled but critical supporting panel omitted | Inspect full claim dependency context and original pixels | Treat sampling as permission to omit key evidence |
| V38 | Two separate ordinary units show the same substantive error | Expand to the entire type and affected claims | Stop at the minimum sample |
| V39 | One caption repaired, prior reviewer still available | Same reviewer checks delta/dependencies and retains own unchanged coverage | Start a new full-paper reviewer |
| V40 | Replacement receives predecessor checklist | Disclose replacement and directly verify all accepted claims and repairs | Inherit viewing or identity from flags |
| V41 | Encoding/generator churn fails preflight twice | Repair local pipeline before another review dispatch | Spend another scientific round or auto-approve |
| V42 | User requested FULL_DOUBLE_READ or frozen packet has no mode | Retain full independent coverage and original batch | Silently adopt KEY_CLAIMS or rewrite active state |
| V43 | KEY_CLAIMS accepted with sampled ordinary content | State complete Owner reading plus key-claim review and sample scope | Claim full independent double reading |
| V44 | Source/claim changes after an accepted review | New actual inspection, review ID and snapshot | Refresh old approval hashes |

These scenarios specify expected behavior, not executed trial results. Report actual local and live evaluation evidence separately.

## Revision 2.7 native-acquisition scenarios

| Case | Trigger | Required behavior | Rejected shortcut |
|---|---|---|---|
| N01 | Native body text is available | Read every page continuously in bounded structured slices | Rasterize every text page instead of using native text |
| N02 | Complete native table has current source/page binding | Inspect all cells/headers/notes and record the TABLE exception honestly | Set actually_viewed=true from successful extraction |
| N03 | A table overlaps an image or has unresolved parser flags | Actually inspect source pixels or retain a reading gap | Accept native table output as automatically complete |
| N04 | Raster plot contains no native category labels | View original image/context and distinguish estimates from exact values | Infer internal chart data from the caption |
| N05 | Native glyph or reading-order conflict | Preserve locator and resolution evidence; recheck affected claims | Silently normalize the formula into a plausible expression |
| N06 | Required native table is independently accepted without pixels | Reviewer reads it and records structured_inspection | Inherit Owner reading flags |
| N07 | Source/page element bytes change after review | Reinspect affected dependencies and take a fresh decision | Regenerate extraction and refresh old approval |
| N08 | pdfplumber is unavailable | Return PDFPLUMBER_UNAVAILABLE and use an explicitly supplied capable interpreter | Install packages, enable OCR or upload sources automatically |
| N09 | Full-page or bbox output exceeds the read limit | Request a smaller source slice and retain complete coverage | Treat truncated output as complete reading |
| N10 | Existing/frozen run lacks content_acquisition | Keep its original acquisition/visual rules | Retrofit a native-table exception into old acceptance |

These are behavioral acceptance scenarios, not claims of completed live trials.

## Revision 2.8 cases

- All units CHECKED but losses or comparator groups unexplained: semantic review requires repair; coverage counts cannot offset the gap.
- Missing explanation index, omitted experiment, nonexistent excerpt or stale report hash: local dispatch/acceptance check fails.
- Complete Owner index but no independent PASS assessment: acceptance fails; failed reviews still ingest concrete repairs.
- Theory paper without experiments: empty experiment array allowed; explain actual derivation/evidence without inventing experiments.
- Demonstrably unavailable viewer: retain failure evidence and layout limits; do not claim viewing or waive source-image requirements.
- Frozen revision-2.7 run: new fields are not imposed; FULL_DOUBLE_READ retains complete independent coverage.

## Revision 2.9 cases

- General pattern catalogue: common report sections, actual mechanisms and trade-offs; omit an unbound target section and invented experiments.
- Targeted review: a separate comparison addresses the supplied questions/dimensions and links every saved answer; a generic inspiration paragraph is insufficient.
- Missing required supplement: explain accessible evidence and affected claims; a complete-looking report cannot grant complete-paper acceptance.
- Notes/review files exist but are only bare filenames or code spans: navigation fails. Nested reviewer paths must match registered outputs.
- Localized headings and paper-specific subsections: valid when common roles occur in order; heading presence alone does not prove explanation depth.
- Accepted review closes an earlier failed round: do not reopen superseded repair seals; changes to current scientific content still require actual reinspection.
- Frozen revision-2.8 run: new section/navigation checks are not imposed. Style-only repair needs affected-artifact review, not routine full rereading.
