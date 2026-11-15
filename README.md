# Paper Reading Skills

[中文版](README.zh-CN.md) | [Skill execution guide](en/README.md)

A bilingual skill for complete, source-grounded paper reading, evidence tracking, independent review, and repair. It covers the paper's text, methods, experiments, figures, and relevant supplements.

## Getting started

1. Clone this repository into a directory named `paper-reading-verification-v2` in a compatible agent’s skills directory or give the agent the path to [SKILL.md](SKILL.md) and the paper.
2. Follow the [English execution guide](en/README.md) or [中文运行指南](zh-CN/README.md).
3. Use Python for the bundled local helpers. Paper interpretation and independent review require capable agents. Automated checks cannot establish scientific understanding or replace independent review.

The repository does not include paper PDFs, reading results, personal research records, or access credentials.

## Version history

The commits for revisions 2.2, 2.4, and 2.5 are sanitized imports reconstructed from existing snapshots; they are not the original development commits. Revision 2.3 is described in the skill documentation, but no separate snapshot was imported.

## Revision notes

## Revision 2.3

Research targets are now explicit versioned JSON, independent of paper identity. Reports retain general findings and a separate target analysis. The [shared report contract](references/targets-and-visual-reports.md) defines inline original-panel display, readable evidence tables, derived-chart data provenance and rendering checks. The local gallery helper creates captioned image galleries from actually inspected local assets. Targets, galleries, backing data and simple inline image bytes participate in review snapshots. This update does not rerun papers or change previously accepted reports.

## Revision 2.4

[Execution safeguards](references/reliable-execution.md) address observed false visual acceptance, manufactured concerns, duplicate evidence, malformed handoffs, repair propagation and clipped report rendering. New executable controls enforce a direct reviewer visual contract, parent/reference integrity and read-only pre-merge validation. They do not prove semantic understanding. Use one reader/Owner plus one independent reviewer unless source complexity warrants more. Minimally supervised trials receive inputs and skill only; the host does not repair or replace their outcomes.

## Revision 2.5

[Repair synchronization](references/repair-synchronization.md) adds read-only discovery of all current text/data artifacts, including unlinked notes and old manual notebooks. New runs require per-file inspection dispositions before repair readiness. Changed files/records, omitted files and declared obsolete wording prevent dispatch or acceptance until rechecked. Explicit historical exceptions retain provenance. Current notes also participate in review snapshots. Semantic correctness still requires actual independent inspection; existing frozen runs are not migrated.

## Revision 2.6

[Review modes](references/review-modes.md) separate complete Owner reading from the scope of independent review. New runs default to verification of all claims and evidence chains with risk-based sampling; full independent rereading remains available.

## Revision 2.7

[Native PDF elements](references/native-elements.md) adds bounded access to text, tables, and other elements using pdfplumber. Graphical content and extraction conflicts still require direct inspection. pdfplumber is an optional extraction dependency and is not installed automatically.
