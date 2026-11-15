# 阶段08｜独立证据审查

你是与主要作者分开的独立审查者。先读[边界](../00_governance/BOUNDARIES.md)、[数据契约](../DATA_CONTRACT.md)和[审查模式](../../references/review-modes.md)。任务是发现遗漏和误解，不能只检查文件。若参与主要撰写或无法访问来源，披露并保持 G3 PENDING。

## 建立独立起点

初次指派时，工具支持则使用无历史的干净上下文。在读取报告结论前，将自己的来源优先结构图保存在 reviews/，启用时先读绑定来源的原生元素。存在必需看图的图形/位图/冲突对象时尽早验证真实像素能力；纯原生文字/表格来源不伪造探测。KEY_CLAIMS 记录身份、页/节结构、图表、方法/结果、附录/附件与遗漏风险，不重建完整底稿。FULL_DOUBLE_READ 自行建立完整清单并检查全部单元。未记录模式的旧运行仍采用原有全面审查规则。

## 检查当前证据

运行 review-plan，核查每条当前 claim 及其完整来源依赖链。独立检查报告/目标答案/综合结论、重要数值、因果/比较/泛化/创新/缺失证据判断、限定及原文疑点是否漏登，要求将漏项登记为 claim。按[PDF原生元素](../../references/native-elements.md)直接查看必查图形/位图/冲突对象的原图像素，保留必要父图/子图上下文；完整有效的原生表格由你独立核读结构化证据。标签不等于图表数据。核查口径、计算、负结果和局限，不能只复述图注。

KEY_CLAIMS：将 Owner 全部清单与自己的来源结构图对照，按控制器计划分层抽查普通单元，N 个非关键单元中至少检查 min(N, max(5, ceil(0.20*N))) 个。发现实质性错误则扩查同类对象和依赖；两个不同单元出现同类实质性错误，检查该类型全部单元。广泛漏读或证据系统性不可信时升级完整双读或不予通过。抽查是诊断起点，不是上限，也不代表全部内容独立重读。

FULL_DOUBLE_READ：核查全部范围内单元、信息性图/子图/表、实验、分类节点和主张。两种模式均要求 Owner 完整精读、关闭阅读缺口、主张有相称证据、方法/实验/图表对应，未决原文疑点对应主张保持 HOLD/CONDITIONAL。不能假定同预算，也不能把作者口气或用户选择当作验证。

核对当前研究目标及全部答案、图像来源、派生数据与计算；有可用查看器时检查最终报告显示，无法渲染则披露。文件、标记、哈希和预检通过都不等于理解或真实查看。

## 一次返回具体决定

完成计划核查后集中返回当前发现。每个修复项列出来源位置、原解释、实际差异、影响、受影响 ID 和可观察的关闭条件；区分科学错误、流程错误和原文疑点。单纯排版偏好不另开科学复审。输出 independent_review.json、.md 和 08_repair_requests.json，真实选择 REVISION_REQUIRED、MATERIAL_BLOCKED、VERIFIED_FOR_SCOPE 或 VERIFIED_WITH_USER_REVIEW。

使用当前审查模板。记录真实 reviewer/session 身份、review_mode、coverage_label、来源优先证据、checked claim/unit ID、实际图像观察、对不看像素验收的必查原生表格由你填写的 structured_inspection，以及 coverage_check。保存实际草稿和观察后，执行 snapshot "<run>" --file "<review-draft.json>"，将返回的四个快照字段写入新的 review ID，确认审查期间被审记录未变。不能自行重写 packet/state，也不能刷新旧批准。

## 增量复审修复

遵循[增量复审](../../references/efficient-reinspection.md)及[修复同步](../../references/repair-synchronization.md)。保留同一个真实审查者。检查 review-delta、修复关闭、受影响依赖、新增证据和逐文件处置；只沿用自己已核实的未变覆盖，记录 continuation.previous_review_id、retained_unit_ids 和 rechecked_unit_ids，检查后取新快照。替补者披露 replacement_reason，直接核查自己接受的全部当前 claim 和修复；前任笔记是有出处的参考，不是继承的查看经历。

失败决定把控制权交给 Owner。重复流程错误先修生成与同步机制，不自动通过。KEY_CLAIMS 验收不能称为完整独立双读。
