# Paper Reading Verification v2

[中文运行指南](zh-CN/README.md) | [English execution guide](en/README.md)

This is a staged, bilingual prompt package. It replaces “key sections were read” as a completion criterion with source-unit coverage, semantic checks, independent review, and explicit user-review packets.


- English entry: [en/README.md](en/README.md)
- Shared task template: [shared/task.template.json](shared/task.template.json)


The two language editions have matching stages and rules. Choose one edition per run. Shared JSON field names remain English for interoperability; prose may use the chosen language.









## Revision 2.3

Research targets are now explicit versioned JSON, independent of paper identity. Reports retain general findings and a separate target analysis. The [shared report contract](references/targets-and-visual-reports.md) defines inline original-panel display, readable evidence tables, derived-chart data provenance and rendering checks. The local gallery helper creates captioned image galleries from actually inspected local assets. Targets, galleries, backing data and simple inline image bytes participate in review snapshots. This update does not rerun papers or change previously accepted reports.

## Revision 2.4

[Execution safeguards](references/reliable-execution.md) address observed false visual acceptance, manufactured concerns, duplicate evidence, malformed handoffs, repair propagation and clipped report rendering. New executable controls enforce a direct reviewer visual contract, parent/reference integrity and read-only pre-merge validation. They do not prove semantic understanding. Use one reader/Owner plus one independent reviewer unless source complexity warrants more. Minimally supervised trials receive inputs and skill only; the host does not repair or replace their outcomes.

## Revision 2.5

[Repair synchronization](references/repair-synchronization.md) adds read-only discovery of all current text/data artifacts, including unlinked notes and old manual notebooks. New runs require per-file inspection dispositions before repair readiness. Changed files/records, omitted files and declared obsolete wording prevent dispatch or acceptance until rechecked. Explicit historical exceptions retain provenance. Current notes also participate in review snapshots. Semantic correctness still requires actual independent inspection; existing frozen runs are not migrated.
