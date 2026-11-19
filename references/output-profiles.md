# Output profiles and the resource ledger

Read this when a different presentation of existing reading is requested, or when recording cost. Commands are prefixed with `python "<skill>/scripts/reading_triage_control.py"`; `WS` is the screening workspace.

## Output profiles

A profile chooses presentation. It never changes what was read or reviewed. Depth, review scope and profile are three separate choices.

| Profile | Minimum reading basis | Typical content |
|---|---|---|
| `PAPER_CARD` | Metadata screening | Identity, sourced statements, ratings by dimension, recommendation, what was not examined |
| `QUICK_SUMMARY` | Skim | Problem, claimed contributions, method, evidence as stated or seen, limitations |
| `GROUP_MEETING` | Skim | Why this paper, approach, evidence and its status, discussion questions |
| `TECHNICAL_EXPLANATION` | Targeted reading | The mechanism in the examined passages, local claims and limits |
| `FULL_READING_REPORT` | Complete reading | The run's own `report.md` from stage 07, unchanged |
| `PEER_REVIEW_STYLE` | Complete reading | Claims, strengths, concerns with source locations, restricted claims |
| `REPRODUCTION_CHECKLIST` | Complete reading | Data, tools, budgets, metrics, NOT_REPORTED details |
| `CROSS_PAPER_MATRIX` | Any; per row | `export --kind matrix` |

```text
profile-plan WS --paper P0001 --profile GROUP_MEETING
render-card WS --paper P0001
register-output WS --paper P0001 --profile GROUP_MEETING --file "<output.md>"
check-output WS --paper P0001 --profile GROUP_MEETING
```

`profile-plan` says whether the evidence supports the profile and returns the banner: a marker line and one sentence stating the reading basis, tier and review status. Put both at the top of the output, unchanged. `render-card` generates a `PAPER_CARD` from the screening record. `register-output` binds a written output to the evidence it presents; `check-output` reports when the output or the evidence behind it has changed.

Rules for every profile:

- Restate recorded content only. A new assertion goes back to source reading and, for a complete-reading run, to stage 08.
- Keep attribution. An author statement stays an author statement in a slide, a card or a summary.
- Carry HOLD and CONDITIONAL restrictions; `register-output` lists them for a complete-reading run.
- Save derived outputs in the workspace, not inside a run. A file added to an accepted run changes the content the reviewer accepted and reopens review. Registered outside, a new presentation needs no new scientific review.
- A complete reading whose review is pending says so in its banner. No profile may present it as verified.

Markdown is the default. HTML, interactive charts and teaching material are not implemented and are not a dependency of any depth.

## Resource ledger

`resource_log.jsonl` in the workspace records two kinds of entries.

- Measured by the helpers: imports, PDF extraction calls and pages, extraction reuse, outline calls, page reads and crops, each with a monotonic-clock duration.
- Reported by the host: model calls and reviewer calls per depth.

```text
log-usage WS --paper P0001 --kind MODEL_CALL --depth L1 --tokens-in 5200 --tokens-out 900 --measured-by "API usage field"
log-usage WS --paper P0001 --kind REVIEWER_CALL --depth L3
resources WS
resources WS --paper P0001
```

Host adapters may supply `--task-kind`, `--phase` and `--review-round` on usage events; paper/depth and role are already known. `resources` reports `budget_windows` for observed reader totals across depth upgrades and reviewer totals by round. These are lower bounds if the host logs only some calls; unknown measurements cannot certify remaining budget. See [initial soft budgets](research-work.md#initial-soft-budgets).

Record tokens or durations only when the runtime reported them, and name that source with `--measured-by`; the helper refuses a quantity without one. Leave them out otherwise. `resources` totals what exists and lists what is unavailable. It reports repeated reads of the same page view, extraction reuse, examined content units, and reviewer calls below L3 (none for ordinary reading; a main-line scoped synthesis review is reported separately). The scripts do not launch models, so an absence of reported calls is "not reported", not zero.

The ledger is bookkeeping. It supports a later controlled comparison; by itself it shows no saving.
