# Skill maintenance plan — 2026-11-16

The user authorized the previously proposed maintenance and integration of the newer skill from the referenced chat. This is an in-place update of the standalone skill repository; other deployments and historical reading runs remain untouched.

Approach: import the reusable revision-2.8 changes from the local paper-agent skill, then consolidate current instructions. Preserve public commands, JSON schemas and legacy compatibility. Keep one Owner and one independent reviewer; retain both review modes and the same-reviewer repair loop.

- [x] Import revision-2.8 code, templates, explanation contract and regression tests; exclude personal queues, trial outputs and historical validation claims.
- [x] Consolidate the entrypoint, bilingual execution/data contracts and role prompts; clarify canonical records, generated outputs and optional evidence notes.
- [x] Document loading routes, module ownership, automated versus semantic checks, and synthesis orchestration.
- [x] Extract record I/O, fingerprints and notebook rendering behind the existing controller API without changing behavior.
- [x] Run the complete local test suite, skill validation, local-link checks and diff checks. Do not claim a real paper trial or measured token saving.

The shared reference contracts are authoritative for detailed schemas. Language editions provide matching operational guidance. Version 2.8 remains the runtime contract; this maintenance does not introduce another data revision. Cross-paper synthesis uses existing per-paper controls and stage 09; no aggregate execution command is implied.

Review focus: preserve the new report-quality gate, all-claim review coverage, source and visual snapshots, immutable failed decisions, repair invalidation, and legacy runs without new fields.

## Validation

The complete local suite ran 203 tests successfully, with one real-PDF test skipped because the default interpreter lacks pdfplumber. Skill validation passed using Python UTF-8 mode; Markdown local-link checks found no missing destinations; compileall and git diff --check passed. AST comparison confirmed every extracted controller function/class matches the imported 2.8 implementation, and all five runtime templates match that source. No real-paper end-to-end trial or cost comparison was performed.

## Follow-up: English-only runtime instructions

At the user's request, the instruction tree and shared architecture reference now contain English only. Chinese human reference material is retained in an external local snapshot, outside runtime discovery. The language CLI option remains a deliverable-language setting; report language and legacy run behavior are preserved.
