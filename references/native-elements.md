# Native PDF elements (revision 2.7)

Use this contract for runs initialized with `content_acquisition.method=PDFPLUMBER_NATIVE`. Earlier runs through revision 2.6 without that field retain their existing acquisition and visual evidence rules. A revision-2.7 packet missing its acquisition contract is invalid. Do not retrofit an active or frozen run. This changes how source content is obtained, not complete Owner reading or mandatory independent claim coverage.

## Extract once, read bounded source slices

Run the canonical controller with a Python interpreter that already provides pdfplumber:

```text
python "<skill>/scripts/reading_run_control.py" extract-elements "<run>"
python "<skill>/scripts/reading_run_control.py" read-elements "<run>" --source-id SRC-01 --pages 1 2 --max-chars 18000
python "<skill>/scripts/reading_run_control.py" read-elements "<run>" --pages 7 --bbox <x0> <top> <x1> <bottom>
```

pdfplumber is an optional dependency of extraction, not of the standard-library controller/checker. Use the host's documented bundled Python when it already supplies the dependency. Other deployments must supply it explicitly. Missing support returns `PDFPLUMBER_UNAVAILABLE`; do not automatically install, download a model, upload a source, enable OCR or silently substitute full-page vision.

New packets bind `content_acquisition` with `method: PDFPLUMBER_NATIVE` and `manifest_ref: source_elements/manifest.json`. The schema-version-1 manifest records `parser.name=pdfplumber`, its version, `ocr_used=false` and `sources[]` entries containing source_id, local_path, sha256, page_count and pages[{page,ref,sha256}] for every available required local PDF. Extraction preserves actual source identity/hash and page-file hashes; source_id disambiguates identical page-local element IDs across sources. Per-page JSON retains source_id, page, width/height, native text, words with IDs/bboxes, tables with IDs/bboxes/rows/cells/flags, images with IDs/bboxes/srcsize, lines/rects/curves and page flags. The text element is p0001-text, with table p0001-t001, image p0001-i001 and word p0001-w00001 ID patterns. Treat object IDs as page-local evidence locators, not semantic labels invented by a model. Files and parser output do not demonstrate that anyone read them.

Read every source page continuously through bounded `read-elements` slices, selecting supplements with `--source-id`. Bounding boxes use PDF points with the origin at the page top-left. Full-page output includes text plus compact table/image/flag summaries; word/geometry detail is requested only for a bbox. Exhausting --max-chars returns ELEMENT_READ_LIMIT rather than silently cutting a page. Extraction caps each PDF at 500 pages and 100 MB and all PDFs at 10,000,000 native characters; PDF_ELEMENTS_LIMIT fails rather than claiming truncated coverage. Encrypted PDFs fail with PDF_ELEMENTS_ENCRYPTED; no password or bypass is attempted. Existing extraction returns ELEMENTS_EXIST; source changes return ELEMENT_SOURCE_CHANGED; invalid manifests/pages return ELEMENTS_INVALID. Do not overwrite evidence to make stale records appear current. Keep section/page joins and source locators. Use text and table slices in the model context rather than dumping every character, drawing primitive or the complete manifest. Detailed JSON stays on disk for narrow inspection and calculation. Inspect source structure against all extracted pages and the inventory; extraction is not permission to omit footnotes, references needed for interpretation, equations, appendices or required supplements.

## Choose the evidence route per object

| Source content | First evidence | Additional inspection |
|---|---|---|
| Body text, captions, native labels | Text/word records and page coordinates | Reopen a crop or alternate native extraction when order, spacing, encoding, superscripts or attribution are unclear |
| Complete native table | Every extracted cell, row/column relation, header, units and notes | Inspect the original when cells are missing/merged incorrectly, emphasis matters, a region contains raster content, or structure/text conflicts |
| Equation or algorithm | Native glyphs, layout and adjacent definitions | View a legible crop when symbol identity, fraction/script structure or reading order is ambiguous; native text is not guaranteed LaTeX |
| Raster chart, photo, screenshot or qualitative image | Its actual embedded-image region and surrounding native caption/context | Actually view source pixels; native captions/labels cannot substitute for image content |
| Vector graphic, plot or flowchart | Native labels plus available lines/curves/coordinates | Actually view its graphical relationships; drawing primitives alone do not establish arrow direction, groups, statistical comparisons or causal meaning |

`LABEL_ONLY` evidence never establishes plotted values or relationships. A raster chart may have no native internal labels at all. Do not turn a caption, an image bounding box or an approximate pixel estimate into an exact data value. If a lawful source table/data file is actually available, preserve its provenance separately; do not execute paper code or expand source access implicitly.

Native extraction can join words, break reading order, map glyphs incorrectly or split/merge tables. Preserve the observed conflict and its exact source location. Resolve it with existing native alternatives and/or direct visual inspection, retaining a local resolution note. Per-page `chars` retain glyph IDs, text, coordinates, font and size; bbox reads include glyphs for narrow formula/encoding checks. A GLYPH_MAPPING_CONFLICT or NO_NATIVE_TEXT page requires actual pixel evidence and a resolution note for the affected unit. Unresolved reading conflicts remain reading gaps; a parser's successful return code is not a resolution.

## Owner records and the narrow table exception

Every checked unit in a new acquisition run records `content_reading` with mode `NATIVE_ELEMENTS`, `VISUAL` or `MIXED`, existing `page_refs`, precise `element_ids` and `conflict_resolution_refs` where a conflict required resolution. NATIVE_ELEMENTS means source-native content was actually read; VISUAL means required pixels were actually read; MIXED retains both. None is assigned from extraction alone. References must resolve to the bound source/page and actual elements covering that unit. A unit does not become CHECKED automatically after extraction.

A TABLE can satisfy its content inspection through verified native elements only when its manifest/source binding is current, table IDs and page locators match, every informative cell/header/note is covered, no bitmap overlaps the table and no unresolved table/page extraction conflict remains. Preserve `visual_review.actually_viewed=false` if no pixels were viewed; the native record is an honest alternative, not a fabricated viewing flag. If those conditions fail, perform and record actual visual inspection or keep the unit incomplete.

The exception is TABLE-specific. FIGURE, PANEL and OTHER_VISUAL relationships still require genuine viewing. All in-scope text, table content, formalism, methods, experiments and graphical objects remain part of complete reading. Ordinary text pages do not require rasterization merely to establish reading.

## Independent review and snapshots

The reviewer establishes its own source-first map from the native source evidence before draft conclusions, checks the complete Owner inventory and verifies every claim required by the selected review mode. It reads mandatory native textual/table evidence itself. For mandatory native tables accepted without pixel viewing it records its own `structured_inspection` with inspected `unit_ids` and local reviewer `evidence_refs`; ordinary text continues to use actual checked unit/claim coverage and source evidence. Owner reading flags do not become reviewer inspection.

Direct reviewer pixel evidence covers the mode-required graphical, raster and conflict objects. A validated native table can use the table exception instead; it must be covered by the reviewer's own structured inspection. A source with no pixel-required objects does not need a fabricated image-capability probe. If informative bitmaps/graphics or unresolved visual conflicts exist, probe actual image capability early and preserve the existing no-false-viewing safeguards.

FULL_DOUBLE_READ still independently checks every in-scope unit; KEY_CLAIMS still checks all registered claims, their dependency chain and the planned ordinary sample. Acquisition route does not reduce either scope. Retain the same actual reviewer for incremental repairs.

Manifest, page files and any resolution evidence belong to the inspected scientific packet. Finish extraction and all content updates before preflight/review. Source, native-element or resolution-evidence changes invalidate affected interpretation and previous acceptance; recheck the dependency chain and take a fresh actual snapshot. Do not regenerate extraction during review or refresh old approval tokens. Old batches and frozen trials stay unchanged.
