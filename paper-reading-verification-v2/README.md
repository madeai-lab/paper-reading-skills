# Paper Reading Verification v2 / 论文完整阅读与证据验证 v2

This is a staged, bilingual prompt package. It replaces “key sections were read” as a completion criterion with source-unit coverage, semantic checks, independent review, and explicit user-review packets.

这是分阶段、双语的Prompt包。完成标准从“读了关键章节”改为：源材料单元覆盖、理解检查、独立审查，以及供用户判断的疑点证据包。

- 中文入口：[zh-CN/README.md](zh-CN/README.md)
- English entry: [en/README.md](en/README.md)
- Shared task template: [shared/task.template.json](shared/task.template.json)


The two language editions have matching stages and rules. Choose one edition per run. Shared JSON field names remain English for interoperability; prose may use the chosen language.

两版阶段和规则对应。一次运行选用一版，共用JSON字段名，说明文字可使用所选语言。





## Revision2.2 / 修订2.2



## Revision 2.3

Research targets are now explicit versioned JSON, independent of paper identity. Reports retain general findings and a separate target analysis. The [shared report contract](references/targets-and-visual-reports.md) defines inline original-panel display, readable evidence tables, derived-chart data provenance and rendering checks. The local gallery helper creates captioned image galleries from actually inspected local assets. Targets, galleries, backing data and simple inline image bytes participate in review snapshots. This update does not rerun papers or change previously accepted reports.

## Revision 2.4

[Execution safeguards](references/reliable-execution.md) address observed false visual acceptance, manufactured concerns, duplicate evidence, malformed handoffs, repair propagation and clipped report rendering. New executable controls enforce a direct reviewer visual contract, parent/reference integrity and read-only pre-merge validation. They do not prove semantic understanding. Use one reader/Owner plus one independent reviewer unless source complexity warrants more. Minimally supervised trials receive inputs and skill only; the host does not repair or replace their outcomes.
