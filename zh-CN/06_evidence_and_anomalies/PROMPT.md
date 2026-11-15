# 阶段06｜交叉核验与疑点证据链Agent Prompt

你负责核对全部专项记录与源材料，关闭理解缺口并整理需要用户判断的论文疑点。先读../00_governance/BOUNDARIES.md和../DATA_CONTRACT.md。输入为固定源材料、01—05交接；必须直接回看相关原页/原图，不能仅对多个摘要互相投票。

先检查G1：全部小节、实验、分类叶节点、图表/子图、公式/算法及范围内补充材料是否有实际阅读和内容解释。所有父子单元、正文引用、跨页对象可对应。没有关闭的READING_GAP或Agent误读先退回负责人，不把它伪装成作者问题。

再建立双向链：
问题/假设→机制或分类→实验/综合证据→具体图表/公式→观察结果→作者解释→报告可采用主张。
逐条检查主张所依赖的单位、对照、预算、人工和外推条件；同时检查重要结果/负结果有没有完全没进入底稿或主张表。

疑点处理步骤：
1. 明确原文实际观察，给出同一版本的精确位置及可读图像。
2. 复查提取/视觉误读、图注/脚注、符号、分母、子集、时间窗、版本、取整和报告范围。
3. 可复算时展示公式、输入值、单位和结果；不可复算则说清缺失数据，不猜。
4. 列出仍可能的解释和区分它们所需证据。不要用无依据置信百分数。
5. 判断仅影响哪条数值/主张，还是涉及核心设计；避免从局部不一致推出全篇无效。
6. 生成供用户double-check的问题及建议暂缓/附条件使用方式。
7. 同一根源疑点合并，说明是影响主结论、局部数值还是仅排版；表达风格和不影响理解的小问题不升级成科学性裁决。

严格分开READING_GAP、WORKFLOW_ERROR、SOURCE_ANOMALY和VERSION_DIFFERENCE。Agent错误自行纠正；作者疑点保留原文并交用户；未收到用户答复时user_decision必须为null。用户选择也不自动成为事实证据。

输出：06_claims.json、06_issues.json、06_gate_G1_G2.md。每项疑点包含完整数据契约字段与证据引用。G2通过可附带尚待用户裁决的SOURCE_ANOMALY，但受影响主张标HOLD/CONDITIONAL；G1不能带未闭合阅读缺口。声明这是阅读/论证核验，不冒充实验复现。

修订2.2：发现可修复缺口就退回具体单元并继续，不因已有疑点分析而结束。合并时逐项比较字段来源，防止同一真值/负结果被套给无关实验；重复比较去重而非累计独立证据。G1/G2闭合后交07和08，不能由核验角色代签独立通过。

语义合并抽查用于发现问题，不授予完整验收：先对不同类型对象核对字段来源；若发现模板默认值污染，检查同生成路径的全部对象和依赖，而不是仅修发现的示例。作者的潜在用途/未来收益不能先改成“已证明改善”再批评；主张必须先忠实归因。
执行交接（2.2）：遵循[EXECUTION.md](../EXECUTION.md)，按merge格式提交源特定逐单元解释及专项记录，保留原角色依据；不能推迟细节，也不能在交接中改清单身份。Owner合并并实际执行next_action，阶段摘要不等于论文完成。01先保存清单再分派依赖读者；07在审查快照前写完报告/用户复核文本。

## Revision 2.4 execution safeguards

Read [Reliable execution](../../references/reliable-execution.md) before this stage. It defines small-team ownership, direct reviewer image capability and session evidence, generated/validated handoffs, source-anomaly comparison checks, dependency-aware repairs and full end-of-report display inspection. A reviewer unable to see source pixels cannot accept a visual paper by relying on writer records. Use the current review template and plain gate strings. Preserve actual blockers and never invent acceptance. Keep one canonical set of scientific IDs; update existing records instead of creating overlapping accounts of the same evidence.

## Revision 2.5 dependency synchronization

For failed-review repairs, finish canonical records, claims, notes, manual and generated notebooks, gate evidence, report, target analysis and visual data/captions as one batch. Regenerate outputs before scanning. New runs require repair-scan and a completed per-file report under repair_sync/; then use repair-ready --sync-file. Later current-file changes reopen readiness. Read [the shared repair synchronization contract](../../references/repair-synchronization.md).
