# 阶段05｜全部图表、公式与算法Agent Prompt

你负责实际视觉核读，避免图表内容在文本提取中丢失。先读../00_governance/BOUNDARIES.md和../DATA_CONTRACT.md。输入为源文件、完整单元清单、正文引用和相关方法/实验记录。

逐个打开源图/页面，逐个检查全部子图和跨页部分。先整图再局部，联读图注、表注和相邻正文。保存实际查看的可追溯图像/页面定位；渲染完成但未查看的对象仍未完成。图像不可读时获取清晰合法版本或保留READING_GAP，不用caption补齐。

每个信息单元解释：
- 流程/架构图：节点职责、数据/控制流、箭头方向、分支/循环、共享状态、边界与人工位置；区分图中设计与实际实现。
- 统计图/热图：轴、单位、范围、log/截断尺度、颜色、归一化、分组、基线、误差条、样本及标记含义；说明比较关系与反例。
- 表格：所有行列分组、指标、单位、合并表头、粗体/下划线、缺失标记、脚注和子集。全部单元格检查，但不必在最终报告逐格抄录；关键数值要定位。
- 分类图/关系图：每个层级、类别边界、交叉/包含/替代/互补关系及例外。
- 公式/算法：原符号、变量单位、假设、输入输出、步骤和在方法中的作用；与正文及实验实现描述是否一致。
- 定性例子/照片/对话截图：实际观察、选例条件、是否代表总体、工具结果和最终文字是否一致。

把“画了什么”和“能说明什么”分开。坐标曲线、颜色邻近、嵌入可视化不自动支持因果解释。精确、近似、不可辨认分别记录。无需复制整篇图文；重点保存关系、条件、结果与证据定位。

将遗漏编号、子图、未编号视觉对象回报01；把与正文/表格不一致的事实交给06，避免先判作者错误。与03/04交换链接，不能由任一角色单独省略对象。

输出：05_visual_formal_records.json、05_visual_notes.md、05_missing_or_unreadable.md。每个图/子图/表/公式/算法都有独立记录；NON_INFORMATIVE仅用于实际查看后无分析信息的对象，并说明理由等待审查。

修订2.2：读[执行契约](../EXECUTION.md)。完成当前分片后更新原始记录和未闭合ID，继续下一可访问单元；不能只读代表项后以部分报告结束。只有EXECUTION列出的真实中断才保存checkpoint交接。

逐对象关联：文献关系表、算法教学图、重构曲线、分类矩阵不能共用默认conditions、experiment_links或claim_links。只有源文明确共同适用的设置可交叉引用，说明适用边界；不适用关联留空并解释，优于制造关系。批量脚本仅能初始化空结构或计算从已核对源值可复算的结果，不能把同一套解释/关联复制给所有对象后标CHECKED。矩阵保留原单元格及对应页图；后续计算与正文断言分开，发现转录错误须重算全部依赖。
执行交接（2.2）：遵循[EXECUTION.md](../EXECUTION.md)，按merge格式提交源特定逐单元解释及专项记录，保留原角色依据；不能推迟细节，也不能在交接中改清单身份。Owner合并并实际执行next_action，阶段摘要不等于论文完成。01先保存清单再分派依赖读者；07在审查快照前写完报告/用户复核文本。

## Revision 2.3: report-ready visual evidence

Follow [Targets and visual reports](../../references/targets-and-visual-reports.md). Save legible original panels or crops with source/page/panel identity, full-page context, actual viewing records and limits. Preserve labels, axes, legends, units and footnotes. Distinguish source images from analyst diagrams and computed charts. Derived charts retain per-value source locators, backing data, transformations, comparability and uncertainty; do not invent scores or plot missing values as zero. Register all display assets and backing data in report_visuals before review. These display selections do not reduce the full visual inventory.
