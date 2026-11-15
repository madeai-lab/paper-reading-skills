# Synchronize repaired dependencies (revision 2.5)

Read this when a review requests repairs. A corrected report can still conflict with reading notes, a manual notebook, gate evidence or target analysis. Correct the complete meaning across current artifacts before asking the reviewer to repeat its work. Do not automatically replace text or close a genuine source concern to satisfy a check.

## Repair as one batch

1. Identify the changed source interpretation and its stable unit, issue, comparison and claim IDs. Follow dependencies through claim restrictions, quantities/units, source explanations, target answers, user-review requests, captions, derived data and gate evidence. Search IDs plus old values and semantic phrases; an ID search alone misses paraphrases. Read surrounding text and negations.
2. Update canonical scientific records through validated handoffs. Recheck G0-G2 when affected. Run `sync` to regenerate the notebook/index after all canonical edits. Inspect older manual notebooks too: an unselected deliverable can still contain a current explanation. Keep raw handoffs and prior reviewer decisions unchanged.
3. Correct current handwritten notes, report, user-review packet, target analysis, visual captions and backing data. Explicit correction history may retain prior wording only as a clearly labelled withdrawn interpretation. Create the repair evidence note now, before the final scan. Do all repairs together so one edit does not immediately invalidate another repair's synchronization report.
4. Run the read-only scan below. Add affected IDs, old/new quantities and semantic phrases with `--terms`; declare obsolete wording with `--obsolete`. Inspect every listed file, including files with zero literal matches. Mark each `UPDATED`, `CHECKED_UNCHANGED` or `HISTORICAL_CONTEXT` and give a specific reason explaining the meaning checked. Never fill identical generic reasons merely to pass validation.

```text
python "<skill>/scripts/reading_run_control.py" repair-scan "<run>" --id "REP-01" --terms "ISS-01" "CLM-08" "citation namespace" --obsolete "ISS-01 requires user confirmation"
```

Save stdout as `<run>/repair_sync/REP-01.json` using UTF-8; create that directory first if needed. This is a draft, not proof of inspection. Keep the emitted identity, file hashes and focus terms. Fill dispositions/reasons. If anything is changed, added or removed during inspection, rerun the scan after editing and recheck its current results. Do not copy old file hashes over changed files.

For a genuine historical occurrence of a declared obsolete literal, add an exact exception to `historical_occurrences`:

```json
{"path":"evidence/correction_notes.md","line":12,"literal":"ISS-01 requires user confirmation","reason":"Explicitly labelled withdrawn interpretation; current ISS-01 is explained, with no pending user request."}
```

An exception is an Owner assertion for reviewer reinspection, never automatic permission to retain conflicting current prose. Do not exempt a whole file, directory or all occurrences.

```text
python "<skill>/scripts/reading_run_control.py" repair-ready "<run>" --id "REP-01" --evidence "evidence/repair_notes.md" --sync-file "<run>/repair_sync/REP-01.json"
python "<skill>/scripts/reading_run_control.py" next "<run>"
```

Repeat readiness for each latest-review request using its own scan report. Any later current-file or scientific-record change invalidates readiness; rescan/recheck affected reports as a batch before reviewer dispatch. File additions/deletions, report tampering and changed scope are checked as well. `repair-ready` cannot approve G3; obtain a new actual independent decision.

## Current artifacts and immutable history

Discovery covers all local Markdown, text, JSON, CSV, TSV, HTML and SVG files, including unlinked notes and manual copies. The packet uses a scientific projection excluding review/status bookkeeping. Task/assignment/state records are control metadata. `handoffs/`, `reviews/` and `repair_sync/` are reserved for immutable handoffs, reviewer outputs and repair reports; never store current reading notes or claim mirrors there. The independent-review deliverable is reviewer output. Put new reviewer checklists, observation notes and decision drafts under `reviews/`, not mixed with current author files. The controller does not write or repair source prose.

The reviewer compares the complete current artifact manifest, checks the actual repair diff and affected dependency closure plus historical exceptions, then takes its own fresh snapshot. Apply the recorded mode from [Review modes](review-modes.md); unchanged ordinary content does not require repeated reading in KEY_CLAIMS. For new runs, unlinked current text also participates in that content fingerprint, so a later stale-note edit invalidates acceptance. A scan cannot discover every semantic dependency or prove that a disposition is truthful. It catches omissions, stale snapshots and declared obsolete literals; actual consistency and image/data correctness still require inspection. Earlier runs are not silently migrated, and frozen trial records remain untouched.

## Efficient reinspection

Read [Efficient independent reinspection](efficient-reinspection.md) before dispatching repair review. Reuse the actual independent reviewer and its own source-first evidence. A new decision needs a new review ID and fresh snapshot, not a fresh agent. Reinspect changes and their affected dependencies while retaining the same reviewer's verified unchanged coverage; expand the review when source, scope or reliability changes. Never invent resumed identity, viewing or approval.

Apply the repair transaction and reviewer continuity protocol in [Efficient independent reinspection](efficient-reinspection.md). Resolve generator/manual-output churn and validate all requests together before one delta dispatch to the original reviewer. Repeated routine repair rounds must not automatically trigger new full-paper reviews.
