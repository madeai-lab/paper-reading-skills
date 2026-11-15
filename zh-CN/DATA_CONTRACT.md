# 交接数据约定

## 修订2.7获取记录

新运行的 `content_acquisition` 绑定 `method=PDFPLUMBER_NATIVE` 与 `manifest_ref=source_elements/manifest.json`；manifest 记录来源哈希、解析器及逐页文件哈希。每个新运行已检查单元均记录 `content_reading`，含 `mode=NATIVE_ELEMENTS|VISUAL|MIXED`、已有 `page_refs`、准确 `element_ids` 和 `conflict_resolution_refs`。ID必须连回正确来源/页面/对象，不得隐藏未解决解析冲突。只有完整有效的原生 TABLE 可据此替代看图；未看像素时仍保留 `actually_viewed=false`。FIGURE/PANEL/OTHER_VISUAL 仍需实际查看。对不看像素而验收的必查原生表格，审查者用自己的 `structured_inspection` 记录已查 `unit_ids` 与本地 `evidence_refs`；其他文字证据仍须真实回源核查主张，不能继承 Owner 标志。获取路径、证据边界及命令见[PDF原生元素](../references/native-elements.md)。元素文件与冲突解决依据受快照绑定，变化会重新打开依赖。旧运行缺少字段不等于启用例外，也不自动迁移。

## 修订2.6：审查模式

先读[审查模式](../references/review-modes.md)，再应用旧版执行说明。新运行默认 KEY_CLAIMS；FULL_DOUBLE_READ 保留完整独立双读；未记录模式的旧运行维持原有全面审查。Owner 始终完整覆盖全部来源单元，阶段08的独立核查范围按模式确定。不迁移正在运行或冻结的批次。

所有阶段使用同一任务编号、source_id、unit_id、experiment_id、claim_id和issue_id。字段名保持英文，内容可中文。模板在[shared](../shared/packet.template.json)；空模板不是已完成记录。

## 1. 定位和单元

source：source_id、title、version、publication_status、local_path或url、sha256（本地文件实际计算）、page_count、access_state、supplement_of、required_for_scope、missing_reason。

unit：unit_id、kind、label、parent_id、children、source_id、locators、assigned_owner、read_state、information_role、understanding_note、evidence_refs、visual_review、dependencies。
kind使用SECTION、FIGURE、PANEL、TABLE、EQUATION、ALGORITHM、APPENDIX、OTHER_VISUAL、BIBLIOGRAPHY。父图和每个子图分别编号，例如P20-F04和P20-F04-d；嵌套小节、组合表、未编号插图同理。

locator：physical_page、printed_page、section、object_label、panel、paragraph_or_cell、image_path。不适用字段可为null；不可猜页码。跨页对象可有多个locator。

read_state使用INVENTORIED、READ、UNDERSTOOD、CHECKED、BLOCKED或NON_INFORMATIVE。每次升级附本阶段记录，不抹去其他角色发现。visual_review含required、actually_viewed、artifact_refs、checks、limitations；截图生成不允许自动设置actually_viewed。

understanding_note写明内容、关系/机制、条件/单位、支持及不支持的解释。笼统“已读懂/见图/正确”不合格。evidence_refs必须指向实际源材料定位及已有底稿/图像，不能只链接旧报告。

## 2. 专项记录

experiment：experiment_id、purpose、unit_refs、design、data_and_sampling、split、ground_truth、models_and_tools、comparators、budget、metrics、results、uncertainty、negative_results、failure_cases、limitations、claim_refs。
数值记录value、unit、denominator、population、time_or_condition、source_locator。字段缺失用NOT_REPORTED、NOT_YET_FOUND或NOT_APPLICABLE并解释依据，不能都填NA。

method/taxonomy：每个组件或节点有自己的ID、定义、输入/输出、关系、假设、训练/运行阶段、分类/映射规则、例外及原文定位。叶节点不能只由父节点一句话代替。

visual/formal record：unit_id、observed_content、encoding、relationships、conditions、text_links、experiment_links、claim_links、exact_vs_estimated、limitations、evidence_refs。公式/算法另记符号、假设、输入输出、步骤/推导功能和适用边界。

claim：claim_id、text、attribution、source_refs、supporting_units、experiment_refs、conditions、support_state、allowed_use、issue_refs。attribution四类见B09；support_state使用SUPPORTED、LIMITED、CONTRADICTED或UNDETERMINED；allowed_use使用USE、CONDITIONAL或HOLD，不把作者强表述直接设为SUPPORTED。

## 3. 疑点记录与用户决定

issue：issue_id、kind、status、observations、source_refs、minimal_evidence、calculation、alternative_explanations、checks_performed、missing_evidence、affected_claims、impact、recommended_use、user_question、user_decision。
kind取READING_GAP、WORKFLOW_ERROR、SOURCE_ANOMALY或VERSION_DIFFERENCE。status取OPEN、CORRECTED、EXPLAINED或USER_REVIEW。user_decision在用户未回答时必须为null，不得模拟同意。

用户复核包用同一issue_id，包含：
1. 一句话疑点；对象版本。
2. 两处或多处原文位置与可读图像/必要转述，说明实际看到什么。
3. 同口径比较或计算；无计算时说明不适用。
4. 已排除和仍可能的解释，不用无依据概率。
5. 影响哪项主张、是否影响其他结果。
6. 建议暂缓/附条件使用的具体结论，以及请用户double-check的具体材料。
7. 用户决定与证据状态分别记录。人类选择不替代源证据。

## 4. 独立审查与状态

review：review_id、reviewer_id、independence_disclosure、source_first_inventory_ref、checked_unit_ids、checked_claim_ids、findings、unresolved_reading_gaps、open_source_issues、gate_decisions、decision、repair_requests。
审查者与被审作者相同、只读了旧摘要、未能独立看源材料时，不能声称独立审查已完成。不能伪造第二个Agent或审查身份。

paper_packet包括task_id、paper_id、scope_mode、scope_revision、paper_status、sources、units、methods_taxonomy、experiments、claims、issues、reviews、gate_results和deliverables。协调者合并交接，保留冲突和原角色记录。采用COMPLETE_PAPER时，G1前全部应读单元均须CHECKED；例外只可为经确认的NON_INFORMATIVE，不能排除难读信息。

每道gate_results记录PASS、FAIL或PENDING，以及决定依据和未闭合项。只有独立审查决定能将G3置PASS。没有结构化证据时不能仅凭报告标题或清单勾选补建通过记录。

## 5. 最终交付

- paper_packet.json：协调合并的索引。
- full_notebook.md：覆盖全部单元的完整阅读底稿，链接专项记录。
- report.md：供用户阅读的报告，明确范围与状态。
- material_index.md：章节、图表/子图、实验、分类、公式和附录目录。
- user_review.md：所有未决SOURCE_ANOMALY及其证据链；无疑点也说明核查范围，不能虚构问题凑数。
- independent_review.json / .md：独立审查结果。
- 其他专项JSON/Markdown按阶段Prompt命名；真实源文件及渲染图保存在用户允许的位置，分享时遵守材料权限。

## 6. 修订2.2运行记录与检查器

paper_packet另记录owner_id、writer_ids（所有实际撰稿角色），skill_revision。execution_state.json按[模板](../shared/execution-state.template.json)记录阶段、未闭合ID、下一动作、阻塞原因/尝试/结果及修复历史；每次交接更新。不得为通过检查器而删除01_inventory.json已有ID；发现新项追加并更新范围修订，定位更正留变更记录。

本地只读检查器采用：01_inventory.json为单元数组；paper_packet字段遵照本契约；gate evidence_refs、unit evidence_refs、visual artifact_refs、source_first_inventory_ref和deliverables值使用可解析的本地路径字符串（相对运行目录或绝对路径）。正文源定位仍另放locators；URL可另保存在source_refs。deliverables五个键为full_notebook、report、material_index、user_review、independent_review。

checked_unit_ids与checked_claim_ids展开为实际ID列表，不用自然语言范围；最后一条reviews必须是当前修订真实审查决定。所有NON_INFORMATIVE也须有解释并由审查者检查。comparison_id/same_as标记同一实验证据的重复呈现，不重复累计。

脚本能发现记录不一致，不能鉴定“见图”是否理解、人工填写身份是否独立、图像是否真的查看，或清单是否漏掉源对象。这些由真实角色工作、源优先审查和实际工具记录验证；不能把返回码0写成G3通过依据。

### 当前修订与缩小范围

独立审查记录必须含reviewed_scope_revision，以及reviewed_source_hashes（source_id到实际sha256的映射），由审查者依据自己检查的材料填写；gate_decisions须与packet全部gate一致。更换源文件或范围后旧审查失效，不能由Owner复制新hash为旧审查背书。改了重要解释/数值/主张须按B16重审。本地助手用reviewed_content_sha256绑定记录解释及本地证据，语义是否充分仍靠真实审查。

只有用户明确缩小范围时可用scope_mode=USER_DEFINED_SCOPE，并保留原清单ID。scope_exclusions逐项记录unit_id、reason、实际用户授权记录的本地路径user_authorization_ref及当前scope_revision；对应单元read_state=OUT_OF_SCOPE，不伪造理解说明。审查者仍检查排除依据并列其ID，报告显著标PARTIAL_SCOPE及实际子范围，不能叫完整论文。COMPLETE_PAPER不允许此排除。依赖未读范围外对象的主张HOLD。Owner不能自行缩范围满足检查器。

repair_requests仅列当前未关闭请求；已修复项移入closed_repairs或保留旧review/history及关闭证据。最后一条review的template_only不能为true；空模板不能签验收。

### 可执行交接与当前内容快照

助手命令见[EXECUTION.md](EXECUTION.md)。使用init/sync/merge，避免另造规范JSON。gate对象用decision、evidence_refs、open_items；execution_state用stage、open_unit_ids、next_actions，不能用phase/open_ids/next_action替代。原始交接包含writer_id，及所需units/methods_taxonomy/experiments/claims/issues/gate_results集合，不加其他顶层键。底稿从记录生成，逐单元提交完整、源特定解释，不能只承诺稍后补细节；保留其他角色工作，将未解冲突记录为issue。

审查者检查最终材料后独立运行snapshot，把reviewed_content_sha256及reviewed_scope_revision、reviewed_source_hashes写入审查。快照绑定清单/来源清单、单元/方法/实验/主张/问题记录、本地来源及证据文件、底稿/索引、报告/用户复核文本；排除执行/审查输出以免循环哈希。定位、解释、证据或报告变化须复查并出新审查。令牌可被虚假复制，真实工具顺序及身份仍是必要证据。没有该字段的旧审查仅为历史记录，不授予当前2.2验收。

repair_requests每项用repair_id、unit_ids、responsible_role、required_action，包含源位置及影响依据。repair-ready在state.repair_progress保存READY_FOR_REVIEW及evidence_refs，不关闭审查请求。审查使用唯一安全review_id追加保存；失败决定也须ingest-review，让Owner取得可执行修复队列。未决请求由真实复查关闭。

next返回CONTINUE、ACCEPTED或INTERRUPTED_WITH_EVIDENCE，以及may_send_final/paper_accepted。CONTINUE要求实际执行next_action，不是最终回复列计划。助手无法强制宿主/模型继续。中断记录必须对应真实有据限制，自行生成文字无法证明限制。

## Revision 2.3 extensions

The optional research_target and report_visuals packet fields, target_analysis.json, report_visuals.md and quantitative backing-data contracts are defined in [Targets and visual reports](../references/targets-and-visual-reports.md). research_target is distinct from bibliographic target_identity. The helper binds it at init --target or set-target --file; target changes preserve source units but invalidate acceptance of changed interpretation/report. Target-specific analysis remains separate from general source findings. Optional fields are omitted from legacy fingerprints when null/absent; existing runs are not automatically migrated or reapproved.

Register display images and derived-chart backing data with artifact_refs/evidence_refs. The snapshot also binds simple inline Markdown images; complex/reference-style or HTML images require explicit registration. Generated display and structural validation do not establish actual viewing, scientific understanding or semantic acceptance. Complete target analysis and visual output before the reviewer snapshots the packet.

## Revision 2.4

The shared [Reliable execution contract](../references/reliable-execution.md) is required. Graphical/raster/conflict objects require the reviewer's own visual_inspection/session/observation evidence for accepted G3; new native-acquisition runs may independently inspect validated complete tables under [Native PDF elements](../references/native-elements.md). Runs without that explicit acquisition contract retain their prior visual requirements. Use handoff-template and review-template; validate-handoff is read-only and precedes merge. Parent/panel links must be reciprocal and same_as references must resolve. Existing runs are not migrated. Templates and structural checks cannot establish actual inspection, independence or understanding. A blocked required image channel retains G3 unaccepted.

## 修订2.6审查字段

任务、packet 和 review 的 review_mode 使用 KEY_CLAIMS 或 FULL_DOUBLE_READ。packet 未记录模式表示旧版 FULL_DOUBLE_READ，不是新默认；不迁移正在运行/冻结的批次。控制器将全部当前 claim ID 计算为强制 key_claim_ids；review_requirements.key_unit_ids 可增加必查单元。claim supporting_units、experiment unit_refs、疑点链接与递归单元依赖/父图上下文决定证据范围。报告、目标答案和综合中的实质性判断均须登记，审查者独立检查语义完整性。

review 记录计算得到的 coverage_label、实际 checked_unit_ids/checked_claim_ids，以及 coverage_check：source_structure_checked=true、owner_coverage_checked=true、omissions=[]、evidence_refs 指向已有审查证据。true 必须来自实际工作。KEY_CLAIMS 覆盖全部当前 claim、必查依赖单元及控制器计算的分层普通样本，审查者视觉记录覆盖必查的已检查视觉单元。FULL_DOUBLE_READ 仍检查全部单元，明确启用原生获取时按原生契约选择证据；旧运行维持其原有全部单元/图像要求。Owner 在两种模式下均须完整阅读。

已有审查后的 continuation 记录 previous_review_id、retained_unit_ids、rechecked_unit_ids，替补时说明 replacement_reason。沿用覆盖要求真实 reviewer_session_id 相同且内容未变；rechecked ID 表示实际新核查，替补不能继承前任查看经历。新决定使用新 review ID 和四个新快照字段。分别说明 Owner 完整精读与独立审查模式，不能将 KEY_CLAIMS 的通过状态表述为完整独立双读。
