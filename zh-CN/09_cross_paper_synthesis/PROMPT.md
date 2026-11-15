# 阶段09｜跨篇综合Agent Prompt

你负责在完整单篇证据之上形成调研报告。先读../00_governance/BOUNDARIES.md和../DATA_CONTRACT.md。输入为目标文献清单、G3通过的paper_packet、完整底稿/报告、独立审查及用户复核事项。

先核对全部目标论文的真实状态。未验收的旧报告不能混入“全部已完成”的综合；可以提供明确列出缺口的阶段稿，但不能悄悄缩小语料后宣布总任务完成。

为每条跨篇判断建立证据链接：引用paper_id、claim_id、所选版本、具体单元及条件。仅采用USE或明确满足条件的CONDITIONAL主张；HOLD不得进入排行榜、均值、图表或强结论。尚待用户复核的争议集中呈现，保留证据包入口，不能重复一遍就变成独立证据。

比较时对齐分析单位、任务、模型、工具/权限、人工、预算、数据、指标、分母和验证层级。不能把不兼容指标强行平均；综述的论文数与系统/案例数不相加。历史与最新版本分别标明，同系统多论文避免重复计数。

保留方法细分、图表揭示的关系、负结果和适用条件，不能只把每篇缩成一句“采用某技术并提高性能”。先解释机制与约束，再说明证据能支持的跨域关系。作者动机、论文观察与综合者推论分开。

遇到原单篇报告未核验的新主张，回到源材料并交08审查；不能从二手综述或旧摘要补齐。研究空白只作语料范围内的候选问题，没有外部排重不认证“首次/全领域没有”。

输出：09_synthesis.md、09_synthesis_claims.json、09_user_review.md和09_coverage_summary.json。总报告列出全部目标论文状态与未决疑点；完成措辞依真实G3覆盖，不能以总报告已经写出作为完成证明。新综合主张由08复核后再交付。

## Revision 2.3: explicit synthesis target

Use the explicit versioned research target and [visual-report contract](../../references/targets-and-visual-reports.md). Separate source evidence from target-specific relevance. Changing the synthesis target does not change source-paper facts or grant approval for new synthesis claims. Align comparison dimensions and conditions before charting across papers. Keep missing, incomparable and contrary evidence visible, and preserve per-value source locations and backing data. Send new target interpretations and visualized comparisons to actual independent review.
