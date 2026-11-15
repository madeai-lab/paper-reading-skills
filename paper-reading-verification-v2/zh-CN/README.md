# 中文运行入口

目的：让每篇论文的正文、实验、图表、细分结构及相关补充材料得到可追溯的理解；发现论文疑点时，提供用户可复查的证据链。

## 运行顺序

| 阶段 | 文件 | 负责角色 | 输入与关卡 |
|---|---|---|---|
| 00 | [边界](00_governance/BOUNDARIES.md)、[协调Prompt](00_governance/COORDINATOR_PROMPT.md) | 协调Agent | 固定任务、版本、材料范围和分工 |
| 01 | [源材料与清单](01_source_inventory/PROMPT.md) | 材料Agent | 直接检查源文件，建立完整单元清单，G0 |
| 02 | [连续全文阅读](02_full_text_reading/PROMPT.md) | 正文Agent | 全部正文及范围内附录逐段覆盖 |
| 03 | [方法与分类](03_methods_and_taxonomy/PROMPT.md) | 方法Agent | 所有机制、假设、细分类别及关系 |
| 04 | [实验与统计](04_experiments_and_statistics/PROMPT.md) | 实验Agent | 所有实验、案例、消融、负结果和统计口径 |
| 05 | [图表与形式化](05_visuals_and_formalism/PROMPT.md) | 视觉Agent | 全部图/子图、表/表注、公式、算法及图文关系 |
| 06 | [交叉核验与疑点](06_evidence_and_anomalies/PROMPT.md) | 核验Agent | 连接方法—实验—图表—主张，形成疑点证据链，G1/G2 |
| 07 | [报告与用户复核包](07_report_and_user_review/PROMPT.md) | 写作Agent | 完整底稿、简明报告及疑点呈现 |
| 08 | [独立验收](08_independent_acceptance/PROMPT.md) | 独立审查Agent | 先看源材料，再对照交付；决定G3 |
| 09 | [跨篇综合](09_cross_paper_synthesis/PROMPT.md) | 综合Agent | 只采用通过G3的单篇主张，逐项保留限制 |

阶段02—05在G0通过后可并行，必须互相交接发现。它们先独立从完整源材料工作，其他角色的记录尚未生成时不等待；在06前再闭合相互依赖。各角色写入独立阶段目录，由Owner合并，避免互相覆盖。07以06为基础；08发现问题时退回相应阶段，修改后重新审查。09的新事实或新比较也须经过08核验。

每个Agent先读[边界](00_governance/BOUNDARIES.md)和[交接数据约定](DATA_CONTRACT.md)，再读自己的Prompt。协调者为每项任务填入任务JSON、源材料根目录、分配的单元ID、输出目录和已有交接包。Prompt中的“你”指该角色Agent，不是论文作者。

## 交付原则

每篇只有一名负责最终闭合的Owner；不允许“视觉Agent以为实验Agent看了、实验Agent以为正文Agent看了”。可以分片读取长论文，但最终必须合并所有分片，不因页数或上下文预算而截断范围。

供用户阅读的精炼报告可以短；保存信息的阅读底稿必须覆盖全部信息单元。先覆盖、理解、核验，再压缩。不能用简短报告反向限制阅读。

[用户复核包示例](../examples/user-review-example.zh-CN.md)演示如何呈现真实源材料疑点，而不是由Agent替用户裁决。

[验收情境](ACCEPTANCE_CASES.md)用于检查是否仍会漏图、漏附录、混淆指标或替作者做无证据裁决。本包的静态验证不等于已验证真实Agent运行效果。

## 修订2.2：调用即执行

先读[执行与停止条件](EXECUTION.md)。只给本skill和论文路径也须自行建任务及输出目录、执行00—08、安排独立审查并闭合修复；不因已写出部分分析而结束。单篇不执行09。
按EXECUTION.md使用本地控制助手统一初始化、逐单元交接、失败审查修复队列及实际被审内容快照。它不运行模型，也不证明语义通过。CONTINUE要求Owner实际完成返回的工作。
