# Paper Reading Verification

An English-instruction skill for complete paper reading, source-linked explanations and independent review. Current runtime contract: **2.9**.

1. Install this directory as `paper-reading-verification-v2` in your assistant's skill directory, or provide [SKILL.md](SKILL.md) and the paper path.
2. Start with the [execution guide](en/README.md).
3. Use Python for the local helpers; native PDF extraction additionally requires an already provisioned pdfplumber interpreter. The host performs reading and reviewer coordination; the scripts do not run models.

Reports must explain the mechanism, metrics and every experiment, alongside complete saved source coverage. The default team is one Owner plus one independent reviewer. Both KEY_CLAIMS and FULL_DOUBLE_READ remain available.

- [Architecture, loading routes and file ownership](references/architecture.md)
- [Reader-facing explanation contract](references/reader-explanations.md)
- [Version history and maintenance scope](CHANGELOG.md)

The repository contains reusable instructions, templates and local tests. It does not contain paper PDFs, personal reading queues or reading-run results. Structural validation is not proof of scientific understanding or a measured cost saving.

Operational instructions are English-only. Reports still use the requested language; the CLI language option controls deliverables, not instruction loading. Human reference translations are stored separately from the runtime package.
