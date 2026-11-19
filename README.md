# Paper Reading Verification

An English-instruction skill for paper reading at a chosen depth: metadata screening, evidence-aware skim, targeted reading, and complete reading with source-linked explanations and independent review. Complete-reading run contract: **2.10**. New-task reading policy: **2** (screening schema **1**).

1. Install this directory as `paper-reading-verification-v2` in your assistant's skill directory, or provide [SKILL.md](SKILL.md) and the paper path.
2. For a new paper start at the [depth guide](en/triage/README.md). The default is L2 research reading; the [complete-reading guide](en/README.md) is for L3.
3. Use Python for the local helpers; native PDF extraction additionally requires an already provisioned pdfplumber interpreter. The host performs reading and reviewer coordination; the scripts do not run models.

Complete-reading reports must explain the mechanism, metrics and every experiment, alongside complete saved source coverage. L2 normally uses one reader; L3 uses an Owner plus a distinct independent reviewer. Both KEY_CLAIMS and FULL_DOUBLE_READ remain available.

- [Choose a reading depth](en/triage/README.md): L0–L2 produce screening records that state what was and was not examined; they never hold a gate or an acceptance. [Depth, relevance and routing rules](references/adaptive-depth.md), [batch screening](references/corpus-screening.md), [output profiles and the resource ledger](references/output-profiles.md).
- [Read the full body in verified section/subsection order](references/section-reading.md); use physical pages to check for omissions, locate evidence and inspect original objects, not as the reading sequence.
- [Lightweight figure/table locators: when to switch from navigation to source evidence](references/native-elements.md#locate-figures-and-tables-before-detailed-inspection)
- [Architecture, loading routes and file ownership](references/architecture.md)
- [Reader-facing explanation contract](references/reader-explanations.md)
- [Version history and maintenance scope](CHANGELOG.md)

The repository contains reusable instructions, templates and local tests. It does not contain paper PDFs, personal reading queues or reading-run results. Structural validation is not proof of scientific understanding or a measured cost saving. [Behavioural evaluation cases](evals/adaptive/README.md) separate static tests, simulated flows and real-paper trials; trial workspaces are not part of the distributed skill. The new research-first policy has not been retested on real papers.

Operational instructions are English-only. Reports still use the requested language; the CLI language option controls deliverables, not instruction loading. Human reference translations are stored separately from the runtime package.
