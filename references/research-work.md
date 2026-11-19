# Research reading: work limits

Use the figure ladder when an object matters. Use the handoff and budget sections when coordinating agents or a task approaches its budget. These are operating rules for new tasks, not new acceptance gates.

## Figure ladder

1. **Understand.** What question does this object answer? Read its encoding, direction of change, conditions and what cannot be inferred. In L1/L2 leave unrelated objects explicitly unexamined. At L3 retain the existing full inventory, per-panel coverage and pixel/structured inspection requirements.
2. **Check for use.** Before quoting a result, or when prose is ambiguous, inspect the relevant axis, scale, legend, baseline, split, unit, uncertainty and footnote against the source. Reopen pixels where extraction damages formulas, headers or data flow. Preserve counterexamples. Reuse an already legible source-bound crop instead of rendering the same view again.
3. **Reconstruct only for a reason.** Curve digitization, color inversion, correlations, inferred percentages and unreported statistics are off by default **even at L3**. Proceed only on an explicit request or when a named consequential conclusion cannot be resolved by source reading or honest qualification. State why and the achievable precision before computing; retain data, transformation, uncertainty and limitations. If the resolution is inadequate, weaken the conclusion, not the rounding. Reading a reported value or checking simple like-for-like arithmetic is not a mandate to reconstruct an entire panel.

Example: “The authors report selective gates in these two trained models; this visualization is not an ablation” can be sufficient. A pixel-derived percentage of closed gates is a *new* claim, not a required part of reading a heatmap.

## Handoff and stopping a review

Keep just **decision, artifact location/version, open problems, next action** in coordinator context. Normally 500–1,000 tokens or less per handoff, not a limit on the reader's source access. Decide who can write the final file before dispatch. If file delivery is allowed, pass paths, hashes and changed IDs. On a text-only host, let the main session author the final prose from bounded evidence and explanations; do not generate and relay whole drafts twice or work around a host restriction.

Batch mechanical checks, reference updates and related reads. Return counts on success and only actionable excerpts on failure. Report meaningful changes, not repeated waiting messages. Reading is not skill development: fix only a blocker to evidence integrity, authorization or the necessary current action; log other friction with trigger and impact.

L3 uses a genuine first review, then by default **one** repair batch and **one** same-reviewer difference review. This bounds dispatch, not the standard for PASS. Follow the existing snapshot, synchronization and continuation contract. If the second decision still finds material problems, deliver the negative decision, remaining work and resume point; do not initiate round three unless explicitly requested. That is the result of a bounded engagement, not a successful final run or a fabricated interruption. On HTTP 429 preserve reviewer, baseline and retry instructions; don't switch people or restart from page one. End an unsuccessful retry with the last valid decision.

| Change | Minimum response |
|---|---|
| Layout or navigation only | Check links and display locally; verify no number, symbol, label or meaning changed. Use an external derived view for restyling. A changed byte-bound report cannot inherit its old approval. |
| Scientific wording | Check the claim, passage and downstream uses. |
| New finding or derived statistic | Inspect its evidence, calculation and dependencies independently. |
| Repeated misreading of a type | Expand to that class of claims. |
| Wrong source, failed core interpretation or widespread broken links | Broaden the review as necessary, or report not accepted if outside the authorized round/budget. |

## Initial soft budgets

For an ordinary accessible 5–20 page technical paper without replication. These are anomaly alerts, **not** measured optima, hard caps or evidence of completion. Estimate separately for dense proofs, long surveys or reproduction.

| Work | Model responses | Cumulative output tokens |
|---|---:|---:|
| L0 | 3 | 2,000 |
| L1 | 8 | 6,000 |
| L2 | 20 | 20,000 |
| L3 Owner | 40 | 40,000 |
| L3 independent first review | 20 | 20,000 |
| Difference review | 8 | 8,000 |

Use runtime output usage, not report length. Count by task and paper; the reader moving up a depth carries earlier reader usage forward. Keep first review and difference review separate; include both in the paper total. Let the host tag usage with `task_kind`, `paper_id`, `depth`, `phase`, `role`, and `review_round` for review, without making the model fill one form per call. Missing telemetry stays unavailable, not zero.

At **either** threshold, stop optional work and test the depth's stopping condition. If not met, identify the concrete blocking gap, minimum next read and reason to continue. A hard user/host limit takes precedence: deliver actual coverage, open questions and a resume locator. A soft alert does not lower requested depth, confer acceptance or permit access outside scope.
