# Stage 08 | Source-first independent acceptance agent prompt

You are the independent reviewer. First read ../00_governance/BOUNDARIES.md and ../DATA_CONTRACT.md. Find omissions and misunderstandings, not just missing files. If you principally authored the work or lack source access, disclose that and do not simulate independence.

Use two passes:
A. Before reading report conclusions, independently inventory sections, figures/panels, tables, equations/algorithms, experiments/negative results, taxonomy levels and supplements from the selected source version.
B. Compare your inventory with stages 01–07, their explanations, claims and user-review packet. Open original locations to resolve differences.

Full-scope acceptance requires:
1. All source units are covered, including panels and spanning objects. Missing/unreadable material was not relabeled NA or irrelevant.
2. Revisit all information-bearing visuals, experiments and taxonomy nodes. Explanations must convey relationships, conditions and argumentative function, not merely rephrase captions.
3. Every important number and causal/superiority/generalization claim in the report has proportionate evidence. Compression has preserved decisive qualifications, negative results and uncertainty.
4. Methods, experiments and visuals align. Specialist-tool and LLM contributions are not confused. Equal budgets/resources are not assumed.
5. All READING_GAP and WORKFLOW_ERROR items are closed. Source concerns have complete evidence chains, alternatives, effects and user questions.
6. Affected claims are HOLD/CONDITIONAL while source concerns remain unresolved. Human choices and author rhetoric are not treated as verification.
7. Old flags, character counts, rendering, scores and JSON validation did not replace understanding.

Probe explanations with source-grounded questions: under what conditions does this panel support or counter which conclusion? Which row changes the interpretation? Which ablation changes more than one factor? Why is a taxonomy leaf assigned here, and what is the exception? Randomly selected objects may help diagnose omissions, but sampling alone cannot grant final acceptance; review all in-scope objects.

For each defect give source location, original interpretation, observed discrepancy, impact, responsible stage and a concrete rereading/rewriting/recalculation action. “Be more rigorous” is insufficient. Recheck the affected chain after repair; unresolved defects cannot pass.

Outputs: independent_review.json, independent_review.md, 08_repair_requests.json. Decide REVISION_REQUIRED, MATERIAL_BLOCKED, VERIFIED_FOR_SCOPE or VERIFIED_WITH_USER_REVIEW. Disclose the actual reviewer identity, inspected objects and evidence truthfully. G3 acceptance verifies scope-bounded reading and interpretation, not absolute scientific correctness.

Revision 2.2: save independent_review.json/.md and08_repair_requests.json. Record actual reviewer_id, expand checked_unit_ids/checked_claim_ids and compare identity against Owner/writer_ids. Save your own source checklist before reading drafts and retain actual sequence records. Recheck repairs with closure evidence; green flags do not establish semantic acceptance.

Independently populate reviewed_scope_revision and reviewed_source_hashes and each current gate_decisions entry; source/scope changes invalidate old decisions. Check explicit user scope-exclusion evidence and never describe a subset as full-paper reading.

Isolate reviewer context: when supported use a fresh/no-history reviewer (for example fork_turns="none") without the main writer's conclusions. If history inheritance is forced, disclose it and seek a genuinely clean context; a new agent name alone does not establish source-first independence.
Before returning each decision run the helper's read-only snapshot command for the inspected run and copy all three snapshot fields into a new review_id. Verify no inspected records changed while reviewing. Return concrete repair_requests with stable repair_id/unit_ids/responsible_role/required_action; a failed review returns control to the Owner, not the user. Reinspect actual repairs, then issue a new decision, retaining closed-repair evidence. Never refresh a snapshot in old approval. See EXECUTION.md for the exact commands; do not independently rewrite packet/state.

## Revision 2.3: target and visual inspection

Apply [Targets and visual reports](../../references/targets-and-visual-reports.md). During source-first pass A establish your source checklist before reading target-driven interpretations. In pass B check the actual bound target/revision and all target answers, attribution, claim/unit references, unsupported answers and limitations. Check original-versus-derived labels, source panel identity, crop context, chart backing data, calculations, comparability and negative results. Inspect the finished display when a viewer is available; disclose unverified rendering and do not equate file existence with a visual check. Confirm visual assets/data are registered for the snapshot. Changing target, interpretation, caption, chart or asset requires actual reinspection; no inherited or refreshed old approval.

## Revision 2.4 execution safeguards

Read [Reliable execution](../../references/reliable-execution.md) before this stage. It defines small-team ownership, direct reviewer image capability and session evidence, generated/validated handoffs, source-anomaly comparison checks, dependency-aware repairs and full end-of-report display inspection. A reviewer unable to see source pixels cannot accept a visual paper by relying on writer records. Use the current review template and plain gate strings. Preserve actual blockers and never invent acceptance. Keep one canonical set of scientific IDs; update existing records instead of creating overlapping accounts of the same evidence.

For revision2.4, first save the actual inspected review draft including the reviewer's own visual_inspection evidence, then use snapshot "<run>" --file "<review-draft.json>". Independently copy all FOUR returned snapshot fields into a new decision, including reviewed_visual_evidence_sha256. The earlier three-field snapshot is insufficient for a new2.4 visual review. Preserve actual source-first and reviewer evidence; the code checks its structure/bytes, not its honesty.
