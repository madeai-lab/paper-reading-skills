# Batch literature screening

Read this when screening more than one paper, building a reading queue or preparing a synthesis over papers read at different depths. Commands below are prefixed with `python "<skill>/scripts/reading_triage_control.py"`; `WS` is the quoted workspace directory. Field definitions are in the [screening contract](screening-contract.md); depth and routing rules in [adaptive depth](adaptive-depth.md).

## Build the candidate set

```text
init WS --owner "<actual-owner>" --target "<target.json>"
import WS --file "<records.csv>"
add WS --title "<title>" --doi 10.xxxx/yyyy
```

`init` needs a new directory. Add `--file <criteria.json>` to state hard criteria ([example](../shared/exclusion-criteria.example.json)) and `--max-depth L0 --user-instruction "<what the user asked>"` when the user limited the whole task, for example to abstracts. Bind only an explicit research target; without one, papers can be skimmed but not judged for relevance. `import` accepts CSV, TSV, JSON, BibTeX and XLSX records (`--format`, `--sheet` when needed) and keeps a copy under `records/`. Column names such as title, abstract, doi, arxiv, url, authors, year and venue are recognized in English and Chinese; unrecognized columns are kept as original values.

De-duplication is deterministic:

1. Same DOI, or same arXiv ID (version suffix ignored), joins the existing paper as another source record.
2. Same normalized title (case, punctuation and spacing ignored; at least 12 characters) joins too, unless both records carry conflicting identifiers of the same kind. Then a new paper is created and both are listed in `possible_duplicate_of` for a person to resolve.
3. An arXiv DOI is treated as the arXiv ID, so a preprint and its published version become two source records of one paper. Decide which version is read when attaching the full text; versions are never merged as evidence.
4. A record whose DOI belongs to one paper and whose arXiv ID belongs to another joins the first and flags both as possible duplicates; it does not re-point either identifier.

Records with no title, DOI, arXiv ID or URL are reported as unusable. Nothing is screened by importing.

## Screen, route, queue

```text
handoff-template WS --paper P0001 --depth L0 --writer "<actual-writer>"
validate WS --file "<pass.json>"
submit WS --file "<pass.json>"
recommend WS --paper P0001
route WS --paper P0001 --file "<decision.json>"
queue WS
status WS --paper P0001
```

Screen every candidate at L0 with the [L0 prompt](../en/triage/L0_METADATA_SCREENING.md). Attach the files you already hold (`attach-source`) so routing knows which papers can be read; attaching reads nothing. `recommend` returns the rule baseline; `recommend --paper P0001 --file <pass.json>` previews it for a pass you have not submitted yet, which is how you fill the decision a skim must carry. `route` records the decision with reasons. Go deeper only where routed: attach the full text, then skim or read the named focus.

```text
attach-source WS --paper P0001 --source "<paper.pdf>"
mark-unavailable WS --paper P0001 --reason "<why>" --attempts "<attempt 1>" "<attempt 2>"
extract WS --paper P0001
outline WS --paper P0001
find-text WS --paper P0001 --terms "ablation" "layer normalization"
read-pages WS --paper P0001 --pages 1 2
render-crop WS --paper P0001 --pages 5 --bbox 48 92 540 420 --out fig1.png
```

`extract` needs an already provisioned pdfplumber interpreter and runs once per source version. `outline`, `read-pages` and `render-crop` are the same navigation helpers as in a run, and `find-text` locates terms in the extracted text so that a keyword check does not cost a second read of every page; none of them advances a state. A saved text or HTML snapshot can support a skim, but extraction and complete reading need the PDF.

`queue` lists papers with a pending action. Order: what the user explicitly requested, then by next action (continue an open run, open a complete reading, targeted reading, skim, attach full text, obtain deferred evidence, recommendations waiting for the user, re-examine a new version, reassess for a new target, record a decision, screen), then by utility, topic and method ratings compared one after another. It is a routing aid, not a ranking of paper quality.

When the research target changes (`set-target WS --file <target.json>`), earlier relevance decisions are suspended and listed for reassessment, together with the link between targeted-reading focus and target questions. Record the new judgement without rereading:

```text
reassess-template WS --paper P0001 --writer "<actual-writer>"
reassess WS --file "<reassessment.json>"
set-criteria WS --file "<criteria.json>"
limit-depth WS --depth L0 --user-instruction "<what the user asked>"
limit-depth WS --paper P0001 --depth L1 --user-instruction "<what the user asked>"
```

Read more only when the new target needs content that was not examined. `set-criteria` replaces the stated criteria and suspends exclusions that cited a changed wording. `limit-depth` records a user limit for the workspace or one paper; see [what the user asked](adaptive-depth.md#what-the-user-asked-bounds-the-work).

## Hand authorized papers to complete reading

```text
request-depth WS --paper P0002 --depth L3 --user-instruction "<what the user asked>"
promote WS --paper P0001 --run "<new-run>" --owner "<actual-owner>" --language en --review-mode KEY_CLAIMS
link-run WS --paper P0003 --run "<existing-run>"
```

`promote` needs a user mandate for complete verification under policy 2. A recorded recommendation alone is insufficient. It opens an ordinary run and returns its assessment; continue with `reading_run_control.py` and the [stage guide](../en/README.md). The [reuse rules](adaptive-depth.md#upgrades-and-reuse) list what carries over. `link-run` points at a run that already exists so its real state appears beside screened papers.

## Counts and exports

```text
flow WS
export WS --kind log
export WS --kind matrix
export WS --kind tiers
```

`flow` reports records identified, unusable, merged, papers, excluded (by criterion or decider), background, deferred, full text attached or unavailable, how many papers reached each depth or deeper, how many have a pass at each depth (a paper read at L2 on the user's request may have no L1 pass), runs opened and runs accepted. The counting follows the idea of a PRISMA flow. A stated protocol is required only when the workspace was created with `--mode SYSTEMATIC_REVIEW --file <criteria.json>`; then every exclusion cites one of the stated criteria. Ordinary reading tasks are not forced into a review protocol.

`export --kind log` writes every routing decision, including superseded ones, as JSON and CSV. `--kind matrix` writes one row per paper with its evidence tier, depth, decision, each dimension with its evidence level, coverage counts and open conflicts. `--kind tiers` writes the stage-09 input.

## Synthesis over mixed depths

```text
tiers WS
check-synthesis WS --file "<09_synthesis_claims.json>"
```

`tiers` computes each paper's tier from actual state: a paper is VERIFIED only while its run is currently accepted. Each synthesis claim declares `evidence_basis` (`ACCEPTED`, `SCREENING_LIMITED` or `SCOPED_L2`), `strength` (`CONCLUSION`, `CANDIDATE` or `BACKGROUND`) and `support` entries ([example](../shared/synthesis-claims.example.json)).

- `ACCEPTED` cites only claims from accepted packets, within USE or with `conditions_acknowledged` for CONDITIONAL. HOLD claims are refused. Any support from a lower tier is `SHALLOW_EVIDENCE_MISLABELED`.
- `SCREENING_LIMITED` is never a CONCLUSION and always states its limitation. A CANDIDATE cites a supported or limited local claim from targeted reading (`local_claim_id`) whose focus was judged for the current target; a claim read for another target revision is `TARGET_APPLICABILITY_STALE` until reassessed. `tiers` lists every local claim with its read scope, source version, attribution, evidence state, target applicability and `independent_review: NONE`. Skimmed and metadata-only papers support BACKGROUND alone.

For actual bounded methods and comparisons, use `SCOPED_L2` under the [Stage 09 use contract](../en/09_cross_paper_synthesis/PROMPT.md). A main-line conclusion needs an independent scoped receipt; this is not paper acceptance. The structural checker cannot establish scientific sufficiency.
