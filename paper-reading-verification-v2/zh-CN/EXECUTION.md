# 执行与结束判断（修订2.2）

论文加skill调用即执行00—08。默认完整范围，不自动扩大为实验复现。本地助手只保存规范记录，不运行模型、建服务、证明已理解，也无法阻止宿主提前结束。

## 1. 初始化，再建立源清单，之后才能分派依赖读者

使用 python "<skill>/scripts/reading_run_control.py" init "<新运行目录>" --source "<论文.pdf>" --owner "<真实Owner标识>" --language zh-CN。
新目录必须不存在。助手复制来源并记录哈希，建立task、assignment、state及packet JSON，所有gate为PENDING。自行补充可查身份信息，启动即安排真实独立审查容量。

读取阶段01，实际检查源文件及全部页面，保存：
- 01_sources.json：来源数组，含真实身份、page_count、版本、local_path和实际sha256。
- 01_inventory.json：完整单元数组，含稳定unit_id、kind、label、source_id、locators、parent_id、children及assigned_owner。包含有信息的无字母区域、理解贡献所需参考信息、缺失但应读的补充材料；不能把每篇被引论文都列成已取得全文的阅读对象。
- 阶段01依据：身份、材料完整性、页/段拼接与范围检查。

编辑清单后用同一助手运行 sync "<运行目录>"，通过merge提交Owner的G0决定。G0有依据地PASS后，02—05才可开始。新发现/定位更正保留在清单中，并使受影响阅读/审查失效，不删除难读对象。

有帮助时给专项读者完整来源、单元ID、阶段Prompt与数据契约；可合并阅读角色。独立审查者必须与作者不同，支持时使用无历史新上下文（如fork_turns="none"），先给来源及08要求，保存其独立清单后再给底稿/结论。已完成读者可释放容量，不能把主要作者换名充当审查者。

## 2. 每批保存真实理解，然后执行下一动作

每次读完一段、交接或修复后运行 next "<运行目录>"。terminal_decision=CONTINUE时实际执行next_action后再判断；返回ID只是分批，不是允许省略其余对象。工作中发进度消息。

角色交接JSON包含writer_id，以及units、methods_taxonomy、experiments、claims、issues、gate_results中的所需集合；不接受其他顶层键。units按已入清单的unit_id部分更新，不能在交接中改身份/kind/定位。提交read_state、源特定understanding_note及真实存在的evidence_refs。信息性视觉对象须实际打开原图，记录visual_review及artifact_refs/checks/limitations。视觉/形式化详细解释可放在unit及笔记中。READ/UNDERSTOOD不会自动升为CHECKED；只有实际完成内容与来源交叉检查才可标CHECKED，脚本收下交接不等于检查通过。

使用 merge "<运行目录>" --file "<角色交接.json>"。助手保留原交接，合并逐单元解释/专项记录，生成full_notebook.md和material_index.md，省去重复手抄同一份底稿。生成文件不证明理解；“细节稍后再写”不是完成证据。实验记录须包含DATA_CONTRACT全部字段，填写与该实验对应的内容或有依据的NOT_REPORTED/NOT_APPLICABLE，不能全套机械填NA。

仅Owner可merge G0—G2，使用decision（PASS/FAIL/PENDING）、evidence_refs、open_items，不能用status代替decision。G1/G2要求实际完整单元检查和阶段06语义核对，不允许只改标志。G3只来自真实独立审查。

连续读正文并保留段落/页间衔接；读全部信息图/子图/表注、公式、实验/负结果、分类关系及附录。文中未给操作定义的被引方法须明确“未给”，不能假装读了被引原文。每个解释保留内容、关系、条件与局限。

## 3. 审查结果把控制权交回Owner

完成06/07，从完整记录写report.md及user_review.md。报告可标“待独立审查，当前决定见paper_packet.json”；审查前写完科学内容，避免为了更新状态而改变已审文本。

独立审查者先自建源清单，再逐项比较packet/底稿/报告与原位置。决定前运行 snapshot "<运行目录>"，把reviewed_scope_revision、reviewed_source_hashes、reviewed_content_sha256填入新的真实审查记录。快照只绑定已查版本，不证明身份或理解。审查期间不改被审材料；若改了，由审查者复查受影响内容后重新取快照。review_id只用字母、数字、下划线、点、连字符，每个新决定使用新ID。

审查返回后，Owner立即运行 ingest-review "<运行目录>" --file "<真实审查.json>"，保留实际决定和失败gate。REVISION_REQUIRED表示继续执行返回的REPAIR动作：
1. 回源核查并修复记录、解释和依赖主张，为每个repair_id保存修复依据。
2. 实际修复后运行 repair-ready "<运行目录>" --id "<repair_id>" --evidence "<本地修复说明>"。
3. 有依据地重新核对失败的本地gate，再交给真实审查者复查；再次失败则继续修复。READY_FOR_REVIEW不是通过。

历史发现必须保留。不能覆盖旧审查、由Owner填验收、把新快照抄进旧批准，也不能因为失败状态已保存就结束。当前repair_requests由审查者逐项关闭，新通过记录保留既往修复及关闭证据。

## 4. 最终交付或有证据的中断

运行 next "<运行目录>" 及 python "<skill>/scripts/reading_run_check.py" "<运行目录>"。失败时修复实际工作或记录不一致后重新判断。完整交付要求ACCEPTED及真实源优先语义验收。脚本只查一致性及材料版本，不能发现全部源遗漏、证明看过图或认证Agent，不能说成科学认证。

仅用户停止、实际平台/资源限制、确实缺失材料、真实缺少独立能力允许未完成交接。材料/能力阻塞前须完成其他可做工作。execution_state记录stop_reason为USER_STOP、RESOURCE_LIMIT、MATERIAL_BLOCK或CAPABILITY_BLOCK，保存restart_action；interruption含observed_constraint、attempts、evidence_refs、affected_unit_ids。材料受阻单元保留BLOCKED，记录affected_repair_ids；能力受阻只适用于完成可做阅读及报告后的REQUEST_REVIEW，并记录affected_action=REQUEST_REVIEW和实际不可用工具证据。“尚未审查”、暂时满员、主观耗时不是能力/资源阻塞。

INTERRUPTED_WITH_EVIDENCE明确表示未完成，不能叫验收。字段无法证明限制是真的，必须核对真实用户/工具/平台证据。突发宿主中断可能来不及调用助手，应保存尽可能小且真实的重启信息，不能暗示会自动后台继续。

作者疑点通常不中断阅读。保留证据链、替代解释、受影响HOLD/CONDITIONAL主张和明确double-check问题，可用VERIFIED_WITH_USER_REVIEW；用户判断与科学证据分别记录。

没有Python时手工维护等价规范记录，披露未运行自动检查，仍须真实审查。确无独立能力时完成可做工作，保留G3 PENDING。来源边界及既有授权始终有效。
