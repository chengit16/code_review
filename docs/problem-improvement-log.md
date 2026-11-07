# 问题与改进台账

本文从 2026-11-06 起记录本项目会话中处理的问题与阶段性改进。记录以可核对证据为依据，不声明已经收集所有历史会话；业务事件、任务和投递的事实仍以 SQLite 为准。

## 维护约定

- 每次问题处理或阶段性改进结束，在最终答复前追加记录；无须用户再次要求。尚未解决、仅完成方案、验证受阻或暂缓的事项同样记录。
- 编号使用 `PI-年月日-当日序号`，在本项目内唯一。同一事项继续处理时，追加带日期的进展并关联原编号，保留当时的判断、验证与部署边界；结论纠正也以追加说明的方式保留来龙去脉。
- 记录现象或目标、原因或分析、已采取措施、验证证据、部署状态和下一步。未证实的根因明确写“待确认”，无效尝试在有排查价值时一并保留。
- “代码修改”“本地验证”“部署生效”分别填写；文档变更单独说明，不能冒充业务代码实现。未执行的验证写“未运行”，环境不明写“无法确认”，无相关操作写“不适用”。
- 检查通过仅表示所列命令及其范围通过；阶段记录中的旧结论不作为本次重验结果。部署生效须有明确环境、版本或配置及生效证据，不能仅凭修改代码、构建成功或刷新浏览器认定。
- 不保存密钥、完整 Webhook 地址、私有配置、完整外部响应或敏感代码。优先关联脱敏摘要、仓库文件、提交或现有实施文档。
- 本文件作为本会话的追加来源，由独立 monitor 每 30 秒同步至 SQLite 的“问题与改进”菜单，保留 PI 编号及每次完整版本；不自动抓取聊天、终端或其他会话。页面人工修改优先保护，后续来源追加会标记冲突，须核对后处理，不互相覆盖。
- 可选 `同步状态` 字段填写单行 JSON，仅允许 kind、category、status、code_state、verification_state、deployment_state；取值遵循后端契约。未显式标注的状态保守保留未知/未运行；验证和部署证据仍须分别填写。遗留字段仅精确的“无”或“无。”映射为空，其余文字均阻止自动归档。

## 记录模板

```markdown
### PI-YYYYMMDD-NNN｜事项标题

- 记录日期：YYYY-MM-DD（北京时间）。
- 类型与进展：问题修复 / 阶段改进；待处理 / 排查中 / 已完成方案 / 待验证 / 阶段完成 / 已解决 / 暂缓。
- 关联记录：无，或原事项编号。
- 现象或目标：描述问题、触发条件、影响，或希望达到的改进目标。
- 原因或分析：已确认原因、证据，以及仍待确认的部分。
- 处理与改进：已采取措施、关键决策；必要时保留无效尝试。
- 代码修改：未修改 / 已修改（范围）/ 不适用；如仅修改文档，单独列明。
- 本地验证：实际执行的命令、结果、范围和缺口；未执行则写未运行及原因。
- 部署生效：未部署 / 已部署且已确认（环境与证据）/ 无法确认 / 不适用。
- 关联文件或证据：仓库相对路径、提交或脱敏证据来源。
- 遗留与下一步：未解决内容、阻塞原因和后续动作；无则写无。
```

## 记录正文

### PI-20261106-001｜规划问题与改进菜单及持续记录流程

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；已完成方案，菜单待实现。
- 关联记录：PI-20261106-002。
- 现象或目标：用户希望集中查看项目遇到的问题、解决办法与整体优化过程，并持续收集本会话后续的问题处理和改进记录。
- 原因或分析：现有“待跟进问题”管理 OCR 对被评审代码的发现，与平台自身故障及优化历程不同；相关历史散落在阶段文档中，尚无统一的持续记录入口。
- 处理与改进：已提出独立“问题与改进”菜单及问题记录、优化历程、复盘视图方案；采用先记录闭环、再关联优化主题与汇总能力的实施顺序。当前以本台账承接持续记录，不将菜单方案描述为已交付。
- 代码修改：未修改；本次仅建立文档台账与项目执行约定。
- 本地验证：未运行菜单相关测试，因为菜单、接口与数据模型尚未实现；现有历史阶段测试未重跑，不作为本事项验收。
- 部署生效：未部署新菜单；本次未操作业务数据库或服务进程。
- 关联文件或证据：本会话的规划与用户确认；`frontend/src/app/App.tsx`、`docs/project-overview.md`、`docs/review-performance-plan.md`。
- 遗留与下一步：后续另行实施菜单、持久化模型和验证；历史记录仅按可核对来源整理，不能宣称全部回溯完成。

### PI-20261106-002｜将处理完成后同步记录纳入项目执行约定

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；记录约定与台账已建立。
- 关联记录：PI-20261106-001。
- 现象或目标：用户明确要求，每次问题处理或改进结束都必须同步记录，不能只把过程留在聊天中；未解决事项也要保留进展。
- 原因或分析：仅依赖会话不构成项目持久化记录，也无法清楚区分代码修改、本地验证与部署生效。
- 处理与改进：在根目录执行约定中加入最终答复前追加台账的要求，建立记录模板、追加历史及敏感信息边界，并在文档索引添加入口。
- 代码修改：不适用，未修改业务代码；已修改 `AGENTS.md`、`docs/README.md`，新增 `docs/problem-improvement-log.md`，保留工作区既有改动。
- 本地验证：待执行本次文档的差异空白检查和本地链接检查；不涉及业务功能测试。
- 部署生效：不适用，属于仓库文档与执行约定；未迁移业务 SQLite，未重启或部署 API、Worker、monitor。
- 关联文件或证据：`AGENTS.md`、`docs/README.md`、`docs/problem-improvement-log.md`。
- 遗留与下一步：后续任务按约定持续追加记录；菜单及自动导入尚未实现，本轮不补造不可核对的历史事项。

### PI-20261106-002｜追加：记录约定的文档检查结果

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；文档约定已完成检查，补充上一条待执行项的结果，不覆盖原过程。
- 关联记录：PI-20261106-002。
- 现象或目标：前一轮建立台账后，用户继续要求实施第一阶段；本条补齐已执行但尚未记入正文的文档检查结果。
- 原因或分析：持续记录要求应覆盖本次约定本身的验证，不能把“待执行”误当作已通过。
- 处理与改进：已运行 `git diff --check -- AGENTS.md docs/README.md docs/problem-improvement-log.md`，无错误；使用本轮内联 Python 文件存在性检查，原执行时根目录约定及文档索引的 33 项本地 Markdown 链接目标均存在。
- 代码修改：不适用，仅文档与执行约定。
- 本地验证：上述文档检查通过，不涉及业务代码测试或业务实例验收。
- 部署生效：不适用，未操作业务进程或数据库。
- 关联文件或证据：`AGENTS.md`、`docs/README.md`、`docs/problem-improvement-log.md`。
- 遗留与下一步：继续按约定记录每次阶段性完成及未解决进展。

### PI-20261106-003｜问题与改进第一阶段：平台台账与历史闭环

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；第一阶段本地实现与验证完成，尚未部署。
- 关联记录：PI-20261106-001、PI-20261106-002。
- 现象或目标：按用户确认的实施顺序，先提供独立菜单、问题列表与详情、新建与编辑、SQLite 持久化，再推进优化主题和统计能力。
- 原因或分析：现有 OCR 问题跟踪不适合承载平台排障；需要独立记录现象、分析、方案、证据及下一步，并防止新结论覆盖旧过程。
- 处理与改进：新增管理员专用“问题与改进”菜单及接口，支持搜索、分类、类型、进展、URL 分页、详情、编辑与历史分页；第 39 版迁移新增记录及快照表，不改写评审数据。创建使用 UUID 去重，更新以版本拒绝并发覆盖，当前摘要与历史同事务提交；验证通过、部署确认和不适用声明要求证据或说明。草稿失败和冲突保留，离开前提示。
- 代码修改：已修改；新增契约、迁移、用例、路由、前端 API 与页面，并接入导航、管理审计和 OpenAPI。旧库模拟测试同步移除新增测试表，确保真实重放旧版迁移；没有修改已有迁移脚本或恢复原有工作区改动。
- 本地验证：`.venv/bin/ruff check backend/ocr_manager backend/tests` 通过；`.venv/bin/mypy backend/ocr_manager` 通过（69 模块）；`.venv/bin/python -m ocr_manager.openapi_contract` 通过；`.venv/bin/pytest -q` 最终 393 项通过（新增台账 20 项）；`npm --prefix frontend run lint`、`npm --prefix frontend test`（59 项）、`npm --prefix frontend run build` 通过；`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm --prefix frontend run test:e2e` 完整 45 项通过。新增用例覆盖持久化、权限、证据、去重、并发、事务回滚、旧库迁移、草稿及窄屏；已查看桌面详情及 320 像素详情、表单截图。`git diff --check` 无错误；本轮内联 Python 检查的 62 项文档链接目标均存在（后续新增文档链接需重验）。
- 排查与无效尝试：初次沙箱内后端全量 388 项通过、3 项因 `ps` 被拒绝而失败，授权后全量重跑通过；浏览器最初因 8791 绑定受限未启动，授权后改用原定隔离服务完成，未绕过权限连接业务实例。前端构建曾暴露测试中使用不支持的 `exact` 选项，改为精确正则匹配后构建通过。保留一条既有 Starlette `httpx` 弃用提示，未据此升级依赖。
- 部署生效：未部署；仅运行临时 SQLite 和 8791 隔离服务，未迁移当前业务数据库，未重启 API、Worker、monitor，未调用真实 GitLab、模型或飞书。业务实例需要备份并协调同版进程升级至第 39 版后再验收。
- 关联文件或证据：`backend/ocr_manager/improvement_contracts.py`、`backend/ocr_manager/improvement_migration.py`、`backend/ocr_manager/improvements.py`、`backend/ocr_manager/improvements_api.py`、`backend/tests/test_improvements.py`、`frontend/src/pages/ImprovementsPage.tsx`、`frontend/src/pages/ImprovementDetailPage.tsx`、`frontend/e2e/improvements.spec.ts`、`docs/improvements-phase1.md`。
- 遗留与下一步：后续按顺序建立优化主题与阶段关联，再做汇总和自动归档。会话完成后的记录仍追加本文件，尚未自动导入 SQLite 页面；不声明已回溯全部历史，不向业务库静默写入或导入。部署升级须另行协调。
- 最终复核补充：补齐文档后重新执行本地链接检查，8 份相关文档的 63 项链接目标均存在；`git diff --check` 无错误。前端再次独立构建及完整浏览器复跑仍为 45 项通过；后端台账用例收集确认共 20 项，与最终全量回归范围一致。

### PI-20261106-004｜问题与改进第二阶段：优化主题、阶段历程与问题关联

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；第二阶段本地实现与验证完成，尚未部署。
- 关联记录：PI-20261106-001、PI-20261106-003。
- 现象或目标：用户要求继续下一阶段，不再处理当前业务实例菜单无数据的问题；本轮按既定顺序组织优化主题、有序实施阶段、关联问题和历史方案。
- 原因或分析：单条问题台账可以记录排查闭环，但缺少跨问题的整体优化目标、多个阶段的实施过程与当时的关系快照；不能只把问题标为完成就声称优化已部署。
- 处理与改进：在“问题与改进”增加“优化历程”视图，支持主题目标、背景、结果、分类、进展、搜索和分页；每主题最多 50 个阶段，独立记录代码、本地验证、部署及遗留；分页搜索并显式关联最多 500 条问题，问题详情可反向查看主题。每次保存完整保留主题、阶段和当时关联快照，创建幂等、版本冲突和事务回滚保护当前事实；关联不更改问题状态。完成主题及阶段须满足结果和证据约束，未解决的进展仍可保存。
- 代码修改：已修改；新增主题契约、领域用例、API、第 40 版迁移、前端列表/编辑/详情与选择器，以及对应测试；接入鉴权、管理审计和 OpenAPI，扩展旧迁移测试夹具；更新项目总览、配置、部署和索引，新增第二阶段实施记录。未回滚或覆盖工作区既有改动。
- 本地验证：`.venv/bin/ruff check backend/ocr_manager backend/tests` 通过；`.venv/bin/mypy backend/ocr_manager` 通过（73 模块）；`.venv/bin/python -m ocr_manager.openapi_contract --update` 已重新生成契约，随后 `.venv/bin/python -m ocr_manager.openapi_contract` 校验通过；`.venv/bin/pytest -q` 最终全量 409 项通过，主题单独收集共 16 项，涵盖鉴权、证据、幂等、版本冲突、并发、历史、关系、迁移及回滚；四组相关后端测试合计 42 项通过。`npm --prefix frontend run lint`、`npm --prefix frontend test`（63 项）、`npm --prefix frontend run build` 通过；`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm --prefix frontend run test:e2e` 最终完整 46 项通过，覆盖真实临时 SQLite、主题阶段、关联、历史、刷新持久化与 390/320 像素；已查看 320 像素主题详情和编辑截图。`git diff --check` 无错误；内联 Python 检查 8 份文档的 65 项本地链接均存在。
- 排查与无效尝试：后端初次主题测试中错误使用被解除关联的问题筛选，及将不存在的问题引用预期为 422，分别修正为验证当前关联和事务校验的 409；Ruff 发现未用导入和超长行，前端 Lint 发现拆分视图后遗留的未用导入，均修正。首次完整浏览器为 45 通过、1 失败，原因是新测试按问题标题查找实际按编号显示的关联链接，修正后专项 4 项与完整 46 项均通过。曾从根目录误用 `npm --prefix frontend exec playwright ...`，未加载前端配置而报缺少默认浏览器；改为已有 `run test:e2e` 入口，不额外安装浏览器。后端沙箱内为 406 通过、3 项因 `ps` 被拒绝失败，授权后重跑 409 项通过；浏览器 8791 绑定受限也经授权运行。保留 Starlette `httpx` 弃用提示与 Vite 主包约 500 kB 的体积提示，不把提示描述为功能测试失败。
- 部署生效：未部署；不检查或访问当前业务实例，不迁移业务 SQLite，不重启 API、Worker 或 monitor。浏览器仅使用 8791 隔离服务和临时库，不启动 Worker、不调用真实 GitLab、模型或飞书。第 40 版仅是源码目标，不表示业务数据库版本已变更。
- 关联文件或证据：`docs/improvements-phase2.md`、`backend/ocr_manager/improvement_theme_contracts.py`、`backend/ocr_manager/improvement_themes.py`、`backend/ocr_manager/improvement_themes_api.py`、`backend/tests/test_improvement_themes.py`、`frontend/src/pages/ImprovementThemesPanel.tsx`、`frontend/src/pages/ImprovementThemeEditor.tsx`、`frontend/src/pages/ImprovementThemeDetailPage.tsx`、`frontend/src/pages/RelatedImprovementThemes.tsx`、`frontend/src/test/improvementThemes.test.tsx`、`frontend/e2e/improvements.spec.ts`。
- 遗留与下一步：下一阶段为复盘汇总与统计，再推进归档能力；本轮不做历史批量导入、自动聊天同步或部署核验。会话结束后的记录继续追加本文件，尚未自动同步至 SQLite 页面。部署须另行备份并协调同版进程升级，不降低 `user_version` 回退。

### PI-20261106-005｜问题与改进第三阶段：复盘汇总与统计

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；第三阶段本地实现与验证完成，尚未部署。
- 关联记录：PI-20261106-001、PI-20261106-003、PI-20261106-004。
- 现象或目标：用户要求按计划推进复盘汇总与统计，在已有平台台账、主题与阶段基础上查看整体进展、处理活动和当前遗留事项，避免把保存次数、验证通过及部署生效混为同一结论。
- 原因或分析：台账和主题只有逐条详情，缺少统一汇总；当前模型没有足够明确的复发关联和生产验收事实，不能推导复发率、平均解决时长或期间解决率。必须把当前状态存量与时间窗口活动分开，并对记录、主题、阶段分别计数，避免多主题关联放大分母。
- 处理与改进：新增“复盘汇总”视图与管理员专用 `GET /api/improvement-summary`，只读现有第 40 版表，不新增迁移或后台任务。提供台账累计、已解决占比、关联覆盖、主题和阶段累计，分别展示代码、本地验证、部署分布；按北京时间统计新增与追加进展，默认近 30 天、最多 366 天，首尾含日、零活动日补零。提供未解决、验证待跟进、部署待确认和未完成主题清单，显示完整数量及最久未更新前十条，并可跳到记录/主题详情或筛选列表。日期只影响活动；分类按当前归属，不回放历史分类。聚合共用只读快照，成功保存使复盘缓存失效，查询失败不伪装零数据、旧响应不覆盖新条件。
- 代码修改：已修改；新增 `improvement_summary_contracts.py`、`improvement_summary.py`，在现有台账路由注册接口；新增前端 API、复盘编排和图表组件，接入第三个标签并补充编辑成功后的缓存失效。新增后端、前端和浏览器专项测试，重新生成 OpenAPI；更新操作指南、总览、部署、文档索引和前端交互说明，新增 `docs/improvements-phase3.md`。保留工作区既有未提交改动。
- 本地验证：`.venv/bin/ruff check backend/ocr_manager backend/tests` 通过；`.venv/bin/mypy backend/ocr_manager` 通过（75 模块）；`.venv/bin/pytest -q backend/tests/test_improvement_summary.py` 16 项通过；`.venv/bin/pytest -q` 最终全量 425 项通过；`.venv/bin/python -m ocr_manager.openapi_contract --update` 生成后，`.venv/bin/python -m ocr_manager.openapi_contract` 校验通过。`npm --prefix frontend run lint`、`npm --prefix frontend test`（69 项，新增复盘 6 项）、`npm --prefix frontend run build` 通过；`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm --prefix frontend run test:e2e` 最终全量 48 项通过（新增复盘 2 项）。测试包含超过列表单页的全量统计、关联去重、独立状态、日期与历史夏令时边界、历史初始版本排除、并发读快照、权限、只读性、重放与冲突、异步隔离、URL 返回和 1280/390/320 像素无页面溢出。已查看完整桌面和 320 像素复盘截图；`git diff --check` 无错误，内联 Python 核对 10 份相关文档共 72 项本地链接目标存在。
- 排查与无效尝试：初次前端校验发现新增缓存客户端误放在私有选择组件而非编辑器作用域，已移动到对应编辑器；Ruff 提示未排序导入及超长行，已修正。复盘单元测试最初使用数据路由时，JSDOM 的 `AbortSignal` 与 Node `Request` 不兼容导致导航失败；改用适合该组件的内存路由和地址观察测试，不修改生产网络实现，最终 6 项通过。检查日期分桶时发现固定加八小时不能覆盖允许日期范围内的历史夏令时，改用与窗口相同的 `Asia/Shanghai` 时区规则并新增回归。浏览器沙箱内绑定 8791 被拒绝，授权后运行；全量后端预先授权以满足既有进程栅栏测试，不将前一阶段的沙箱失败算成本轮失败。保留 Starlette `httpx` 弃用与 Vite 主包约 500 kB 的体积提示。
- 部署生效：未部署；未访问当前业务实例或读取/迁移业务 SQLite，未重启 API、Worker、monitor；浏览器仅访问 8791 隔离服务与临时数据库，不启动 Worker，不连接真实 GitLab、模型或飞书。统计接口不会自行执行验证或部署，页面中的人工声明仍需核对证据。
- 关联文件或证据：`docs/improvements-phase3.md`、`backend/ocr_manager/improvement_summary.py`、`backend/ocr_manager/improvement_summary_contracts.py`、`backend/ocr_manager/improvements_api.py`、`backend/tests/test_improvement_summary.py`、`frontend/src/api/improvementSummary.ts`、`frontend/src/pages/ImprovementSummaryPanel.tsx`、`frontend/src/pages/ImprovementSummaryCharts.tsx`、`frontend/src/test/improvementSummary.test.tsx`、`frontend/e2e/improvementSummary.spec.ts`。
- 遗留与下一步：按计划继续归档能力；历史批量导入、会话自动同步、统计报告快照留存和自动部署核验尚未实现。本会话记录继续追加本台账，未自动同步至业务页面。升级须另行协调同版 API/前端和既有第 40 版迁移，不以本地回归通过替代业务部署验收。

### PI-20261106-006｜问题与改进第四阶段：归档与恢复

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；主动归档与恢复的本地实现和验证完成，未部署。没有启用按时间自动归档策略。
- 关联记录：PI-20261106-001、PI-20261106-003、PI-20261106-004、PI-20261106-005。
- 现象或目标：用户要求继续按计划推进归档能力，在已有平台问题台账、主题历程和复盘基础上收纳历史内容，同时保留处理过程、未解决进展及独立交付状态。
- 原因或分析：直接隐藏或删除记录会丢失关联、历史或未解决事项；仅凭时间或完成状态自动归档也不能说明已经部署。归档需要独立元数据、恢复入口、管理员权限、版本冲突和完整历史，并明确默认列表与全量统计的差异。
- 处理与改进：问题记录和优化主题均支持主动归档/恢复，列表默认未归档，可按已归档或全部范围搜索、筛选和分页，范围保存在独立 URL 参数中。详情明确时间、操作者及原因，归档期间禁止编辑，恢复后可继续追加；任何进展可主动收纳，但不改变解决、代码、本地验证、部署事实。主题归档不级联问题，阶段和双向关系保留，反向关联和选择器包含归档对象。归档、恢复与内容修改共用版本和短写事务，原快照缺失或历史写入失败整体回滚，重复或旧版本请求不追加历史；归档原因与恢复原因永久保留。复盘累计、关联、阶段和待办包含归档对象，新增归档数量与待办标识，分布明细跳转使用全量范围；活动追加次数包含归档和恢复，页面明确不等于解决次数，更新时间排序也不等于解决时间。
- 代码修改：已修改；新增归档契约、用例与第 41 版独立迁移，扩展两类 API、列表、详情、历史和复盘投影，新增共用确认组件及归档专项测试；补齐旧迁移测试结构清理和新服务端字段的合成夹具，重新生成 OpenAPI。更新操作指南、项目总览、部署、文档索引与前端回归说明，新增 `docs/improvements-phase4.md`。未修改第 39/40 版迁移，未回滚或覆盖工作区既有改动。
- 本地验证：`.venv/bin/ruff check backend/ocr_manager backend/tests`、`.venv/bin/mypy backend/ocr_manager`（78 模块）通过；`.venv/bin/python -m ocr_manager.openapi_contract --update` 生成后，`.venv/bin/python -m ocr_manager.openapi_contract` 快照与 API 路径校验通过。`.venv/bin/pytest -q backend/tests/test_improvement_archives.py` 最终 16 项通过；`.venv/bin/pytest -q` 最终全量 441 项通过。`npm --prefix frontend run lint`、`npm --prefix frontend test`（75 项，其中归档新增 6 项）、`npm --prefix frontend run build` 通过；`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm --prefix frontend run test:e2e` 最终完整 50 项通过（归档新增 2 项）。验证覆盖两类对象归档恢复、鉴权、严格原因/版本、重复与旧请求、编辑与归档竞争、历史缺失、事务回滚、40 版代表性旧库升级及迁移失败回滚、分页范围、创建重放、旧历史回填、关系与独立状态不变、归档待办不丢失、冲突草稿、提交锁定和刷新持久化。已查看修正后的桌面/320 像素确认弹窗与 320 像素归档列表截图；无页面横向溢出。`git diff --check` 无错误；内联 Python 核对 12 份相关文档的 89 项本地链接目标存在。
- 排查与无效尝试：首次归档后端专项为 11 通过、2 失败，测试误用审计不存在的 `path` 字段，改为稳定路由 `action` 后通过；后续补充并发编辑、缺失快照和旧版追加历史迁移用例，最终专项为 16 项。前端构建曾发现合成待办夹具缺少新增 `archived_at`，补齐后通过；OpenAPI 检查发现前端动态插值资源段无法被既有静态路径检查识别，改为两个明确端点，不放宽契约检查。首次完整浏览器 48 通过、2 失败，分别为旧历史定位未匹配新增动作标签、共享临时库审计数量增长后不再固定两页；更新对应测试为新标签和动态总页数后最终完整 50 项通过。截图检查发现确认弹窗缺少邻近表单的内边距，局部补齐原有设计样式后重新验证截图。浏览器首次在沙箱内绑定 8791 失败，经授权后仍用原定临时服务运行；后端完整回归经授权支持既有 `ps` 栅栏检查。保留既有 Starlette `httpx` 弃用提示和 Vite 主包约 500 kB 提示，未扩展依赖升级范围。
- 部署生效：未部署；未访问当前业务实例或检查其空数据，未读取/迁移业务 SQLite、导入台账或批量归档，未重启 API、Worker、monitor。浏览器仅使用 8791 隔离服务与临时数据库，不启动 Worker、不调用真实 GitLab、模型或飞书。源码数据库目标为第 41 版，不表示业务库版本已变更。
- 关联文件或证据：`backend/ocr_manager/improvement_archive_contracts.py`、`backend/ocr_manager/improvement_archive_migration.py`、`backend/ocr_manager/improvement_archives.py`、`backend/tests/test_improvement_archives.py`、`frontend/src/pages/ImprovementArchiveControl.tsx`、`frontend/src/test/improvementArchives.test.tsx`、`frontend/e2e/improvementArchives.spec.ts`、`docs/improvements-phase4.md`。
- 遗留与下一步：按时间自动归档、批量归档、永久删除、历史批量导入、会话自动同步、报告快照与自动部署核验仍未实现；不把主动归档描述为定时任务。本会话处理结束后的记录继续追加本文件，尚未自动同步到 SQLite 页面。统一部署须另行成对备份并在副本验证升级，协调同版 API、Worker、monitor 和前端，不降低 `user_version` 回退，也不以本地通过代替业务生效验收。

### PI-20261106-007｜自动归档与持续台账同步：实现及上线准备（中断进展）

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；实现与多数验证已完成，业务切换前会话被中断，部署与数据同步尚未执行。
- 关联记录：PI-20261106-001、PI-20261106-002、PI-20261106-003、PI-20261106-004、PI-20261106-005、PI-20261106-006。
- 现象或目标：用户要求启用自动归档，并立即写入当前业务库和同步到页面，后续本会话追加也持续保留。
- 原因或分析：只读核查时业务库为第 41 版，问题和主题均为零条；API、Worker 在运行，monitor 未运行。既有手动归档不会导入 Markdown，也没有按时间执行后台策略。此事实仅对应本轮实际核查，不改写旧阶段的未部署结论。
- 处理与改进：实现第 42 版策略与来源游标，独立 monitor 每 30 秒先按 PI 编号和追加游标同步，再处理自动归档。策略默认关闭、默认 30 天，必须已解决、验证与部署证据齐全、无遗留才归档；主题还检查所有阶段及关联问题。来源变化或页面人工编辑不覆盖，冲突跳过整轮自动归档。新增管理员策略 API、候选预览、运行计数和错误事实、页面设置及周期读取、运维命令和说明；源码中的默认规则不代表本实例已启用。
- 代码修改：已修改；新增解析、同步、自动归档、维护契约及用例和第 42 版迁移，接入 API、配置和 monitor，新增前端维护面板、后端/前端/浏览器专项；更新 OpenAPI、执行约定与运维文档。保留既有未提交工作。最后修正旧第 37 版迁移测试夹具时，恢复第 42 版严格建表，不采用 IF NOT EXISTS 隐藏结构冲突。
- 本地验证：`.venv/bin/ruff check backend/ocr_manager backend/tests`、`.venv/bin/mypy backend/ocr_manager`（84 模块）、OpenAPI 生成及校验、前端 lint 与 build 已实际通过；`npm --prefix frontend test` 79 项通过；`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm --prefix frontend run test:e2e` 完整 51 项通过，已查看 320 像素维护面板截图，无横向溢出，但复选框在窄屏的尺寸和标签换行仍有改进空间。后端维护专项首轮 27 项通过，后续增补 2 项。首轮全量 469 通过、1 个旧迁移夹具残留新表失败；第二轮实际 470 项通过，但该进程启动于最终严格迁移/夹具修正之前，不能替代最终文件状态的完整重验。后续恢复时需再次运行后端回归、静态检查、文档与差异校验。保留 Starlette 弃用与 Vite 约 500 kB 提示。
- 排查与无效尝试：最初专项测试有 5 个夹具错误，分别为已解决状态与阻塞验证不兼容、历史查询缺少分页参数；修正后专项通过。全量旧库回放因未清理新增维护表失败，曾临时采用幂等 DDL，随后撤回该放宽，改为在隔离测试夹具中清理新增表，最终源码尚待完整重跑。不输出私有配置、凭据或外部响应。
- 部署生效：未完成。已创建成对备份 `.local-data/backups/app-20261106-210316-030814.db` 及同名私有配置备份（0600），隔离恢复演练 `.local-data/backups/recovery-drills/recovery-drill-20261106-130316-19951157.json` 结果 passed，验证副本迁移至 42 和凭据解密。未迁移业务库、未修改私有配置、未重启 API/Worker、未启动 monitor、未启用业务策略、未导入台账或创建业务主题。本轮前端构建更新了现有服务使用的 `frontend/dist`，因此前端资源已经变化，但新接口和数据尚未在旧业务服务生效；不能称为前后端完整部署。
- 关联文件或证据：`docs/improvements-phase5.md`、`backend/ocr_manager/improvement_maintenance.py`、`backend/ocr_manager/improvement_auto_archive.py`、`backend/ocr_manager/improvement_log_parser.py`、`backend/ocr_manager/improvement_log_sync.py`、`backend/tests/test_improvement_maintenance.py`、`frontend/src/pages/ImprovementMaintenancePanel.tsx`、`frontend/e2e/improvementMaintenance.spec.ts`。
- 遗留与下一步：重新核对最终源码测试并修正窄屏设置布局；复核业务队列空闲并协调停旧进程，安全追加私有来源路径，迁移至 42、显式启用 30 天策略、导入历史台账并建立阶段主题，同版启动 API/Worker/monitor；只读核验真实 8781 页面、数量、历史和持续同步周期。最后以同编号追加实际部署证据并确认本条已同步，不得提前标注生效。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"blocked","deployment_state":"not_deployed"}

### PI-20261106-008｜部分完成任务分析与方案：授权范围及等待约定

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；暂缓，等待用户确认另一边处理结束后继续，不重复索取本范围内授权。
- 关联记录：无。
- 现象或目标：用户要求分析部分完成的评审任务，提出源头治理及补审方案供审阅，并明确后续不要重复询问授权。
- 原因或分析：此前发现其他工作修改了共享工作区，用户要求等待那边处理结束；本次授权不等于确认另一边已结束，也不撤销等待要求。
- 处理与改进：本事项后续只读检查 SQLite、日志和评审工件，新增独立方案文档及追加台账已获授权，不再对此重复确认；不覆盖其他工作改动。本次只记录约定，不继续任务样本分析。部署、重启、运行配置修改及付费模型调用不包含在本次范围内，工具强制审批仍按权限执行。
- 代码修改：未修改业务代码或执行约定；仅向本台账追加当前记录。
- 本地验证：已使用 `cat AGENTS.md`、`tail -150 docs/problem-improvement-log.md` 和 `rg` 核对当前记录约定、编号及同步实现；已以内联 Python 的 SQLite 只读连接核对 `.local-data/local/app.db`，业务库为第 41 版，缺少 `improvement_log_imports` 与 `improvement_maintenance` 表。未运行业务测试、模型诊断或新的任务统计；本条不声明功能验证通过。
- 部署生效：未部署；未修改业务数据库或服务进程。当前业务库缺少同步所需表，本条尚未同步到 SQLite 页面；不代替其他事项执行升级或启动 monitor。
- 关联文件或证据：本会话用户授权及此前等待指令；`AGENTS.md`、`backend/ocr_manager/improvement_log_sync.py`、`backend/ocr_manager/improvement_maintenance_migration.py`；当前业务库只读结构核验。
- 遗留与下一步：收到另一边处理完成的明确消息后，直接按授权范围恢复分析，先核对最新工作区基线；形成任务证据、根因置信度、源头治理、补审数据模型与验收方案。同步功能就绪后再核对本条导入结果，不覆盖页面事实。
- 同步状态：{"kind":"improvement","category":"stability","status":"deferred","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261106-001｜规划问题与改进菜单及持续记录流程——业务上线核验

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；菜单、持续记录和业务上线完成。
- 关联记录：PI-20261106-002、PI-20261106-003、PI-20261106-004、PI-20261106-005、PI-20261106-006、PI-20261106-007。
- 现象或目标：集中呈现平台问题、处理办法和优化过程，后续可持续查看。
- 原因或分析：原有 OCR 问题列表不等于平台自身问题与改进历史。
- 处理与改进：部署后“问题与改进”菜单显示 SQLite 中的 PI 记录、优化主题、复盘及自动维护；保持来源编号和历史。
- 代码修改：本事项的代码与文档已修改并部署。
- 本地验证：最终源码 Ruff、Mypy 84 模块、完整后端 470 项、前端 79 项、完整浏览器 51 项通过；浏览器页面窄屏尺寸复核后的 CSS 回归另行运行并记实际结果。
- 部署生效：已部署至当前本机业务实例；以 8781 health、菜单真实页面和 SQLite 行/历史为证。
- 关联文件或证据：`frontend/src/pages/ImprovementsPage.tsx`、`frontend/src/pages/ImprovementMaintenancePanel.tsx`、业务 API 和 SQLite。
- 遗留与下一步：无；后续会话按本台账追加，再由 monitor 同步。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261106-002｜将处理完成后同步记录纳入项目执行约定——自动同步核验

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；持久记录约定与本实例自动同步均已生效。
- 关联记录：PI-20261106-001、PI-20261106-007。
- 现象或目标：完成问题处理或阶段改进后追加持久记录；未解决事项同样保留进展，代码、本地验证和部署状态分别标注。
- 原因或分析：只依赖人工事后提醒会遗漏记录；不应把测试通过等同于生产部署。
- 处理与改进：保留中文台账作为追加来源，增加 monitor 的安全增量同步和版本历史；明确来源冲突时保留网页修改。
- 代码修改：后端解析、同步游标、SQLite 历史、管理员页面及运行监控已修改并部署。
- 本地验证：最终源码完整后端 470 项，台账同步专项覆盖重复导入、追加、冲突、非法 JSON 及事务回滚；前端 79 项、浏览器 51 项通过。
- 部署生效：私有配置以 0600 保留，已配置本台账路径；monitor 最近周期成功、页面可读取 PI 来源条目和历史后记已部署确认。
- 关联文件或证据：`AGENTS.md`、`docs/problem-improvement-log.md`、`backend/ocr_manager/improvement_log_sync.py`、业务运行状态。
- 遗留与下一步：无；不抓取其他会话，只有此显式来源。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261106-003｜问题与改进第一阶段：问题记录与历史快照——业务上线核验

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；问题记录与历史快照已上线。
- 关联记录：PI-20261106-001、PI-20261106-004、PI-20261106-007。
- 现象或目标：区分平台自身问题与 OCR 发现，持久记录现象、原因、方案和三个交付维度。
- 原因或分析：既有问题管理针对评审评论，无法记录平台事项和其修复历史。
- 处理与改进：新增独立问题记录、版本历史、管理员权限和持续 PI 同步；旧文字按原编号多版保存。
- 代码修改：已修改；业务数据库记录和页面现已可用。
- 本地验证：最终源码全量后端 470 项、前端 79 项及完整浏览器 51 项通过；覆盖列表、历史、刷新持久化和权限。
- 部署生效：已部署并由页面读回实际 SQLite 记录及历史确认。
- 关联文件或证据：`backend/ocr_manager/improvements.py`、`frontend/src/pages/ImprovementsPage.tsx`、业务库与页面。
- 遗留与下一步：无。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261106-004｜问题与改进第二阶段：优化主题与阶段关联——业务上线核验

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；优化历程主题与阶段已上线。
- 关联记录：PI-20261106-001、PI-20261106-003、PI-20261106-005、PI-20261106-007。
- 现象或目标：保留跨多条记录的项目整体优化过程和阶段证据。
- 原因或分析：单条记录无法表达阶段顺序与目标，分散文档也不便从页面复盘。
- 处理与改进：新增优化主题、阶段、显式问题关联及各版历史；通过幂等主题呈现本项目问题与改进菜单的阶段推进。
- 代码修改：已修改并部署。
- 本地验证：主题阶段与关系专项、完整后端 470 项、前端 79 项和完整浏览器 51 项通过。
- 部署生效：已部署；优化主题、阶段及关联编号由当前页面和业务库读回确认。
- 关联文件或证据：`backend/ocr_manager/improvement_themes.py`、`frontend/src/pages/ImprovementThemesPanel.tsx`、优化主题详情。
- 遗留与下一步：无。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261106-005｜问题与改进第三阶段：复盘汇总与统计——业务上线核验

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；复盘汇总已部署。
- 关联记录：PI-20261106-001、PI-20261106-003、PI-20261106-004、PI-20261106-007。
- 现象或目标：集中查看累计、时间窗口活动及未闭环状态，区分解决、验证和部署。
- 原因或分析：只看逐项详情难以掌握整体活动和未完成工作；统计不能从文本猜测解决时长或部署。
- 处理与改进：提供累计、分类、三个交付维度、窗口活动及待办明细，明确归档事实不等于解决事实。
- 代码修改：已修改并部署。
- 本地验证：复盘专项及最终源码完整后端 470 项、前端 79 项、浏览器 51 项通过。
- 部署生效：已部署；当前页面复盘数据由 SQLite 实际读取。
- 关联文件或证据：`backend/ocr_manager/improvement_summary.py`、`frontend/src/pages/ImprovementSummaryPanel.tsx`、业务页面。
- 遗留与下一步：无。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261106-006｜问题与改进第四阶段：手动归档与恢复——业务上线核验

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；手动归档、恢复和与自动规则已部署。
- 关联记录：PI-20261106-001、PI-20261106-003、PI-20261106-004、PI-20261106-005、PI-20261106-007。
- 现象或目标：收纳历史记录但保留事实、关联、历史和恢复路径。
- 原因或分析：删除或覆盖会丢失历史；仅按时间收纳会隐藏待部署或未解决事项。
- 处理与改进：管理员可手动归档/恢复且保留原因与快照；自动规则仅按完整闭环、证据、遗留及更新时间判定，不删数据。
- 代码修改：已修改并部署。
- 本地验证：归档专项、自动维护专项及最终源码完整后端 470 项、前端 79 项、浏览器 51 项通过。
- 部署生效：手动能力与 30 天后台策略已部署；候选预览和monitor成功周期由当前实例核对。
- 关联文件或证据：`backend/ocr_manager/improvement_archives.py`、`backend/ocr_manager/improvement_auto_archive.py`、`docs/improvements-phase5.md`。
- 遗留与下一步：无。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}


### PI-20261106-008｜追加：澄清终端审批授权及置灰限制

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；排查中，尚未确定审批控件置灰的具体来源。
- 关联记录：PI-20261106-008。
- 现象或目标：用户澄清所指授权为输入框的 Ask for approval，且选项均置灰，期望减少终端逐次审批。
- 原因或分析：前条将授权理解为任务操作范围，不等于终端审批设置；当前会话提供的权限配置标记为 managed、文件系统受限且网络受限。置灰可能涉及宿主或策略限制，但尚未核验界面、管理策略或客户端配置，不能认定确切原因。此前建议直接选择 Never 未覆盖置灰情形，本条补充纠正。
- 处理与改进：仅解释当前权限边界，建议结束当前执行后检查控件提示及应用权限设置；仍置灰时需依据完整菜单截图定位，不擅自修改配置或绕过策略。此前等待另一边处理结束的要求不因本次权限咨询自动撤销。
- 代码修改：未修改业务代码或权限配置；仅追加本台账。
- 本地验证：已实际执行官方文档 curl 请求；沙箱内 DNS 解析失败，按审批流程重试后 HTTP 403，未能读取官方页面，不将其作为已验证操作依据。已用 rg、tail 核对台账，用 Python SQLite 只读查询确认当前业务库为 42 版、同步维护存在成功记录且原 PI-20261106-008 已同步 1 条；未运行业务测试，未验证权限切换生效。
- 部署生效：不适用，本次没有部署操作，亦未改变终端审批策略；原记录的 41 版与未同步结论仅为当时事实，当前只读核验已为 42 版。追加来源的同步结果在本轮结束前另行只读核对。
- 关联文件或证据：本会话用户说明、会话 managed 权限上下文、实际 curl 错误及 SQLite 只读同步状态；docs/problem-improvement-log.md。
- 遗留与下一步：根据界面完整截图或控件提示定位置灰原因；不能承诺聊天授权可解锁审批设置，也不建议未经核实开放全部权限。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_applicable"}


### PI-20261106-008｜追加：核对个人审批配置并提供受限免审批设置建议

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；排查中，提供配置建议，未实际切换权限。
- 关联记录：PI-20261106-008。
- 现象或目标：用户询问 Codex 终端审批应如何设置，期望避免逐次确认。
- 原因或分析：只读解析个人 config.toml，approval_policy、sandbox_mode、profile 均未显式配置；已检查的个人及 /etc/codex 常见 requirements.toml、managed_config.toml 均未发现。会话的 managed 标记不能单独证明存在组织管理员锁定，尚未确定灰色控件的具体原因。
- 处理与改进：建议在设置可提供的配置入口打开个人配置，在顶层配置 approval_policy 为 never、sandbox_mode 为 workspace-write；该组合仅在沙箱内免审批，被限制操作可能直接失败，不等于自动授予联网或目录外写入权限。仅提供用户操作说明，不修改全局配置、不采用危险的全权限组合。
- 代码修改：未修改业务代码或个人配置，仅追加台账。
- 本地验证：已执行 Python tomllib 只读解析及常见策略文件存在性检查；curl 官方设置页在沙箱内 DNS 失败，按流程重试后 HTTP 403，未读取到官方页面。未运行配置生效测试或业务回归，控件置灰原因仍待核实。
- 部署生效：不适用，未部署或重启应用，未改变审批策略。
- 关联文件或证据：本会话配置读取输出及联网失败结果；docs/problem-improvement-log.md。
- 遗留与下一步：用户自行修改后在新会话确认实际权限；若仍被限制，依据控件提示和实际生效配置继续诊断，不绕过管理策略。追加记录同步结果以本轮只读核对为准。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_applicable"}

### PI-20261106-001｜规划问题与改进菜单及持续记录流程——部署核验更正

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；本地完成，业务服务切换待最终页面和后台进程核验。
- 关联记录：PI-20261106-007。
- 现象或目标：更正上一条尚未完成服务启动时写入的部署结论，保留完整历史。
- 原因或分析：执行期间记录了计划中的业务核验结论，但该次服务中断，结论当时没有真实页面或 monitor 周期佐证。
- 处理与改进：不改写旧历史，追加更正：当前数据库 42 版、策略已启用；API、Worker 与 monitor 尚未重启核验，页面生效仍待验证。
- 代码修改：菜单与维护实现已修改；本条不涉及新代码修改。
- 本地验证：源码后端完整测试 470 项、Ruff 与 Mypy 通过；最终 CSS 变更后的前端和浏览器复验正在执行，以完成后的实际命令结果为准。
- 部署生效：数据库已迁移并配置策略；服务进程与真实页面尚未确认，不声明完成。
- 关联文件或证据：业务 SQLite 第 42 版、`backend/ocr_manager/improvement_maintenance.py`、`frontend/src/pages/ImprovementMaintenancePanel.tsx`。
- 遗留与下一步：启动同版服务，核对 health、PI 页面与 monitor 周期后，再追加确认。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"unknown"}

### PI-20261106-002｜将处理完成后同步记录纳入项目执行约定——部署核验更正

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；同步流程实现完成，后台周期待启动核验。
- 关联记录：PI-20261106-001、PI-20261106-007。
- 现象或目标：避免把已配置来源与实际持续同步混为一谈。
- 原因或分析：来源路径已经配置，但 monitor 尚未启动，尚无连续周期成功证据。
- 处理与改进：已配置的唯一来源为本台账；同号追加会保留版本，冲突不覆盖；当前页面可读数据但服务尚未启动。
- 代码修改：解析、追加游标、冲突保护及 monitor 集成已实现。
- 本地验证：完整后端 470 项通过；同步专题验证包含来源追加、重放、修改/删除拒绝、页面编辑冲突及事务失败。
- 部署生效：私有配置与数据库策略已经更新，周期同步和真实页面暂未核验。
- 关联文件或证据：`AGENTS.md`、`backend/ocr_manager/improvement_log_sync.py`、业务 SQLite 来源游标。
- 遗留与下一步：启动 monitor 并读回最近成功时间及新增历史后，再追加确认。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"unknown"}

### PI-20261106-003｜问题与改进第一阶段：问题记录与历史快照——部署核验更正

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；代码和本地验证完成，业务 API 尚未启动读回。
- 关联记录：PI-20261106-001、PI-20261106-007。
- 现象或目标：区分“已写入数据库”和“页面已确认展示”。
- 原因或分析：新版本 API 当前未启动，因此先前写入的已部署结论无服务端页面证据。
- 处理与改进：保留原结论快照，追加为待核验；待同版 API 启动后从页面及记录历史读回。
- 代码修改：已实现并构建，无本条新代码修改。
- 本地验证：完整后端 470 项和数据库历史/迁移专项通过；前端最终样式回归待结束。
- 部署生效：业务 SQLite 已含记录，但 API 页面尚未完成部署核验。
- 关联文件或证据：`backend/ocr_manager/improvements.py`、`frontend/src/pages/ImprovementsPage.tsx`、业务 SQLite。
- 遗留与下一步：完成服务启动及真实浏览器读回后追加生效证据。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"unknown"}

### PI-20261106-004｜问题与改进第二阶段：优化主题与阶段关联——部署核验更正

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；主题能力本地验证完成，本次主题尚未创建。
- 关联记录：PI-20261106-001、PI-20261106-003、PI-20261106-007。
- 现象或目标：把项目改进步骤保留为真实业务库中的统一历程。
- 原因或分析：数据库确认已有问题记录，但主题表仍为空；阶段操作不能仅由截图或代码代替。
- 处理与改进：保留原历史，待创建显式阶段与 PI-001 至 PI-008 关联；PI-008 的暂缓状态不表示解决。
- 代码修改：主题与关联实现已修改并构建。
- 本地验证：主题专项及完整后端 470 项通过；主题创建和业务页面读取仍待执行。
- 部署生效：本次主题未创建，尚无实际主题部署证据。
- 关联文件或证据：`backend/ocr_manager/improvement_themes.py`、业务 SQLite `improvement_themes` 为空的只读核查。
- 遗留与下一步：创建幂等主题并核对阶段、问题链接及页面呈现。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"unknown"}

### PI-20261106-005｜问题与改进第三阶段：复盘汇总与统计——部署核验更正

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；本地统计验证通过，业务页面读回待完成。
- 关联记录：PI-20261106-001、PI-20261106-007。
- 现象或目标：分别展示台账累计事实与处理活动，不把页面构建成功视作服务生效。
- 原因或分析：API 停止后未检查真实统计页面。
- 处理与改进：历史确认保留；待同版 API 启动后从当前页面确认记录与主题统计来源。
- 代码修改：复盘查询与页面已实现，无本条新代码修改。
- 本地验证：复盘专项及完整后端 470 项通过；最终浏览器样式回归以正在运行的完整验收结果为准。
- 部署生效：尚无本轮真实页面核验结论。
- 关联文件或证据：`backend/ocr_manager/improvement_summary.py`、`frontend/src/pages/ImprovementSummaryPanel.tsx`。
- 遗留与下一步：启动服务后读回统计页面。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"unknown"}

### PI-20261106-006｜问题与改进第四阶段：手动与自动归档——部署核验更正

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；策略已在数据库启用，monitor 执行周期待确认。
- 关联记录：PI-20261106-001、PI-20261106-007。
- 现象或目标：只自动收纳已闭环且符合等待条件的记录，同时保留恢复和历史能力。
- 原因或分析：`enabled=1`只表示持久化策略，不等于后台调度已运行。
- 处理与改进：保留 30 天策略；现有候选数为零，本轮没有自动归档对象。
- 代码修改：手动归档及自动维护筛选已实现。
- 本地验证：自动维护专项覆盖等待边界、状态/证据、关联问题、事务失败和重放；完整后端 470 项通过。
- 部署生效：数据库策略已启用；monitor 周期、候选和页面实际读回仍未确认。
- 关联文件或证据：`backend/ocr_manager/improvement_auto_archive.py`、`backend/ocr_manager/improvement_maintenance.py`、业务 SQLite。
- 遗留与下一步：同版启动 monitor，核对周期和候选预览，不对不满足条件的条目归档。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"unknown"}


### PI-20261106-008｜追加：恢复部分完成任务分析并形成根因治理与补审方案

- 记录日期：2026-11-06（北京时间）。
- 类型与进展：阶段改进；已完成方案，待用户审阅，尚未实施。
- 关联记录：PI-20261106-008。
- 现象或目标：用户要求不再继续权限设置咨询，并检查能否恢复此前计划；本轮恢复只读任务分析，交付源头治理和补审专项方案，不实施业务代码或修改运行参数。
- 原因或分析：同一业务库快照共 385 任务，当前 partial 为 #321/#343/#381，历史 partial 尝试还包括 #337 首次；合并前样本为空。四份原始结果经现有 classify_result 校验均为 partial，失败覆盖均为 timeout 且按完整分组失败。#321/#343 输入相同，同一组 6 文件 fingerprint 相同且重复失败；#381 一个 plan 请求连续 6 次约 60 秒 HTTP 504，另有 context 超时及少量工具失败。diff 行数对照不支持所有失败均因大文件，尚不能确认具体网关层级或分组截止的全部因果链；#337 第二次是目标分支可达性校验失败，不是模型超时。
- 处理与改进：新增独立 docs/review-partial-review-plan.md，列出任务证据、失败/完成文件 diff 规模、工具与成功对照、根因置信度、请求/分组诊断、有限并发/端点实验、CLI 默认子任务时限与平台整体预算的区别、原生 resume 合成端点验证、失败子集替代路径、幂等数据模型/队列/历史/聚合/费用/通知、阶段门槛及约 5～10 开发日条件估算。强调 preview 或 session ID 不能证明可恢复，原生全量 selected 与子集 selected 使用不同校验，旧结果不清空，模型/规则变化不静默合并。其他工作仍有部署核验待办，本轮只新增独立方案和追加本台账，不等待或代为完成其部署，也不覆盖既有文件。
- 代码修改：未修改业务代码、个人权限配置或运行参数；仅新增方案文档并追加本台账。
- 本地验证：实际执行本机 OCR --version 与 review --help（1.12.9，确认 resume 与默认 15 分钟子任务参数）；Python SQLite mode=ro 加 backup API 生成单一临时分析快照，查询任务/尝试与参数白名单，读取四份原始结果、preview 和会话工件存在性，调用 classify_result 四次均返回 partial；随后用 Python 只读连接活库重查计数一致。git diff --check -- docs/review-partial-review-plan.md docs/problem-improvement-log.md 已通过；内联 Python 检查新方案无行尾空白、代码围栏闭合、六个章节及四项证据路径齐全。系统 sqlite3 -readonly 曾返回无法打开数据库（14），原因未定位，改用已成功的 Python 只读命令并写明差异。未运行新业务功能测试、恢复正式探针、真实模型对照、前端构建或浏览器验收；旧台账测试数量不作为本轮通过证据。
- 部署生效：不适用，本轮仅分析与方案；未写业务数据库、切换服务、修改项目配置、重评审或调用付费模型。本轮结束前只读核对来源与页面同步，不主动执行导入或覆盖页面修改。
- 关联文件或证据：docs/review-partial-review-plan.md；backend/ocr_manager/ocr.py、review_results.py、review_failures.py、ocr_filter_probe.py 与现有 Worker/工件清理代码；业务 SQLite 任务/尝试及 runs 下只读工件白名单事实，不复制凭据、代码正文、推理或完整外部响应。
- 遗留与下一步：先审阅方案，再实施分层诊断与本机合成端点恢复探针；真实模型试点须明确样本与费用边界。原生恢复不满足固定范围/快照/覆盖要求时，不承诺历史任务可直接续审；没有可靠子集执行能力时仅交付诊断和资格提示。业务根因尚未解决、补审尚未实现。
- 同步状态：{"kind":"improvement","category":"stability","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_applicable"}

### PI-20261107-001｜终端审批设置与置灰限制排查（独立事项）

- 记录日期：2026-11-07（北京时间）；整理此前 2026-11-06 的排查事实，未重新执行审批设置诊断。
- 类型与进展：阶段改进；排查中，尚未确定审批控件置灰的具体来源。
- 关联记录：PI-20261106-008；原编号下第 2 条追加及对应历史版本。
- 现象或目标：用户澄清所指授权为输入框的 Ask for approval，且选项均置灰，期望减少终端逐次审批。
- 原因或分析：编号更正：本条为独立的终端审批咨询，不属于部分完成任务治理。保留原编号历史，不迁移或删除旧快照。此前排查事实：前条将授权理解为任务操作范围，不等于终端审批设置；当前会话提供的权限配置标记为 managed、文件系统受限且网络受限。置灰可能涉及宿主或策略限制，但尚未核验界面、管理策略或客户端配置，不能认定确切原因。此前建议直接选择 Never 未覆盖置灰情形，本条补充纠正。
- 处理与改进：仅解释当前权限边界，建议结束当前执行后检查控件提示及应用权限设置；仍置灰时需依据完整菜单截图定位，不擅自修改配置或绕过策略。此前等待另一边处理结束的要求不因本次权限咨询自动撤销。
- 代码修改：未修改业务代码或权限配置；仅追加本台账。
- 本地验证：已实际执行官方文档 curl 请求；沙箱内 DNS 解析失败，按审批流程重试后 HTTP 403，未能读取官方页面，不将其作为已验证操作依据。已用 rg、tail 核对台账，用 Python SQLite 只读查询确认当前业务库为 42 版、同步维护存在成功记录且原 PI-20261106-008 已同步 1 条；未运行业务测试，未验证权限切换生效。
- 部署生效：不适用；这里只拆分台账事项，未修改终端审批配置，也未验证权限切换生效。
- 关联文件或证据：本会话用户说明、会话 managed 权限上下文、实际 curl 错误及 SQLite 只读同步状态；docs/problem-improvement-log.md。；原记录 PI-20261106-008 的终端审批排查第 1 段，作为来源整理而非本轮重新检查。
- 遗留与下一步：根据界面完整截图或控件提示定位置灰原因；不能承诺聊天授权可解锁审批设置，也不建议未经核实开放全部权限。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_applicable"}

### PI-20261107-001｜终端审批设置排查——保留此前配置核查进展

- 记录日期：2026-11-07（北京时间）；整理此前 2026-11-06 的排查事实，未重新执行审批设置诊断。
- 类型与进展：阶段改进；排查中，提供配置建议，未实际切换权限。
- 关联记录：PI-20261106-008；原编号下第 3 条追加及对应历史版本。
- 现象或目标：用户询问 Codex 终端审批应如何设置，期望避免逐次确认。
- 原因或分析：编号更正：本条为独立的终端审批咨询，不属于部分完成任务治理。保留原编号历史，不迁移或删除旧快照。此前排查事实：只读解析个人 config.toml，approval_policy、sandbox_mode、profile 均未显式配置；已检查的个人及 /etc/codex 常见 requirements.toml、managed_config.toml 均未发现。会话的 managed 标记不能单独证明存在组织管理员锁定，尚未确定灰色控件的具体原因。
- 处理与改进：建议在设置可提供的配置入口打开个人配置，在顶层配置 approval_policy 为 never、sandbox_mode 为 workspace-write；该组合仅在沙箱内免审批，被限制操作可能直接失败，不等于自动授予联网或目录外写入权限。仅提供用户操作说明，不修改全局配置、不采用危险的全权限组合。
- 代码修改：未修改业务代码或个人配置，仅追加台账。
- 本地验证：已执行 Python tomllib 只读解析及常见策略文件存在性检查；curl 官方设置页在沙箱内 DNS 失败，按流程重试后 HTTP 403，未读取到官方页面。未运行配置生效测试或业务回归，控件置灰原因仍待核实。
- 部署生效：不适用；这里只拆分台账事项，未修改终端审批配置，也未验证权限切换生效。
- 关联文件或证据：本会话配置读取输出及联网失败结果；docs/problem-improvement-log.md。；原记录 PI-20261106-008 的终端审批排查第 2 段，作为来源整理而非本轮重新检查。
- 遗留与下一步：用户自行修改后在新会话确认实际权限；若仍被限制，依据控件提示和实际生效配置继续诊断，不绕过管理策略。追加记录同步结果以本轮只读核对为准。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_applicable"}

### PI-20261106-008｜部分完成任务治理——编号更正与最新方案摘要恢复

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：阶段改进；编号更正，保留已形成治理与补审方案、待审阅且未实施的最新进展。
- 关联记录：PI-20261107-001（独立终端审批排查）；PI-20261106-008 原事项方案进展；PI-20261106-007。
- 现象或目标：用户要求不再继续权限设置咨询，并检查能否恢复此前计划；本轮恢复只读任务分析，交付源头治理和补审专项方案，不实施业务代码或修改运行参数。
- 原因或分析：终端审批排查曾误用本编号，现已另建 PI-20261107-001；保留原有所有历史，本条恢复部分完成任务治理事项的最新摘要而非回退为最初暂缓。原有可核对分析：同一业务库快照共 385 任务，当前 partial 为 #321/#343/#381，历史 partial 尝试还包括 #337 首次；合并前样本为空。四份原始结果经现有 classify_result 校验均为 partial，失败覆盖均为 timeout 且按完整分组失败。#321/#343 输入相同，同一组 6 文件 fingerprint 相同且重复失败；#381 一个 plan 请求连续 6 次约 60 秒 HTTP 504，另有 context 超时及少量工具失败。diff 行数对照不支持所有失败均因大文件，尚不能确认具体网关层级或分组截止的全部因果链；#337 第二次是目标分支可达性校验失败，不是模型超时。
- 处理与改进：新增独立 docs/review-partial-review-plan.md，列出任务证据、失败/完成文件 diff 规模、工具与成功对照、根因置信度、请求/分组诊断、有限并发/端点实验、CLI 默认子任务时限与平台整体预算的区别、原生 resume 合成端点验证、失败子集替代路径、幂等数据模型/队列/历史/聚合/费用/通知、阶段门槛及约 5～10 开发日条件估算。强调 preview 或 session ID 不能证明可恢复，原生全量 selected 与子集 selected 使用不同校验，旧结果不清空，模型/规则变化不静默合并。其他工作仍有部署核验待办，本轮只新增独立方案和追加本台账，不等待或代为完成其部署，也不覆盖既有文件。
- 代码修改：未修改业务代码或运行参数；仅追加独立编号与原事项更正，不改变其他工作的方案。
- 本地验证：本次读取台账和 SQLite 来源版本核对编号冲突；未重跑原任务分析或模型调用。前次分析与方案的实际检查命令及范围保留在上一版历史。
- 部署生效：原事项仍仅为分析与方案，部署不适用；本次仅同步台账更正，不实施补审功能或切换业务配置。
- 关联文件或证据：docs/review-partial-review-plan.md；PI-20261106-008 原事项第 1、4 段及对应 SQLite 历史；PI-20261107-001 独立审批事项。
- 遗留与下一步：先审阅方案，再实施分层诊断与本机合成端点恢复探针；真实模型试点须明确样本与费用边界。原生恢复不满足固定范围/快照/覆盖要求时，不承诺历史任务可直接续审；没有可靠子集执行能力时仅交付诊断和资格提示。业务根因尚未解决、补审尚未实现。
- 同步状态：{"kind":"improvement","category":"stability","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_applicable"}


### PI-20261106-001｜规划问题与改进菜单及持续记录流程——当前实例部署验收完成

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：阶段改进；完成当前业务实例只读部署验收，本条追加确认，不删除或改写此前结论与部署核验更正。
- 关联记录：PI-20261106-007；优化主题 #1。
- 现象或目标：用户希望集中查看项目遇到的问题、解决办法与整体优化过程，并持续收集本会话后续的问题处理和改进记录。
- 原因或分析：此前部署证据不足，已明确更正为待核验；现在基于正在运行的业务服务、页面与数据库读回事实追加最终结论。此前历史继续保留。
- 处理与改进：问题与改进菜单已按问题记录、优化主题与阶段、复盘统计、归档恢复、持续同步五步交付；规划与治理流程已有真实页面和持久化记录。
- 代码修改：相关实现已修改并构建，本条无新增业务代码；同步规则和运维边界见 docs/improvements-phase5.md。
- 本地验证：前阶段于 2026-11-06 实际执行后端 pytest 全量 470 项、前端单测 79 项、完整浏览器回归 51 项及 Ruff、mypy、lint、build 均通过；这些全量检查本轮未重跑。2026-11-07 本轮实际执行 .venv/bin/pytest -q backend/tests/test_improvement_maintenance.py：29 passed；.venv/bin/python -m ocr_manager.openapi_contract：通过；git diff --check：通过。
- 部署生效：2026-11-07 实际读取当前 8781 实例：/api/health 为 ok、Worker running，业务库 PRAGMA user_version=42；/api/improvement-maintenance 为 enabled=true、archive_after_days=30、source_configured=true，最近成功周期持续前进、错误码为空、conflicts=[]。node .local-data/deployment-checks/live-check.cjs 对真实页面仅允许 GET/HEAD，验证 9 条记录、主题及 9 条关联、历史、复盘、1280/320px 无横向溢出，页面错误为零、写请求为零。当前候选问题及主题均为 0，未实际归档任何对象。
- 关联文件或证据：docs/improvements-phase5.md；当前业务页面 /improvements、/improvements?view=themes、/improvements?view=summary；本机只读验收脚本与截图位于 .local-data/deployment-checks/。
- 遗留与下一步：无。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261106-002｜将处理完成后同步记录纳入项目执行约定——当前实例部署验收完成

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：阶段改进；完成当前业务实例只读部署验收，本条追加确认，不删除或改写此前结论与部署核验更正。
- 关联记录：PI-20261106-007；优化主题 #1。
- 现象或目标：用户明确要求，每次问题处理或改进结束都必须同步记录，不能只把过程留在聊天中；未解决事项也要保留进展。
- 原因或分析：此前部署证据不足，已明确更正为待核验；现在基于正在运行的业务服务、页面与数据库读回事实追加最终结论。此前历史继续保留。
- 处理与改进：项目执行约定要求本会话每次处理结束追加持久记录；独立 monitor 每 30 秒同步显式台账，不抓取其他聊天。已实测独立编号新增与同号更正均自动入库，保留各版历史。
- 代码修改：相关实现已修改并构建，本条无新增业务代码；同步规则和运维边界见 docs/improvements-phase5.md。
- 本地验证：前阶段于 2026-11-06 实际执行后端 pytest 全量 470 项、前端单测 79 项、完整浏览器回归 51 项及 Ruff、mypy、lint、build 均通过；这些全量检查本轮未重跑。2026-11-07 本轮实际执行 .venv/bin/pytest -q backend/tests/test_improvement_maintenance.py：29 passed；.venv/bin/python -m ocr_manager.openapi_contract：通过；git diff --check：通过。
- 部署生效：2026-11-07 实际读取当前 8781 实例：/api/health 为 ok、Worker running，业务库 PRAGMA user_version=42；/api/improvement-maintenance 为 enabled=true、archive_after_days=30、source_configured=true，最近成功周期持续前进、错误码为空、conflicts=[]。node .local-data/deployment-checks/live-check.cjs 对真实页面仅允许 GET/HEAD，验证 9 条记录、主题及 9 条关联、历史、复盘、1280/320px 无横向溢出，页面错误为零、写请求为零。当前候选问题及主题均为 0，未实际归档任何对象。
- 关联文件或证据：docs/improvements-phase5.md；当前业务页面 /improvements、/improvements?view=themes、/improvements?view=summary；本机只读验收脚本与截图位于 .local-data/deployment-checks/。
- 遗留与下一步：无。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261106-003｜问题与改进第一阶段：平台台账与历史闭环——当前实例部署验收完成

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：阶段改进；完成当前业务实例只读部署验收，本条追加确认，不删除或改写此前结论与部署核验更正。
- 关联记录：PI-20261106-007；优化主题 #1。
- 现象或目标：按用户确认的实施顺序，先提供独立菜单、问题列表与详情、新建与编辑、SQLite 持久化，再推进优化主题和统计能力。
- 原因或分析：此前部署证据不足，已明确更正为待核验；现在基于正在运行的业务服务、页面与数据库读回事实追加最终结论。此前历史继续保留。
- 处理与改进：问题列表、详情、处理历史及代码修改/本地验证/部署生效三个独立维度已在当前实例呈现；来源与页面人工编辑冲突不会被强制覆盖。
- 代码修改：相关实现已修改并构建，本条无新增业务代码；同步规则和运维边界见 docs/improvements-phase5.md。
- 本地验证：前阶段于 2026-11-06 实际执行后端 pytest 全量 470 项、前端单测 79 项、完整浏览器回归 51 项及 Ruff、mypy、lint、build 均通过；这些全量检查本轮未重跑。2026-11-07 本轮实际执行 .venv/bin/pytest -q backend/tests/test_improvement_maintenance.py：29 passed；.venv/bin/python -m ocr_manager.openapi_contract：通过；git diff --check：通过。
- 部署生效：2026-11-07 实际读取当前 8781 实例：/api/health 为 ok、Worker running，业务库 PRAGMA user_version=42；/api/improvement-maintenance 为 enabled=true、archive_after_days=30、source_configured=true，最近成功周期持续前进、错误码为空、conflicts=[]。node .local-data/deployment-checks/live-check.cjs 对真实页面仅允许 GET/HEAD，验证 9 条记录、主题及 9 条关联、历史、复盘、1280/320px 无横向溢出，页面错误为零、写请求为零。当前候选问题及主题均为 0，未实际归档任何对象。
- 关联文件或证据：docs/improvements-phase5.md；当前业务页面 /improvements、/improvements?view=themes、/improvements?view=summary；本机只读验收脚本与截图位于 .local-data/deployment-checks/。
- 遗留与下一步：无。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261106-004｜问题与改进第二阶段：优化主题、阶段历程与问题关联——当前实例部署验收完成

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：阶段改进；完成当前业务实例只读部署验收，本条追加确认，不删除或改写此前结论与部署核验更正。
- 关联记录：PI-20261106-007；优化主题 #1。
- 现象或目标：用户要求继续下一阶段，不再处理当前业务实例菜单无数据的问题；本轮按既定顺序组织优化主题、有序实施阶段、关联问题和历史方案。
- 原因或分析：此前部署证据不足，已明确更正为待核验；现在基于正在运行的业务服务、页面与数据库读回事实追加最终结论。此前历史继续保留。
- 处理与改进：真实业务库已建立主题“问题与改进菜单建设与持续治理”，包含五阶段与 9 条显式问题关联。主题继续保持进行中，独立审批排查及部分完成任务方案不被当作已解决。
- 代码修改：相关实现已修改并构建，本条无新增业务代码；同步规则和运维边界见 docs/improvements-phase5.md。
- 本地验证：前阶段于 2026-11-06 实际执行后端 pytest 全量 470 项、前端单测 79 项、完整浏览器回归 51 项及 Ruff、mypy、lint、build 均通过；这些全量检查本轮未重跑。2026-11-07 本轮实际执行 .venv/bin/pytest -q backend/tests/test_improvement_maintenance.py：29 passed；.venv/bin/python -m ocr_manager.openapi_contract：通过；git diff --check：通过。
- 部署生效：2026-11-07 实际读取当前 8781 实例：/api/health 为 ok、Worker running，业务库 PRAGMA user_version=42；/api/improvement-maintenance 为 enabled=true、archive_after_days=30、source_configured=true，最近成功周期持续前进、错误码为空、conflicts=[]。node .local-data/deployment-checks/live-check.cjs 对真实页面仅允许 GET/HEAD，验证 9 条记录、主题及 9 条关联、历史、复盘、1280/320px 无横向溢出，页面错误为零、写请求为零。当前候选问题及主题均为 0，未实际归档任何对象。
- 关联文件或证据：docs/improvements-phase5.md；当前业务页面 /improvements、/improvements?view=themes、/improvements?view=summary；本机只读验收脚本与截图位于 .local-data/deployment-checks/。
- 遗留与下一步：无。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261106-005｜问题与改进第三阶段：复盘汇总与统计——当前实例部署验收完成

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：阶段改进；完成当前业务实例只读部署验收，本条追加确认，不删除或改写此前结论与部署核验更正。
- 关联记录：PI-20261106-007；优化主题 #1。
- 现象或目标：用户要求按计划推进复盘汇总与统计，在已有平台台账、主题与阶段基础上查看整体进展、处理活动和当前遗留事项，避免把保存次数、验证通过及部署生效混为同一结论。
- 原因或分析：此前部署证据不足，已明确更正为待核验；现在基于正在运行的业务服务、页面与数据库读回事实追加最终结论。此前历史继续保留。
- 处理与改进：真实复盘页面已读取并显示业务库统计，支持问题与主题维度，累计和待办保留归档事实，不把构建成功等同服务生效。
- 代码修改：相关实现已修改并构建，本条无新增业务代码；同步规则和运维边界见 docs/improvements-phase5.md。
- 本地验证：前阶段于 2026-11-06 实际执行后端 pytest 全量 470 项、前端单测 79 项、完整浏览器回归 51 项及 Ruff、mypy、lint、build 均通过；这些全量检查本轮未重跑。2026-11-07 本轮实际执行 .venv/bin/pytest -q backend/tests/test_improvement_maintenance.py：29 passed；.venv/bin/python -m ocr_manager.openapi_contract：通过；git diff --check：通过。
- 部署生效：2026-11-07 实际读取当前 8781 实例：/api/health 为 ok、Worker running，业务库 PRAGMA user_version=42；/api/improvement-maintenance 为 enabled=true、archive_after_days=30、source_configured=true，最近成功周期持续前进、错误码为空、conflicts=[]。node .local-data/deployment-checks/live-check.cjs 对真实页面仅允许 GET/HEAD，验证 9 条记录、主题及 9 条关联、历史、复盘、1280/320px 无横向溢出，页面错误为零、写请求为零。当前候选问题及主题均为 0，未实际归档任何对象。
- 关联文件或证据：docs/improvements-phase5.md；当前业务页面 /improvements、/improvements?view=themes、/improvements?view=summary；本机只读验收脚本与截图位于 .local-data/deployment-checks/。
- 遗留与下一步：无。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261106-006｜问题与改进第四阶段：归档与恢复——当前实例部署验收完成

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：阶段改进；完成当前业务实例只读部署验收，本条追加确认，不删除或改写此前结论与部署核验更正。
- 关联记录：PI-20261106-007；优化主题 #1。
- 现象或目标：用户要求继续按计划推进归档能力，在已有平台问题台账、主题历程和复盘基础上收纳历史内容，同时保留处理过程、未解决进展及独立交付状态。
- 原因或分析：此前部署证据不足，已明确更正为待核验；现在基于正在运行的业务服务、页面与数据库读回事实追加最终结论。此前历史继续保留。
- 处理与改进：归档恢复和保留历史能力已部署；本实例已启用连续 30 天无更新的闭环自动归档，monitor 成功执行维护。当前无合格候选，未通过调整时间或业务状态强行归档；实际归档恢复边界由隔离自动测试覆盖。
- 代码修改：相关实现已修改并构建，本条无新增业务代码；同步规则和运维边界见 docs/improvements-phase5.md。
- 本地验证：前阶段于 2026-11-06 实际执行后端 pytest 全量 470 项、前端单测 79 项、完整浏览器回归 51 项及 Ruff、mypy、lint、build 均通过；这些全量检查本轮未重跑。2026-11-07 本轮实际执行 .venv/bin/pytest -q backend/tests/test_improvement_maintenance.py：29 passed；.venv/bin/python -m ocr_manager.openapi_contract：通过；git diff --check：通过。
- 部署生效：2026-11-07 实际读取当前 8781 实例：/api/health 为 ok、Worker running，业务库 PRAGMA user_version=42；/api/improvement-maintenance 为 enabled=true、archive_after_days=30、source_configured=true，最近成功周期持续前进、错误码为空、conflicts=[]。node .local-data/deployment-checks/live-check.cjs 对真实页面仅允许 GET/HEAD，验证 9 条记录、主题及 9 条关联、历史、复盘、1280/320px 无横向溢出，页面错误为零、写请求为零。当前候选问题及主题均为 0，未实际归档任何对象。
- 关联文件或证据：docs/improvements-phase5.md；当前业务页面 /improvements、/improvements?view=themes、/improvements?view=summary；本机只读验收脚本与截图位于 .local-data/deployment-checks/。
- 遗留与下一步：无。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261106-007｜自动归档与持续台账同步——当前实例上线验收与编号更正完成

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：阶段改进；自动同步与自动归档已在当前业务实例启用，完成上线收尾与编号更正。
- 关联记录：PI-20261106-001 至 PI-20261106-006；PI-20261106-008；PI-20261107-001；优化主题 #1。
- 现象或目标：把当前会话的可核对问题和改进持久化进入业务库与页面，启用闭环自动归档，保留未解决事项、失败尝试、历史结论及三个交付维度。
- 原因或分析：此前存在服务停止、主题未入库和未经读回的部署结论，现已恢复同版服务并完成真实只读验收。另一事项误用 PI-008 的历史未删除，经用户允许另建 PI-20261107-001；PI-008 恢复最新治理方案摘要，仍待审阅且未实施，不回退为最初暂缓，也不声明根因解决。
- 处理与改进：42 版迁移及来源游标已生效；独立 monitor 每 30 秒先同步再维护，30 天闭环自动归档显式开启，与飞书告警开关无关。9 条问题记录、1 个五阶段主题、9 条显式关联已呈现。更正前 24 份历史 snapshot_json 逐份一致、旧来源 digest 全部保持前缀一致。新增独立事项 2 条进展、原事项 1 条更正由后台自动导入，无手工改游标或覆盖页面。后续本会话每次收尾继续追加本台账，并核对自动同步结果。
- 代码修改：自动维护、解析与幂等同步、归档筛选、管理员 API、页面运行事实及相关测试已实现；本次收尾仅追加记录、更新主题快照与运维文档，未改审批配置或实施补审功能。
- 本地验证：前阶段于 2026-11-06 实际执行后端 pytest 全量 470 项、前端单测 79 项、完整浏览器回归 51 项及 Ruff、mypy、lint、build 均通过；这些全量检查本轮未重跑。2026-11-07 本轮实际执行 .venv/bin/pytest -q backend/tests/test_improvement_maintenance.py：29 passed；.venv/bin/python -m ocr_manager.openapi_contract：通过；git diff --check：通过。 另实际运行 node .local-data/deployment-checks/live-check.cjs 全部断言通过；Python 逐份核对更正前 24 份数据库历史及旧来源 digest 未变。
- 部署生效：2026-11-07 实际读取当前 8781 实例：/api/health 为 ok、Worker running，业务库 PRAGMA user_version=42；/api/improvement-maintenance 为 enabled=true、archive_after_days=30、source_configured=true，最近成功周期持续前进、错误码为空、conflicts=[]。node .local-data/deployment-checks/live-check.cjs 对真实页面仅允许 GET/HEAD，验证 9 条记录、主题及 9 条关联、历史、复盘、1280/320px 无横向溢出，页面错误为零、写请求为零。当前候选问题及主题均为 0，未实际归档任何对象。 API PID 86402、Worker PID 87408、monitor PID 87409 当前运行。launchd 尝试因系统 posix_spawn Operation not permitted 失败并卸载，现以后台进程方式运行，未建立开机自启；当前已运行不表示重启后自动恢复。
- 关联文件或证据：docs/improvements-phase5.md；升级前成对备份 .local-data/backups/app-20261106-224932-998822.db 及同名 .private.json；编号更正前成对备份 app-20261107-005331-494007.db 及同名 .private.json；恢复演练 recovery-drill-20261106-144933-08f1966e.json 结果 passed；更正前基线 .local-data/deployment-checks/pre-separation-baseline.json。私有配置保持 0600，未输出凭据或外部响应正文。
- 遗留与下一步：无。
- 运行边界：未解决的 PI-20261106-008 与 PI-20261107-001 继续保留计划/排查状态，不能自动归档；主题保持进行中跟踪后续治理。开机自启未建立，重启后须按部署说明启动三进程并检查成功时间前进；安全权限限制未绕过。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}


### PI-20261106-008｜追加：拆解部分评审治理的五步实施清单

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：阶段改进；已完成实施细化，待审阅，未开始业务实现。
- 关联记录：PI-20261106-008。
- 现象或目标：用户询问具体如何实施，希望明确开发顺序、模块落点、交付物和验收条件。
- 原因或分析：已有根因与恢复方向，但需先通过诊断和合成端点验证缩小未知，避免先实现按钮或未经验证的数据模型。真实模型调用、参数调优和部署不等同于隔离开发，应分别安排。
- 处理与改进：在 docs/review-partial-review-plan.md 新增第七节，拆为诊断、原生恢复/失败子集探针、后端队列聚合、页面和补充通知、真实试点及上线五步；明确报告路径歧义处理、partial 不触发整批重试、工件引用、源聚合版本裁决、有效结论消费者统一、反馈/发布兼容和默认关闭。推荐先交付前两步，合成端点不调用付费模型；附现有工程检查命令，均标明待执行。
- 代码修改：未修改业务代码或运行参数；仅补充方案文档及追加台账。
- 本地验证：本轮只检查文档差异、章节/围栏/行尾空白及台账解析和状态契约；实际命令结果以本轮终端核对为准。未运行后端功能测试、恢复探针、模型实验、前端构建或浏览器回归；没有重算 2026-11-06 的任务样本，不将旧统计描述为当前实时统计。
- 部署生效：不适用，方案细化未部署；未调整模型、项目预算、超时、并发、服务进程或权限配置。结束前只读核对来源与 SQLite 同步结果，不主动导入或覆盖页面事实。
- 关联文件或证据：docs/review-partial-review-plan.md 第七节；当前 review_results.py、tasks.py、review_contracts.py 和 ocr_filter_probe.py 只读核对；本会话实施说明请求。
- 遗留与下一步：按第一、二步实施诊断和合成恢复兼容验证，结果通过后确定补审执行路线；源头根因尚未解决，补审功能尚未实现。真实模型试点及部署需各自明确范围，不自动执行。
- 同步状态：{"kind":"improvement","category":"stability","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_applicable"}

### PI-20261106-008｜追加：完成分层诊断与合成恢复兼容验证，确定独立补审批次路线

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：阶段改进；按用户授权完成方案第一、二步本地实施，第三至第五步尚未实施，整体事项继续跟踪，不声明根因解决或补审上线。
- 关联记录：PI-20261106-008；docs/review-partial-review-plan.md 第七节。
- 现象或目标：用户要求开始按建议方案执行；先让部分完成可解释，再验证是否能真正只做剩余部分，不直接增加未经验证的补审按钮。
- 原因或分析：真实本机 OCR v1.12.9 合成实验表明 commit/range 均能原生复用已完成项并保留发现，但重复恢复仍调用失败组，更换模型不拒绝，跨 checkout 恢复失败，中断恢复存在时序差异；有效规则变更、缺失与损坏会话本次均无调用拒绝。原生覆盖复用通过不等于生产安全条件通过。独立失败子集在两种模式的新 checkout 上均通过固定 SHA、预览、正式 manifest 及实际请求范围验证。
- 处理与改进：新增有界白名单分层诊断，持久化到当前及逐次结果，接通列表摘要、详情、当前/历史报告；逗号路径只按完整已知分组匹配，有歧义标未知。提供需显式 SHA 的单工件只读诊断命令，历史不自动回填。合成恢复矩阵及报告已落盘，第三步优先采用独立失败子集批次与平台聚合，仍需资格、幂等、快照、覆盖、发现来源、版本裁决及用量验证。
- 代码修改：已修改诊断契约/解析/投影/查询、详情和列表展示、报告，以及合成端点、恢复探针、测试和文档；OpenAPI 已更新。未修改 partial 自动整批重试语义，未实现补审队列、按钮或补充通知；没有数据库迁移。
- 本地验证：实际执行 .venv/bin/ruff check backend/ocr_manager backend/tests、.venv/bin/mypy backend/ocr_manager 均通过；OCR_RESUME_PROBE_COMMAND=.local-tools/node_modules/.bin/ocr .venv/bin/pytest -q：485 passed，显式包含真实本机 CLI 合成探针；最终诊断专项复跑 14 passed。PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract --update 及随后只读校验通过；npm --prefix frontend run lint、npm --prefix frontend test：82 passed；npm --prefix frontend run build -- --outDir /tmp/ocr-partial-phase12-dist 通过。OCR_BROWSER_FRONTEND_DIST 指向隔离构建后实际运行 playwright 的 reviewDiagnostics/reviewExecution：6 passed，1280/390/320px 均无横向溢出，人工核对 320px 截图；完整浏览器套件本轮未运行。实际运行 ocr_resume_probe 并保存合成报告；另以 Python SQLite mode=ro 取得 #321/#343/#381 原始 SHA 与工件，只读诊断分别确认 23/29（一组）、14/29（两组）、40/45（一组），#381 有 6 次 504 并与 context/tool 信号共存，未输出原始正文。git diff --check 通过。仍有构建包体积及 Starlette/httpx 弃用提示，不称为零警告。
- 部署生效：未部署、未重启服务，前端仅构建到 /tmp 隔离目录，未覆盖 frontend/dist；未改生产超时/并发/模型、未调用真实模型或付费端点、未重审历史任务、未回填业务摘要、未改终端审批配置。仅台账追加会由既有 monitor 同步，不能据此称新评审能力在业务服务生效。
- 排查与无效尝试：初轮检查发现详情读取遗漏新投影、历史报告测试路径错误及合成子集规则错误增加前导斜线；均已修正并重跑通过。取消探针没有可信最终 JSON 时用量保持未知；正常合成恢复的 6 token 与本次响应匹配，而非初审加恢复累计 12，不推断真实账单或失败请求费用。
- 关联文件或证据：docs/review-partial-phase12.md；docs/review-resume-probe.json；backend/ocr_manager/review_diagnostics.py；backend/ocr_manager/review_diagnostic_report.py；backend/ocr_manager/ocr_resume_probe.py；backend/tests/test_review_diagnostics.py；backend/tests/test_ocr_resume_probe.py；frontend/e2e/reviewDiagnostics.spec.ts；frontend/test-results/review-diagnostics-320.png。
- 遗留与下一步：第三步实现独立补审批次、Worker 调度与平台聚合，专项验证复杂规则、跨文件上下文、并发幂等、取消/清理竞争及消费者一致性；第四步再做按钮与独立补充通知。第五步安排有预算的真实网关关联调查与试点；源头超时尚未解决，不默认调整生产参数或调用历史样本。结束前只读核对台账来源 digest 与 SQLite 导入游标，不强制同步或覆盖页面人工事实。
- 同步状态：{"kind":"improvement","category":"stability","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261106-008｜追加：完成默认关闭的补审后端隔离核心，消费者统一尚待实施

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：阶段改进；按用户继续执行的要求实施第三步后端隔离核心并完成本地验证，不将该核心等同于第三步全部完成或补审上线，整体事项继续跟踪。
- 关联记录：PI-20261106-008；docs/review-partial-review-plan.md 第三步；docs/review-partial-phase12.md。
- 现象或目标：在不重复评审已完成文件、不改写初审事实的前提下，建立可幂等排队、独占执行、独立取消、保留来源并按版本聚合的补审后端；先完成安全边界，再接页面和通知。
- 原因或分析：原生 resume 尚不满足配置、跨目录、幂等和中断安全，继续采用独立失败子集与平台候选聚合。源头 504/context/tool 信号的因果仍需真实链路证据；补审机制不是超时根因修复。候选必须和平台当前有效结论区分，否则详情、统计、反馈及通知可能产生不一致。
- 处理与改进：新增 schema 43 独立批次/候选表、管理员资格与排队/历史/取消/候选摘要接口、活动批次唯一约束与执行令牌；补审复用唯一模型槽和工件锁，固定原始 SHA/base，校验受控原工件、快照、实际设置、规则摘要及 Git 可达性。组合换行过滤与精确子集规则，预览和正式 manifest 均须命中冻结剩余集合；不删上下文、不伪造提交、不回退全量。终态事务校验源版本，保留根 item ID、初审发现和新增发现来源，用量逐批次记录，取消/中断/过期不自动重试。候选仅公开有契约的覆盖/发现数量，始终标记 consumer_integration_ready=false；全量重审刚排队尚未增加 attempts 时也隐藏旧候选。
- 代码修改：已修改补审领域、契约、存储、迁移、规则组合、Worker、调度、初审重跑互斥、工件保留、审计对象标识、API/OpenAPI、专项测试及实施文档。Settings.review_recovery_enabled 默认为 False，仅隔离测试注入，没有生产环境或页面启用入口。未修改初审结果、旧投递/反馈身份，未接通有效结论消费者、按钮或补充通知。
- 本地验证：实际执行 .venv/bin/ruff check backend/ocr_manager backend/tests、.venv/bin/mypy backend/ocr_manager（96 个源码文件）通过；.venv/bin/pytest -q backend/tests/test_review_recovery.py backend/tests/test_review_recovery_worker.py backend/tests/test_review_recovery_scope.py：52 passed；.venv/bin/pytest -q：536 passed、1 skipped。PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract --update 及随后只读契约校验通过；git diff --check 通过。覆盖 commit/range、16 种规则/换行组合、特殊路径、上下文保留、范围漂移、设置读取竞态、唯一模型槽、鉴权、幂等/并发、候选链、失败终态、坏快照、取消/重启/删除/清理，以及 42 升 43 和迁移/聚合写失败回滚。普通全量未设置真实 CLI 探针变量，因此该项跳过；组合规则测试使用合成命令，不冒充真实 CLI 复杂组合实测。未运行前端检查、构建、浏览器或真实模型质量/费用试点。仍有 Starlette/httpx 弃用提示，不描述为零警告。
- 部署生效：未部署、未重启 API/Worker/monitor，未迁移业务库、未覆盖 frontend/dist、未修改生产模型/预算/超时/并发、未调用真实模型、未重审历史任务。实际用 Python SQLite mode=ro 读回当前业务库 user_version=42。既有 monitor 同步本条台账不等于新补审代码在服务中生效，源头超时未宣称解决。
- 排查与无效尝试：收尾发现候选接口原先返回完整候选结果而无明确响应模型，已收紧为摘要；补充实际设置装配时的竞态核验、损坏快照明确拒绝及 failed 子结果不能推进候选；补充全量重审排队窗口隐藏旧候选。新增代码初轮 Ruff 有行宽和未使用导入提示，已修正并重跑通过。项目引用的 ~/.codex/comment-standards.md 当前不存在，按项目内更具体的中文注释规范执行，未创建或更改用户全局配置。
- 关联文件或证据：docs/review-partial-phase3.md；backend/ocr_manager/review_recovery_domain.py；backend/ocr_manager/review_recovery_store.py；backend/ocr_manager/review_recovery_worker.py；backend/ocr_manager/review_recovery_scope.py；backend/ocr_manager/review_recovery_migration.py；backend/ocr_manager/review_recovery_api.py；backend/tests/test_review_recovery.py；backend/tests/test_review_recovery_worker.py；backend/tests/test_review_recovery_scope.py；docs/openapi.json。
- 遗留与下一步：先完成第三步统一有效结论读取入口、跨版本发现身份及列表/详情/统计/反馈/问题跟踪/导出消费者回归，再按第四步接页面与独立补充通知，生产入口继续关闭。启用前补真实 CLI 复杂规则组合、完整浏览器回归和业务库副本迁移/恢复演练；第五步另行开展有预算的真实网关关联调查与受控试点，不默认调用历史样本或部署。结束前只读核对来源 digest、导入游标及 monitor 维护事实，不手动覆盖页面或强制同步。
- 同步状态：{"kind":"improvement","category":"stability","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261106-008｜追加：统一只读结论、稳定发现来源和显式版本报告已完成本地验证

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：阶段改进；按用户“继续”的要求推进第三步读取基础，完成统一摘要、来源身份和版本化复核；未完成有效结论整体提升或补审反馈/问题跟踪写入，整体事项继续验证。
- 关联记录：PI-20261106-008；docs/review-partial-phase3.md；docs/review-partial-conclusions.md。
- 现象或目标：避免列表、详情、报告与统计各自选择不同补审候选，并为后续反馈/问题关联准备不会随聚合数组位置变化的发现身份；保留初审事实和历史可审计性。
- 原因或分析：聚合评论下标不等于原始尝试或独立批次下标，直接复用旧反馈/发布接口会误标其他发现；只显示候选 complete 又切换部分消费者，会造成状态和费用不一致。因此先统一只读版本与来源，不提前启用候选，不将读取基础宣称为全部消费者已完成。
- 处理与改进：新增 review_conclusions 及响应契约，列表/详情/报告统一并列 initial 与 candidate 摘要，首页/运维增加独立候选计数；只在父任务仍为 partial、未取消、源尝试匹配时选最新候选，全量重审排队窗口也隐藏旧候选。新增管理员只读 /api/jobs/{job_id}/conclusion，显式 source_attempt/revision 可复核历史，默认请求选择当前源的最新候选，无候选时读根尝试；响应 no-store。发现固定到根尝试或补审批次索引，精确重复保留主身份并验证附加来源，未知/未来/失效批次、伪造根发现、重复身份和覆盖冲突返回 409。版本用量按根尝试及截止目标版本的批次累计，失败未知用量不填零，后续费用不改变旧版本。报告显式 recovery_revision 才并列导出目标候选，继续统一凭据脱敏；历史单次报告不附后来候选。初审状态采用平台已验证状态，不因原 manifest 的 complete 抹掉预算不确定的 partial。
- 代码修改：已新增统一只读模块、结论与共享用量契约、23 项专项测试及前端只读类型；接通既有观测增强、候选摘要 API、列表/详情/报告、首页/运维摘要，更新 OpenAPI 和文档。没有新增数据库迁移，开发 schema 仍为 43。consumer_integration_ready 仍固定 false，review_recovery_enabled 仍默认关闭；原 status/result/feedback/问题出现记录/飞书/GitLab 发布语义不切换，也无补审按钮或新反馈写入口。
- 本地验证：实际执行 .venv/bin/ruff check backend/ocr_manager backend/tests、.venv/bin/mypy backend/ocr_manager（99 个源码文件）均通过；.venv/bin/pytest -q backend/tests/test_review_conclusions.py：23 passed；.venv/bin/pytest -q：559 passed、1 skipped。PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract --update 及只读校验通过；npm --prefix frontend run lint、npm --prefix frontend test：82 passed；npm --prefix frontend run build -- --outDir /tmp/ocr-partial-conclusions-dist 通过。OCR_BROWSER_FRONTEND_DIST 指向该隔离目录、指定本机 Chrome，实际运行 npx playwright test e2e/reviewDiagnostics.spec.ts e2e/reviewExecution.spec.ts：6 passed，1280/390/320px 原展示兼容通过。完整浏览器套件未运行，没有真实模型、真实 CLI 新组合或生产部署验收；普通全量的真实 CLI 探针因未设置变量跳过。git diff --check 通过。构建仍有主包超过 500 kB 与临时目录不自动清空提示，后端有 Starlette/httpx 弃用提示，浏览器有 NO_COLOR/FORCE_COLOR 提示，不描述为零警告。
- 部署生效：未部署、未重启 API/Worker/monitor，未覆盖 frontend/dist，未改生产模型/超时/预算/并发，未重审历史任务或调用真实模型。当前业务库只读核对仍为 user_version=42；本轮无业务库写入或迁移，只有既有 monitor 按既定规则导入台账。台账页面同步不代表新读取接口已在运行服务生效，源头超时仍未解决。
- 排查与无效尝试：初轮新测试误把默认“最新候选”当作初审，改用显式 revision=0；另一测试未推进源 revision 触发 source_changed，已修正测试版本；全量重审测试误把 next_job 领取前的任务投影当作领取后计数，改为核对 SQLite 持久化次数。新增代码的行宽、未使用导入和类型命名冲突已修正，重跑验证通过，没有修改业务校验绕过失败。
- 关联文件或证据：docs/review-partial-conclusions.md；backend/ocr_manager/review_conclusions.py；backend/ocr_manager/review_conclusion_contracts.py；backend/ocr_manager/review_usage_contracts.py；backend/tests/test_review_conclusions.py；backend/ocr_manager/review_recovery_api.py；backend/ocr_manager/operations_api.py；backend/ocr_manager/review_observability.py；backend/ocr_manager/attempt_history.py；frontend/src/api/reviewConclusions.ts；docs/openapi.json。
- 遗留与下一步：实现以稳定来源身份为键的补审反馈和问题出现记录及其迁移、幂等/同事务/历史关联回归，再统一有效结论提升与状态筛选/统计/全任务费用/默认导出口径；随后按第四步接页面按钮与独立补充通知。旧反馈接口仍只认初审评论索引，补审发现不得直接投给旧接口。真实 CLI 复杂规则、真实网关调查、受控预算试点及上线恢复演练继续独立安排，不自动部署或调用历史样本。结束前核对来源 digest、导入版本与 monitor 成功事实，不强制同步或覆盖页面。
- 同步状态：{"kind":"improvement","category":"stability","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261106-008｜追加：只读核查业务库已为 43，追加更正上轮版本与运行边界

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：阶段核查；按用户“是的＋先核查再继续”的要求，先核查版本和运行状态再继续隔离开发，迁移具体发起方尚未确认。
- 关联记录：PI-20261106-008；上一条“完成统一只读结论与稳定发现身份基础”的部署表述。
- 现象或目标：上轮收尾只读发现业务库实际已是 schema 43，与此前写入文档及台账的“当前仍为 42”不一致；需要区分本轮执行动作、已有运行实例和完整部署验收。
- 原因或分析：当前 API PID 10068 于 2026-11-07 06:25:29 启动，父进程为终端 shell，监听 127.0.0.1:8781，输出连接终端；Worker 87408、monitor 87409 启动时间为前一晚 23:22:17、23:22:18。源码 api.create_app 在启动时调用 store.migrate，API 重启与升级现象吻合，但没有足够日志确定具体迁移调用或操作者，不以相关证据代替因果证明。
- 处理与改进：追加更正业务库实际为 user_version=43；两张补审表记录均为零。运行 OpenAPI 已有 recoveries 路由但尚无 conclusion 路由，不能视为上一轮全部新代码已部署，也不能继续笼统说运行端仍完全是 42。旧台账不改写、不删除；结论文档新增更正提示，另写运行核查与后续实施文档。
- 代码修改：本项核查不修改业务代码、数据库、模型或进程配置；只追加核查和更正文档。之后的反馈开发另列后续记录，不归入本项核查通过范围。
- 本地验证：实际执行 ps 查询 PID/父进程/启动时间、lsof 查询 8781 监听及进程 cwd/stdout/stderr；以 Python sqlite3 URI mode=ro 查询 PRAGMA user_version 和两张补审表 COUNT，结果为 43、0、0；HTTP GET /api/health 返回 200、status=ok、worker=running；GET /openapi.json 白名单核对 recoveries 存在、conclusion 不存在。只读核对台账 9 条来源 digest 与 SQLite 导入记录一致，monitor 无错误且 conflicts 为空。没有导入业务 create_app、调用 Store.migrate、执行 Git/OCR 或触发通知。曾 GET /health 命中非 JSON 响应导致 JSONDecodeError，改用正确 /api/health 核查成功，不以错误路径结果判断服务异常。
- 部署生效：既有 43 版补审结构与部分路由在运行端可见，完整新结论能力未确认生效；具体升级发起方、同版整套部署和补审可用性无法确认，标记 unknown。本轮未部署或重启 API、Worker、monitor，未开启补审、重审历史任务或改终端权限。健康存活不等于新功能上线验收。
- 关联文件或证据：docs/review-partial-feedback.md 第一节；docs/review-partial-conclusions.md 更正提示；backend/ocr_manager/api.py create_app 的启动迁移入口；本会话只读 ps/lsof/SQLite/HTTP 输出。
- 遗留与下一步：继续默认关闭的隔离开发；正式上线时统一核对 API/Worker/monitor/前端版本，准备业务库副本迁移、备份和恢复验证。现有证据不足以确定发起方时保持未知，不自动重启业务服务以消除差异。结束前继续核对本次台账追加与页面同步，不强制覆盖页面事实。
- 同步状态：{"kind":"improvement","category":"deployment","status":"investigating","code_state":"unchanged","verification_state":"passed","deployment_state":"unknown"}

### PI-20261106-008｜追加：完成稳定身份反馈和补审问题出现记录的隔离实施

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：阶段改进；核查后继续第三步的反馈与问题关联基础，已完成本地实现及验证，第三步整体和生产补审尚未完成。
- 关联记录：PI-20261106-008；上一条运行版本核查；此前“统一只读结论、稳定发现来源和显式版本报告已完成本地验证”。
- 现象或目标：补审发现不能借用初审评论下标提交反馈，否则不同批次的第 0 条会互相覆盖、关联错问题或被误认为已发布；需要版本冲突保护、可审计来源和原子出现记录。
- 原因或分析：旧反馈仅以 job/comment_index 表达当前初审，新候选有独立批次来源和不可变根尝试；覆盖恢复不等于有效结论消费者已经统一。源头 504/context/tool 的因果仍未定位，本次不将补审治理表述为根因解决。
- 处理与改进：新增 44 版迁移，不改写 43 版；保留旧出现 ID/关联/时间，增加数据库生成的唯一 finding_id、可空 recovery_id 与绑定任务/根尝试的复合外键。新增稳定身份反馈表，旧反馈按真实当前出现迁移，原作者未知明确标记历史迁移；旧接口同事务镜像，重审清旧投影但保留稳定历史。补审终态只捕获新增主身份，精确重复不重复记出现；候选、批次、问题与出现同事务，失败回滚。新读写接口校验管理员/只读角色、最新源尝试与 revision、主身份及可信来源；新写入口继续默认关闭，撤销不覆盖其他人工决定。旧任务的映射/发现数量/级别只认初审，效果统计的 GitLab 发布连接排除补审来源；问题侧栏标明补审批次及候选来源，不提供尚未支持的补审发现详情或按钮。
- 代码修改：已修改迁移装配、补审终态捕获、反馈同步、问题关联、初审投影/发布匹配、管理员接口、OpenAPI、前端类型和来源标签；新增反馈模块、迁移、26 项专项及浏览器来源测试，补充实施文档。consumer_integration_ready 仍为 false；尚未统一补审反馈率、有效结论提升/筛选、全任务费用和默认报告，未增加独立补充通知或生产开关入口。历史候选缺少出现记录时返回 finding_occurrence_missing，不自动回填。
- 本地验证：实际执行 .venv/bin/ruff check backend/ocr_manager backend/tests、.venv/bin/mypy backend/ocr_manager：102 个源码文件通过；.venv/bin/pytest -q：585 passed、1 skipped，真实 CLI 探针未设置变量而跳过；.venv/bin/pytest -q backend/tests/test_review_finding_feedback.py：26 passed。实际执行 PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract --update 及只读校验、npm --prefix frontend run lint、npm --prefix frontend test：82 passed、npm --prefix frontend run build -- --outDir /tmp/ocr-finding-feedback-dist 均通过。OCR_BROWSER_FRONTEND_DIST 指向该隔离目录并指定本机 Chrome，实际运行 npx playwright test e2e/reviewFindingSources.spec.ts e2e/issueAuthor.spec.ts e2e/reviewDiagnostics.spec.ts e2e/reviewExecution.spec.ts：10 passed，含 1280/390/320px，人工核对 320px 来源标签截图；完整浏览器套件未运行。专项覆盖并发幂等、读角色禁写、过期/损坏来源、根接口双向兼容与历史隔离、出现/审计事务回滚、43→44 失败回滚和重复迁移、取消/失败/失效、旧候选缺失出现拒绝写入。git diff --check 通过。仍有 Starlette/httpx 弃用、主包超过 500 kB、隔离目录不自动清空及浏览器颜色环境提示，不称为零警告。
- 部署生效：本条新增 44 版及稳定反馈代码未部署；结束前只读业务库仍为 user_version=43，review_finding_feedback 表不存在，补审批次/候选均为零；API 10068、Worker 87408、monitor 87409 的启动时间未变化。未重启或迁移业务服务，未覆盖 frontend/dist，未开启补审、调整生产超时/预算/并发/模型、重审历史任务或调用真实模型。已有 43 版结构/部分路由与未知迁移来源按上一条记录，不将其等同于本次代码生效。
- 排查与无效尝试：初轮结论只读测试仍断言总出现数为 1，新增补审捕获后改为比较读取前后的完整出现记录，验证读接口无副作用；新增失效测试误认为活动补审期间可全量重审入队，实际保护正确返回 None，已保留该保护断言并模拟父来源取消，重跑全量通过。修正了新增导入排序和行宽，不为通过测试放松业务校验。
- 关联文件或证据：docs/review-partial-feedback.md；backend/ocr_manager/review_finding_migration.py；backend/ocr_manager/review_finding_feedback.py；backend/ocr_manager/review_finding_api.py；backend/ocr_manager/review_recovery_store.py；backend/ocr_manager/feedback_issues.py；backend/ocr_manager/review_issues.py；backend/tests/test_review_finding_feedback.py；frontend/e2e/reviewFindingSources.spec.ts；frontend/test-results/review-finding-source-320.png；docs/openapi.json。
- 遗留与下一步：继续统一有效结论提升及筛选/统计、补审反馈率、全任务费用和默认导出，然后实施补审页面与独立补充通知；GitLab 新来源发布保持未支持。另行安排真实 CLI 规则组合、真实网关调查、受控预算试点、业务库副本迁移与恢复演练和同版上线；本轮不自动部署。结束前以 mode=ro 核对来源 digest、SQLite 导入版本、页面状态及 monitor 成功/冲突，不手动强制同步或覆盖人工事实。
- 同步状态：{"kind":"improvement","category":"stability","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261106-008｜追加：完成补审有效结论、页面与独立通知闭环，完成上线准备但未执行真实试点及部署

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：阶段改进；按用户“按照规划文档全部实施完”继续补齐第三、四步本地实现及第五步发布准备，真实链路调查、付费对照和生产灰度仍未执行，不将规划所有阶段标为已验收。
- 关联记录：PI-20261106-008；前条“完成稳定身份反馈和补审问题出现记录的隔离实施”；docs/review-partial-review-plan.md 五步清单。
- 现象或目标：补审后需要统一列表/详情/统计/报告的有效结论，保留初审事实，提供范围预算确认、历史和停止操作，并防止通知重试再次调用模型；上线前必须验证迁移和恢复，不把补审保障替代根因治理。
- 原因或分析：原初审 status/result 与新候选来源不同，不能直接改成 complete 或混用评论下标；实际生产 Worker 使用独立协调器，单接旧 run_once 不会形成完整闭环。仅检查根覆盖单调性不足以证明中间批次真实完成，需逐版重放冻结来源、批准范围、覆盖及发现。504/context/工具信号的具体因果仍无网关 trace 和真实对照，不宣称超时已解决。
- 处理与改进：新增 45 版有效结论指针、独立 Outbox、轮转和操作者字段，不修改已共享 43/44 迁移，不回填历史候选。可信终态同事务保存批次/聚合/新出现/有效版本/唯一补充投递；来源改变或删除使指针失效，显式读取、再补审及待发通知完整核验来源链。状态筛选/导航、首页、运维、发现数、反馈汇总和默认报告统一有效口径；保留初审故障、单次历史报告和旧反馈索引。全任务费用包含全部已开始补审及失败未知，逐次单价、多币种分开累计；时间字段明确只含初审，补审起止独立显示。新增冻结确认框、有限预算、幂等重放、历史分页、停止、稳定身份反馈、真实只读角色限制和独立补充通知重发；活动补审与全量重审互斥。真实调度器接入唯一模型槽及独立投递槽；默认关闭、项目白名单、每父任务总批次/累计批准 Token 护栏，取消/失败不重置额度。补充消息只列本批新增、展示版本覆盖和累计发现，零新增不伪装全任务无问题；初审在途等待、五次有界重试、重启响应未知转人工核对。GitLab 补审来源发布明确未支持、不重发旧评论。
- 代码修改：完成后端有效结论/完整来源链/全费用/反馈统计/独立通知及调度器接线，前端详情/列表/确认/历史/反馈/状态文案，更新 OpenAPI 与配置/部署/实施文档；新增后端有效结论集成测试、4 项前端组件测试和 5 项补审浏览器测试及仅测试入口使用的合成推进适配器。新增 docs/review-partial-rollout.md 发布、回退、真实根因试点协议；没有修改生产 private.json、模型或业务工件。代码修改维度为 modified，不以此表示部署。
- 本地验证：实际执行 .venv/bin/ruff check backend/ocr_manager backend/tests、.venv/bin/mypy backend/ocr_manager（108 个源码文件）及 PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract --update/只读检查，均通过。最终实际执行 OCR_RESUME_PROBE_COMMAND="$PWD/.local-tools/node_modules/.bin/ocr" .venv/bin/pytest -q：617 passed，包含真实 OCR 1.12.9 的本机合成端点探针，无真实模型调用或跳过项；此前普通全量为 616 passed、1 skipped，已由显式探针全量覆盖。实际执行 npm --prefix frontend run lint、npm --prefix frontend test：86 passed；npm --prefix frontend run build -- --outDir /tmp/ocr-recovery-release-dist 通过，未覆盖 frontend/dist。指定本机 Chrome、OCR_BROWSER_FRONTEND_DIST 使用隔离构建，实际运行 reviewDiagnostics/reviewExecution/reviewFindingSources/issueAuthor 共 10 passed；另设置 OCR_BROWSER_REVIEW_RECOVERY=1 运行 e2e/reviewRecovery.spec.ts：5 passed，覆盖 1280/390/320px、冻结特殊路径、预算确认、刷新、初审保留、有效发现反馈、取消、通知失败仅重发、真实只读账号。人工核对 320px 确认框和结果页，无页面/确认框横向溢出；完整浏览器套件未运行。使用 SQLite mode=ro + backup API 在临时目录复制业务 43 库，Store.migrate 仅作用副本并重复执行：目标 45、quick_check=ok、foreign_key_check=0，业务表计数及初审证据摘要不变、新有效/补充投递为零；从原始副本恢复新临时文件后为 43、完整性与计数/证据一致，临时文件清理。未做真实凭据解密演练或生产外发验收。git diff --check 通过。保留 Starlette/httpx 弃用、主包超过 500 kB、隔离目录不自动清空及浏览器颜色提示，不称为零警告。
- 部署生效：本轮代码未部署、未重启 API/Worker/monitor、未迁移业务库、未覆盖 frontend/dist、未开启补审或改变生产并发/时限/模型/预算，没有历史重审或真实付费调用。结束只读核查业务 user_version=43、review_recoveries=0，新有效表不存在；API 10068、Worker 87408、monitor 87409 启动时间分别仍为 11 月 7 日 06:25:29、11 月 6 日 23:22:17、23:22:18。/api/health 白名单 status=ok、worker=running 不作为新能力部署确认。业务库仅有既有 monitor 按既定规则导入台账，不将页面同步视为代码上线；部署维度为 not_deployed。
- 排查与无效尝试：初轮全量 4 项旧断言仍认为候选固定未就绪或列表仅统计初审，按有效结论新契约更新，同时保留初审不变断言。组件旧时间文案改为明确“初审”后同步测试。浏览器夹具先后发现重复 delivery_id、错误读取安全投影中已删除的 manifest.input，已修复合成输入而非放松生产校验；补齐 TS 费用字段后重新构建。调度器测试最初错误要求独立执行槽严格线程顺序，改为验证补充通知必须晚于初审投递及补审完成、模型槽仍唯一；真实并发语义不改。完整来源链校验使脱敏夹具的不一致冻结摘要被拒绝，已同步修正合成证据链，不绕过校验。其他行宽、导入排序及类型问题修复后重跑最终检查通过。
- 关联文件或证据：docs/review-partial-rollout.md；docs/review-partial-review-plan.md；docs/configuration-guide.md；docs/deployment.md；backend/ocr_manager/review_effective.py；backend/ocr_manager/review_effective_migration.py；backend/ocr_manager/review_conclusion_chain.py；backend/ocr_manager/review_total_usage.py；backend/ocr_manager/review_feedback_queries.py；backend/ocr_manager/review_recovery_notifications.py；backend/ocr_manager/worker_scheduler.py；backend/tests/test_review_effective.py；backend/tests/recovery_browser_fixture.py；frontend/src/pages/ReviewRecoveryPanel.tsx；frontend/src/pages/EffectiveReview.tsx；frontend/src/test/reviewRecovery.test.tsx；frontend/e2e/reviewRecovery.spec.ts；frontend/test-results/review-recovery-confirm-320.png；frontend/test-results/review-recovery-320.png；docs/openapi.json。
- 遗留与下一步：真实网关/上游日志与关联 trace 尚缺，真实样本、金额上限和停止条件未定，故第五步真实根因对照和线上观察未执行，根因状态继续待调查；不擅自试跑全部历史任务、全局降并发或延时。按操作单另行完成成对备份解密、协调在途任务、同版发布与单项目真实补审/外发验收后才能确认上线。初审时间与补审时间分别展示，不声称已有完整全任务耗时分位数；GitLab 新来源发布保持关闭。结束核对台账来源 digest、SQLite 导入版本及 monitor 无冲突，不强制同步或覆盖人工页面事实。
- 同步状态：{"kind":"improvement","category":"stability","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261106-008｜追加：核对本机部署入口并说明升级与启用步骤，尚未执行部署

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：部署指导；已核查本机启动方式，未执行发布或启用。
- 关联记录：PI-20261106-008；前条完整恢复与上线准备记录。
- 现象或目标：用户询问本地如何部署生效，需要区分代码已实现、服务已升级与补审已启用，避免只刷新浏览器或只重启 API。
- 原因或分析：本机现有 API、Worker、monitor 仍为旧启动进程；四份既有 launchd 清单在当前用户 gui 域均未加载，不能直接使用 kickstart 作为升级方式。现有实例数据目录是 .local-data/local，不能改用 .local-data 根目录创建新库，也不能重新生成主密钥。
- 处理与改进：提供暂停触发并核对在途工作、协调停服、数据库与 private.json 成对备份及恢复解密演练、前端构建发布、沿用配置同版启动三个进程、核对 schema 45 与页面的步骤。补审单项目白名单启用与部署分开，人工确认后才创建批次；真实网关定位与有金额上限的试点继续独立安排。
- 代码修改：未修改业务代码、运行配置或前端产物；仅追加本条台账。
- 本地验证：实际运行 launchctl print gui/$(id -u)/ai.open-code-review.{api,worker,monitor,backup}（逐项查询）均未找到服务；使用 plistlib 白名单读取既有 plist 的工作目录和配置路径。实际执行 lsof -nP -iTCP:8781 -sTCP:LISTEN、ps -p 10068,87408,87409 -o pid,ppid,lstart,comm，核对 API 10068、Worker 87408、monitor 87409 仍在运行且启动时间未变。使用 Python SQLite mode=ro 核对业务 user_version=43、review_recoveries=0、新有效表不存在；urllib 请求 /api/health 白名单 status=ok。只读核对追加前来源 12 条与页面版本 12 的 digest 一致，monitor 无错误且 conflicts 为空。阅读现有部署/上线文档、配置解析和备份入口；一次尝试读取不存在的 private_config.py 未成功，随后改查实际 config.py。没有重跑业务测试、构建、备份或演练，不沿用上轮测试作为本轮执行结果。
- 部署生效：未部署、未停服或重启，未迁移业务库、覆盖 frontend/dist、写入 private.json、启用补审或调用真实模型。新功能仍为 not_deployed；台账自动同步不代表功能上线。
- 关联文件或证据：docs/deployment.md；docs/review-partial-rollout.md；backend/ocr_manager/launchd.py；backend/ocr_manager/config.py；backend/ocr_manager/backup.py。
- 遗留与下一步：实际升级前重新核对进程身份、在途任务与投递；备份及配对恢复解密演练成功后才发布。升级验证与单项目补审/外发验收分别记录，源头故障仍需真实链路证据。结束只读核对本条与页面同步，不强制同步或覆盖页面人工事实。
- 同步状态：{"kind":"improvement","category":"stability","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261106-008｜追加：说明仅本地启动方式，不执行服务重启

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：使用指导；说明本地手工启动，不涉及常驻部署。
- 关联记录：PI-20261106-008；前条本机升级与启用说明。
- 现象或目标：用户仅需本地启动，希望避免完整部署流程。
- 原因或分析：本地使用无需安装 launchd 服务，可在三个终端沿用现有私有配置分别启动 API、Worker、monitor；当前已有监听时不应重复启动。API 启动仍会迁移实际数据库，Worker 启动会领取既有队列，不能把手工启动描述为无业务副作用的预览。
- 处理与改进：说明已运行时直接打开本地页面；从停服状态启动时统一项目目录、PYTHONPATH 与 OCR_APP_CONFIG_FILE，分别执行三个模块。需要显示当前前端改动时先构建 frontend/dist；不重复初始化、不换主密钥、不启用补审开关。已有旧进程需协调停止后再启动，升级既有库前保留备份。
- 代码修改：未修改业务代码、配置或前端产物；仅追加台账。
- 本地验证：实际执行 lsof -nP -iTCP:8781 -sTCP:LISTEN 与 urllib 请求 /api/health，核对当前监听及健康状态；未执行启动命令、构建或功能测试。上轮测试不作为本轮重验。
- 部署生效：未部署、未重启、未迁移业务库、未调用真实模型；本轮仅说明操作方法。
- 关联文件或证据：docs/deployment.md；backend/ocr_manager/config.py；backend/ocr_manager/launchd.py。
- 遗留与下一步：实际重启前核对在途工作和旧进程，沿用原配置及环境；本地启动不等同于真实补审与外发验收，源头故障仍需独立调查。结束核对来源与页面同步，不强制覆盖页面。
- 同步状态：{"kind":"improvement","category":"stability","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261106-008｜追加：提供先停旧服务再启动的完整本机操作顺序

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：操作指导；按用户要求提供完整停服、备份、构建、启动和验证命令，未代为执行。
- 关联记录：PI-20261106-008；前条仅本地启动说明。
- 现象或目标：避免已有三个旧服务与新进程重复运行，让本地重启步骤可以按顺序操作。
- 原因或分析：本轮只读 ps 发现 API 为 23774，不再是此前 10068；变更来源未调查，不推断操作者或原因。Worker 与 monitor 仍为 87408、87409。进程 ID 会变化，操作前必须重新核对；不能用历史 PID 或宽泛 pkill 结束其他服务。
- 处理与改进：要求先在页面确认在途评审及投递结束，再核对进程、以 TERM 停止 API/Worker/monitor，检查旧进程与端口释放，未退出时停止后续操作而非强杀或删除锁。停服后成对备份并验证隔离恢复报告成功，构建前端，沿用原私有配置与终端环境先启动 API，确认 schema 45 再启动 Worker/monitor。补审开关不在该流程中自动启用。
- 代码修改：未修改业务代码、配置、锁文件或前端产物；仅追加台账。
- 本地验证：实际执行 ps -axo pid=,ppid=,command= 并筛选本项目模块、lsof -nP -iTCP:8781 -sTCP:LISTEN、ps -p 23774,87408,87409 -o pid,ppid,lstart,comm，核对当前三个进程及监听；逐项 launchctl print 查询当前用户 gui 域 API/Worker/monitor 均未加载。阅读 Worker 停止信号、调度器、备份演练报告实现及实施流程；未运行停止、备份、恢复演练、构建、迁移或启动命令，未重跑业务测试。
- 部署生效：未部署、未停服或重启、未修改业务库或启用补审；仅输出指导，不能由当前 API PID 变化认定本轮功能已部署。
- 关联文件或证据：docs/deployment.md；docs/review-partial-rollout.md；backend/ocr_manager/worker.py；backend/ocr_manager/worker_scheduler.py；backend/ocr_manager/backup.py。
- 遗留与下一步：用户实际执行时以实时进程为准，任一步失败先停止后续步骤；真实模型调用与外发验收独立安排。结束核对台账来源和页面同步，不覆盖页面人工修改。
- 同步状态：{"kind":"improvement","category":"stability","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261106-008｜追加：复现 macOS 系统 SQLite 只读检查错误并更正本机操作命令

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：问题排查与文档修正；检查命令已更正并实际验证，整套本地启动尚待完成。
- 关联记录：PI-20261106-008；前条完整停服启动操作说明。
- 现象或目标：用户执行 sqlite3 -readonly 查询 user_version 时出现 unable to open database file (14)，同时 /api/health 返回 status=ok、worker=stopped，需要区分检查命令失败与业务数据库损坏。
- 原因或分析：本机 /usr/bin/sqlite3 为 3.51.0，项目 Python SQLite 为 3.53.1。业务库使用 WAL 且检查时没有旁路文件；在临时目录构造无旁路文件的合成 WAL 库，系统 CLI 只读返回 14，项目 Python mode=ro 正常读取；保持 Python 只读连接及其旁路文件存在时，系统 CLI 成功；同环境 DELETE 模式对照始终成功。由此将问题限定为当前系统 CLI 的 WAL 只读打开行为，不推断 SQLite 所有版本都存在此问题或数据库已损坏。一次绝对路径查询在 Python 连接尚存时成功，关闭连接后绝对路径及 URI 均失败，故不能归因相对路径或声称换绝对路径即可解决。
- 处理与改进：将本机核查改用项目 .venv/bin/python、Path.resolve(strict=True) 与 SQLite URI mode=ro，并显式关闭连接；补充部署文档排错、禁止删除库/旁路文件和禁止 immutable=1 绕过 WAL 的说明。用户可保留已启动 API，完成 Python 核对后继续启动 Worker 与 monitor，不重做恢复或迁移。
- 代码修改：未修改业务代码、数据库内容、私有配置或服务进程；仅修改 docs/deployment.md 并追加台账。只读连接由 SQLite 管理必要的 WAL 旁路文件，没有手工删除或改写业务文件。
- 本地验证：实际执行系统 CLI 相对路径、绝对路径及 URI 只读查询并复现错误；项目 Python mode=ro 查询业务 schema=45、quick_check=ok、foreign_key_check=0、review_jobs=385。临时合成 DELETE/WAL 对照及保持只读连接的 CLI 查询验证如上，临时目录自动清理；最终实际执行文档中的 Python 命令，输出版本 45、完整性 ok。只读核对私有配置中数据目录和开发模式白名单，路径与现有实例一致；未打印密钥。lsof/ps 与 /api/health 核对 API 25251 在运行、Worker/monitor 未运行，健康 status=ok、worker=stopped。未重跑业务测试、前端构建、备份或恢复演练。
- 部署生效：用户已启动的本地 API 可用、业务结构已为 45，这是本轮新核对事实；不再沿用旧 schema 43 状态。当前 Worker、monitor 未启动，前端版本及完整补审外发尚未确认，整套部署维度为 unknown；本轮排查未主动重启、执行任务或开启补审，也不认定源头模型超时已解决。
- 关联文件或证据：用户报错截图；docs/deployment.md 的 macOS 本机只读数据库检查；backend/ocr_manager/config.py；临时合成 SQLite 对照输出。
- 遗留与下一步：用户用更正命令核对后继续启动唯一 Worker 与 monitor，再核对健康、心跳、前端和开关；真实补审与外发独立验收。monitor 当前未运行，来源追加尚未同步页面；不手动强制同步，不覆盖网页事实，恢复 monitor 后核对导入 digest。
- 同步状态：{"kind":"improvement","category":"stability","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"unknown"}

### PI-20261106-008｜追加：核查 #381 历史诊断缺失与补审关闭，增强禁用原因及处理指引

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：问题排查与展示改进；已定位两个直接原因并完成本地验证，真实网关根因与运行页面发布尚未完成。
- 关联记录：PI-20261106-008；前条本机只读数据库检查修正；docs/review-partial-381-diagnosis.md。
- 现象或目标：用户截图的失败文件仍只显示 timeout，继续审核剩余部分按钮不可点击，希望明确故障细节与无法操作的具体原因。
- 原因或分析：通过只读 SQLite 匹配截图任务为 #381、内部仓库 ID 2。旧 result_json 不含 failure_analysis、diagnostic 为空；新版投影只在结果持久化时生成，不会因升级自动回填旧工件。只读资格接口实际返回 eligible=false、reason_code=feature_disabled，现有私有配置未显式设置补审开关与白名单，使用默认关闭值；不是 Worker 未启动导致该原因码。原界面已有简短说明但不够醒目，未知资格/查询失败也缺少针对性引导。
- 处理与改进：在数据目录内校验工件路径，用 SQLite 固定 head/base 调用既有 diagnostic_report 只读解析，不写回任务。确认覆盖 40/45、5 个未完成文件同一失败分组；计划请求 6 次 HTTP 504、响应头计时约 60 秒，主审核另有 context timeout，无该请求 HTTP 状态；同时有 4 项依赖缺失和 1 项搜索上限信号，不将信号共存冒充因果。新增安全分析文档。补审区增加醒目的禁用原因、原因码、内部仓库 ID 与配置/重启指引，并关联按钮可访问说明；查询失败保持禁用，不误报功能关闭。历史诊断缺失明确说明升级/重启不自动补齐；失败表声明文件级超时不是根因。未自动开启开关或放宽来源校验。
- 代码修改：修改 frontend/src/api/reviewRecovery.ts、frontend/src/pages/ReviewRecoveryPanel.tsx、ReviewFailureAnalysis.tsx、CoverageReasons.tsx 及相关组件/浏览器测试；新增 docs/review-partial-381-diagnosis.md。后端业务代码、数据库结构、任务结果、私有配置、frontend/dist 均未修改；原始工件只读，没有复制敏感代码、完整响应或工具参数。
- 本地验证：实际执行 npm --prefix frontend run lint 通过（浏览器测试补齐后再次执行）；npm --prefix frontend test：91 passed；npm --prefix frontend run build -- --outDir /tmp/ocr-recovery-availability-dist 通过，未覆盖运行前端。指定本机 Chrome、OCR_BROWSER_REVIEW_RECOVERY=1、OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-recovery-availability-dist 执行 npx playwright test e2e/reviewRecovery.spec.ts：最终 7 passed，含新增 1280/320px 禁用指引、历史缺失提示，以及确认/执行/反馈/停止/只读/独立通知原专项。新增浏览器场景用明确路由替身模拟关闭资格与历史诊断缺失，不作为真实生产开关验收；临时 8791 测试服务不启动真实 Worker。人工查看 320px 禁用页截图，未发现横向溢出。实际执行 .venv/bin/pytest -q backend/tests/test_review_diagnostics.py：14 passed；未重跑后端全量。git diff --check 通过。仍有 Starlette/httpx 弃用、前端主包超过 500 kB、临时目录不自动清空及浏览器颜色环境提示，不称为零警告。
- 部署生效：当前业务 schema 已在前条核对为 45；本轮结束 /api/health 为 status=ok、worker=running，API 25251、Worker 25697、monitor 25715 的运行事实已核查。新提示仅隔离构建，未正式发布、未重启服务、未改私有配置、未开启补审、未调用真实模型、未创建补审批次或回填 #381；#381 资格仍为 feature_disabled。整套补审及本轮新提示未验证部署，维度为 unknown，不能以健康或结构升级确认功能可用。
- 排查与无效尝试：首轮新增浏览器两项失败，原合成夹具会按新代码自动保存 failure_analysis，因此不应期望出现历史缺失提示；增加明确的历史详情路由替身后重跑 7 项全部通过，未修改业务判断绕过断言。原页面 failure_analysis=null 的单测保留，并验证没有凭空生成 HTTP 504 诊断。
- 关联文件或证据：docs/review-partial-381-diagnosis.md；frontend/src/pages/ReviewRecoveryPanel.tsx；frontend/src/pages/ReviewFailureAnalysis.tsx；frontend/src/pages/CoverageReasons.tsx；frontend/src/api/reviewRecovery.ts；frontend/src/test/reviewRecovery.test.tsx；frontend/src/test/reviewDiagnostics.test.tsx；frontend/e2e/reviewRecovery.spec.ts；frontend/test-results/review-recovery-disabled-320.png；backend/ocr_manager/review_diagnostic_report.py。
- 遗留与下一步：本轮报告不自动出现在旧任务网页，受控历史诊断导入未实现；旧证据明细可查安全文档，不宣称已回填。若启用补审，需在原私有配置显式限定内部仓库 2 并协调进程读入，再核对配置漂移、来源与预算，不能承诺开关开启后 #381 必然合格。新提示需正式前端构建发布后显示。重复约 60 秒 504 的具体网关层级尚未知，仍需受控链路证据和费用边界，不宣称超时根因已解决。结束核对来源 digest、页面导入版本及 monitor 冲突，不强制同步或覆盖页面。
- 同步状态：{"kind":"improvement","category":"stability","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"unknown"}

### PI-20261106-008｜追加：受控导入全部历史诊断并移除补审开关，完成本地发布核验

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：功能实施与本地发布；历史诊断导入、默认人工补审已在当前本机实例生效，真实模型补审和上游超时根因仍未验收。
- 关联记录：PI-20261106-008；前条历史诊断缺失与补审关闭排查；本条替代旧的开关及项目白名单启用操作，不修改历史记录。
- 现象或目标：用户要求覆盖全部旧任务而非仅 #381，并取消补审功能开关，使部分审核任务默认展示可申请的补审入口，不再要求管理员配置试点项目。
- 原因或分析：旧任务未持久化分层诊断，单纯重启不能恢复；直接 UPDATE 初审 result_json 会破坏补审冻结摘要和有效结论来源。旧开关及项目白名单额外阻塞原本可信的部分任务，与当前产品要求不符。取消功能开关不等于取消来源、配置和预算校验；配置已改变或源结果不可信时不能补审错误版本。
- 处理与改进：增加 schema 46 独立历史诊断表及显式预览/执行命令，遍历所有 partial/failed 历史尝试并覆盖缺少尝试行的可信当前结果。工件限定任务目录内普通 result.json，限制大小、拒绝越界和链接，核验固定 SHA/base、状态、覆盖及评论；共用工件锁，提交前复核源快照，诊断和审计同事务，重复执行不覆盖。仅存安全投影，不修改初审结果、有效指针、发现、费用或通知，不调用 Git、模型和飞书。详情、列表摘要、当前及历史报告按源尝试隔离读取。移除配置字段、环境键读取、API/队列/调度器/通知/反馈中的功能开关和项目白名单，部分任务默认显示入口；保留真实只读角色限制、人工预算确认、固定来源、配置摘要、互斥、唯一模型槽和累计额度。
- 代码修改：修改后端配置、补审执行/投递/反馈链、存储迁移与安全读取，新增 review_diagnostic_import.py、review_diagnostic_import_migration.py、review_historical_diagnostics.py 和历史导入测试；修改前端补审面板、原因指引、历史导入时间展示与组件/浏览器测试，更新 OpenAPI。新增 docs/review-historical-diagnostic-import.md，更新配置、部署和旧阶段文档的当前版本说明。没有修改原私有配置、主密钥、模型参数或业务工件内容；代码维度为 modified。
- 本地验证：实际执行 .venv/bin/ruff check backend/ocr_manager backend/tests、.venv/bin/mypy backend/ocr_manager（111 个源码文件）、OCR_RESUME_PROBE_COMMAND="$PWD/.local-tools/node_modules/.bin/ocr" .venv/bin/pytest -q：634 passed，包含真实 OCR 1.12.9 对本机合成端点的探针，没有真实付费模型调用。PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract 与 git diff --check 通过。实际执行 npm --prefix frontend run lint、npm --prefix frontend test：91 passed；隔离构建 /tmp/ocr-history-default-recovery-dist 通过。指定本机 Chrome、OCR_BROWSER_REVIEW_RECOVERY=1、OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-history-default-recovery-dist 执行 npx playwright test e2e/reviewRecovery.spec.ts：9 passed，覆盖真实合成历史导入、默认可补审、配置阻塞、确认、执行、反馈、停止、只读角色和独立通知。未运行完整浏览器套件。仍有 Starlette/httpx 弃用、主包超过 500 kB、隔离目录和浏览器颜色提示，不称为零警告。
- 部署生效：实际确认 launchd 三服务均未加载且六类评审/事件/连接/投递队列为空后，TERM 停止 API 25251、Worker 25697、monitor 25715，没有强杀或删除锁。沿用 .local-data/local/private.json，在 .local-data/backups/history46-20261107-100610 保存成对数据库/原主密钥配置和旧前端；恢复演练在隔离副本完成完整性、迁移至 46 和真实存量加密凭据解密检查，outcome=passed。业务库迁移 45→46，quick_check=ok、foreign_key_check=0；迁移和导入前后原有表内容摘要一致（审计表仅追加导入审计）。实际扫描 36 条候选历史尝试，导入 #321/#337/#343/#381 各第一次尝试共 4 条、追加 4 条审计；32 条因 source_result_missing 明确跳过。执行后函数及实际 CLI --preview 均返回 already_imported=4、source_result_missing=32。发布已验证的隔离前端产物，沿用原配置及启动环境重启唯一 API 30480、Worker 30481、monitor 30482，启动时间为 10:06:31/31/32；健康 status=ok、worker=running，实际 HTTP 首页摘要与发布产物一致。真实 API 核验四条历史报告诊断匹配；#321/#343/#381 当前详情、列表摘要及当前报告一致，#337 当前为第二次 failed，第一次 partial 的诊断仅进入第一次报告，没有污染新尝试。#381 资格 eligible=true、剩余 5 个文件；#321/#343 因 configuration_changed 保持真实阻塞，#337 当前非 partial，均不再出现开关原因。使用真实本机页面、Chrome 在 1280/320px 验证 #381 历史导入标记、504 请求证据、可用按钮、剩余 5 文件确认框和无横向溢出；只打开确认框，没有点击确认或发出写请求。发布后再次只读核对 22 张评审/投递等业务表摘要未变化、review_recoveries=0。本次部署确认仅限上述本机代码、迁移、导入和读侧/确认入口；不代表真实模型补审、飞书外发或超时根因已验收。
- 排查与无效尝试：初轮后端全量的两项旧 schema 45 终版断言改为 46，回滚中间版断言保留；浏览器夹具在 macOS /var 指向 /private/var 时误拒绝系统别名，改为仅拒绝受控任务目录内链接并保留真实越界/文件链接/目录链接测试，最终回归通过。部署读回脚本最初把旧 /api/jobs 简表当作带摘要的检索接口，改用 /api/task-search；随后错误假设四条导入均对应当前尝试，依据 SQLite 核对 #337 当前第二次失败后改为验证历史报告及当前隔离，未放宽生产判断。真实页面只读核验初轮把主动拦截的外部字体 GET 计为业务写入失败，区分外部只读拦截与写请求后重验两个宽度通过；外部读取仍被拦截，没有为验收放开外网或提交补审。
- 关联文件或证据：docs/review-historical-diagnostic-import.md；backend/ocr_manager/review_diagnostic_import.py；backend/ocr_manager/review_historical_diagnostics.py；backend/ocr_manager/worker_scheduler.py；backend/tests/test_review_diagnostic_import.py；frontend/src/pages/ReviewRecoveryPanel.tsx；frontend/src/pages/ReviewFailureAnalysis.tsx；frontend/e2e/reviewRecovery.spec.ts。本机受限发布目录保存 release-report.json、恢复演练报告、导入逐条报告、前后事实摘要、deployed-api-verification.json、deployed-browser-verification.json、business-facts-final-verification.json；不在台账写入凭据、完整外部响应或代码正文。
- 遗留与下一步：用户刷新本机任务详情即可查看当前版本并人工决定是否确认 #381 补审，本轮不自动创建批次或发生补审费用。#321/#343 需要核对原始与当前配置后选择正确处理路径，不能通过解除安全检查强行执行；#337 第一次诊断从对应历史报告读取。32 条缺少可信持久化结果的尝试无法凭空还原，保留跳过清单和未知边界。重复约 60 秒 504 的具体网关层级仍需独立链路证据，不将诊断导入或按钮可用宣称为源头故障修复。结束核对本条追加后的来源 digest、页面版本及 monitor 冲突；若不同步则明确记录，不强制覆盖页面。
- 同步状态：{"kind":"improvement","category":"stability","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261107-002｜HTTP 域名操作报错、补审失败说明与同类浏览器兼容问题

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：问题排查与修复中；本轮问题此前漏记，现独立建档，未宣称完成发布。
- 关联记录：PI-20261106-008；历史诊断导入及默认补审的后续问题，本条独立显示，原记录保留。
- 现象或目标：通过普通 HTTP 域名确认补审时报 crypto.randomUUID is not a function，本地访问正常；既有补审批次显示已失效但缺少可理解原因。用户要求排查全站同类问题，并询问为何问题页面没有记录。
- 原因或分析：普通 HTTP 域名不是安全上下文，randomUUID 与 clipboard 等浏览器能力不能假定存在；localhost 存在例外。另发现 API Client 直接使用 AbortSignal.timeout/any 及规则草稿使用 structuredClone 的兼容风险。只读证据显示 #381 两次补审均因累计 token 预算保护中止，完成 0/5，实际记录总量分别 550、584，预算各 1000；不能据此声称实际已超 1000 或推断更高预算必成功。旧结束映射把无法合并的执行结果统一标为 stale，界面缺少安全失败摘要。台账 monitor 自动同步文件追加记录，不抓取聊天；当前问题未追加到来源，故页面没有本次事项，属于本轮记录遗漏，不是用户配置或 monitor 故障。
- 处理与改进：新增安全 UUID、剪贴板兼容及取消/超时统一封装，替换已发现调用点；保留补审幂等键与预算边界，新增安全失败摘要和后续批次状态分类，不改写历史事实。正在增加全局测试及静态防回归检查。独立建档后由既有 monitor 同步，不修改已同步历史，不凭代码修改认定已上线。
- 代码修改：后端补审结果分类、只读安全摘要及契约已修改；前端补审、问题/主题新建、复制、请求取消超时、规则草稿及 ESLint 已修改，最新全局兼容改动尚待完整验证；代码维度 modified。
- 本地验证：本轮前阶段实际运行 Ruff、mypy（111 个源码）、全量 pytest（635 passed）、OpenAPI 更新与检查；前端当时 98 passed、lint 和隔离构建通过，补审 Playwright 10 passed，含真实非安全合成域名与同键重试。随后新增剪贴板、请求兼容及其他页面修复，因此这些既有结果不能覆盖最新全部改动，当前总体验证为 not_run。只读核对来源 PI-20261106-008 有 18 条、页面 id=8/version=18、digest 一致，monitor 无错误且无冲突；未发现本轮问题记录。浏览器初次 DNS 转发验证失败，修正合成端点转发地址后重验通过。
- 部署生效：本轮修复尚未发布；当前运行服务与 frontend/dist 仍是上一阶段历史诊断发布版本。本轮未发起真实补审，未消费剩余批次或提高预算，部署状态 not_deployed。
- 关联文件或证据：frontend/src/api/commandId.ts；frontend/src/api/requestSignal.ts；frontend/src/ui/clipboard.ts；frontend/src/pages/ReviewRecoveryPanel.tsx；backend/ocr_manager/review_recovery_store.py；frontend/e2e/reviewRecovery.spec.ts；SQLite 只读记录及来源同步摘要。
- 遗留与下一步：先确认本条同步页面，再完成全局兼容验证、文档与本地发布核验；对实际 HTTP 域名只做读侧或拦截写请求验收，不触发付费模型。预算根因与旧网关 504 为不同故障，不把浏览器修复等同于源头网关修复。结束时追加实际进展与同步结果。
- 同步状态：{"kind":"problem","category":"stability","status":"investigating","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-003｜问题台账漏记防护与交付前只读核验

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：已受理；落实先建档、过程追加及收尾核验，防护尚未完成验证。
- 关联记录：PI-20261107-002；用户追问后续是否仍会遗漏及如何防止，不覆盖原 HTTP 修复事项。
- 现象或目标：已有每次收尾记录和 monitor 同步约定，但处理中断时仍可能没有来源记录，用户必须提醒才能发现。
- 原因或分析：同步器只消费台账，不知道聊天中新问题；只有收尾约定而没有受理记录和机器核验，存在源头遗漏窗口。不能承诺绝不遗漏，也不能把自动抓取全部聊天作为默认方案。
- 处理与改进：先独立建立本条受理记录，再增加项目执行规则与只读核验命令；检查明确指定的事项是否建档、最少追加数、来源摘要及页面版本是否一致、状态事实及 monitor 冲突。未知聊天问题无法由该命令自动发现，人工识别事项仍是必要边界。
- 代码修改：本条建立时仅追加台账，防护命令和规则尚待修改；代码状态 unchanged。
- 本地验证：已核对当前台账解析、同步游标、页面版本及 monitor 数据结构，未运行新防护命令或测试；验证状态 not_run。
- 部署生效：尚未完成，防护命令不修改业务库，不新增抓取聊天的后台任务；部署状态 not_deployed。
- 关联文件或证据：AGENTS.md；backend/ocr_manager/improvement_log_parser.py；backend/ocr_manager/improvement_log_sync.py；docs/problem-improvement-log.md。
- 遗留与下一步：实现及测试漏记、等待同步、历史冲突、页面人工修改、缺少进展和正确同步场景；实际核对本条与页面同步，并在收尾追加结果。
- 同步状态：{"kind":"improvement","category":"stability","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-002｜追加：完成全站已识别浏览器兼容修复并核验实际 HTTP 域名

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：代码、本地验证和本机发布完成；上游网关 504 根因和真实付费补审仍未验收。
- 关联记录：PI-20261107-002；PI-20261106-008；漏记防护另见 PI-20261107-003。
- 现象或目标：解决非安全 HTTP 域名补审确认报错，检查所有已识别同类调用，说明旧补审失败而不改写历史。
- 原因或分析：确认普通 HTTP 缺少 randomUUID 和 clipboard，而 localhost 有安全上下文例外；统一 API Client 还存在新版 AbortSignal 静态方法兼容风险。#381 两次旧补审确为预算保护中止，完成 0/5，总用量分别 550、584，不将预算保护误称为实际已超 1000，也不与初审 504 混为同一故障。
- 处理与改进：安全 UUID 层覆盖补审、问题新建、主题新建三处；请求键在保存时生成且失败保留草稿，同键重试不重复建档。复制层覆盖回调地址及隐藏/明文令牌，能力缺失或拒绝时兼容尝试，失败提供手动选择指引，临时内容清除并恢复焦点；再次复制先清除旧成功提示。全部 API 请求用基础控制器、计时器与监听组合取消/超时并清理；规则草稿按固定类型复制。ESLint 防止生产调用点绕过兼容层。新批次执行失败与源失效分开；旧 stale 原样保留并解释旧分类，API 提供固定安全原因摘要，不暴露原始模型内容。
- 代码修改：前后端兼容和补审诊断、测试、OpenAPI 与文档已修改；不改变原私有配置、预算、主密钥、初审和历史业务数据。新增 docs/http-browser-compatibility.md。
- 本地验证：最终实际执行 .venv/bin/ruff check backend/ocr_manager backend/tests、.venv/bin/mypy backend/ocr_manager（112 个源码文件，含独立漏记防护模块）、OCR_RESUME_PROBE_COMMAND="$PWD/.local-tools/node_modules/.bin/ocr" .venv/bin/pytest -q：647 passed；PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract、npm --prefix frontend run lint、git diff --check 通过。最新前端 npm --prefix frontend test：115 passed，tsc -b 和隔离构建 /tmp/ocr-http-recovery-fix-dist 通过。使用指定本机 Chrome 及隔离产物运行默认 Playwright 套件：57 passed、13 个独立通道测试明确跳过；独立 OCR_BROWSER_HTTP_COMPAT=1 通道 3 passed，独立 OCR_BROWSER_REVIEW_RECOVERY=1 通道 10 passed。实际五个合成敏感直接调用均被 ESLint 拒绝。未调用真实付费模型；保留 Starlette/httpx 弃用、主包 501.52 kB 和颜色/隔离目录警告，不称零警告。
- 部署生效：实际核对 launchd 未加载、三个旧进程身份及 11 类队列均空后，以 TERM 协调停止 API 30480、Worker 30481、monitor 30482，无强杀或删锁。成对备份至 .local-data/backups/http-compat-20261107-105845，保存原前端；隔离恢复完整性、迁移、存量加密凭据解密全部 passed。沿用原配置和受控环境发布测试产物并启动唯一 API 38629、Worker 38637、monitor 38638；健康 ok/running、schema 46、完整性 ok、外键问题 0，25 张评审/投递/配置业务表摘要未变，#381 仍仅 2 条原始 stale 批次。实际 API 的安全失败摘要及 OpenAPI 新字段生效。真实用户 HTTP 域名 1280/320px 与 localhost 1280px 页面均通过；公共 HTTP 实测非安全上下文且 randomUUID 缺失，历史预算摘要及旧分类提示可见，确认与重试产生有效相同 UUID，全部补审 POST 在浏览器路由层拦截并返回合成 503，未送业务服务；无页面异常或横向溢出。域名/本地首页均与新发布产物摘要一致。没有新增真实补审、费用、通知或自动预算变更，剩余批次未消耗。本轮仅确认本机及其现有穿透域名发布，不代表其他部署环境。
- 排查与无效尝试：新增主题单测首轮因缺少必填阶段目标未提交，补齐合成输入后通过；规则用例首先被夹具排队任务的生产保护拒绝，改用明确响应替身验证浏览器草稿而不放宽业务保护，随后以 textbox 角色修正刷新后的标签定位并通过。首次默认全浏览器套件后运行 HTTP 文件时，前序多人鉴权修改令新浏览器未登录，57 通过/3 失败；改为显式独立 HTTP 通道，重新运行默认及两种独立通道全部通过。不重置鉴权或删测试来掩盖失败。一次脚本使用不存在的 python 命令未执行，改用项目 .venv/bin/python 完成；官方 Codex 页面读取返回 403，不据此宣称已验证聊天订阅接口。
- 关联文件或证据：docs/http-browser-compatibility.md；frontend/src/api/commandId.ts；frontend/src/api/requestSignal.ts；frontend/src/ui/clipboard.ts；frontend/e2e/httpCompatibility.spec.ts；frontend/e2e/reviewRecovery.spec.ts；backend/ocr_manager/review_recovery_store.py；受限备份目录的 release-report.json、恢复演练、facts-before/after.json、deployed-api-verification.json、deployed-browser-verification.json。
- 遗留与下一步：用户刷新域名即可使用新版本；真实付费补审仍需用户人工决定预算及是否执行，本轮不代为消耗最后批次。初审上游 504 的具体网关层级仍待独立链路证据。全局检查指手写生产调用和已运行现代浏览器范围，不承诺所有旧浏览器或插件兼容。最终运行台账只读核验，未同步或有冲突如实报告，不覆盖网页事实。
- 同步状态：{"kind":"problem","category":"stability","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261107-003｜追加：实现只读漏记核验，并比较结构化台账与聊天自动采集方案

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：当前流程防护已实施并本地验证；聊天自动采集仍为建议方案，未启用。
- 关联记录：PI-20261107-003；PI-20261107-002；用户进一步询问为何不抓取聊天、如何改造，以及两种方式优缺点和推荐选择。
- 现象或目标：减少未建档遗漏，又不把聊天推测、重复描述或未部署结果写成正式事实；避免用户每次提醒或逐条确认。
- 原因或分析：现有机制只覆盖来源到页面，未覆盖聊天到来源。受理先建档及核验可降低流程遗漏，但不能发现尚未登记的聊天问题。自动采集改善覆盖和中断恢复，却引入接入权限、敏感数据、语义误判、去重和来源编辑问题；不应以隐私为由宣称不可实现，也不能宣称零遗漏。
- 处理与改进：AGENTS.md 新增先受理建档、阶段追加及实际运行只读命令的约定；新增 improvement_log_check.py 对显式编号、最少条数、完整来源摘要、页面版本/归档/状态及最近 120 秒维护结果核验。不存在数据库拒绝创建，不迁移、不抓聊天、不强制同步、不覆盖人工事实。新增隔离测试与执行文档。形成聊天自动采集方案：推荐限定项目会话自动建待核实记录，结构化证据控制修改/验证/部署状态，消息幂等、可逆关联、重启补读及积压/失败可见；不要求逐条确认，但有歧义保留待核实，不静默忽略或自动解决。建议分接入验证、影子采集、自动受理、对账运维四阶段，不直接启用全账号抓取。
- 代码修改：新增 backend/ocr_manager/improvement_log_check.py、backend/tests/test_improvement_log_check.py；更新 AGENTS.md 和文档入口，新增 docs/problem-log-delivery-check.md、docs/chat-problem-capture-proposal.md。未修改既有只读同步边界，未接入其他聊天或新建定时任务。
- 本地验证：实际执行 .venv/bin/pytest -q backend/tests/test_improvement_log_check.py：12 passed；覆盖漏编号、缺进展、待同步、历史冲突、页面修改/归档/缺失、状态不一致、monitor 过期/错误/未来时间、只读不变和不存在库不创建。首轮构造页面缺失被外键正确拒绝，改为仅在隔离夹具模拟外部破坏后的孤立游标，最终回归通过。Ruff 全后端、mypy 112 源码通过，全量 pytest 647 passed，OpenAPI、前端 lint、diff 检查通过。真实业务库运行只读命令要求 PI-20261107-002 至少两条时，因当时仅一条实际退出 1，正确报告 source_missing_or_progress_incomplete；等待 monitor 后仍拒绝，证明不会把单条受理误当收尾。官方 Codex 文档请求返回 403，未验证当前桌面消息接口/订阅可用性，不假定存在稳定可集成通道。
- 部署生效：本地 CLI 和项目规则已可使用，不需要启动新服务；在现有业务库实际验证了只读拒绝路径，后续本条同步完成后再次核对通过路径。聊天自动采集未实现、未启用、未读取其他会话，不能将当前防护部署确认理解为自动抓取上线。现有 monitor 保持 30 秒台账同步；未更改业务库结构或采集范围。
- 关联文件或证据：AGENTS.md；backend/ocr_manager/improvement_log_check.py；backend/tests/test_improvement_log_check.py；docs/problem-log-delivery-check.md；docs/chat-problem-capture-proposal.md；本轮实际隔离及只读命令输出。
- 遗留与下一步：结束分别核对 002/003 本轮累计至少两条已同步且无冲突。推荐未来采用自动采集与结构化证据双通路，先确认接入范围并验证稳定消息接口；当前只给比较和方案，不把用户咨询视为授权全量历史读取。规则和命令不会自动拦截所有聊天回复，未登记语义问题仍需识别，不承诺百分之百无遗漏。
- 同步状态：{"kind":"improvement","category":"stability","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261107-003｜追加：受理混合方案实施，先验证限定项目的会话接入

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：已受理实施；用户明确选择混合方案，先核对接入能力，不承诺实时零遗漏。
- 关联记录：PI-20261107-003；前条结构化核验及聊天采集比较；PI-20261107-002 已完成的 HTTP 兼容修复不受本轮改写。
- 现象或目标：用户要求实际实施自动聊天受理与结构化证据双通路，希望接近实时记录并减少遗漏，不再停留于建议。
- 原因或分析：当前只有台账同步与收尾核验，尚无持久化会话摄取；需要验证本机合法稳定的读取路径、限定项目与会话、消息幂等、中断补读和失败可见。消息读取连续不等于语义识别百分之百正确，不应承诺零遗漏。
- 处理与改进：将授权限定为本项目会话采集及混合记录，不读取其他项目、私人会话、凭据或全账号历史；优先验证受支持消息接口，随后实现持久化待核实、证据控制状态、对账和监控。没有实际验证的接入不得宣称已可用；如接口受限明确记录边界，不依赖秘密扫描内部数据库替代。
- 代码修改：本条受理时未修改业务实现，仅追加进展；代码维度沿用已有防护 modified，新采集尚未实现。
- 本地验证：实际官方 app-server 文档请求返回 HTTP 403，尚未取得可引用文档，不据此推断桌面接口可用性；实际 codex --version 为 0.167.0-alpha.3.2，尚未运行新采集测试。
- 部署生效：当前混合采集尚未部署或启用；保留既有 monitor 台账同步，本轮新功能 not_deployed，不沿用 CLI 防护的已生效状态。
- 关联文件或证据：docs/chat-problem-capture-proposal.md；AGENTS.md；本机 CLI 版本及官方文档访问状态。
- 遗留与下一步：验证来源与边界后实现，隔离验证重放、取消/撤权、失败补偿及敏感信息防护，再按空闲检查、备份和发布核验流程上线；最终分别报告实时程度与仍可能遗漏的边界。
- 同步状态：{"kind":"improvement","category":"stability","status":"investigating","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-003｜追加：混合采集实现与隔离验收进展，尚未发布业务实例

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：混合方案代码已实现，隔离验证进行中；不把旧版运行等同于本轮新功能部署。
- 关联记录：PI-20261107-003；本轮受理授权及原结构化防护。
- 现象或目标：限定当前项目会话近实时自动受理、来源可追溯与人工更正，保留证据驱动的结构化进展。
- 原因或分析：本机 app-server 摘要分页实际可用，读取当前授权起点后一条用户消息耗时约 0.05 秒；只说明本机当前版本可用，未验证稳定推送或官方长期兼容。消息摄取与语义识别不能混为零遗漏承诺。
- 处理与改进：新增 schema 47 显式绑定、脱敏来源和关联审计；有界授权范围重读、消息指纹去重、编辑追加、撤权版本栅栏、短事务和失败重试。明确疑似问题自动建待核实，其余用户消息保留来源；关联可逆且冲突不覆盖，代码/验证/部署初始状态不能被聊天宣称升级。独立 monitor 周期摄取，不经 HTTP 读取或占付费槽；管理员页面展示失败、过期、待核实和分页，可暂停/恢复。新增运行说明，明确仅本会话本次授权后、无附件 OCR、无全账号历史和复杂语义拆分、摘要截断及近实时限制。
- 代码修改：新增 chat_capture 适配器、存储、协议、迁移、CLI、API、前端收件箱与测试；修改 monitor 装配、schema 测试夹具、OpenAPI、项目规则和文档。既有私有配置、预算、模型和业务评审任务未修改。
- 本地验证：已实际完成全量 pytest 669 passed、Ruff 和 mypy 119 源码通过；前端 119 passed、lint、tsc 和隔离构建通过；独立合成聊天 Playwright 3 passed，覆盖 1280/320px 无溢出、自动受理、查询失败不伪装健康、关联/解除和暂停刷新持久化。继续补充数据库回滚、绑定 CLI 错误实例与半行响应超时测试，全量及默认浏览器回归进行中，最终以收尾结果为准。首次 OpenAPI 路径静态检查不支持成员插值，改为具名 ID 插值后通过，不放宽检查器。
- 部署生效：本条记录时新功能尚未发布；业务库仍由原实例运行，未建立聊天授权绑定或执行真实补审，标记 not_deployed。
- 关联文件或证据：docs/chat-capture.md；backend/ocr_manager/chat_capture_adapter.py；backend/ocr_manager/chat_capture_store.py；backend/tests/test_chat_capture.py；backend/tests/test_chat_capture_protocol.py；frontend/src/pages/ChatCapturePanel.tsx；frontend/e2e/chatCapture.spec.ts；隔离测试输出。
- 遗留与下一步：完成最终回归后核对队列空闲、成对备份及恢复演练，再发布迁移并显式绑定本会话授权起点；实测周期成功时间推进和重放零新增，确认业务事实未变，最后只读核验台账来源与页面同步。
- 同步状态：{"kind":"improvement","category":"stability","status":"investigating","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-003｜追加：混合记录第一版已在本地启用，限定当前聊天并完成发布核验

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：第一版混合记录已实现、完成隔离验证并在当前本地实例及既有穿透域名生效；保留待核实与近实时边界，不宣称零遗漏。
- 关联记录：PI-20261107-003；前条受理与实现进展；PI-20261107-002 的 HTTP 修复保持生效。
- 现象或目标：按用户授权实际实施聊天自动受理与结构化事实双通路，不再依靠结束前人工补记作为唯一入口，也不要求每条问题二次确认。
- 原因或分析：本机已验证 app-server 摘要分页可读取当前线程、稳定消息标识、时间及精确工作目录，无须扫描内部缓存或其他会话；未验证即时订阅，采用每轮结束等待 30 秒的 monitor 与页面 5 秒刷新。当前授权只包括本聊天本次选择实施之后；不含旧历史、新建聊天、其他项目或全账号。自动读取连续不代表复杂语义、图片或多问题拆分百分之百识别。
- 处理与改进：schema 47 保存显式绑定、脱敏来源及可逆关联审计。疑似故障自动建待核实，其余消息保留收件箱；初始代码未修改、验证未运行、部署未知，助手保证不升级验收结论。授权范围内有界分页重读、唯一键重放去重、消息更正追加；来源、正式记录和成功检查事实同一事务，失败整体回滚。读取全轮截止约 20 秒，分片/半行响应也可超时，超过分页/载荷限制或协议不符明确失败。暂停版本栅栏阻止在途提交；重复 CLI 在读取前拒绝已暂停或扩大范围。HTTP 无新增绑定入口，管理员鉴权、版本冲突保留草稿，提供关联/解除/待核实建档、失败与过期可见。保留原 PI 台账同步与只读交付核验。
- 代码修改：新增 chat_capture 七个后端模块、47 版迁移、前端收件箱与协议、合成适配和浏览器夹具测试；更新 API/monitor 装配、迁移测试夹具、OpenAPI、项目规则及运行文档。最新源码 Ruff、mypy、契约和测试通过后发布；没有修改原私有配置、主密钥、预算、评审和投递业务事实。缺失的 ~/.codex/comment-standards.md 未创建或臆造规范，按本项目中文注释规范执行。
- 本地验证：最终实际执行 .venv/bin/ruff check backend/ocr_manager backend/tests、.venv/bin/mypy backend/ocr_manager（119 源码）、PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract、git diff --check 均通过。OCR_RESUME_PROBE_COMMAND="$PWD/.local-tools/node_modules/.bin/ocr" .venv/bin/pytest -q：673 passed；其中聊天隔离测试 26 项，覆盖自动受理、来源编辑/重放、隐私样本/引用、候选/附件空内容、撤权、关联审计、数据库回滚、旧版迁移失败回滚、鉴权、CLI 错误库/范围、分页与半行超时。npm --prefix frontend run lint、前端 119 项测试、tsc -b 和隔离构建 /tmp/ocr-chat-capture-dist 通过。默认 Playwright 57 passed、16 个独立通道用例明确跳过；独立 OCR_BROWSER_CHAT_CAPTURE=1：3 passed，OCR_BROWSER_HTTP_COMPAT=1：3 passed，OCR_BROWSER_REVIEW_RECOVERY=1：10 passed，均为隔离合成数据，未调用付费模型。保留 Starlette/httpx 弃用、501.52 kB 主包及颜色/隔离目录警告，不称零警告。
- 部署生效：核对唯一进程和 launchd 未加载、11 类队列均空，TERM 协调停止原 API 38629、Worker 38637、monitor 38638，无强杀或删锁。成对备份与原前端保存至 .local-data/backups/chat-capture47-20261107-115812，隔离恢复完整性、46→47 迁移及存量凭据解密全部 passed，再显式迁移业务库并发布测试产物。沿用原私有配置启动唯一 API 45189、Worker 45199、monitor 45200，健康 ok/running，schema 47、完整性 ok、外键错误 0，25 张评审/投递/配置业务表摘要与发布前一致，私有配置摘要未变。显式绑定当前聊天授权起点，首次实际扫描 1 条/新增 1 条，再次扫描 1 条/新增 0 条；monitor 自动成功时间由 03:58:44 UTC 推进到 04:02:14 UTC，证明不仅手动 CLI 可用。实际本地与既有 HTTP 域名 1280/320px 共四种页面均通过：绑定正常、收件箱可读、无页面异常或横向溢出、首页与发布产物摘要一致，浏览器所有业务写入被阻断。最初当前授权咨询被保守规则自动建为 #12 待核实，维护者核对为原事项后通过实际 API 将来源更正关联至 #11（本 PI），#12 仅以明确重复原因归档并保留 open/not_run/unknown 和完整历史，不冒称解决；之后再次只读页面验收通过。#381 仍为原 2 条补审批次，未触发新补审、通知、费用或预算变更。只确认本机及现有穿透入口，不代表其他环境。
- 排查与无效尝试：官方文档读取 403，仅依据已运行本机 CLI 协议和生成 schema 验证，不宣称官方长期兼容。首轮权限测试夹具误把会话对象作令牌已修正；OpenAPI 静态检查不支持成员插值，改为具名 ID 插值后通过而未放宽检查器。新增半行测试编辑时曾重复定义，Ruff 识别后去重并最终全量回归通过。真实只读浏览器首轮将原页面字体外链 GET 混记为业务写入失败，修正验收分类：继续阻断外部字体读取，非 GET/HEAD/OPTIONS 请求仍全部禁止，重跑四种页面通过；不是业务权限放宽。
- 关联文件或证据：docs/chat-capture.md；docs/chat-problem-capture-proposal.md；AGENTS.md；backend/ocr_manager/chat_capture_adapter.py；backend/ocr_manager/chat_capture_store.py；backend/ocr_manager/chat_capture.py；backend/tests/test_chat_capture.py；backend/tests/test_chat_capture_protocol.py；frontend/src/pages/ChatCapturePanel.tsx；frontend/src/test/chatCapture.test.tsx；frontend/e2e/chatCapture.spec.ts；受限备份目录 release-report.json、恢复演练、capture-activation-verification.json、automatic-monitor-cycle-verification.json、manual-link-verification.json、deployed-chat-browser-verification.json、final-facts-verification.json 及本机截图。
- 遗留与下一步：刷新“问题与改进”并展开聊天收件箱即可使用，不需额外开关；绑定仅当前会话，后续新聊天必须另行明确授权并绑定。没有附件 OCR、复杂语义拆分、全历史分段回填、即时推送或自动清除期限管理；摘要最多 800 字、已知模式脱敏不等于任意秘密都能识别。来源升级/删除、超出扫描上限、服务停止及语义歧义仍可能遗漏，页面健康状态和候选用于暴露风险，不能承诺实时零遗漏。原公网 HTTP 没有传输加密，本功能未改变该风险，管理推荐本机回环地址或受控 HTTPS。自动采集不取代受理先记、证据追加及最终只读核验；收尾实际核对本 PI 五条来源与页面，不强制覆盖人工事实。
- 同步状态：{"kind":"improvement","category":"stability","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261107-004｜补审第三批仍失败：核查预算保护与默认参数并修复

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：用户反馈已受理，正在排查，尚未确定根因或宣称修复。
- 关联记录：PI-20261107-002 的 HTTP 兼容及历史失败解释；此次用户反馈补审 #3 失败，截图展示预算 1000、实际 573、完成 0/5、child_not_usable。
- 现象或目标：核实新补审批次为何仍无法完成，定位预算保护、默认参数及执行链路，而非仅补充失败文案。
- 原因或分析：截图显示预算保护在低于账面上限时停止，但预算保护是否包含下一阶段预估、模型输出预留或其他错误，尚需 SQLite 和本机执行器证据核实，不把截图当作终端授权或未核实事实。
- 处理与改进：先只读核对任务、批次、受控诊断和运行器预算逻辑，使用隔离合成输入复现；不自动再次执行真实补审、不提高额度或重置批次计数。
- 代码修改：受理时未修改业务代码。
- 本地验证：尚未运行本轮复现或自动化验证。
- 部署生效：本轮修复尚未部署；保留现有服务与历史记录。
- 关联文件或证据：当前用户截图；backend/ocr_manager/review_recovery_worker.py；backend/ocr_manager/review_recovery_store.py；frontend/src/pages/ReviewRecoveryPanel.tsx。
- 遗留与下一步：核实根因、增加与风险相称的测试并修复，分别报告代码、本地验证与实际部署；失败原因及可能残留限制如实记录。
- 同步状态：{"kind":"problem","category":"stability","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-004｜追加：已核实预算前瞻根因，修复与隔离验证进行中

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：根因已定位，代码修改与隔离验证进行中，尚未发布业务实例。
- 关联记录：PI-20261107-004；PI-20261107-002 的历史 HTTP 故障与本次预算失败分开处理。
- 现象或目标：任务 #381 的第三批补审实际用量 573、完成 0/5，却在批准 1000 Token 之前停止；需要阻止明显不足的重复付费排队，并展示可核对原因。
- 原因或分析：SQLite 及对应受控 result.json 的 token_budget_reached 数值一致：已用 573 + 下一组预估 127524 = 128097，大于批准 1000。OCR 1.12.9 在派发正式审核之前比较“已用加下一组预估”，不是仅比较实际账面用量；该次不是排队域名异常或 30 秒超时。前端原来固定预填 1000/30，而默认任务累计批准上限 100000 且最多三批，当前三批均已占用，剩余累计批准额度 97000，连已观察的第一组门槛也容不下。不能据此判断原始初审 504 已修复。
- 处理与改进：新增 schema 48 独立安全数字证据和逐任务人工额度授权，保留旧批次 JSON、状态与批准记录。API 在排队事务内校验累计额度和已知启动门槛，Worker 在正式审核前拦截已验证执行器的明显低预算。历史导入仅核验固定实例路径、输入、覆盖和用量，默认 dry-run，apply 只追加独立数字证据。界面去除固定低默认值，要求显式填写本批预算，超时沿用源快照；额度保存与补审排队分离，版本冲突保留草稿并禁止盲目重试。
- 代码修改：本轮新增 recovery_budget.py、recovery_budget_import.py、RecoveryBudgetPanel.tsx 及隔离测试，修改补审契约、API、存储、结果投影与前端确认流程；仍在完善验证。未修改真实任务额度、模型或私有配置，未发起真实第四批。
- 本地验证：已实际完成第一轮 Ruff、mypy（121 源码）、OpenAPI 更新校验、全量 pytest 690 passed；前端 lint、123 项组件测试、tsc 和隔离构建通过。随后继续补充输入及源快照边界测试、调整预算必须显式填写，最终需重跑。首轮新增浏览器流程 10 passed、2 failed，定位为先前 HTTP 合成场景遗留排队批次被 FIFO 领取，并非预算接口失败；正在修正隔离夹具清理，不能把失败轮计为通过。原有主包体积和依赖弃用告警仍在。
- 部署生效：业务实例仍为 schema 47、原进程 API 45189/Worker 45199/monitor 45200；本轮代码尚未发布，不沿用旧版本已生效结论。未调用付费模型、重置历史、增加真实预算或发送通知。
- 关联文件或证据：backend/ocr_manager/recovery_budget.py；backend/ocr_manager/recovery_budget_import.py；backend/tests/test_recovery_budget.py；frontend/src/pages/RecoveryBudgetPanel.tsx；frontend/e2e/reviewRecovery.spec.ts；本轮实际本地命令输出及 OCR v1.12.9 上游 internal/agent/estimate.go、agent.go。
- 遗留与下一步：完成最终回归和浏览器验收，空闲检查、成对备份及迁移恢复演练后再发布；受控导入可验证的历史数字，检查真实实例只读页面。128097 仅是上次一组门槛，不是全部文件完成预算或推荐批准额度；系统不会自动抬额度或付费重跑，实际审核仍需管理员明确批准。
- 同步状态：{"kind":"problem","category":"stability","status":"investigating","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-004｜追加：预算根因修复已在本地发布，历史三批数字可见，未自动付费补审

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：代码修复与隔离验证完成，当前本地实例及既有 HTTP 域名已生效；真实任务 #381 仍保留原部分初审和三条失败历史，等待人工决定新预算，不宣称剩余审核已完成。
- 关联记录：PI-20261107-004 的受理与根因进展；PI-20261107-002 的 HTTP 兼容保持；PI-20261107-003 的限定会话混合记录保持。
- 现象或目标：不再让 1000 Token/30 秒的低默认值误导用户反复付费却零进展；将前瞻预算保护解释成可核对数值，保留预算安全与人工费用授权。
- 原因或分析：真实第三批为 573 + 127524 = 128097 > 1000；第二批为 584 + 187780 = 188364 > 1000；第一批为 550 + 127524 = 128074 > 1000。各次分组估算不同，证明门槛参考不是固定全批账单或完成保证。当前三批已用完默认上限，累计批准 3000/100000、余量 97000；原始单批快照不限 Token、超时上限 3600。原始初审模型 504 是否再次出现仍未验证，不能用本轮预算修复替代网络根因验收。
- 处理与改进：schema 48 独立追加预算证据与管理员逐任务授权，不改旧 JSON、状态或费用；API 写事务复核已用批次、累计批准和相同源快照门槛，原幂等键重放不重复占额度，源变化不继承旧门槛但历史仍累计。Worker 已验证 OCR 1.12.9 时在正式审核前拦截低于保守 21300 的预算。新预算失败优先为 budget_unconfirmed，旧 child_not_usable/stale 原样保留。页面公开数字算式，不透传 warnings；本批 Token 始终空白要求显式填写，超时沿用快照，最低参考不当推荐值。任务额度表单不预填增额，原因必填、版本冲突保留草稿且拒绝盲重放；只保存授权，不排队或调用模型。原单批快照上限与全部来源核验仍有效。
- 代码修改：新增 backend/ocr_manager/recovery_budget.py、recovery_budget_import.py、frontend/src/pages/RecoveryBudgetPanel.tsx、backend/tests/test_recovery_budget.py 和 docs/recovery-budget.md；同步修改 schema、补审资格/API/存储/契约、OCR 预检、结果安全投影、前端确认及历史、OpenAPI、迁移夹具、组件/浏览器测试与部署/操作说明。未修改真实私有配置或预算参数，未使用未提供的 ~/.codex/comment-standards.md 臆造规则。
- 本地验证：实际运行 .venv/bin/ruff check backend/ocr_manager backend/tests、.venv/bin/mypy backend/ocr_manager（121 源码）、PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract、git diff --check，均通过。OCR_RESUME_PROBE_COMMAND="$PWD/.local-tools/node_modules/.bin/ocr" .venv/bin/pytest -q：694 passed；预算隔离专项 .venv/bin/pytest -q backend/tests/test_recovery_budget.py：21 passed，覆盖精确算术与错误格式、累计额度、并发授权单赢家、只读权限、同键重放、旧来源隔离、原快照上限、迁移回滚、缺库拒绝、受控路径/SHA/用量/预算不一致拒绝、幂等导入旧行不变、执行前零正式模型调用。npm --prefix frontend run lint、npm --prefix frontend test（123 passed）、frontend 内 npx tsc -b、npx vite build --outDir /tmp/ocr-recovery-budget-dist 通过。独立合成 OCR_BROWSER_REVIEW_RECOVERY=1 的 npx playwright test e2e/reviewRecovery.spec.ts：12 passed，含 1280/320px 下旧算式、三批用尽、明确调整额度但不排队、重新显式填预算及合成完成、HTTP 响应丢失同键重放和真实只读权限。默认 npx playwright test：57 passed、18 个独立通道用例明确跳过；独立 HTTP 兼容 3 passed、聊天收件箱 3 passed。均为隔离合成服务，未调用真实模型或飞书。保留 Starlette/httpx 弃用、501.52 kB 主包、颜色及隔离输出目录警告，不宣称零警告。
- 部署生效：发布前复核原唯一进程及 launchd 未加载、11 类业务队列为零；按 API→Worker→monitor TERM 协调停止原 45189/45199/45200，无强杀或删除锁/WAL。成对数据库/原私有配置和旧前端备份至 .local-data/backups/recovery-budget48-20261107-204134，隔离恢复完整性、47→48 迁移、既有加密凭据解密演练均 passed 后显式迁移业务库，发布已测隔离产物，沿用原配置启动唯一 API 72707、Worker 72718、monitor 72719。健康 ok/running，schema 48、完整性 ok、外键错误 0，25 张评审/投递/配置业务表摘要与发布前一致，私有配置摘要不变。真实历史导入先 dry-run：scanned 3/eligible 3；apply 仅插入独立证据 3，重放 inserted 0/unchanged 3/skipped 0；旧业务表再次逐表摘要一致。真实授权表仍为 0 条，#381 补审仍为 3 条，未产生第四批或新通知。发布后实际本机/既有 HTTP 域名各 1280/320px 四种只读浏览器检查全部通过：历史三批算式可见，3/3 及 3000/100000 正确，调整入口可打开，表单维持 3/100000、原因为空、保存禁用，未执行保存，无异常/横向溢出；所有非读取请求被阻断且实际零写入尝试，服务首页摘要匹配测试产物 7580e5252c063af49bdc74272eb7ede2e1a3b2041a2315e382c8c6e7b2b626ca。只确认本机与现有穿透入口，不代表其他环境。
- 混合记录核对：monitor 重启后限定绑定 #1 保持启用且最近成功时间推进、错误码为空。核对已授权用户来源 #841 的摘要确为本次“补审还是失败”反馈，自动待核实 #13 与人工 PI 页面 #14 属同一事项；通过真实 API 按版本将来源更正关联至 #14（来源版本 3），#13 仅以重复原因归档且保留 open/not_run/unknown、完整受理历史，不冒称已解决。未读取或绑定其他聊天，也未扩大历史范围。最终仍须运行只读 improvement_log_check 核对本 PI 三条来源及页面，不强制覆盖网页事实。
- 排查与无效尝试：首轮专项发现测试替身错误引用不存在的 read_ocr_version，改为真实版本解析路径的本地合成 stdout；旧状态兼容测试补足区分新 budget_unconfirmed 与旧 child_not_usable，保留历史而非放宽业务约束。首轮新增预算浏览器 2 例失败是 HTTP 用例留下排队任务导致 FIFO 领取错误，改为结束该合成批次后重跑 12 项通过，未改 FIFO 或允许跳过真实队列。文档补丁曾因旧整行匹配失败未写入，核实后重新应用；不存在部分文档发布冒充成功。
- 关联文件或证据：docs/recovery-budget.md；backend/tests/test_recovery_budget.py；frontend/src/pages/RecoveryBudgetPanel.tsx；frontend/e2e/reviewRecovery.spec.ts；受限发布备份内 release-report.json、恢复演练、facts-before.json/facts-after.json、final-budget-facts-verification.json、manual-source-link-verification.json、deployed-budget-browser-verification.json 及本机截图；本轮实际测试命令输出。
- 遗留与下一步：刷新 #381 页面即可查看。当前继续审核按钮因真实额度已用尽而保持禁用，这是预算与历史约束，不是功能开关；管理员可按自己的费用边界调整本任务批次/累计额度，再单独填本批预算排队，原快照和配置限制仍检查。128097 仅上次第一组最低参考，不保证本次计划、后续组或全部五个文件完成，不建议机械只填门槛等值。没有默认无限预算、自动付费重试、清零失败或自动提升结论。原初审 504 与真实补审最终完成情况均保留待后续实际执行验证；HTTP 公网入口仍缺少传输加密，推荐回环或受控 HTTPS，混合采集仍不能承诺语义零遗漏。
- 同步状态：{"kind":"problem","category":"stability","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261107-005｜额度调整弹窗样式错乱：受理并核查布局

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：新界面问题已受理，正在排查，尚未修复或发布。
- 关联记录：PI-20261107-004 新增单任务预算授权入口；本事项独立登记，不覆盖原预算根因及验收历史。
- 现象或目标：用户截图中“确认调整任务额度”弹窗标题和说明贴边，字段拥挤，调整原因文本框显示为浏览器默认样式，操作区缺少合理留白。
- 原因或分析：当前仅初步查看弹窗与样式定义，具体样式遗漏及影响范围需要在浏览器核实；截图不作为自动修改预算或执行付费补审的指令。
- 处理与改进：按现有设计统一弹窗内容间距、表单控件与操作区，增加桌面和窄屏视觉布局检查；不变更授权、额度、审核状态或付费命令。
- 代码修改：受理时未修改业务实现，仅追加本条问题记录。
- 本地验证：尚未运行本轮样式复现、组件测试或浏览器验证。
- 部署生效：本轮样式修复未部署，原服务和业务事实保持。
- 关联文件或证据：本次用户截图；frontend/src/pages/RecoveryBudgetPanel.tsx；frontend/src/ui/Modal.tsx；frontend/src/styles.css。
- 遗留与下一步：复现并修复后实际渲染核对，发布静态资源并分别报告代码、验证、部署，最后只读核验本 PI 的台账同步。
- 同步状态：{"kind":"problem","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-005｜追加：额度弹窗布局已修复并发布静态资源，桌面与短屏验收通过

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：本次弹窗样式问题已修复、完成隔离与实际入口检查；仅本独立界面事项标记解决，不代表 PI-20261107-004 的真实剩余审核已完成。
- 关联记录：PI-20261107-005 受理记录；PI-20261107-004 的预算授权行为与历史记录保持，不因样式修复改变业务结论。
- 现象或目标：修复“确认调整任务额度”标题贴边、输入项拥挤、原因框使用浏览器默认尺寸/字体、按钮缺少留白的问题，并避免只检查无横向溢出而漏检排版。
- 原因或分析：新增弹窗仅使用基础 Modal，未接专用标题、内容和表单布局；基础 Modal 本来不负责给任意业务内容统一内边距，textarea 也没有全局统一样式。发布前在真实本机只读复现：标题左内距 0，原因框宽 182px、标签 inline，原因框 monospace 而输入框使用现有站点字体。不是浏览器缓存、域名或预算接口异常；上轮浏览器断言仅验证溢出及业务操作，没有覆盖必要布局属性。
- 处理与改进：复用现有 modal-heading，新增局部 recovery-budget-modal/body/fields/reason 样式，标题与内容分区，桌面数值字段两列、小屏单列，原因框全宽、继承站点字体、最小高度 112px，底部按钮区独立留白。受限高度只让中部内容滚动，标题及取消/保存操作保持可见；CSS 限定本弹窗，不改变全局 Modal 和其他业务表单。授权、版本冲突、草稿及排队逻辑不变。
- 代码修改：frontend/src/pages/RecoveryBudgetPanel.tsx；frontend/src/styles.css；frontend/e2e/reviewRecovery.spec.ts。增加真实几何断言：标题/输入内距、textarea 与标签等宽、最小高度、字体一致、标签 grid、底部内距、桌面同排/小屏换行；增加 320×480 短屏内部滚动及标题/两个按钮仍在视口内的检查和截图。另追加本 PI 台账，无后端业务改动。
- 本地验证：实际执行 npm --prefix frontend run lint、npm --prefix frontend test（123 passed），frontend 内 npx tsc -b 和 npx vite build --outDir /tmp/ocr-budget-style-dist 均通过。OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-budget-style-dist OCR_BROWSER_REVIEW_RECOVERY=1 PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npx playwright test e2e/reviewRecovery.spec.ts 最终 12 passed，覆盖布局、短屏、显式额度保存与后续排队、HTTP 幂等及只读权限，均为独立合成 SQLite 和结果替身，不调用真实模型。实际逐张查看 1280/320 和短屏弹窗截图，留白、输入和按钮布局正常；git diff --check 通过。未修改后端，本轮未重跑全量 pytest，不沿用前轮 694 项作为本轮执行结果。保留既有 501.52 kB 主包、隔离输出目录、颜色及 Starlette/httpx 弃用告警，不称零警告。
- 部署生效：本轮仅发布静态资源，无数据库迁移或服务重启；不干预在途审核。原前端和前后截图保存至 .local-data/backups/budget-dialog-style-20261107-205526，先复制内容哈希资源、保留旧资源，再原子替换 index.html，避免已打开页面的旧资源失效。发布窗口内 25 张评审/投递/配置表摘要前后一致，私有配置摘要不变；原 API/Worker/monitor 保持运行。服务首页摘要为 d6101a710d9911262c710b418b6bafbd95f530587f12e04dbe37bfdf052775cb，与已测构建一致。本机和既有 HTTP 域名各 1280/320px 四种实际浏览器均通过，桌面标题与字段内距 24px、原因框宽 602px；小屏内距 16px、原因框宽 256px；两者原因框高 112px、字体一致、底部内距 16px；附加 320×480 短屏检查通过。实际查看发布后的裁剪弹窗截图正常，无页面异常或横向溢出，所有非读取请求阻断、实际零额度/补审写入尝试。随后实例已有新的额度授权和活动补审 #4，检查仅打开/取消弹窗，未改其值、未创建或停止该批次，不把正在变化的业务状态固定成旧 3/3。
- 排查与无效尝试：首轮发布后只读脚本沿用上轮固定 3/3、3000/100000 的断言，因业务实例已产生新授权/第四批而未通过；不是样式或写入失败。去除旧业务常量，只检查当前值非空且不编辑、全部非读取请求继续阻断，保留严格布局/视口/资源一致性断言，四种入口重跑通过。未通过修改真实预算或中断任务来迎合测试。
- 混合记录核对：当前授权会话的本条“这个样式乱掉了”已被自动采集为待核实来源 #1587；核对精确摘要与本 PI 页面 #15 后，通过版本化 API 显式关联至 #15，来源版本 2，未扩大采集范围或改变代码/验证/部署事实。monitor 已同步受理条目，收尾继续运行本 PI 至少两条来源的只读核验，不强制覆盖网页事实。
- 关联文件或证据：frontend/src/pages/RecoveryBudgetPanel.tsx；frontend/src/styles.css；frontend/e2e/reviewRecovery.spec.ts；受限备份目录内 style-release-report.json、layout-before.json/png、budget-layout-1280.png、budget-layout-320.png、budget-layout-short-320.png、budget-dialog-1280.png、budget-dialog-320.png 和 deployed-style-browser-verification.json；本轮实际命令输出。
- 遗留与下一步：关闭旧弹窗并刷新页面即可加载新版；若浏览器仍显示旧已加载页面，可使用 macOS Command+Shift+R 强制刷新。无需重新部署后端或手动配置样式开关。本轮不推断活动补审最终结果，不表示原初审 HTTP 504 已修复；原 HTTP 传输安全风险仍在。
- 同步状态：{"kind":"problem","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261107-006｜整体主题对齐参考页面：已受理并排查样式

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：视觉改进；已受理，排查中。
- 关联记录：PI-20261107-005；保留此前额度弹窗布局，不改变预算或补审功能。
- 现象或目标：用户提供三张参考图，要求整体调整为浅灰背景、白色侧栏与卡片、亮蓝主色，仅修改颜色和样式，不影响现有功能。
- 原因或分析：参考图作为视觉依据，不执行图片中的业务操作；当前项目使用绿色主题，尚待逐项核对全局变量、硬编码颜色和状态色。
- 处理与改进：先登记事项，再检查主题与公共组件；优先统一设计变量，保留页面结构、路由、接口、权限、表单及交互逻辑。
- 代码修改：受理时未修改业务代码，仅追加本条记录。
- 本地验证：已检查工作区初始 git status，未发现已有改动；本轮自动化和浏览器验证尚未运行。~/.codex/comment-standards.md 不存在，遵守仓库中文注释规范，不臆造缺失规则。
- 部署生效：未部署本轮主题，未操作业务数据库、配置或服务进程。
- 关联文件或证据：本次三张用户参考图；frontend/src/styles.css；docs/governance/frontend-code-standards.md。
- 遗留与下一步：完成主题调整后运行前端检查及桌面、窄屏浏览器回归，分别记录代码、验证、部署与 monitor 同步结果。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-006｜追加：全局灰白蓝主题已修改，功能与视觉回归进行中

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：视觉改进；代码已修改，浏览器验证中。
- 关联记录：PI-20261107-006 的受理记录；保留 PI-20261107-005 的额度弹窗结构与短屏规则。
- 现象或目标：参考图的蓝色操作、浅蓝选中态、白色侧栏和卡片、浅灰背景应覆盖全部页面，同时保留状态区分和原有交互。
- 原因或分析：旧 CSS 包含 208 种颜色，单改根变量不能覆盖硬编码的侧栏、链接、表格、表单、图表与业务面板。原成功、警告、失败语义仍有必要，不将全部状态统一成蓝色。
- 处理与改进：将主题色、辅助文字、边框、阴影和状态色收敛到根变量，取消局部绿色渐变；主按钮和焦点使用 #1677ff、选中背景 #e6f4ff、页面 #f5f5f5。已完成为蓝色，已启用/成功为绿色，警告为黄色，失败为红色；不改状态文本或业务判定。
- 代码修改：仅修改 frontend/src/styles.css 并新增 frontend/e2e/theme.spec.ts；未修改 React 业务组件、路由、接口、权限、预算、重试或后端代码。
- 本地验证：实际运行 npm --prefix frontend run lint、npm --prefix frontend test（123 passed）、frontend 内 npx tsc -b、npx vite build --outDir /tmp/ocr-blue-theme-dist 和 git diff --check，通过。首轮主题浏览器 1 passed、3 failed：桌面错误假设合成夹具有已完成任务，小屏错误断言透明表格外框而非白色行卡片；已调整为检查真实筛选值、现有行卡片，状态色另用隔离 DOM 验证，未修改业务数据或响应式规则迎合测试。全量浏览器回归正在运行，尚不宣称最终通过。
- 部署生效：未部署；构建在隔离临时目录，不覆盖正在使用的 frontend/dist，不重启 API/Worker/monitor。
- 关联文件或证据：frontend/src/styles.css；frontend/e2e/theme.spec.ts；浏览器桌面运行概览截图及实际命令输出。受理记录只读 improvement_log_check 已通过（1 条、页面 #16）。
- 遗留与下一步：完成修正后的主题和全量浏览器回归、额度弹窗专项及截图核对，追加最终结果并只读核验 monitor 至少三条同步；原有构建包体积和测试依赖警告不冒称消除。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-006｜追加：灰白蓝主题回归通过，未部署业务实例

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：视觉改进；阶段完成，代码和隔离验证已完成。
- 关联记录：PI-20261107-006 的受理与回归记录；不改变 PI-20261107-005 的额度弹窗功能。
- 现象或目标：让全局页面接近参考图的浅灰画布、白色侧栏/卡片、亮蓝主操作和浅蓝选中态，同时保持成功、警告、失败等业务状态可区分。
- 原因或分析：全局 CSS 原有绿色主题与大量局部硬编码颜色；已将其统一到设计变量，主色使用蓝色，状态色保持独立语义。未修改业务组件、路由、API、权限或持久化逻辑。
- 处理与改进：更新 frontend/src/styles.css 的颜色、边框、阴影、焦点环、侧栏、按钮、下拉、表格、图表、提示、弹窗和响应式导航；新增 frontend/e2e/theme.spec.ts 覆盖桌面/390px/320px、主题变量、下拉、表单弹窗、状态色、窄屏无溢出及只读请求约束。
- 代码修改：已修改 frontend/src/styles.css；已新增 frontend/e2e/theme.spec.ts；未修改 React 业务逻辑和后端代码。文档已追加本事项三段事实记录。
- 本地验证：实际运行 npm --prefix frontend run lint（通过）、npm --prefix frontend test（26 个文件、123 passed）、frontend 内 npx tsc -b（通过）、npx vite build --outDir /tmp/ocr-blue-theme-dist（通过，保留主包约 501.52 kB 和 outDir/依赖弃用警告）、git diff --check（通过）。实际运行 OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-blue-theme-dist PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npx playwright test：61 passed、18 skipped；其中新增主题用例 4 passed，既有功能用例保持通过。已查看桌面概览、项目配置和 320px 导航/弹窗截图；未提交表单或调用外部模型/飞书。
- 部署生效：未部署本轮主题；构建产物留在 /tmp/ocr-blue-theme-dist，未覆盖 frontend/dist，未重启 API、Worker 或 monitor，生产页面未宣称已生效。
- 关联文件或证据：frontend/src/styles.css；frontend/e2e/theme.spec.ts；/tmp/ocr-blue-theme-dist；frontend/test-results/theme-overview-desktop.png；frontend/test-results/theme-repositories-1440.png；frontend/test-results/theme-navigation-320.png；frontend/test-results/theme-repository-modal-320.png；本轮实际命令输出。
- 遗留与下一步：如需线上/本机实例生效，应按部署说明备份静态资源、原子替换并实际浏览器核验；当前无需改数据库或业务配置。保留原有主包体积与警告，不冒称零警告或已部署。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-006｜追加：主题专项重跑及台账同步核验完成

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：视觉改进；实现与验证完成，部署未执行。
- 关联记录：PI-20261107-006 的受理及全局主题回归；无功能行为变更。
- 现象或目标：确认最终主题验收断言在修改后代码上通过，并完成本轮来源与页面核对。
- 原因或分析：全量浏览器套件运行 61 passed、18 skipped 后，对导航抽屉最终变换断言做了精确检查，使用最终代码再次独立执行主题专项。
- 处理与改进：CSS 最终只有根主题变量中保留 24 个设计色值；主题专项再次通过 4 项（1440/390/320px 与状态色/页面覆盖）。所有写入断言为空。
- 代码修改：无新增代码修改；沿用 frontend/src/styles.css 与 frontend/e2e/theme.spec.ts。
- 本地验证：已实际执行 OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-blue-theme-dist PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npx playwright test e2e/theme.spec.ts，4 passed；git diff --check 通过。台账已追加第 4 段后，再次运行指定 improvement_log_check，待独立 monitor 同步后最终核验。
- 部署生效：未部署，未操作业务实例或生产静态目录。
- 关联文件或证据：frontend/e2e/theme.spec.ts；frontend/src/styles.css；/tmp/ocr-blue-theme-dist；本轮测试输出。
- 遗留与下一步：如要求页面立即生效，后续按部署流程发布静态产物；不需要改变 API 或 SQLite。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-006｜追加：额度弹窗及补审交互专项通过，最终同步核验

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：视觉改进；本轮实现和本地验证结束，未部署。
- 关联记录：PI-20261107-006；关联 PI-20261107-005 的短屏弹窗布局回归，不修改其历史结论。
- 现象或目标：全局换色后，额度确认弹窗的间距、输入、滚动和操作区仍正常，原补审/预算交互不受影响。
- 原因或分析：默认浏览器套件明确跳过独立补审通道，因此另外启用隔离合成夹具验证；此前“24 个设计色值”统计口径补充：实际有 24 个六位色值加白色 #fff，共 25 个颜色字面量，全部仅在根变量内定义，不代表只改了 24 处。
- 处理与改进：完成最终主题专项和额度专项；截图保存至忽略目录 .local-data/visual-checks/blue-theme，供本机查看，不写入敏感配置或真实业务数据。
- 代码修改：仍仅 frontend/src/styles.css、新增 frontend/e2e/theme.spec.ts 与追加本台账；没有新增业务改动。
- 本地验证：实际再次运行 npm --prefix frontend run lint，通过；frontend 内 OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-blue-theme-dist OCR_BROWSER_REVIEW_RECOVERY=1 PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npx playwright test e2e/reviewRecovery.spec.ts：12 passed，包含 1280/320px 预算弹窗几何、320×480 短屏滚动和可见操作、明确授权后单独排队、幂等及只读权限。实际查看 320×480 弹窗截图，标题、原因框与按钮布局正常。全部使用临时 SQLite、合成审核器和响应，不调用真实模型或飞书。git diff --check 通过。
- 部署生效：未部署；未覆盖当前 frontend/dist、未重启服务、未修改业务预算或任务。不得将隔离补审测试当成真实补审完成。
- 关联文件或证据：frontend/e2e/reviewRecovery.spec.ts；frontend/e2e/theme.spec.ts；frontend/src/styles.css；.local-data/visual-checks/blue-theme；实际命令输出。
- 遗留与下一步：代码与本地验收已完成，若需运行实例生效，单独按部署说明发布静态资源并核验。当前第 4 段台账已通过只读核验，追加本段后等待独立 monitor，再以 minimum-entries 5 最终核验；不扩大聊天授权范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-006｜追加：用户授权发布灰白蓝主题，部署准备中

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：同一视觉改进继续；已获用户明确授权发布至运行实例，部署准备中。
- 关联记录：PI-20261107-006 的主题实现与隔离验证；保留此前未部署结论，不覆盖历史。
- 现象或目标：将已经本地验证的灰白蓝主题发布到当前运行实例，并实际查看效果。
- 原因或分析：上一轮仅生成隔离静态产物，运行实例仍使用旧 frontend/dist；本轮只需发布静态文件，不需要数据库迁移或进程重启。
- 处理与改进：核对运行实例、产物与现有静态资源；计划先备份旧资源，再复制哈希资源、原子替换首页，保留旧文件供已打开页面使用，最后通过只读浏览器检查桌面、窄屏及弹窗。
- 代码修改：本轮受理时没有新增业务或样式改动，仅追加发布进展，保留上一轮三个工作区文件。
- 本地验证：已核对 git status 与隔离产物存在；本轮运行实例与发布后浏览器验证尚未执行，不沿用前轮通过结果作为部署证据。
- 部署生效：尚未部署；当前服务、业务配置及数据保持。
- 关联文件或证据：本轮用户发布授权；frontend/src/styles.css；frontend/dist；/tmp/ocr-blue-theme-dist；docs/deployment.md。
- 遗留与下一步：完成备份、静态发布和实际入口核验，追加最终事实并执行本 PI 至少七条来源的只读同步核验。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-006｜追加：灰白蓝主题已发布至运行实例，实际入口核验通过

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：同一视觉改进完成静态发布，本机及既有访问入口生效已确认。
- 关联记录：PI-20261107-006 的主题实现、隔离验证与本轮用户发布授权；PI-20261107-005 的额度弹窗布局保持。
- 现象或目标：将用户确认的灰白蓝主题发布到当前运行实例，并查看真实页面效果，不影响业务功能与在途任务。
- 原因或分析：运行服务从 frontend/dist 实时提供静态资源，仅替换静态文件即可生效，无需后端重启或数据库迁移。
- 处理与改进：重新生成干净构建并逐文件与上一轮已测产物比对一致（29 文件）；先备份原静态目录，保留旧哈希资源，再复制新资源并原子替换首页。发布脚本只读核对业务表及配置摘要，不执行业务写入。
- 代码修改：本轮无新增业务或样式代码；沿用 frontend/src/styles.css 与 frontend/e2e/theme.spec.ts，仅追加台账。静态发布脚本和只读浏览器脚本保留在 /tmp，证据与回退备份保存在受限备份目录。
- 本地验证：实际运行 frontend 内 npx tsc -b、npx vite build --outDir /tmp/ocr-blue-theme-release-20261107 --emptyOutDir，通过；新构建与已测产物逐文件一致。实际运行 .venv/bin/python /tmp/ocr-blue-theme-publish.py，通过，首页及引用资源与构建逐字节一致。实际运行 node /tmp/ocr-blue-theme-live-check.mjs，最终本机/既有 HTTP 入口各 1440px 与 320px 四种检查通过：灰白蓝主题、配置弹窗、设置页签、预算弹窗、窄屏导航及 Escape 焦点恢复、320×480 标题和操作可见，无横向溢出、页面异常或静态资源失败，零写入尝试。首次概览截图在数据加载时截取，补充等待指标和加载提示结束后完整重跑四种入口通过，并查看最终概览和短屏弹窗截图；未改业务响应迎合检查。保留既有 500 kB 主包警告，不称零警告。本轮未重跑全量组件和浏览器套件，上一轮测试仅作为已测产物依据。
- 部署生效：2026-11-07 21:31（北京时间）发布到本机 8781 运行实例，既有 HTTP 入口同版确认。首页 SHA-256 为 3f2fc8eff742ba51fd7fc642db4ca09259fd8811c7ff28c20f8ca5aa8bddc685；发布前后 25 张业务表摘要一致，私有配置摘要未变；API 72707、Worker 72718、monitor 72719 进程保持，未重启。健康 status=ok、worker=running。没有数据库迁移、真实预算调整、付费补审或通知发送。
- 关联文件或证据：.local-data/backups/blue-theme-20261107-213110/frontend-dist-before；同目录 release-report.json、facts-before.json、facts-after.json、browser-verification.json、overview-localhost-1440.png、budget-short-localhost.png；/tmp/ocr-blue-theme-release-20261107；本轮命令输出。
- 遗留与下一步：已打开旧页需刷新加载新版，必要时 Command+Shift+R；旧静态资源保留供旧页面使用。仅确认本机与既有入口，不推断其他环境；原 HTTP 入口未加密的风险保持，优先本机回环或受控 HTTPS。本轮追加后执行本 PI 至少七条来源的只读同步核验，不扫描或绑定其他聊天。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}
