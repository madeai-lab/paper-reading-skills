# Read the body by verified section

## Native reading quickstart

After `init`, use one Owner to map, read and check the frozen source. Below, prefix each command with `python "<skill>/scripts/reading_run_control.py"`; replace `RUN` with the quoted run directory. IDs, page numbers and boxes are examples, not defaults. The [worked records](../en/DATA_CONTRACT.md#worked-example-one-page-design-note) show exactly what goes in each JSON file.

**1. Find candidates.** Extract once. `outline` prints plain text by default; add `--out` only to create a **new**, run-relative draft under `tools/`. For a hard-to-place heading or doubtful passage, `--view text` gives a short UTF-8 native page check. Do not loop over pages to export the body.

```text
extract-elements RUN
outline RUN --source-id SRC-01 --out tools/inventory.draft.json
read-elements RUN --view text --pages 1 --source-id SRC-01
```

**2. Verify, then sync.** Check the proposed headings, joins, columns, object boundaries and omissions on the original. If an abstract would span more than two physical pages, the draft retains page hints but no readable body: verify where the main text starts, even if every page has text. Correct the hierarchy, add missed objects/panels and put **only verified rows** into `RUN/01_inventory.json`, preserving existing IDs. A draft is neither the inventory nor evidence. Save the source/scope checks, then run:

```text
sync RUN
section-coverage RUN --source-id SRC-01 --details
```

To focus the previews, append `--pages 1 2`; it does not narrow the source audit. Account for flagged regions, fix selectors and sync again if needed. Validate and merge an evidenced **Owner G0** before beginning dependent reading (see the worked records).

**3. Read whole sections, not whole pages.** In verified outline order, request readable UTF-8 prose. Carry the argument across chunks and keep each segment's source page, page reference and element/word IDs.

```text
read-section RUN --id S1 --format text
read-section RUN --id S1 --format text --cursor TOKEN
```

Replace `TOKEN` with the value on the last line, `next_cursor: TOKEN`, for this unchanged unit. Stop requesting chunks at `next_cursor: END` (JSON: `null`). Omit `--max-chars` normally; the ceiling is **18,000 characters**, not tokens. No cursor or coverage result advances a read state.

**4. Inspect the object when the text points to it.** For example, if the verified figure is on physical page 5:

```text
read-elements RUN --source-id SRC-01 --view locator --pages 5
render-crop RUN --source-id SRC-01 --pages 5 --bbox 48 92 540 420 --out evidence/f1.png --scale 2
```

Use the object's actual bbox in top-left PDF points; `--scale` is optional. Open the PNG at `RUN` plus the returned `path` in an image-capable viewer. Check its legend, marks or arrows against the caption and prose. A render receipt binds the crop to the source; it is **not** a viewing record. Only then hand off the explanation, native `content_reading` and required `visual_review`. For tables and conflicts, use the [object-specific evidence route](native-elements.md#choose-the-evidence-route-per-object).

## 01: Map the source outline

Verify headings, hierarchy, order and transitions against the source. Use the contents, bookmarks or native heading candidates to navigate, then check the actual boundaries and layout, including front matter, appendices, bibliography and required supplements. Give each unit its own text: map a parent's introductory paragraphs to the parent and each subsection's text to that child. Do not map the entire subtree again on the parent. For a long, simple section, verify its ends and intervening layout; locally expand a verified run of whole interior pages into individual locators. Do not read the body page by page first just to transcribe a map.

In `01_inventory.json`, a native `SECTION`, `APPENDIX` or `BIBLIOGRAPHY` unit binds its `source_id` and lists `locators` in reading order. Each body selector applies to **one physical page**. On a shared page, use the same verified heading for both units. For example, the last locator of S2 and the first of S3 could be:

```json
{"physical_page": 7, "body": {"stop_before": "3 Results"}}
```
```json
{"physical_page": 7, "body": {"start_at": "3 Results"}}
```

- `"body": {}` explicitly selects **all native words** on that page. A locator without `body` is a source location, not a whole-page selector.
- `body` may contain any combination of `bbox`, `start_at` and `stop_before`. A `bbox` such as `[48, 80, 300, 740]` uses PDF points from the top left. A word is inside when its center satisfies `x0 <= x < x1` and `top <= y < bottom`. For two columns, use separate locators for the left and right regions in logical order; split further where the layout or section changes.
- Within the selected region's native word stream, each boundary phrase must match a **unique sequence of complete words**. `start_at` includes its phrase; `stop_before` excludes it. Check spelling, punctuation and order against native words. If a heading repeats, words are glued, or the stream interleaves columns, use smaller verified boxes or read the original section. Do not guess a substring, occurrence or reading order.

## 02: Read and reconcile

- **A section will not read.** `INVALID_SECTION` means check the synced ID and kind (`SECTION`, `APPENDIX` or `BIBLIOGRAPHY`); `SECTION_UNMAPPED` means no `body` selector. For `INVALID_SECTION_MAP`, inspect the boundary in native words and the original layout; fix an ambiguous phrase, reversed span or overlapping box in inventory, not in a handoff. Sync and restart the affected unit. `INVALID_SECTION_CURSOR` calls for restarting the unchanged/current section without a token. For `ELEMENT_READ_LIMIT`, omit an oversized budget; if one word plus provenance cannot fit the ceiling, inspect the source conflict rather than truncating it.
- **Coverage flags remain.** Check each native source, including supplements. Inspect `unmapped_pages`, `partial_pages`, `overlap_pages`, `no_native_text_pages`, `unbound_sections` and `invalid_sections`. With `--details`, `unmapped_runs` gives located previews; `total_unmapped_runs` is the count, not the number returned. When `next_offset` is present and non-null, repeat with `--offset` and that value, keeping the same page filter. Empty previews do not clear overlaps, invalid selectors or pages without native words.
- **Decide what was missed.** Compare flagged regions with the source. Assign omitted prose, captions, references and footnotes to the right unit; document actual running headers or a parent containing only children. Fix, sync and recheck. On textless pages or unresolved glyphs, inspect the original and record the resolution or keep a `READING_GAP`. Mapped word counts, page totals and an exhausted cursor are not evidence of comprehension.

For an older active run without body selectors, unavailable helpers/Python or a non-PDF source, read the actual source in the same section order and record the headings, paragraphs, pages or object locators actually inspected. Do not invent native coverage, infer a whole page from an old locator, migrate frozen records or waive existing evidence requirements. Preserve any missing checks and unresolved gaps under the [execution contract](../en/EXECUTION.md#deliver-or-preserve-genuine-interruption).
