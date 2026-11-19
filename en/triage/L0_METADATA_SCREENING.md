# L0 | Metadata screening

You screen candidates from their records: title, abstract, DOI or arXiv ID, URL, BibTeX or spreadsheet rows. You do not open the paper body. Use the [pass fields](../../references/screening-contract.md#passes) and the [routing rules](../../references/adaptive-depth.md#routing).

For each paper:

1. Confirm identity from the record: which identifiers exist, which source record they come from, and whether several records describe one work or possibly different works. Do not resolve a `possible_duplicate_of` flag by guessing.
2. Classify `paper_type` (EMPIRICAL, SYSTEM, BENCHMARK, CASE_STUDY, SURVEY, THEORY, POSITION or UNKNOWN) and the field. Use UNKNOWN when the record does not show it.
3. List the metadata actually used as `examined` items, each citing its source record. Record `full_text_read: false`.
4. Record potentially valuable methods or experiments as `potential_value` statements. They are AUTHOR_CLAIM when taken from the abstract and ANALYST_INFERENCE when they are your reading of it.
5. With a bound target, rate the seven dimensions. Give the basis for each. `evidence_adequacy` stays UNKNOWN: an abstract cannot show experimental quality. Use UNKNOWN wherever the record is silent and name the missing information.
6. Run `recommend` and record a decision with `route`, or include the decision in the pass.
7. If the record explicitly shows that the paper violates a criterion the workspace stated beforehand, exclude it on that basis: cite the criterion and quote what the record says. Unknown ratings on other dimensions do not block this. If the record is merely silent about the criterion, defer.
8. If the user limited the task to abstracts or to a time budget, stop here. Report which papers you recommend reading further and why; do not open their files.

Do not:

- claim, imply or hint that the paper was read;
- exclude a paper because information is missing; defer it and say what is needed;
- exclude a paper for low novelty; an applied or negative-result paper can matter for the target;
- merge the dimensions into one score or rank papers by a total;
- fill fields from memory of the paper or from another paper with a similar title.

Deliver per paper: identity and source record, type, what the authors state, ratings with evidence level, uncertainty, and the routing decision with its reasons. For a list, add `flow`, `queue` and the exported log.
