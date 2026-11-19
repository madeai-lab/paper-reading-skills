# Read the body by verified section

Use this guide when mapping or reading prose. The reading unit is the source's section or subsection, not the physical page. Page numbers locate evidence and reveal omissions; they do not set reading order or prove understanding.

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

After inventory sync and evidenced G0, read each unit in verified outline order, carrying the argument across page and chunk boundaries. For a mapped native unit use the controller (no page argument):

```text
python "<skill>/scripts/reading_run_control.py" read-section "<run>" --id S2
python "<skill>/scripts/reading_run_control.py" read-section "<run>" --id S2 --cursor <returned-token> --max-chars 12000
```

The response identifies `unit_id`, `label` and `source_id`. Read `segments` in order: each gives `text`, `physical_page`, `page_ref`, `text_id`, `first_word_id`, `last_word_id`, `locator_index` and `flags`. `--cursor TOKEN` and `--max-chars N` are optional. Read the first chunk, then pass its `next_cursor` for the same unit until no token remains. `reading_state_changed` is false. Record what the section says, its conditions, qualifications and links to surrounding units, using the returned source locators. Inspect cited figures, tables, notes and ambiguous extraction on the original or by the [appropriate object evidence route](native-elements.md#choose-the-evidence-route-per-object); the prose stream does not stand in for them.

Cross-check the map for each native source, including supplements, after sync and wherever omissions are suspected:

```text
python "<skill>/scripts/reading_run_control.py" section-coverage "<run>" --source-id SRC-01
```

Inspect `unmapped_pages`, `partial_pages`, `overlap_pages` and `no_native_text_pages`, plus `unbound_sections` and `invalid_sections`. Compare flagged regions, selectors and section joins to the source. Assign missing prose to its unit; assign meaningful headings, references, captions, tables/figures and footnotes to the right text or object, or explain their disposition (for example a running title/footer, or a parent containing only children). Correct inventory locators, sync and recheck affected content. On a page without native words, inspect the original; unreadable material remains a `READING_GAP`. Both commands are read-only: neither marks a unit read, approves a gate nor clears an unresolved item. Record how each flagged region was accounted for; leave unresolved gaps open. Mapped word counts, page totals and an exhausted cursor are not evidence of comprehension.

For an older active run without body selectors, unavailable helpers/Python or a non-PDF source, read the actual source in the same section order and record the headings, paragraphs, pages or object locators actually inspected. Do not invent native coverage, infer a whole page from an old locator, migrate frozen records or waive existing evidence requirements. Preserve any missing checks and unresolved gaps under the [execution contract](../en/EXECUTION.md#deliver-or-preserve-genuine-interruption).
