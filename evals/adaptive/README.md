# Behavioural evaluation of adaptive reading

These files measure whether adaptive depth behaves as intended. They are not runtime instructions and are never loaded during a reading task.

## Three tiers, never merged

| Tier | What runs | What a pass means | Status in this repository |
|---|---|---|---|
| `STATIC_UNIT` | `scripts/test_reading_triage.py` | Record rules reject malformed or dishonest input | Run locally with the test suite |
| `SIMULATED_FLOW` | `scripts/test_reading_corpus.py`, `scripts/test_reading_promotion.py`, `router` mode below | Bookkeeping holds across import, routing, upgrade and synthesis checks, on constructed records and a fixture PDF | Run locally with the test suite |
| `REAL_PAPER_E2E` | An agent reads real papers with the skill; `records` mode scores its workspace against human gold | The agent screened, attributed and routed real papers acceptably | One small trial on six papers, kept locally outside the repository; run to find process defects, with expectations written by the skill's author. No scored result is recorded here |

Passing the first two tiers does not show that an agent reads papers well. Report each tier separately and mark unexecuted tiers NOT_RUN.

## Routing rules on gold ratings

```text
python scripts/eval_adaptive_reading.py router --cases evals/adaptive/router_cases.json
```

[router_cases.json](router_cases.json) holds cases with gold ratings and the decisions considered acceptable: unrelated papers, missing information, relevant low-novelty work, cross-domain transfer, surveys against empirical papers, missing full text, an explicit L3 request, weak and contradictory evidence. The expected decisions are design expectations for the rule baseline, so agreement is a regression check of the rules, not an accuracy result. The output is always labelled `SIMULATED_FLOW`.

## Scoring real agent output

1. Give an agent the skill, a research target and raw candidate records and PDFs. Withhold the gold file and any expected decisions.
2. Let it produce a screening workspace. Have it report model and reviewer calls with `log-usage`, with token counts only when the runtime provides them.
3. A person annotates gold in the format of [gold.example.json](gold.example.json): per paper, whether it is core, the acceptable decisions, the expected attribution of selected statements, the recorded statements that the source does not support, and the SHA-256 of the paper actually read.
4. Score:

```text
python scripts/eval_adaptive_reading.py records --workspace "<workspace>" --gold "<gold.json>"
```

| Metric | Definition |
|---|---|
| Core paper miss rate | Gold core papers whose current decision is neither a promotion, a completed research reading (REMAIN_AT_L2), nor a deferral, over gold core papers. Deferred core papers are listed separately |
| Routing accuracy | Papers whose current decision is among the acceptable ones, over papers |
| Evidence attribution accuracy | Gold-checked statements recorded with the expected attribution, over gold-checked statements |
| Unsupported claim rate | Recorded statements and supported or limited local claims that gold marks unsupported, over all such recorded items |
| Computational cost | The resource ledger: extraction calls, pages, repeated page reads, reported calls, tokens and durations. Unreported values stay null |
| Reviewer utilization | Reported reviewer calls by depth, calls below L3 (expected none) and papers by evidence tier |

A result is labelled `REAL_PAPER_E2E` only when the gold file declares it and binds every paper to the hash of the attached source. That binding is necessary, not sufficient: the evaluator remains responsible for using real papers and independent gold. A ratio with an empty denominator is null.

## Comparing cost

A saving can be claimed only from a controlled comparison: the same papers and target, one arm reading everything at L3 and one arm using adaptive depth, the same model and review mode, usage taken from the runtime, and the miss rate reported next to the cost. Until such a run exists, state measurements only.
