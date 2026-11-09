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

### PI-20261107-007｜Ant Design 全量组件迁移影响评估：已受理

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：独立架构改进评估；已受理，范围分析中，未实施迁移。
- 关联记录：PI-20261107-006 的灰白蓝主题；本事项是组件库迁移评估，不混同已完成的颜色调整或部署。
- 现象或目标：用户希望先了解引入 Ant Design 并替换项目现有组件的改动规模、功能和样式风险，再讨论规划方案。
- 原因或分析：当前前端为 React 19、Vite、原生控件与自建 UI，Select 使用 Radix；完整替换涉及组件事件、受控值、表单、表格、弹窗与测试，不只是换主色。具体影响正在基于源码核对。
- 处理与改进：先盘点组件与页面、全局 CSS、状态和 URL 所有权、草稿与确认流程及自动化依赖；本轮只做影响评估，不安装依赖、不改代码或运行实例。
- 代码修改：尚未修改业务或样式代码，仅追加本记录；保留之前主题的既有工作区改动。
- 本地验证：已实际读取 package.json、UI 文件清单与原生控件文本匹配统计；这些是静态盘点，不是兼容性或迁移通过证据，本轮未运行迁移原型和自动化测试。
- 部署生效：不适用；未迁移、未发布、未重启服务。
- 关联文件或证据：本轮用户问题；frontend/package.json；frontend/src/ui；frontend/src/styles.css；frontend/src/pages；frontend/e2e。
- 遗留与下一步：完成实际源码核对后给出分层影响与估算边界，规划和实施由后续用户确认，不承诺零回归或未经验证的包体收益。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_applicable"}

### PI-20261107-007｜追加：Ant Design 迁移影响评估完成，未启动迁移

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：影响评估阶段完成；正式规划及实施范围待后续确认。
- 关联记录：PI-20261107-007 的受理；PI-20261107-006 的已部署灰白蓝主题不变，本轮不重复发布。
- 现象或目标：用户先了解全量组件替换的规模、收益与回归风险，再讨论规划，不把咨询自动扩展为实施。
- 原因或分析：源码中基础控件与业务控制流耦合程度不同；简单展示控件较低风险，表单草稿、同步确认改异步、URL 分页与当前页选择、移动端表格、Portal 焦点及全局 CSS 是主要影响面。纯 UI 迁移可保留后端和数据库，但不代表前端行为零风险。
- 处理与改进：新增 docs/ant-design-impact-assessment.md，记录静态盘点、风险分层、保留边界、版本/性能不确定性与估算口径。本项目全站通用 UI 替换评为中到偏大前端重构，保留领域封装、查询和 API；约 10～20 工程人日仅为熟悉项目单人条件下的讨论量级，不是排期承诺，需复杂页面原型后校准。未提交正式分期执行计划。
- 代码修改：无业务代码或样式修改，仅新增影响评估文档和本台账。当前 git 核对没有继承上一轮未提交主题文件，因此受理条目中“保留之前三个工作区文件”仅表示不撤回此前成果，不应解释为本轮实际发现三份未提交改动。
- 本地验证：实际运行 TypeScript AST 静态盘点（排除 src/test）：生产源码 96 文件、TSX 75、Page.tsx 入口 18；button 157/51文件、input 93/34文件、textarea 15/6文件、form 26/24文件、table 20/18文件、Modal 11/10文件、SelectField 42/23文件、Pagination 9/9文件；全局 CSS 931 行，window.confirm 声明 27 处，组件测试文件 26、浏览器文件 18。实际运行 npm view antd version peerDependencies engines dist.unpackedSize --json，registry 返回 6.7.0、React/ReactDOM >=18.0.0；仅核对声明，不证明兼容，不把包解压大小当首屏下载体积。git diff --check 和 Python 文档 UTF-8/章节/已跟踪修改仅文档检查通过。本轮未安装 antd、未执行组件原型、lint、构建或自动化功能测试，不声明迁移验证通过。
- 部署生效：不适用；本轮仅评估文档，没有安装依赖、修改运行实例、迁移数据或发布产物，保留当前已部署主题。
- 关联文件或证据：docs/ant-design-impact-assessment.md；frontend/package.json；frontend/src/ui/Modal.tsx、SelectField.tsx、Pagination.tsx、UnsavedChangesGuard.tsx、useConfigurationDraft.ts；frontend/src/pages/JobsPage.tsx、RecoveryBudgetPanel.tsx、SystemSettingsPage.tsx；frontend/src/styles.css；实际静态检查与 registry 输出。
- 遗留与下一步：与用户确认通用 UI 替换、Form 状态接管、原生确认替换及移动端/图标/图表范围后，再提出正式规划。当前待用户决策，不把评估完成当迁移已实现；只读核验本 PI 至少两条来源同步，不扩大聊天授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_applicable"}

### PI-20261107-008｜可配置多任务并发落地差距：已受理

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：架构改进评估；已受理，排查中，未授权实施或调高业务并发。
- 关联记录：本会话此前的第四阶段单协调器解耦及单 Worker 多执行槽建议；不引用其他事项的部署结论作为本期验收。
- 现象或目标：用户询问按单 Worker、可配置多个模型评审任务的建议落地，当前还缺少什么；需要基于最新源码及可核对运行事实回答。
- 原因或分析：此前方案保留模型任务并发 1；当前项目已经继续演进，须重新核对调度器、执行槽、队列及新增补审预算，不直接沿用旧状态。
- 处理与改进：先登记事项；计划只读核对源码、当前本机安全运行投影与并发控制入口，列出必要改造和验证范围，不启动 OCR 或修改配置。
- 代码修改：尚未修改业务代码，仅追加本条受理记录；本轮初始 git status 无输出。
- 本地验证：已实际运行 git status --short、读取 AGENTS.md、docs/chat-capture.md、台账历史及工程规范；尚未执行功能测试、并发实验或模型请求，静态阅读不代表并发验收通过。
- 部署生效：未部署本轮功能，未重启进程、迁移数据库或调整并发；当前服务是否运行待只读核对。
- 关联文件或证据：backend/ocr_manager/worker_scheduler.py；backend/ocr_manager/scheduler_state.py；docs/review-performance-phase4.md；本会话用户问题。
- 遗留与下一步：完成最新差距评估后追加同编号结论；等待既有 monitor 同步，并运行 minimum-entries 2 的只读核验，不绑定或扩展聊天采集范围。
- 同步状态：{"kind":"improvement","category":"performance","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-008｜追加：并发落地差距已核对，待实施可配置模型执行池

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：架构评估阶段完成；后续实现待确认，不把建议当成已支持多任务评审。
- 关联记录：PI-20261107-008 的受理；本会话第四阶段与并发讨论。
- 现象或目标：明确当前能否直接启用多个 OCR 评审、可复用基础及必须补齐的控制和验证。
- 原因或分析：当前 WorkerScheduler 每槽 max_workers=1 且只有一个 future；worker_execution_slots 以 model/ingress/delivery 为唯一主键，监控返回 model_task_concurrency=1，页面只读。合并后任务存在本类别顺序保护，但预审、补审与初审之间没有多模型槽所需的统一仓库占用约束。失败子集补审和模型诊断也必须占同一总额度，不能扩线程池后绕过上限。已有独立 HOME、worktree、原子领取、工件/仓库锁和进程组栅栏可复用，真实 OCR 多任务兼容与供应商额度仍未验证。
- 处理与改进：建议保留单协调 Worker、SQLite 和现有独立通知/事件槽；新增独立调度配置及管理员版本化 API，默认 1、首批开放 1～2，热调高、调低排空不强杀；执行槽迁移为可唯一识别多模型单元。初审/预审/补审统一仓库互斥，模型诊断占总配额，公平游标集中维护；同任务补审不得并行合并覆盖或重复占批准预算。调度并发不应直接混入冻结评审内容配置摘要，单任务内部并发和预算继续按原快照执行。跨仓库先试点，同仓库多任务作为后续独立语义变更。
- 代码修改：无业务代码修改，只追加本事项两段台账；没有新增接口、迁移、设置控件或多模型执行池。
- 本地验证：实际只读核对 worker_scheduler.py、scheduler_state.py、storage.py 的 next_job、premerge.py 的 next_premerge、review_recovery_store.py 的 claim、review_recovery_worker.py、ocr.py 和 WorkerExecution.tsx。实际运行 .venv/bin/pytest -q backend/tests/test_worker_scheduler.py backend/tests/test_scheduler_queue.py：13 passed，保留一条 Starlette httpx 弃用提示，仅证明现有单模型槽基线，不是 N 槽验收；未跑全量和真实付费 OCR 多任务实验。实际通过回环 GET /api/health 与 /api/operations、SQLite mode=ro 查询得到当前事实；未打印凭据或完整业务内容。~/.codex/comment-standards.md 不存在。
- 部署生效：只读确认当前本机健康 status=ok、worker=running，schema 48，三个槽均 idle、心跳新鲜，模型任务上限 1；相比本会话较早的 stopped 状态已变化，但不推断何时或由谁启动。内部 OCR 并发配置缺省为 4，启用仓库为 2 个。可配置多任务并发未实现、未部署；未调整内部并发、模型参数、补审授权或任务，未重启任何服务。
- 关联文件或证据：上述源码和本轮命令输出；backend/ocr_manager/worker_scheduler.py:98；backend/ocr_manager/scheduler_state.py:13；backend/ocr_manager/scheduler_state.py:92；backend/ocr_manager/ocr.py:311。
- 遗留与下一步：完成配置/迁移/API/前端、统一领取与多任务恢复；隔离覆盖动态升降、同仓库互斥、三类评审公平、取消/删除/重审、补审预算和覆盖合并，随后经明确授权用受控小样本实测 OCR 两任务、供应商限流和资源影响。任务并发与内部并发乘积只是潜在压力，不等于精确 HTTP 请求数或费用。本轮没有核实供应商 RPM/TPM，不能承诺并发 2 的效果；本编号保持 planned，不宣称实现闭环。收尾等待独立 monitor 后按 minimum-entries 2 核验来源与页面，不强制同步或修改已同步历史。
- 同步状态：{"kind":"improvement","category":"performance","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-008｜追加：已授权实施单 Worker 的 1～10 任务并发

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：同一并发改进继续；已受理，实施中。
- 关联记录：PI-20261107-008 的差距评估；用户本轮明确要求首版允许自由设置 1～10，替代此前建议的 1～2，不覆盖历史建议。
- 现象或目标：保留单 Worker，管理员可调整模型任务总并发，默认 1；降低上限不强杀在途任务，同仓库串行，普通评审、预审、补审和模型检查统一受限。
- 原因或分析：现有单槽执行器、持久化结构及只读页面需要共同改造；上限 10 是设置范围，不是资源、供应商额度或吞吐保证。
- 处理与改进：先核对当前实现与工程约束，再实现配置、迁移、调度和管理入口，增加隔离自动化验证；不自动调高本机并发、不执行付费评审。
- 代码修改：受理时尚未修改业务代码，仅追加台账；已有台账工作区改动予以保留。
- 本地验证：已运行 git status --short 并读取项目约定及工程规范；本轮功能测试未运行。
- 部署生效：未部署，未重启服务或迁移运行数据库，运行上限未调整。
- 关联文件或证据：用户本轮授权；worker_scheduler.py、scheduler_state.py、WorkerExecution.tsx。
- 遗留与下一步：完成实现与隔离验证后追加事实记录，按本编号累计条数执行只读同步核验；不扩大聊天采集范围。
- 同步状态：{"kind":"improvement","category":"performance","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-008｜追加：1～10 模型任务池已实现，专项与后端全量验证推进

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：同一并发改进实施中，正在完成浏览器及最终验收。
- 关联记录：PI-20261107-008 的授权实施；用户指定的首版范围为 1～10，不沿用旧建议的 1～2 限制。
- 现象或目标：单 Worker 可调总容量，热升降不强杀，跨仓库并行且同仓库跨类型互斥，补审授权预算保持。
- 原因或分析：只扩线程会遗漏持久化身份、全局总配额、降低容量时高编号在途槽及业务取消后的实际退出窗口；本轮统一处理这些边界。
- 处理与改进：新增 schema 49、调度配置/变更记录及管理接口，增加独立模型槽和共享公平游标、领取事务的仓库占用检查、管理设置及已保存/已应用/执行中/排空展示；新增隔离验证和说明文档。调度容量不加入评审内容快照。
- 代码修改：已修改后端调度/队列、前端监控及测试/契约；未调整运行实例，已有历史台账保持不覆盖。
- 本地验证：实际专项 pytest（worker_concurrency、worker_scheduler、scheduler_queue、review_recovery、recovery_budget）65 passed；随后 .venv/bin/pytest -q 全量 708 passed、1 skipped，保留 Starlette/httpx 弃用提示。实际 npm --prefix frontend test -- --reporter=dot：130 passed；ruff check backend/ocr_manager backend/tests --fix、mypy backend/ocr_manager、前端 lint、tsc -b 通过；隔离 Vite 构建通过，仍有既有主包超过 500 kB 提示；已生成 OpenAPI，新契约只读校验及浏览器全量尚在完成中。
- 部署生效：未部署；未重启 API/Worker/monitor，未迁移 .local-data/local/app.db，未覆盖 frontend/dist，未调高本机容量或触发真实付费评审。上述并发 10 仅为临时库合成执行器验证，不是实际机器或模型配额承载确认。
- 关联文件或证据：scheduler_config.py、scheduler_api.py、worker_scheduler.py、scheduler_state.py；test_worker_concurrency.py、test_execution_fence.py；WorkerConcurrency.tsx；docs/worker-task-concurrency.md；实际命令输出。
- 遗留与下一步：完成桌面/320px 持久化和冲突浏览器验收、静态契约与最终差异检查；真实 OCR 并发和供应商限流/资源效果未经验证，不承诺倍数收益。完成后追加最终记录并按本编号累计条数只读核验同步。
- 同步状态：{"kind":"improvement","category":"performance","status":"verifying","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-008｜追加：1～10 可配置任务并发实现及隔离验收完成，运行实例未升级

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：本轮代码实现和本地验收完成；运行实例升级与真实 OCR 容量试点未执行。
- 关联记录：PI-20261107-008 的评估、用户授权和实施进展；首版配置范围依用户要求为 1～10。
- 现象或目标：管理员自行控制单 Worker 模型任务总容量，默认 1；跨仓库并行，同仓库跨初审/预审/补审/关联诊断互斥，模型诊断计入上限，通知和事件保留独立槽。
- 原因或分析：多槽需要独立持久化身份和代次、共享公平游标、领取事务仓库保护及降低容量的全局在途计数；仅扩线程或看业务终态会超领或提前释放仍在退出的任务。本轮通过临时库和受控命令验证这些边界，不把设置上限当作机器或供应商额度保证。
- 处理与改进：完成 schema 49 的旧槽证据保留及配置/变更历史、严格整数与版本冲突 API、热升降执行池、已保存/已应用/执行中/排空展示和 1～10 管理入口。调度容量不进入评审内容快照；补审批准路径/Token/批次不放宽，不自动补审或重试。增加迁移、权限、并发、恢复、进程组停止及任务取消隔离验证，更新 OpenAPI 和使用/部署文档。
- 代码修改：后端 scheduler_config.py、scheduler_api.py、scheduler_state.py、worker_scheduler.py、storage.py、premerge.py、review_recovery_store.py、api.py；前端新增 workerScheduler 服务及 WorkerConcurrency 组件，更新执行槽展示和监控入口；补充测试与旧版迁移夹具，不引入额外 Worker、队列服务器或依赖，不撤回已有用户改动。
- 本地验证：最终实际 .venv/bin/pytest -q：710 passed、1 skipped，保留 Starlette/httpx 弃用提示；.venv/bin/ruff check backend/ocr_manager backend/tests、.venv/bin/mypy backend/ocr_manager（123 文件）、PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract、git diff --check 均通过。实际 npm --prefix frontend run lint 和 npm --prefix frontend test -- --reporter=dot 通过（27 文件、131 测试）；frontend 内 npx tsc -b 与 npx vite build --outDir /tmp/ocr-concurrency-dist --emptyOutDir 通过，保留既有主包大于 500 kB 提示。使用 OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-concurrency-dist 及本机 Chrome 的默认 Playwright 套件 64 passed、18 skipped；另设 OCR_BROWSER_REVIEW_RECOVERY=1 跑 reviewRecovery.spec.ts：12 passed；最终单独重跑 workerConcurrency.spec.ts：5 passed，包含 1440/320px 保存/刷新、版本冲突草稿、十槽排空与无横向溢出，部分用例与默认套件重叠，不累加为独立通过总数。实际查看桌面设置及 320px 十槽截图。最初旧版迁移夹具/版本断言和同仓库互斥旧假设导致回归失败，已适配后完整重跑通过；新增十槽浏览器测试曾误用断言 matcher 导致两项失败，改为 Playwright 的 toContainText 后五项全部通过，没有改业务响应掩盖失败。
- 部署生效：未部署。实际只读 SQLite mode=ro 核对当前业务库仍为 schema 48；未重启 API/Worker/monitor，未迁移该库、覆盖 frontend/dist 或调高运行实例并发；构建和浏览器服务使用独立临时产物/数据库，没有真实付费 OCR 并发试点、真实补审授权调整或通知发送。代码/隔离验证完成不能替代本机生效。
- 关联文件或证据：docs/worker-task-concurrency.md、docs/configuration-guide.md、docs/deployment.md、docs/openapi.json；backend/tests/test_worker_concurrency.py、test_execution_fence.py；frontend/e2e/workerConcurrency.spec.ts；.local-data/visual-checks/worker-concurrency 下隔离截图；本轮实际命令输出。
- 遗留与下一步：首次使用前按说明备份并正常停止共享库进程，整体升级同版 API/Worker/monitor 和前端，保持默认 1 后核对已应用版本，再由管理员自行设置 1～10；旧代码不能直接打开新版库，回退须恢复备份并核对新增数据补偿。真实 OCR 多进程兼容性、本机内存/CPU/磁盘与供应商 RPM/TPM 未实测；首版无新增账户级限速器，建议逐步调高，不能承诺十路容量或提速倍数。前四段已通过只读同步核验，追加本段后等待独立 monitor，再执行 minimum-entries 5 核验，不强制同步或扩大聊天授权。
- 同步状态：{"kind":"improvement","category":"performance","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-008｜追加：已核对并发设置页面入口，澄清尚未发布

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：同一并发事项的入口咨询；已核对，说明实现与运行实例的区别。
- 关联记录：PI-20261107-008 的 1～10 配置实现；不另行扩展为独立设置页或发布授权。
- 现象或目标：用户询问在哪里设置 1～10、是否有具体页面；需要明确现有页面路径及为何当前访问可能看不到。
- 原因或分析：已实现的设置位于管理员“运行监控”页 /operations 的“模型任务并发设置”区块，不是新增独立导航菜单；此前实现与隔离验证已完成，但上一轮没有升级运行实例，不能把源码入口当作当前已可访问。
- 处理与改进：明确操作路径“左侧运行监控 → Worker 调度与执行槽下方 → 模型任务并发设置”，输入 1～10 并保存；同时说明首次需要整体升级同版前后端及 API/Worker/monitor，之后日常调整无需重启。当前咨询不自动触发发布、重启或并发调整。
- 代码修改：本轮没有新增业务代码，沿用已实现入口，仅追加本段；不改已同步记录。
- 本地验证：本轮实际运行 rg 核对 App.tsx 的 /operations 管理员路由、OperationsPage.tsx 的设置区块和 WorkerConcurrency.tsx 的组件入口；属于源码定位，未重跑功能测试或访问运行页面，不沿用上轮测试次数作为本轮新验收。
- 部署生效：本轮未发布、重启或迁移业务库，未调高并发；上一轮未部署事实保持，不声称当前运行页面已有该入口。
- 关联文件或证据：frontend/src/app/App.tsx；frontend/src/pages/OperationsPage.tsx:57；frontend/src/pages/WorkerConcurrency.tsx；本轮用户问题及实际源码匹配输出。
- 遗留与下一步：用户如需当前实例可操作，下一步执行备份及同版整体升级，而非仅刷新旧页面。首次只读核验因本段 resolved/not_run 组合不满足内容校验而暂不可用；确认本段尚未导入（已导入仍为五段）后改为 planned/not_run，表示实例升级待执行，不修改前五段已同步事实。本轮按累计六条重新核验，不强制同步或扩大聊天授权。
- 同步状态：{"kind":"improvement","category":"performance","status":"planned","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-008｜追加：已受理本机停旧启新操作指引

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：同一并发事项继续；正在核对本机启动与整体升级步骤。
- 关联记录：PI-20261107-008 的 schema 49 实现及尚未部署事实。
- 现象或目标：用户要求说明如何停止以前的服务、再启动新的本地服务；本轮是操作指引，不擅自执行停止、迁移或启动。
- 原因或分析：API、Worker、monitor 共用业务库，必须避免旧进程混写；既有私有配置和主密钥必须沿用，不能重建凭据或删除锁文件。
- 处理与改进：登记后核对已有启动脚本、部署文档和进程启动方式，准备仅针对当前项目的停止、备份、构建、同版启动和验证命令。
- 代码修改：未修改业务代码，仅追加台账。
- 本地验证：本轮受理时尚未执行停启、迁移或真实评审；拟只读核对命令入口，不把指引当成实际执行通过。
- 部署生效：未部署，本轮没有停止或启动服务。
- 关联文件或证据：用户本轮要求；docs/deployment.md；项目启动入口待核对。
- 遗留与下一步：给出可执行指引及避免误停其他项目的边界后追加结果，按本编号实际条数执行只读同步核验。
- 同步状态：{"kind":"improvement","category":"performance","status":"planned","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-008｜追加：本机停旧启新指引已核对，实际升级待用户执行

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：同一并发事项的本机操作指导完成；没有执行发布，仍待实例升级与容量试点。
- 关联记录：PI-20261107-008 的并发实现、页面入口说明及停启指引受理。
- 现象或目标：提供本机停止旧服务、成对备份、构建新前端、启动同版三进程及查看并发设置的具体步骤。
- 原因或分析：实际只读确认 8781 由本项目虚拟环境的 Uvicorn 监听，另有独立 Worker、monitor；三者工作目录均为当前项目，当前用户 launchctl list 未发现 ai.open-code-review 服务。不能用全局杀 Python 或重复启动 Worker 的方式切换。
- 处理与改进：指引按当前项目绝对路径和模块名匹配旧进程，发送 TERM 并等待退出，检查端口；沿用 .local-data/local/private.json 和原主密钥，使用现有 backup CLI 备份数据库与配置，再构建 frontend/dist；分别启动 API、Worker 和 monitor，API 先完成 schema 49 迁移与健康核对，再启动另外两个进程。保持默认并发 1，通过 /operations 的模型任务并发设置手动调整；明确同仓库仍串行、在途任务应先结束、旧代码不能直接打开新版库。
- 代码修改：本轮只追加台账，没有新增或修改业务代码、依赖、启动脚本或私有配置；保留上一轮并发实现工作区。
- 本地验证：实际运行 git status --short、读取部署与实施/采集文档、rg 核对启动入口、读取 backup.py 的备份及权限校验、worker.py/alerts.py 的启动和迁移入口；实际运行 launchctl list 的项目标签过滤、lsof -nP -iTCP:8781 -sTCP:LISTEN、限定模块的 ps 检查，以及 lsof -a -p 72707,72718,72719 -d cwd -Fn，确认当前进程归属。实际运行 PYTHONPATH=backend .venv/bin/python -m ocr_manager.improvement_log_check --database .local-data/local/app.db --source-id PI-20261107-008 --minimum-entries 7 返回 passed=true，页面 18、版本 7；本段追加后需按累计八条再次核验。没有实际执行所提供的停止、备份、构建、迁移、启动或健康验收命令，没有重跑功能测试，静态核对不是升级成功。
- 部署生效：未部署；本轮没有停止或重启任何服务，没有迁移业务数据库、覆盖现有 frontend/dist 或调整任务并发，没有触发真实 OCR 和飞书通知。
- 关联文件或证据：docs/deployment.md；backend/ocr_manager/backup.py、config.py、worker.py、alerts.py、asgi.py；实际进程只读输出及本轮同步核验结果。
- 遗留与下一步：由用户依次执行指引；任一步失败不得继续启动后续进程，旧进程未退出时不删除锁、不强杀替代排查。数据库及配置快照不是运行工件全量备份，保留原工件；回退须停服恢复配对备份和对应旧代码，不能降低数据库版本号。等待正常 monitor 周期后执行 minimum-entries 8 只读核验，不强制同步或扩大聊天采集授权；真实容量仍建议从 2 起逐步观察。
- 同步状态：{"kind":"improvement","category":"performance","status":"planned","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-009｜本机停止服务命令执行反馈：已受理

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：操作问题；已受理，排查中。
- 关联记录：PI-20261107-008 的停旧启新操作指引。
- 现象或目标：用户反馈执行指引时报错，截图显示终端中的多行停止命令，未见明确错误正文；需要核对命令解析与当前进程状态，避免重复停启。
- 原因或分析：尚未确认是粘贴编辑状态、命令执行错误还是无匹配进程后的非零退出；不能仅凭截图认定根因。
- 处理与改进：先登记，随后只读检查相关服务并在隔离 shell 核对命令；不执行实际停止、启动、迁移或模型请求。
- 代码修改：仅追加本条台账，没有修改业务代码或私有配置。
- 本地验证：受理时尚未运行本轮诊断，截图本身不作为执行成功或失败证据。
- 部署生效：未部署，本轮没有停止或启动服务。
- 关联文件或证据：本轮用户截图；上一轮停服务命令。
- 遗留与下一步：核对后给出针对性处理步骤；追加结果并以本编号至少两条运行只读同步核验，monitor 已停止时明确未同步，不擅自恢复服务或扩大采集范围。
- 同步状态：{"kind":"problem","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-009｜追加：当前旧服务已无运行迹象，说明无匹配退出码与后续步骤

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：只读核对完成；未见实际错误正文，停止后的当前状态已核对，升级仍待执行。
- 关联记录：PI-20261107-009 的受理；PI-20261107-008 的停旧启新指引。
- 现象或目标：解释用户截图与终端错误提示的区别，判断是否需要重复停止旧服务。
- 原因或分析：截图只有命令，没有明确异常正文，不能证明具体报错原因。本轮限定当前项目解释器及模块检查未找到 API、Worker、monitor，8781 无监听；pgrep 和 lsof 无匹配时返回 1，不是 shell 语法错误，也不能据此认定停止失败。此前指引未解释这一预期非零状态，可能造成误解；无法仅凭本轮观测确认旧服务由哪条命令停止。
- 处理与改进：告知当前无需重复停止，继续按原指引先成对备份、再构建，成功后启动 API 并检查健康，最后启动 Worker 和 monitor；如终端仍处于多行编辑可先取消当前输入，如另有真实错误须补充错误正文。后续检查需区分无匹配与实际失败，不用全局杀进程或删除锁。
- 代码修改：仅追加两段台账，没有修改业务代码、私有配置或启动脚本。
- 本地验证：实际运行限定项目路径及模块的 ps/rg 检查、lsof -nP -iTCP:8781 -sTCP:LISTEN、launchctl list 的项目标签过滤，均无对应服务输出，lsof_exit=1；在 /bin/zsh -f 中实际执行原模式的变量赋值、pgrep 与数组赋值只读部分，无解析错误，匹配数量为 0、pgrep_exit=1。没有执行 kill、备份、构建、迁移、启动、真实 OCR 或功能测试；只读状态不是升级验收。
- 部署生效：本轮未部署、未停止或重启服务；当前旧进程未运行不等于新服务已启动，业务库升级情况未核对。
- 关联文件或证据：本轮用户截图、只读进程和端口检查、隔离 zsh 输出。
- 遗留与下一步：本轮追加时 monitor 同样不在运行，预计台账尚不能自动同步；收尾实际运行本编号 minimum-entries 2 的只读核验，按真实结果说明，不擅自启动 monitor 或强制同步。待用户完成同版启动后由原 monitor 正常同步；如有其他报错，依据正文继续同编号排查，不把推测当确定根因。
- 同步状态：{"kind":"problem","category":"experience","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-010｜运行监控页信息架构与布局重规划：已受理

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：体验改进规划；已受理，排查中，未授权实施业务页面改造。
- 关联记录：PI-20261107-008 的模型任务并发设置；以当前截图和源码为准，不推断运行实例的升级状态。
- 现象或目标：用户反馈运行监控页布局不友好，要求重新设计与规划；需兼顾当前运行、异常、执行槽、并发配置和历史性能信息的可发现性。
- 原因或分析：截图可见概览、异常和历史分组统计混排，说明文字较长、统计分组纵向展开；完整结构与数据口径尚待核对。
- 处理与改进：先登记，随后只读核对页面、组件、指标和既有设计规则，产出分层布局、交互和分阶段实施建议；不修改运行配置或发布前端。
- 代码修改：仅追加台账，尚未修改业务代码或样式。
- 本地验证：受理时仅查看用户截图，尚未运行本轮布局或功能验证。
- 部署生效：未部署，未停止或启动服务、迁移数据库或调整并发。
- 关联文件或证据：本轮用户截图；frontend/src/pages/OperationsPage.tsx 待核对。
- 遗留与下一步：完成方案后追加结论并执行本编号至少两条只读同步核验；如制作示意，明确样例数据不是业务事实，不将原型等同实现。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-010｜追加：四分区重设计方案与交互示意已完成，待确认实施

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：体验规划完成；业务页面尚未改造，实施待确认。
- 关联记录：PI-20261107-010 的受理；不将 PI-20261107-008 的并发实现测试当作本布局的验收。
- 现象或目标：解决实时运行与历史性能混排、并发设置被长报告推到下方、异常口径及状态数字难理解的问题。
- 原因或分析：实际源码先渲染全部 ReviewPerformance 再渲染 WorkerExecution/WorkerConcurrency；历史分组随数据增长拉长页面。排队/运行显示合计，重试/通知失败混合次数及记录数；monitoring.py 的全历史当前结论计数与近七天耗时同屏。历史失败触发通用异常，不足以证明服务当前故障。原 API 已返回 execution_jobs，前端尚未声明，实时原始执行与有效结论必须分开。
- 处理与改进：新增 docs/operations-redesign-plan.md，推荐同入口四标签“运行与并发、性能分析、告警与通知、维护与审计”；默认页提升并发控制和执行槽，集中已保存/已应用/在途/排空状态，历史统计改可比较表格，未知和样本量保真。固定近七天，不伪造日趋势或从分组分位数计算总体分位数；保留已有主题、权限、版本冲突、费用提示与危险操作确认。提供独立的可切换四标签示意，全部为样例且无业务 API 请求；不改变业务页面。
- 代码修改：新增规划文档与当前会话目录中的示意文件，仅追加本台账；没有修改业务源码、样式、私有配置或运行产物，未引入新组件库，保留既有工作区改动。
- 本地验证：实际读取 OperationsPage.tsx、ReviewPerformance.tsx、WorkerExecution.tsx、WorkerConcurrency.tsx、监控类型和查询服务、App.tsx、AlertsPanel.tsx、ReconciliationPanel.tsx、AuditLogPanel.tsx、monitoring.py、review_metrics.py 及现有主题/前端规范；实际 git diff --check 通过。实际使用 visualize/scripts/render.py 生成独立预览，Node 调用现有 @playwright/test 与本机 Chrome 检查 1440/1024/768/375/320px 的四标签切换、横向溢出及本地模拟保存，最终通过且 pageerror 为空；实际查看 1440/375px 截图。首次示意使用原生表单在预览沙箱未触发预期更新，改为显式按钮后重新生成；一次预览因未传 --force 未覆盖旧文件导致同一检查失败，最终覆盖并完整重跑通过。这些仅为示意自检，不是业务功能测试，未运行规划中的前端全量、后端或真实 OCR 验收。
- 部署生效：未部署；未覆盖 frontend/dist、重启 API/Worker/monitor、迁移数据库、调并发或触发模型/通知。未凭截图推断本机是否已升级并发功能。
- 关联文件或证据：docs/operations-redesign-plan.md；当前会话可视化目录 operations-redesign.html、operations-redesign-preview.html、operations-redesign-1440.png、operations-redesign-375.png；本轮静态阅读与浏览器检查输出。
- 遗留与下一步：用户确认后先做结构和发现性，再补交互/查询生命周期和回归；是否发布本机另行确认。当前项目 monitor 进程只读检查无匹配，收尾运行本编号 minimum-entries 2 核验，若未导入则明确未同步，不强制导入、不启动 monitor 或扩大采集范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-007｜追加：结合全站重设计重新核对 Ant Design 统一规范可行性

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：同一组件库评估继续；正在核对采用边界，尚未实施迁移。
- 关联记录：PI-20261107-007 既有影响评估；PI-20261107-010/011 的监控与全站重设计规划。
- 现象或目标：用户询问是否可用 Ant Design 开发重设计页面，并写入规则约束后续所有开发，以及会产生哪些影响。
- 原因或分析：需区分“统一通用组件”与“强制所有内容由组件库实现”，同时明确本项目规则不自动约束其他项目；不能把架构建议当依赖已安装或迁移已授权。
- 处理与改进：先记录，再核对已有评估、当前依赖和工程规范，给出推荐规则、风险及前置实施安排；不安装依赖、改页面或直接落地强制规则。
- 代码修改：仅追加本段台账，未修改 AGENTS.md、业务代码、依赖或私有配置。
- 本地验证：实际运行 git status --short，读取已有 Ant Design 评估、frontend/package.json 和 AGENTS.md；尚未执行本轮兼容验证或构建。
- 部署生效：未部署，未更新运行产物、重启服务或迁移数据库。
- 关联文件或证据：docs/ant-design-impact-assessment.md；frontend/package.json；docs/governance/frontend-code-standards.md 待进一步核对。
- 遗留与下一步：完成解释后追加同编号结论并按实际条数只读核验同步，不扩大采集范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-007｜追加：推荐 Ant Design 统一通用组件，采用规则和迁移边界已补充

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：可行性说明及规则建议完成；依赖安装、规则生效及页面迁移未执行。
- 关联记录：PI-20261107-007 前期影响评估与本轮追加受理；PI-20261107-010/011 已有布局规划。
- 现象或目标：说明组件库可用于重设计，并明确如何约束本仓库后续开发、优势、风险及与布局规划衔接。
- 原因或分析：统一组件可减少重复控件与交互分歧，但不能替代信息架构、移动端设计或业务状态。现有全局样式和同步确认需要适配；直接重写所有表单、异步确认和表格会叠加风险。此前全站规划明确不新增组件库，若正式采用必须同步修订，而不是隐式扩大实施范围。
- 处理与改进：在 docs/ant-design-impact-assessment.md 追加采用建议、拟写入 AGENTS/前端规范的七条规则，以及基础设施和风险试点前置安排；建议新增/重设计通用 UI 统一 Ant Design，允许业务封装、语义布局、图表和浏览器原生关闭确认例外。保留 API/路由/查询层和既有业务状态，存量分批迁移，不自动引入 ProComponents 或图表库，不强制所有复杂表单同时由 Form 接管。
- 代码修改：只修改评估文档及追加台账；未修改生效 AGENTS.md/前端规范、package.json/锁文件、页面、样式或私有配置，保留既有工作区改动。
- 本地验证：实际 npm view antd version peerDependencies engines --json 返回 6.7.0、React/ReactDOM >=18.0.0；声明包含当前 19.2，不等于运行兼容通过。实际读取当前依赖、前端规范、评估及全站规划，rg 核对全局元素样式，阅读 UnsavedChangesGuard.tsx 和 SelectField.tsx；未安装、运行功能测试、浏览器原型或构建，不沿用上轮测试次数为本轮验收。收尾实际运行 diff 检查和本编号累计四条只读同步核验，按命令结果报告。
- 部署生效：未部署，没有更新 frontend/dist、重启服务、迁移数据库、调并发或触发外部调用；组件库尚未安装，不称规则已生效。
- 关联文件或证据：docs/ant-design-impact-assessment.md 新增统一规范建议；frontend/package.json；docs/governance/frontend-code-standards.md；当前全局 CSS、草稿守卫和 SelectField；registry 实际输出。
- 遗留与下一步：如正式采用，先同步两份布局规划的组件库边界，再建立主题/上下文/样式隔离和代表性表单/表格/额度弹窗验证，用已确认运行监控作为首批页面，后续分批迁移；包体积、短屏窄屏与完整兼容仍待实测。规则仅约束此仓库，不自动作用于其他项目，也不能替代评审和验证。
- 同步状态：{"kind":"improvement","category":"experience","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-007｜追加：已获采用授权，实施前发现工作区基线变化待确认

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：用户已授权按建议落实；实施前暂停核对工作区变化，不宣称迁移已开始或完成。
- 关联记录：PI-20261107-007 的组件库评估与规则建议；PI-20261107-010/011 的页面重设计规划。
- 现象或目标：拟落实 Ant Design 规则、基础设施、风险交互验证和首批运行监控改版；初始工作区与上一轮可见状态存在变化。
- 原因或分析：本轮实际 git status --short 仅显示 docs/ant-design-impact-assessment.md 和 docs/problem-improvement-log.md 修改，而上一轮可见多份并发业务源码及规划等未提交变更。变化不是本轮处理者执行，尚未核对是否由用户提交或其他操作造成，不推断代码被删除或丢失；按执行约束暂停并请用户确认可使用当前基线。
- 处理与改进：说明已接受实施请求，但在确认基线前不安装依赖、不改业务或生效规则；只读取了当前入口和弹窗用于初始检查，没有执行后续迁移。
- 代码修改：仅追加本段台账；没有修改业务源码、AGENTS.md、依赖、锁文件或私有配置，没有撤回任何现有变更。
- 本地验证：实际运行 git status --short，读取台账末尾、App.tsx、main.tsx 和 Modal.tsx；未运行兼容测试、lint、单元测试、浏览器检查或构建。收尾按本编号累计五条执行只读同步核验，结果不代替基线确认或迁移验收。
- 部署生效：未部署，没有覆盖 frontend/dist、重启服务、迁移数据库或触发外部调用。
- 关联文件或证据：本轮 git status 输出与上轮可见工作区状态；用户本轮采用授权。
- 遗留与下一步：请用户确认这些业务变更是否已提交，以及是否以当前工作区作为实施基线；确认后继续已说明的基础接入和首批改版，不重复询问组件库选择。不强制台账同步或扩大聊天采集范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-010｜追加：用户确认运行监控四分区设计基线

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：设计方向已确认，业务页面待实施；同时扩展其他页面体验排查。
- 关联记录：PI-20261107-010 的规划与交互示意；全站排查另以 PI-20261107-011 跟踪。
- 现象或目标：用户明确运行监控页按照已提出方案设计，再检查其他页面并统一整理重设计规划。
- 原因或分析：运行监控四分区作为确定基线，不再重复选择视觉方向；跨页面问题需先核对，不据单页截图推断全部页面同样严重。
- 处理与改进：保留四分区、并发与执行槽前置、历史性能单列的方案，纳入全站分批实施顺序；本轮先做其他页面梳理，不把规划确认等同业务代码已改造。
- 代码修改：本段只记录确认，没有修改业务页面、接口或配置。
- 本地验证：尚未执行本轮功能验收；确认依据为本轮用户请求。
- 部署生效：未部署，不声称新布局已在本机生效。
- 关联文件或证据：docs/operations-redesign-plan.md；用户本轮确认。
- 遗留与下一步：完成全站清单与优先级后安排分批实施，收尾按本编号累计三条核验同步；不覆盖已同步历史。
- 同步状态：{"kind":"improvement","category":"experience","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-011｜全站页面体验排查与分批重设计：已受理

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：体验改进规划；已受理，排查中。
- 关联记录：PI-20261107-010 的运行监控四分区设计；不将此前灰白蓝主题或组件库评估当作本轮布局验收。
- 现象或目标：用户要求找出其他页面类似的信息堆叠、状态表达及操作入口问题，整理统一重设计规划。
- 原因或分析：尚未完成其他页面审查，须按实际路由、页面组件、状态与已有测试核对，区分已存在的良好模式与待改问题。
- 处理与改进：先登记，随后只读审查主要路由与页面、共用组件和交互检查依据，输出问题位置、优先级、页面目标结构、实施范围与验证计划；不批量改造业务或发布。
- 代码修改：仅追加台账，保留既有工作区改动，没有修改业务代码。
- 本地验证：受理前实际运行 git status --short、列出 frontend/src/pages 文件及阅读实施/规范采用说明；尚未运行页面功能或浏览器验收。
- 部署生效：未部署，没有停止或启动服务、迁移数据库、修改并发或发送外部请求。
- 关联文件或证据：本轮用户请求；frontend/src/app/App.tsx 和 frontend/src/pages 待进一步核对。
- 遗留与下一步：完成后追加方案结论；按本编号至少两条及关联编号实际条数分别核验同步，不扩大聊天采集授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-011｜追加：主要页面静态排查与全站分批重设计规划已整理

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：本轮排查和规划完成；业务页面改造、逐页视觉验收及发布尚未执行。
- 关联记录：PI-20261107-011 的受理；PI-20261107-010 已确认的运行监控四分区为设计基线。
- 现象或目标：系统整理其他页面的信息层级、状态表达和操作可发现性问题，避免只优化运行监控或全站盲目换肤。
- 原因或分析：源码确认事件补审表及历史在收件箱前、任务诊断与补审在发现前、首页效果区在最近评审前；系统设置审核规则混排编辑/反馈/预览/历史，优化主题按阶段完整铺开。任务列表、系统设置和问题侧栏已有 URL/折叠/草稿/窄屏机制，应保留而非重做。首次接入加载/失败仍计算缺省进度、Webhook 地址就绪不等于外部配置完成；账号模式和关联配置辅助查询缺失可显示为默认关闭或未配置，需要隔离复现后优先修正。未测量实际页面高度、用户效率或查询性能，不把源码风险冒充逐页浏览器缺陷。
- 处理与改进：新增 docs/whole-site-ux-redesign-plan.md，覆盖主要路由、页面级建议、P0/P1/P2 优先级、四种页面模板和四批实施/验收计划；用户已确认的运行监控独立方案补充基线确认与全站链接，文档索引增加两份规划。推荐先修状态事实与实施监控，再优化评审链路、配置/平台管理，最后全链路回归与单独确认发布；不绑定新组件库或底层架构重做。
- 代码修改：本轮仅新增/更新规划、文档索引与台账，没有修改业务源码、主题、依赖或配置；保留上一轮并发实现等现有工作区改动，没有执行页面批量改造。
- 本地验证：实际 git status --short；读取 App.tsx 主要路由、各主要页面及详情/配置/批量/草稿组件、交互回归文档与 Playwright 夹具/用例范围；实际 git diff --check 通过。实际运行 .venv/bin/python 的只读文档链接和源码渲染顺序核对脚本：两份规划各一处本地链接均存在，五处指定先后关系断言通过。一次 zsh 检索辅助命令因 echo 的等号展开失败，改为 printf 后成功读取，不涉及业务执行。回环 GET /api/health 实际返回 status=ok、worker=running；只作当前只读状态观测，不证明新布局部署。实际 PI-20261107-010 minimum-entries 3 同步核验通过（页面 20、版本 3）。未运行 lint、单元测试、构建或逐页浏览器验收；文中的这些命令均为待实施后的验证计划。
- 部署生效：未部署，没有覆盖 frontend/dist、迁移数据库、重启服务、调并发、触发真实评审或发送通知；本机运行中的旧/新业务版本没有作为本轮验收项核对。
- 关联文件或证据：docs/whole-site-ux-redesign-plan.md；docs/operations-redesign-plan.md；docs/README.md；实际静态阅读、只读结构核对与健康检查输出。
- 遗留与下一步：按分批计划补隔离视觉/交互基线并实施，P0 未复现前不宣称修复；完整保留权限、冻结输入、版本冲突、费用提示、三维交付及采集授权边界。最后等待正常 monitor 同步，再以本编号 minimum-entries 2 和关联编号累计三条分别只读核验，不强制导入或扩大聊天范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-007｜追加：用户确认当前基线，恢复 Ant Design 首批实施

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：已获实施与基线确认，实施中。
- 关联记录：PI-20261107-007 前次暂停；PI-20261107-010/011 的页面规划。
- 现象或目标：按已确认建议落实本仓库通用组件规范、基础接入及运行监控试点，不进行全站机械替换。
- 原因或分析：用户已明确可以使用当前工作区，保留两份既有文档修改；当前监控仍为所有模块纵向展开，配置轮询与草稿需隔离。
- 处理与改进：先接入统一主题/中文上下文及样式隔离，再拆四个 URL 视图、按需查询与性能表；使用隔离服务验证草稿、批量选择、预算确认和窄屏。
- 代码修改：本段仅登记恢复；业务、规则和依赖改造随后执行，未称完成。
- 本地验证：实际读取 git status、AGENTS、前端规范、实施流程、监控源码与已有测试；尚未运行本轮 lint、构建或交互回归。
- 部署生效：未部署，不覆盖 frontend/dist、不重启业务服务、不触发真实 OCR 或通知。
- 关联文件或证据：用户“可以”确认；docs/operations-redesign-plan.md；frontend/src/pages/OperationsPage.tsx。
- 遗留与下一步：完成首批实施后记录实际检查与未完成范围，按累计条数只读核验同步。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-010｜追加：四分区与运行口径改造已编码，进入隔离验收

- 记录日期：2026-11-07（北京时间）。
- 类型与进展：既定方案实施中，尚未完成验收或发布。
- 关联记录：PI-20261107-010 已确认基线；PI-20261107-007 的 Ant Design 接入。
- 现象或目标：运行状态与并发前置，性能比较改为分组表格，告警和维护按需访问。
- 原因或分析：初审原始执行状态与有效结论不同，不能混用；视图卸载会丢失本地草稿，全量保留且无 enabled 控制又持续发请求。
- 处理与改进：四个 URL 标签保留访问过的面板，隐藏停轮询；初审指标使用 execution_jobs、旧字段缺失显示未知；性能本地筛选和行详情；清理使用上下文二次确认，冻结保留天数；维护审计/对账折叠按需加载。告警编辑器移除配置变化重挂载，使用独立草稿。
- 代码修改：OperationsPage 拆分运行/维护与契约；并发控件、告警控件和性能表采用 Ant Design；保留已有 API、调度、权限和维护子模块业务逻辑。
- 本地验证：首次安装因本机 npm 缓存 EACCES 失败，使用 --cache /tmp/ocr-ant-design-npm-cache 安装 antd@6.7.0 成功，审计零漏洞；此前依赖未就绪的 tsc 失败后，重新 lint、tsc、27 文件 131 项测试及隔离 Vite 构建通过。新增分区测试和浏览器用例后仍待再次完整执行，不将前次通过覆盖后续未测代码。构建提示入口与监控分块超过 500 kB，需记录实测影响。
- 部署生效：未部署；隔离产物 /tmp/ocr-ant-design-dist，不覆盖运行实例、重启服务、迁移数据库或触发外部调用。
- 关联文件或证据：frontend/src/pages/operations；frontend/src/styles/operations.css；frontend/e2e/operations.spec.ts。
- 遗留与下一步：补齐新测试与旧页面回归，核对样式层、草稿、十槽、清理弹窗和包体积；同编号追加结果并核验同步。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-007｜追加：统一规则与 Ant Design 首批接入完成，本地验证通过、尚未发布

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：首批代码与本地验收完成；仍有存量分批迁移和本机发布，非全站迁移完成。
- 关联记录：PI-20261107-007 的采用授权/基线确认；PI-20261107-010 运行监控首批；PI-20261107-011 全站后续规划。
- 现象或目标：统一本仓库后续新增/重设计通用组件，先完成主题、中文与上下文、样式隔离和监控试点，保护现有高风险交互。
- 原因或分析：组件库会增加前端体积，旧全局元素样式与 ant-app 链接重置存在真实冲突；不能靠规则文档宣称兼容，也不能同时重写全部 Form、同步守卫和业务层。
- 处理与改进：锁定 antd@6.7.0；AGENTS 与前端规范写入采用/例外/渐进迁移规则，同步两份布局规划。统一 DesignProvider，App component=false 不重置存量链接，旧样式进 legacy 层并显式排除 Ant Design 基础控件；性能/告警/维护按分区加载。保留原生同步离开守卫、Radix 和有调用方的旧组件，不新增 Pro 或图表库。
- 代码修改：前端依赖/锁文件、应用上下文、样式、运行监控相关组件、测试和说明已修改；未修改后端、数据库结构、调度策略或私有配置。存量项目表单、批量表和补审额度弹窗本轮只兼容验证，不称已迁移。
- 本地验证：实际 npm --prefix frontend run lint、(cd frontend && npx tsc -b)、npm --prefix frontend test -- --reporter=dot 通过（28 文件、136 项）；(cd frontend && npx vite build --outDir /tmp/ocr-ant-design-dist --emptyOutDir) 通过。实际在 frontend 目录以 PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-ant-design-dist npx playwright test operations.spec.ts workerConcurrency.spec.ts reviewExecution.spec.ts theme.spec.ts alignment.spec.ts workflows.spec.ts optimization.spec.ts ux.spec.ts navigation.spec.ts 运行 56 项通过；另加 OCR_BROWSER_REVIEW_RECOVERY=1 运行 npx playwright test reviewRecovery.spec.ts，12 项通过，无跳过。这是选定范围的 68 项隔离浏览器验证，非全部专项或真实外部验收。实际 git diff --check 与四份主文档本地链接存在性检查通过。
- 排查与无效尝试：首次 npm 因旧缓存 EACCES 失败，改临时缓存安装成功，不改全局权限；依赖未就绪 tsc 缺包不计通过；两个新增 JSDOM 用例因响应式替身恢复失效失败，修正后通过。首轮浏览器发现旧导航 reset、窄屏标签点击及中文短按钮定位问题并修正；复选框对齐测试按 v6 DOM 调整，最终显式排除旧基础样式后完整 56+12 重跑通过。未用强制点击、删除业务断言或扩大超时规避。
- 部署生效：未部署；未覆盖 frontend/dist、重启 API/Worker/monitor、修改真实并发或预算、迁移业务库，未调用真实 OCR/飞书。不能据本轮本地测试断言业务端口已更新。
- 关联文件或证据：docs/ant-design-adoption.md 与 docs/frontend-interaction-checks.md；frontend/src/app/DesignProvider.tsx；隔离构建日志和测试输出。同工具链 git archive HEAD 临时构建比较：入口 JS 原始 501521→772703 字节，同算法 gzip 161523→255084 字节（约增加 91.4 KiB）；全部 JS 原始 740594→1523725 字节。监控入口拆分后约 164.5 kB，Table 约 327.9 kB；主入口超过 500 kB 的 Vite 提示仍在，未掩盖，也未当作实测首屏耗时。
- 遗留与下一步：当前首批验证通过，后续页面/P0 状态问题仍按全站规划推进；业务实例发布需单独执行与核对。收尾按本编号累计七条只读核验正常 monitor 同步，不强制导入或扩大聊天采集范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-010｜追加：运行监控四分区首批验收完成，等待本机发布

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：本批监控改造代码与本地验证完成；部署未执行，保留阶段边界。
- 关联记录：PI-20261107-010 设计基线及实施进展；PI-20261107-007 接入结果；PI-20261107-011 的其余页面规划。
- 现象或目标：不再跨越性能长报告寻找并发控制，历史评审问题不冒充当前系统宕机，低频维护不占用默认页和后台查询。
- 原因或分析：execution_jobs 与 jobs 分别表示原始初审执行和当前有效结论；模型槽还包含补审/诊断，不能混为初审。旧 API 字段缺失不是零，备份副本检查也不是完整恢复演练。
- 处理与改进：四个 URL 标签、运行指标和待关注入口、桌面执行槽左/并发右与窄屏并发前置；性能表含 URL 项目/状态/规模筛选、分页、行详情和样本口径；告警设置和通知分区；维护地址、预览、清理、对账和审计保持可达。隐藏停读/轮询，已访问草稿保留；当前视图刷新；清理冻结天数二次确认、取消无写入、焦点恢复；并发 409 不重放，已保存/已应用/版本差异和排空可见。
- 代码修改：OperationsPage 拆为页面编排、OperationsRuntime、OperationsMaintenance 和只读类型，修改并发/性能/告警及维护查询启用参数；新增局部布局与隔离测试。未变更后端调度、API 写入契约、OCR 内部并发或数据库。
- 本地验证：实际执行 PI-20261107-007 本轮列明的 lint、tsc、136 项组件测试、隔离 Vite 构建、56 项基础/兼容浏览器与12项合成补审专项，全部通过；operations.spec.ts 覆盖 1440/1024/768/375/320px、十槽、排空、键盘筛选 URL、刷新/回退、草稿及隐藏不轮询、清理确认。workerConcurrency 验证 1～10/409/降低容量，旧表单草稿、当前页批量和额度确认均重新验证。已实际查看本轮桌面与窄屏运行截图；不将合成数值当作真实任务。早期失败和修正过程见同轮 007 收尾，不覆盖历史结论。git diff --check 和文档链接检查通过。
- 部署生效：未部署；只运行临时 8791/SQLite 和 /tmp 构建，不覆盖业务静态目录、不重启服务或执行真实清理/评审/通知。没有将 UI 代码更新等同用户本机生效。
- 关联文件或证据：docs/operations-redesign-plan.md 的实施追加；docs/ant-design-adoption.md；frontend/e2e/operations.spec.ts；frontend/src/test/operations.test.tsx；隔离输出与截图。
- 遗留与下一步：本机发布后另做实际入口/版本核对；存量维护内部控件保留，其他页面重设计及 P0 状态修正未在本批完成。按本编号累计五条只读核验正常 monitor 同步，不自动调整并发或发起补审。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-010｜追加：受理本机生效操作说明，先核对静态资源提供方式

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：同一监控改造的本机生效说明，核对中；用户询问操作方法，未要求代为停止或发布。
- 关联记录：PI-20261107-010 首批验收；PI-20261107-007 的 Ant Design 接入。
- 现象或目标：给出使本机页面采用新构建的最小操作，避免无必要中断 Worker 或重新生成主密钥。
- 原因或分析：8781 由 API 提供 frontend/dist，5173 是开发服务；本轮仅前端改造，是否需要重启要核对资源挂载与缓存，不套用历史数据库升级的全进程停机流程。
- 处理与改进：先核对部署文档、前端脚本、资源挂载和现有监听状态，只给出准确命令与验证办法。
- 代码修改：仅追加台账，未修改业务或构建目录。
- 本地验证：实际读取 git status、docs/deployment.md 和 frontend/package.json，确认 build 为 tsc -b && vite build；尚未检查本轮 HTTP 缓存或执行发布。
- 部署生效：未部署、未重启服务、未改配置或调用 OCR/通知。
- 关联文件或证据：docs/deployment.md；frontend/package.json；用户本轮请求。
- 遗留与下一步：说明推荐操作及开发预览区别，追加实际核对结果并核验累计条数同步；不把用户随后执行的命令当成已经执行。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-010｜追加：已核对本机仅需更新静态构建，无须停止 Worker

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：本机生效步骤已核对；仅提供操作说明，没有代为发布。
- 关联记录：PI-20261107-010 上一段操作说明受理；PI-20261107-007 已安装依赖。
- 现象或目标：让用户在当前本机 8781 看到新四分区，而不无故中断在途评审。
- 原因或分析：实际 FrontendFiles 每次请求读取 frontend/dist；本机入口已经挂载，当前 HTTP 入口引用与磁盘旧 index.html 一致。此次改造未修改后端或迁移库，因此更新静态资源后刷新即可，不需要按历史后端升级流程停止全部服务。
- 处理与改进：建议先保存页面草稿、备份现有 frontend/dist，再在项目目录执行 npm --prefix frontend run build；成功后打开 http://127.0.0.1:8781/operations?tab=runtime 并使用 macOS 强制刷新。依赖本机已安装，不要求再次安装；构建失败不称生效，保留备份供恢复。5173 仅开发预览且当前无监听，不混为正式本机入口。
- 代码修改：本轮仅主动追加两段台账；未修改业务文件、依赖或静态产物。
- 本地验证：实际 lsof 核对 8781 监听及 5173 无监听；实际 GET / 返回 200，入口引用 index-nTipW7Q9.js 与 frontend/dist/index.html 一致；GET /api/health 返回 status=ok、auth_mode=dev、worker=running。实际读取 FrontendFiles.get_response、frontend_dist 挂载与本机 API 进程命令确认上述提供方式；git diff --check 通过。本轮未运行 build、复制备份或重启服务，源码静态结论不冒充新布局浏览器验收。
- 部署生效：未执行；用户尚未执行建议命令的结果未知，不能将现有健康检查当作新版布局已生效。
- 关联文件或证据：backend/ocr_manager/api.py 的 FrontendFiles 与静态目录挂载；frontend/package.json；本轮只读 HTTP/监听输出。
- 遗留与下一步：用户构建成功并刷新后核对四分区、并发设置与性能视图；如仍旧版再核对资源路径、浏览器缓存或实际监听进程，不先盲目停 Worker。收尾按本编号累计七条只读核验正常同步，不扩大采集范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-011｜追加：受理其余页面第二批迁移，先保护状态事实与任务操作

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：用户已授权继续，实施中。
- 关联记录：PI-20261107-011 全站规划；PI-20261107-007/010 首批组件规范与监控迁移。
- 现象或目标：继续迁移接入引导和评审任务页面，并修正关联配置读取失败被显示为未配置的状态表达。
- 原因或分析：上一批只完成监控试点；本轮按既定 P0 与评审主链路推进，不把全站换组件当成业务正确性证明。
- 处理与改进：拟采用 Ant Design 控件与分层布局，保留 URL 筛选、当前页批量范围、费用确认及现有草稿守卫；先隔离验证，不自动覆盖本机服务。
- 代码修改：本段仅登记受理，尚未修改本批业务源码；保留工作区既有变更。
- 本地验证：实际 git status --short、阅读前端规范及台账；~/.codex/comment-standards.md 当前不存在，遵循项目中文注释与更严格规范。尚未运行本批自动化验证。
- 部署生效：未部署；不覆盖 frontend/dist、不重启业务 API/Worker/monitor、不执行真实评审或通知。
- 关联文件或证据：用户“再继续其他页面的迁移吧”；docs/whole-site-ux-redesign-plan.md。
- 遗留与下一步：实施后追加实际变更与验证范围，按本编号累计条数只读核验正常同步，不强制抓取或扩大聊天范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-011｜追加：第二批迁移因工作期间出现外部提交暂停，尚未通过验证

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：部分编码，暂停等待用户确认当前基线；不宣称阶段完成。
- 关联记录：PI-20261107-011 本轮第二批受理；PI-20261107-007/010 首批改造。
- 现象或目标：接入引导与任务列表开始迁移 Ant Design，并修正配置辅助查询的未知表达。
- 原因或分析：工作期间 HEAD 出现非本处理者执行的提交 065f522（fix：重构运行监控页面），包含本轮新写但尚未完成验证的 OnboardingPage、TaskFilters、TaskSelectionBar、JobsTable、JobsPagination 和 ReadFeedback 等文件；初始多项工作区变更也已进入该提交。根据保护用户修改规则立即停止后续业务修改，不回退、不 amend，等待确认是否以当前提交继续。
- 处理与改进：已编写接入证据清单、任务筛选/表格/分页及冻结编号费用确认初稿；任务页编排、配置辅助状态修正和局部样式仍有未提交改动。保留现有草稿守卫及 API 契约，未执行外部测试或真实重审。本批仍需修复类型、更新回归用例、检查布局和完整验证，不能直接构建发布。
- 代码修改：部分已编码、未完成；存在上述外部提交和本处理者未提交修改，未操作 Git 历史或用户原有变更。本段仅追加暂停事实。
- 本地验证：实际读取前端规范、实施流程、相关源码与测试、后端只读连接测试与 repository-readiness 契约；实际 cd frontend && npx tsc -b && npm run lint 在 tsc 阶段失败，JobsTable 的 onCell 仅返回 data-label 与 Ant Design 单元格属性弱类型不兼容，共七处 TS2322；后续 lint 未执行。实际 git status --short、git log、git reflog 和 git show HEAD:frontend/src/pages/OnboardingPage.tsx 核对提交变化；没有运行本批单元测试、隔离构建或浏览器验收，不沿用上批通过结论。
- 部署生效：未部署；没有覆盖 frontend/dist、重启业务 API/Worker/monitor、迁移数据库或发起真实评审/通知，现有本机页面是否由用户另行更新未知。
- 关联文件或证据：提交 065f522 与本轮 git/tsc 输出；frontend/src/pages/jobs；frontend/src/styles/task-migration.css。
- 遗留与下一步：用户确认以当前工作区继续后，先修复类型与控件回归，再完成本批测试及文档；最后按本编号累计四条只读核验正常 monitor 同步。暂停不等于验收或发布完成。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"modified","verification_state":"failed","deployment_state":"not_deployed"}

### PI-20261107-011｜追加：用户确认当前基线，恢复第二批页面迁移

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：用户已确认继续，实施中。
- 关联记录：PI-20261107-011 上次暂停；以提交 065f522 和现有未提交修改为基线。
- 现象或目标：完成接入引导、任务列表与配置辅助状态修正的本地验收，不将半成品发布。
- 原因或分析：用户在明确询问基线后回复“继续”，允许保留现有全部内容继续处理；当前工作区与暂停时一致。
- 处理与改进：先修复表格类型，再补状态失败、冻结确认、筛选分页、草稿与窄屏验证；不回退用户提交。
- 代码修改：本段仅登记恢复，尚未增加本轮业务改动；保留既有修改。
- 本地验证：实际 git status --short、git log -2 --oneline、读取暂停记录及现有页面；本轮测试尚未执行。
- 部署生效：未部署，不更新 frontend/dist、不重启业务服务、不发起真实评审或通知。
- 关联文件或证据：用户“继续”；提交 065f522；本轮只读输出。
- 遗留与下一步：完成本批修复、隔离验证与文档后追加结果，并核验同编号累计条数同步。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-011｜追加：第二批编码与组件验证完成，整批浏览器回归中

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：本地验证中，未发布。
- 关联记录：PI-20261107-011 恢复实施；用户确认的提交 065f522。
- 现象或目标：完成接入引导、任务列表迁移和配置辅助状态修正，保护已有业务语义。
- 原因或分析：Select 不进入原生 FormData；加载按钮图标可能改变可访问名称；静态引入任务表格会增大入口。连接测试旧通过和回调 URL 均不能作为当前配置验证结论。
- 处理与改进：补显式条件合并、折叠保值、冻结编号和禁重放、独立恢复、路由按钮内存导航、任务懒加载、统一 Select 高亮；保留高级业务控件与同步草稿守卫。新增状态和批量专项测试，不改后端。
- 代码修改：本批页面、私有表格/分页、样式、路由按钮和测试已修改；未进行其余主链路及完整配置编辑器迁移。
- 本地验证：实际 npx tsc -b、npm run lint 通过；npm test -- --reporter=dot 最终 30 文件 143 项通过；隔离 Vite 构建通过，500 kB 提示仍在。初轮浏览器发现七处失败：新增用例未等待 URL 导航、表单几何统计误包含 Select 内部输入、旧移动链接定位、加载按钮可访问名称和选择器主题预期；修正后重点复验 21/22，余一项定位由 loading 图标改变可访问名导致，增加明确 aria-label 后专项 1/1 通过。新增组件弹窗测试因 JSDOM 动画隐藏失败，在该测试独立关闭动效后两项通过，未删冻结与网络失败断言。最终 65 项整批浏览器回归正在执行，未将阶段结果当作最终通过；补审专项尚待重跑。实际 git diff --check 通过；已查看 1440/320 任务及 320 引导截图。
- 部署生效：未部署，不覆盖 frontend/dist、不重启 API/Worker/monitor、不调用真实 OCR/GitLab/飞书、不迁移业务库。
- 关联文件或证据：frontend/e2e/taskMigration.spec.ts；frontend/src/test/configurationFacts.test.tsx；frontend/src/test/taskMigration.test.tsx；/tmp 隔离构建和日志。
- 遗留与下一步：等待整批与补审回归结果，更新实际报告、包体积和剩余页面清单，再只读核验同编号累计条数同步。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-011｜追加：第二批接入引导与任务列表迁移验收完成，未发布

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：本批代码与本地验收完成；全站迁移仍有后续页面。
- 关联记录：PI-20261107-011 本轮恢复与验证进展；用户确认基线 065f522；PI-20261107-007/010 的主题与监控兼容范围。
- 现象或目标：完成接入证据清单、任务列表 Ant Design 迁移及配置辅助查询未知表达，避免错误状态或范围引导写操作。
- 原因或分析：回调 URL 和旧通过不证明当前配置；Select 不进入原生 FormData；React 路由过渡快速返回可能取消重挂载，只靠 key 无法保证旧选择清空；loading 图标会改变确认按钮可访问名；任务静态引入把表格依赖加入首屏。
- 处理与改进：引导按配置、接收、连接证据分层，未知与当前版本待核实明确；任务使用统一控件、桌面表/窄屏摘要、URL 条件和25/50/100分页、UTC时间、折叠保值；范围改变主动清空选择并保留 key 隔离；批量冻结编号/费用确认、取消无写入、请求锁定、防重放和逐项接受；项目、飞书、账号辅助查询独立恢复、不显示假未配置或默认关闭。引导路由按钮保留内存导航，任务懒加载。高级存量业务组件和同步草稿守卫保留，未机械重写。
- 代码修改：本批页面、任务私有表格/分页、筛选/批量、设计上下文高亮、局部样式与只读反馈/路由按钮、测试和三份说明已更新；保留当前用户提交与其他修改，没有提交、回退或 amend。没有修改后端、数据库或调度契约。项目/飞书/账号页本批仅状态修正，不能称整页迁移。
- 本地验证：最终实际 cd frontend && npx tsc -b、npm run lint、npm test -- --reporter=dot 通过（30 文件、143 项）；npx vite build --outDir /tmp/ocr-site-ux-dist --emptyOutDir 通过。实际以 PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-site-ux-dist npx playwright test taskMigration.spec.ts operations.spec.ts workerConcurrency.spec.ts reviewExecution.spec.ts theme.spec.ts alignment.spec.ts workflows.spec.ts optimization.spec.ts ux.spec.ts navigation.spec.ts taskAuthor.spec.ts --output /tmp/ocr-migration-final 完整重跑65项通过；同环境额外 OCR_BROWSER_REVIEW_RECOVERY=1 npx playwright test reviewRecovery.spec.ts --output /tmp/ocr-migration-recovery，12项通过，无跳过。合计77项选定隔离浏览器，不等于全部专项或真实外部验收。实际 git diff --check、三份主文档本地链接检查通过；实际查看1440/320任务及引导截图，页面无横向溢出，桌面表内允许局部滚动。
- 排查与无效尝试：前次类型错误已修；新测试与旧控件迁移定位、JSDOM动画及主题预期失败均已修正，未把失败称通过。前一轮完整浏览器64/65，仍出现快速条件切换返回旧选择；修改为提交条件前显式清空选择后，同专项 --repeat-each=3 三次通过，再最终完整65+12通过；未删业务断言、强制点击或加大超时掩盖。初次静态任务入口约1258.7kB，路由拆分后最终入口749788字节、同Python gzip 248462字节、全部JS1559711字节，共用Table约305.3kB；500kB提示仍在，非实测首屏性能。
- 部署生效：未部署；隔离临时SQLite/8791与/tmp产物，不覆盖frontend/dist、不重启业务API/Worker/monitor、不迁移业务库或发起真实评审/通知，也未将用户可能自行操作推断为新版已生效。
- 关联文件或证据：docs/ant-design-adoption.md 第二批记录；docs/whole-site-ux-redesign-plan.md；docs/frontend-interaction-checks.md；frontend/e2e/taskMigration.spec.ts；frontend/src/test/configurationFacts.test.tsx、taskMigration.test.tsx；/tmp最终测试输出。
- 遗留与下一步：后续继续任务详情、问题与侧栏、合并前审查和事件页，再完整配置/平台管理与首页；存量高级业务控件后续单独迁移。构建成本与真实发布验收仍保留边界。本编号累计七条，收尾实际只读核验正常monitor同步，不强制导入或扩大采集范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-011｜追加：受理剩余全站页面迁移与设计实施

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：用户明确要求继续完成剩余全部改造，实施中；不扩展为后端或部署任务。
- 关联记录：PI-20261107-011 第二批验收；PI-20261107-007/010 组件规范与监控首批。
- 现象或目标：按已确认全站规划，完成剩余评审链路、配置/平台管理和首页的设计及 Ant Design 渐进迁移，保留业务事实、权限、草稿与 URL 行为。
- 原因或分析：当前已迁移运行监控、接入引导和任务列表；任务详情、待跟进问题、合并前审查、事件、完整配置、账号/历史/改进及首页仍为存量布局，需要分域检查，不能机械替换全局控件。
- 处理与改进：先盘点剩余页面和测试基线，按评审链路、配置/平台管理、首页推进；每批保留同步离开守卫、危险操作、部分覆盖和读取错误边界，隔离验证。
- 代码修改：本段仅登记受理，尚未修改本轮剩余页面；保留用户当前所有提交与工作区变更。
- 本地验证：实际读取 PI-20261107-011 既有规划与收尾；此前测试结果只作为历史背景，不替代本轮验证。剩余页面检查尚未开始。
- 部署生效：未部署；不覆盖 frontend/dist、不重启 API/Worker/monitor、不调用真实 OCR/GitLab/飞书、不迁移数据库。
- 关联文件或证据：用户“继续完成剩下的全部改造和设计吧”；docs/whole-site-ux-redesign-plan.md。
- 遗留与下一步：盘点页面组件依赖及业务回归后分批实施；每轮及时追加实际进展并累计核验本编号同步状态，不扩大聊天采集范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-011｜追加：评审主链路四页完成一轮迁移与定向回归

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：任务详情、问题列表、合并前审查、合并事件已完成本轮子批；全站剩余改造仍在实施，未宣称全部完成。
- 关联记录：PI-20261107-011 本轮受理及第二批验收；PI-20261107-007 Ant Design 采用规范。
- 现象或目标：将评审主链路优先信息与危险/历史操作分层，同时保留既有状态语义、权限和 URL 行为。
- 原因或分析：任务详情长页面缺少定位入口，问题列表筛选/列密度高，预审详情将列表推离视口，事件历史补扫位于日常收件箱之前。
- 处理与改进：任务详情增加结论、失败/补审、覆盖/费用、文件历史、通知尝试导航；问题列表改 Ant Design Select/Input/Table/Pagination，详情保留原侧栏；合并前审查改 Ant Design Table 与 URL 驱动 Drawer；事件收件箱改 Ant Design Table，历史 MR 补扫和记录移入折叠次级区域。显式保留提交人≠责任人、人工修复≠自动验证、失败/部分/旧版≠通过、扫描完成≠审查完成及 31 天/费用/危险操作确认。
- 代码修改：修改 frontend/src/pages/JobDetailPage.tsx、ReviewIssuesPage.tsx、PremergePage.tsx、EventCenterPage.tsx 和 task-migration.css；修订事件及问题交互的隔离 E2E 断言。未改后端、数据库、外部 API 或服务调度；其余页面仍有工作。
- 本地验证：实际 `cd frontend && npx tsc -b && npm run lint && npm test -- --reporter=dot` 全部通过，30 个测试文件、143 项通过；实际 `npx vite build --outDir /tmp/ocr-site-ux-dist --emptyOutDir` 通过，保留 Vite 500kB 警告。实际 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-site-ux-dist npx playwright test e2e/ux.spec.ts e2e/workflows.spec.ts --grep '问题|合并前|事件中心'` 4 项通过；定向用例先发现 Select 文本断言方式及事件标题/折叠状态不匹配，修正后复跑通过。默认 Playwright 浏览器缺失造成的首次无法启动不计通过。`git diff --check` 通过。
- 部署生效：未部署。产物仅在 `/tmp/ocr-site-ux-dist`，未覆盖 frontend/dist、重启 API/Worker/monitor、修改本机配置或调用真实 OCR/GitLab/飞书。
- 关联文件或证据：docs/whole-site-ux-redesign-plan.md；docs/ant-design-adoption.md；docs/frontend-interaction-checks.md；Playwright 定向结果与隔离构建日志。
- 遗留与下一步：继续完整项目/系统设置、账号/配置历史、问题与改进视图、首页及剩余存量控件改造；之后执行更完整的页面/角色/视口回归并由用户确认本机静态资源切换。新增此记录后 PI-20261107-011 共九条；待本轮边界说明再执行只读同步核验。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-011｜追加：评审主链路子批收尾，后续页面继续排期

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：本次工作轮次收尾；仅完成全站规划中的评审主链路四页子批，其余配置/平台管理和首页尚未实施，PI-20261107-011 保持进行中。
- 关联记录：PI-20261107-011 本轮受理及四页子批进展。
- 现象或目标：汇报本轮修改、验证及本机生效边界，不把分阶段迁移误报为“全站已改完”。
- 原因或分析：规划涉及十余个业务页面和多角色/响应式回归；本轮仅完成优先链路，配置编辑、历史/账号、改进、首页及全链路检查仍需独立实施。
- 处理与改进：实施边界和定向检查已更新到全站规划、Ant Design 接入说明及交互检查文档；后续按配置与平台管理、首页/复盘、全站回归的顺序继续。
- 代码修改：已修改本轮四个评审页面和相应隔离测试；保留用户既有提交和其他工作区更改。不创建提交，不回退或重启任何服务。
- 本地验证：以本轮最终实际命令为准：TypeScript、lint、143 项 Vitest、隔离构建、4 项相关 Playwright 及 `git diff --check` 全部通过。另一次未指定已安装 Chrome 的完整两文件浏览器测试无法启动，原因是 Playwright Chromium 缓存缺失，不计为通过；已使用 Chrome 完成上述定向测试。
- 部署生效：未部署；`frontend/dist` 和本机服务状态未更改，本机是否生效尚未验证。
- 关联文件或证据：PI-20261107-011 当前台账；docs/whole-site-ux-redesign-plan.md；docs/ant-design-adoption.md；docs/frontend-interaction-checks.md。
- 遗留与下一步：后续同编号继续追加配置页面、平台管理、首页及全站验收；本轮台账核验使用 `--minimum-entries 10`，遵循项目规定等待 monitor 正常同步，不强制抓取聊天或改写网页记录。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-011｜追加：配置历史、账号、问题与改进及首页继续迁移

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：继续实施 P2 页面子批；全站剩余清单仍未闭环。
- 关联记录：PI-20261107-011 本轮任务链路与前一子批收尾；全站改造规划。
- 现象或目标：将低频维护工具降为次级入口，统一账号/历史页展示，同时优先突出最近评审。
- 原因或分析：改进主视图之前固定展示两个低频工具；配置历史/账号表格仍是存量表格；首页效果分析早于常用最近评审列表。
- 处理与改进：问题与改进维护/聊天工具置于折叠区，保留三个 URL 视图；配置历史和账号列表改用 Ant Design Table/卡片，保留恢复密钥警示、角色权限、账号会话失效及未知认证状态；首页最近评审移至趋势分析前。
- 代码修改：修改 ImprovementsPage、ConfigHistoryPage、UsersPage、OverviewPage 及本轮样式。同步扩充全站计划、接入说明和交互验证命令；项目配置与系统设置完整编辑器、优化主题详情信息架构、全面 E2E 仍未完成。
- 本地验证：实际 `cd frontend && npx tsc -b && npm run lint` 通过；实际 `npm --prefix frontend test -- --reporter=dot` 为 30 文件 143 项通过；隔离 Vite 构建通过，仍提示 500kB 告警。实际 Playwright 命令 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-site-ux-dist npx playwright test e2e/workflows.spec.ts e2e/improvements.spec.ts e2e/improvementSummary.spec.ts e2e/improvementArchives.spec.ts e2e/improvementMaintenance.spec.ts --grep '账号模式|项目新增|问题与改进|复盘|归档|维护|采集'` 共 6 项通过。另此前本轮评审主链路指定 4 项通过。实际 `git diff --check` 仍须最终重跑。
- 部署生效：未部署；只构建在 `/tmp/ocr-site-ux-dist`，未改 `frontend/dist`、重启服务或操作真实配置/账号。
- 关联文件或证据：docs/whole-site-ux-redesign-plan.md；docs/ant-design-adoption.md；docs/frontend-interaction-checks.md；隔离 Playwright 输出。
- 遗留与下一步：完善项目与系统设置表单和主题详情；专项测试配置历史恢复、密钥不回显、草稿冲突、角色和全视口；再做全站浏览器回归和本机发布准备。本编号新增记录后累计十三条，结束时只读核验台账同步。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-011｜追加：本轮剩余页面阶段性收尾（全站仍待继续）

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：当前工作轮次完成，PI-20261107-011 继续进行；不能将本轮视作全部页面完成。
- 关联记录：PI-20261107-011 当前页面实施与本地验证进展。
- 现象或目标：整理已实施的页面组、可核对的本地验证和接下来尚未完成的页面。
- 原因或分析：全站规划不只包含本轮几个组件表格；项目配置、系统设置完整表单和全部浏览器覆盖仍有大量专属业务语义。
- 处理与改进：将两组页面子批结果与已知 Vite 包警告记录在计划、组件采用说明和可执行检查文档；保留剩余明确清单。
- 代码修改：本轮共涉及评审任务详情、待跟进问题、合并前审查、事件中心、问题与改进、配置历史、访问权限、首页，以及相关 E2E 断言和迁移样式；没有改后端服务、数据库、调度或外部接口。
- 本地验证：实际通过 `cd frontend && npx tsc -b && npm run lint`、30 文件 143 项 Vitest、临时构建；定向隔离浏览器（评审主链路 4 项；账号/项目/问题归档/复盘 6 项）合计 10 个本轮用例通过；构建保留 500kB 提示。配置历史专门恢复用例、全站完整浏览器回归尚未运行。最终 `git diff --check` 和台账命令实际结果以本轮最终执行记录为准。
- 部署生效：未部署，`frontend/dist` 未覆盖，本机 API/Worker/monitor 未重启。新版本机页面未确认。
- 关联文件或证据：PI-20261107-011；docs/whole-site-ux-redesign-plan.md；docs/ant-design-adoption.md；docs/frontend-interaction-checks.md。
- 遗留与下一步：下轮继续项目配置、系统设置、主题详情与其余页；再补专项与全视口全链路回归。本编号新增此记录后累计十四条；等待正常 monitor 后运行规定只读核验。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-011｜追加：更正本轮记录累计数并核实台账同步

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：本轮台账核验的数量更正与闭环补充；PI-20261107-011 继续进行中。
- 关联记录：PI-20261107-011 本轮主链路、配置/账号子批收尾记录。
- 现象或目标：按页面实际条目与只读核验结果准确记载来源条数，避免依估算填写最小数量。
- 原因或分析：前一段误把当前编号累计记录写作十四条；首轮按十四条运行核验返回页面 12 条，后续以实际来源/页面核对后确认本轮收尾记录为十二条。
- 处理与改进：不改写此前已同步段落；追加本更正记录，说明规定的来源累计条数应以页面核验当前版本为准。
- 代码修改：无新增业务代码；只追加本核对记录。
- 本地验证：实际先运行 `PYTHONPATH=backend .venv/bin/python -m ocr_manager.improvement_log_check --database .local-data/local/app.db --source-id PI-20261107-011 --minimum-entries 14`，返回 entries=12、page_id=21、page_version=12 并失败（阈值高于实际累计）；随后以已同步实际条数运行同命令的 `--minimum-entries 12`，返回 passed=true、entries=12、page_version=12。现追加此条后应等待 monitor 同步，再以 `--minimum-entries 13` 核验。
- 部署生效：不适用；未部署任何代码或服务。
- 关联文件或证据：本轮 improvement_log_check 两次 JSON 输出；.local-data/local/app.db 页面 21/version 12。
- 遗留与下一步：本追加段需正常同步，结束前依实际源条数运行 13 条核验；不强制抓取聊天或覆盖网页记录。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-011｜追加：完成账号/历史展示层与首页信息顺序调整

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：继续实施，配置历史/账号展示、问题与改进导航、首页顺序已完成当前设计子批。
- 关联记录：PI-20261107-011 前述评审主链路与剩余页阶段记录。
- 现象或目标：改善首页常用信息优先级，并降低账号/历史信息的视觉密度，保留敏感数据和认证状态边界。
- 原因或分析：成效趋势曾早于最近任务；账号与配置历史为存量表格；问题与改进低频管理工具占据主视图上方。
- 处理与改进：首页先最近评审再效果趋势；账号与配置历史增加 Ant Design 卡片和表格；问题与改进维护/聊天收件箱改次级折叠入口，主视图 URL 不变。
- 代码修改：已调整 OverviewPage、UsersPage、ConfigHistoryPage、ImprovementsPage 及 task-migration.css。完整项目配置、模型和系统规则设置、主题详情信息架构及所有页面专项还未覆盖。
- 本地验证：实际 TypeScript 与 ESLint 通过、30 文件 143 项 Vitest 通过；临时构建通过但保留 500kB 告警；本轮实际定向 Playwright 两组共10项通过（评审链路4，账号/项目/归档/复盘6）；配置历史恢复本轮未单独覆盖。git diff --check 最终复核通过。
- 部署生效：未部署，静态产物仅在 `/tmp/ocr-site-ux-dist`，未更新 `frontend/dist` 或重启本机服务。
- 关联文件或证据：`docs/whole-site-ux-redesign-plan.md`、`docs/ant-design-adoption.md`、`docs/frontend-interaction-checks.md`、本轮前端测试输出。
- 遗留与下一步：继续项目配置与系统设置完整表单、主题详情、配置历史恢复专项及全站角色/视口回归；本记录后预期来源 14 条，以页面实际核验为准。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-011｜追加：当前续改轮次收尾，剩余配置表单仍待继续

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：本轮当前工作结束，PI-20261107-011 并未全站闭环；下一轮应继续而非按全部完成处理。
- 关联记录：PI-20261107-011 同轮各页面及台账数量更正记录。
- 现象或目标：如实区分已改造页面、已验证范围、尚未完成的页面与本机生效状态。
- 原因或分析：虽完成评审主链路和若干平台展示页面，但完整项目/系统配置表单和主题详情仍使用存量交互，且全站逐页/多视口测试未完成。
- 处理与改进：相关文档列明已实施和未覆盖范围；下一次从项目配置编辑器、模型/飞书/规则设置和主题详情继续，不跳过草稿保护与敏感信息专项。
- 代码修改：本轮保留此前确认的提交及所有用户工作区变更；新增涉及任务详情、问题、预审、事件、账号、配置历史、改进、首页。未修改服务端、数据库、真实外部系统或本机部署。
- 本地验证：最终实际命令为 `cd frontend && npx tsc -b && npm run lint`、`npm --prefix frontend test -- --reporter=dot`（30文件/143项）、隔离 Vite 构建、10 项选定 Playwright、`git diff --check`；均通过。全 E2E、配置历史恢复、完整页面/全视口/全部角色验收尚未运行。台账同步以本段后的 `--minimum-entries 15` 核验结果为准。
- 部署生效：未部署。`frontend/dist`、本机 API/Worker/monitor 未修改/重启，本机新版是否生效未确认。
- 关联文件或证据：PI-20261107-011 及三份全站/Ant Design/交互文档。
- 遗留与下一步：继续完成剩余配置表单、主题详情和全站回归；等 monitor 正常同步后只读核验本编号实际累计 15 条，不扩大采集或改写既有记录。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-011｜追加：继续完成剩余配置页、主题详情与全站验收

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：用户明确要求继续处理全部剩余改造；恢复实施，不再询问是否继续。
- 关联记录：PI-20261107-011 当前页面批次及未完成范围。
- 现象或目标：完成项目配置、系统设置和主题详情剩余设计迁移，并扩大全站本地回归，区分代码完成与本机发布。
- 原因或分析：上轮已完成评审链路和若干展示页，但高风险配置表单、各分区草稿/密钥/自动保存边界、主题阶段详情与全站视口回归仍未覆盖。
- 处理与改进：先核对项目配置及模型/飞书/规则编辑器和主题详情的状态、草稿守卫和测试夹具，再分批迁移；保留权限、URL、草稿冲突、独立保存、凭据不回显、危险确认和外部调用边界。
- 代码修改：本段仅登记继续实施，尚未修改本阶段业务源码。
- 本地验证：实际读取上一轮遗留和当前工作区状态；本阶段专项检查尚未执行。
- 部署生效：未部署；不覆盖 `frontend/dist`，不重启服务或调用真实模型/GitLab/飞书。
- 关联文件或证据：用户“继续下一步呀，全部处理完，不需要再问我”；PI-20261107-011 上轮记录。
- 遗留与下一步：实施后立即记录代码、验证和部署三个维度，收尾按来源与页面实际条数核验同步。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261107-011｜追加：全站当前页面改造与隔离回归完成，未部署本机

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：用户要求无需再询问并继续全部处理；本轮已完成剩余页面子批及全套浏览器回归，代码实施达到当前规划范围，本机发布未执行。
- 关联记录：PI-20261107-011 本轮受理、评审主链路/配置账号子批及首批 Ant Design 规则。
- 现象或目标：收完项目与系统展示、主题详情和全站当前可执行回归，同时如实标明未覆盖专项与部署状态。
- 原因或分析：原剩余清单包含项目仓库、模型规则、主题阶段导航和全站浏览器检查；旧测试定位依赖原生折叠、表格和分页 DOM，在改造后需要更新为实际组件语义。
- 处理与改进：完成仓库 Table/状态 Tag/Switch、模型 Table/Card、审核规则预览/反馈/历史次级折叠、主题阶段导航及三类验证/部署摘要，保留完整阶段证据、配置草稿守卫、密钥不回显、URL/权限和领域表单状态。调整维护折叠、问题作者和多种分页的 E2E 定位/行为验证。更新全站规划、Ant Design 采用说明与交互验证文档，明确未执行的专项、体积警告及不部署边界。
- 代码修改：本轮延续工作区页面改造，新增/调整 `frontend/src/pages/RepositoriesPage.tsx`、`SettingsPage.tsx`、`ReviewRulesPage.tsx`、`ImprovementThemeDetailPage.tsx`、`frontend/src/styles/task-migration.css` 以及相应组件/浏览器测试和三份设计/验证文档。未改后端业务 API、数据模型、调度、凭据或真实外部配置。
- 本地验证：实际 `cd frontend && npx tsc -b && npm run lint && npm test -- --reporter=dot` 通过；30 文件、143 项通过。实际隔离 Vite 构建 `npx vite build --outDir /tmp/ocr-site-ux-dist --emptyOutDir` 通过，保留入口 750.15 kB、超过 500 kB 的告警。实际已安装 Chrome 的完整 `npx playwright test` 最终 81 passed、18 skipped、0 failed；18 项是需显式环境/专项开启的聊天采集、补审恢复及 HTTP 兼容测试，不计通过。初次全套发现 4 项旧 DOM/定位断言不适配，修正后专项 15 项通过并全套复跑通过。`git diff --check` 通过。实际台账核验在追加本段前回读 16 条、page version 16；追加后仍待 monitor 同步并重查实际累计条数。
- 部署生效：未部署。构建仅输出到 `/tmp/ocr-site-ux-dist`；未覆盖 `frontend/dist`，未停止/启动/重启本机 API、Worker 或 monitor，未调用真实 OCR/模型/GitLab/飞书；本机是否加载新版本未确认。
- 关联文件或证据：`docs/whole-site-ux-redesign-plan.md`、`docs/ant-design-adoption.md`、`docs/frontend-interaction-checks.md`、隔离构建与 Playwright 最终输出。
- 遗留与下一步：18 项跳过测试及真实外部集成/完整角色状态组合仍需在各自明确专项环境验证；Vite 大块告警待另作性能拆包评估；本机发布仍需单独操作和入口确认。本条后以 SQLite 中该编号实际累计条数运行规定只读核验，不扩大采集或改写已同步段落。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261107-011｜追加：监控同步及来源页面条数核对通过

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：全站体验改造当前轮收尾的台账来源/页面同步状态已由只读工具核实。
- 关联记录：PI-20261107-011 本轮实施、验证与未部署记录。
- 现象或目标：确认 monitor 有正常同步本轮事实，来源累计数达到页面记录数，避免只根据本地 markdown 宣称已同步。
- 原因或分析：本轮收尾记录追加后，按项目要求等待 monitor 正常同步，再检查 SQLite 页面版本与来源条目累计。
- 处理与改进：不修改历史段落、不强制抓取聊天；只在 monitor 周期后执行指定只读核验命令。
- 代码修改：无；本条只记录台账同步核验结果。
- 本地验证：实际执行 `PYTHONPATH=backend .venv/bin/python -m ocr_manager.improvement_log_check --database .local-data/local/app.db --source-id PI-20261107-011 --minimum-entries 17`，返回 `passed=true`、`entries=17`、`page_id=21`、`page_version=17`、`errors=[]`。
- 部署生效：不适用；该命令只读台账同步状态，不部署网页或服务。
- 关联文件或证据：规定 `improvement_log_check` 实际 JSON 输出；本地数据库页面 21/version 17。
- 遗留与下一步：本核验追加段需在正常 monitor 周期后再以实际累计 18 条复查；不宣称未执行的外部链路专项或本机发布。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}


### PI-20261107-011｜追加：受理本机新页面静态产物切换

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：已受理，正在核对本机静态资源部署。
- 关联记录：PI-20261107-011 全站改造及未部署记录；用户本轮明确要求页面切换到新版本。
- 现象或目标：将已改造的前端在本机 8781 页面生效，不扩大为后端升级或真实外部业务验证。
- 原因或分析：部署说明及源码表明 FastAPI 从项目 frontend/dist 读取静态文件；当前监听端口为 127.0.0.1:8781，需核对运行进程路径及入口资源。
- 处理与改进：拟隔离构建、备份旧静态产物、先发布带哈希资源再原子切换入口，并读回 HTTP 文件校验；无需重启时保持 API、Worker 和 monitor 原状。
- 代码修改：未修改业务源码；本段仅追加受理记录。
- 本地验证：实际读取部署说明、静态挂载源码、git status 与监听端口；构建及部署后验证尚未执行。
- 部署生效：尚未切换，待本轮执行核验。
- 关联文件或证据：docs/deployment.md；backend/ocr_manager/api.py；本轮用户授权。
- 遗留与下一步：构建与切换后追加实际证据，等待 monitor 并执行累计条数核验；不读取或输出私有密钥。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}


### PI-20261107-011｜追加：本机新版前端已切换并只读验证

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：完成用户授权的本机页面静态资源切换。
- 关联记录：PI-20261107-011 本轮静态切换受理；前述全站改造与隔离验收。
- 现象或目标：让 127.0.0.1:8781 提供最新工作区前端，不中断现有评审。
- 原因或分析：当前 API 从项目 frontend/dist 按请求读取静态资源，无需为纯前端发布重启 API、Worker 或 monitor。
- 处理与改进：重新隔离构建并备份旧产物，先发布新哈希资源，再原子替换 index.html；保留旧哈希资源，兼容已打开标签页的延迟模块加载。
- 代码修改：未修改业务源码；更新 frontend/dist 静态产物，并追加台账。构建基于当前提交 d4c096d 的前端源码。
- 本地验证：实际 cd frontend 执行 npx tsc -b 和 npx vite build --outDir /tmp/ocr-ui-release.WvGIva --emptyOutDir 通过；保留超过 500 kB 的入口块告警。通过 urllib 逐个读回 50 个非入口文件并比较 SHA-256，首页和 /jobs、/repositories、/settings、/improvements、/operations 深链入口与新产物一致。Chrome/Playwright 仅访问项目配置、评审任务、系统设置、问题与改进四页，均渲染标题并加载 index-Buizoxxd.js，pageerror 为零；未执行业务写操作或真实外部连接测试。健康接口返回 status=ok、worker=running；API 仍为原 PID 88557。
- 部署生效：本机 127.0.0.1:8781 的新前端静态入口及资源已确认生效；新入口为 /assets/index-Buizoxxd.js，样式为 /assets/index-BthLK-Yf.css。API、Worker、monitor 未重启，不涉及后端升级或数据库迁移。用户已经打开的标签页需刷新，尚未确认用户浏览器缓存状态。
- 关联文件或证据：.local-data/ui-releases/20261108-103925/previous-dist 旧静态备份；同目录 release-report.json 为脱敏发布核验；frontend/dist/index.html；本轮 HTTP 文件校验与浏览器只读输出。
- 遗留与下一步：本次页面切换无未完成操作；用户保存未提交表单后刷新即可加载新版，缓存未更新时使用 Command+Shift+R。此前未覆盖的业务专项和构建体积告警未在本次解决。等待 monitor 后以累计 20 条核验台账同步。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"confirmed"}

### PI-20261108-001｜任务详情页信息层级与阅读体验重设计

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：已受理，排查中。
- 关联记录：PI-20261107-011 全站体验改造；本事项独立跟进任务详情的深度设计。
- 现象或目标：用户反馈任务详情不友好；截图中诊断和用量先于发现、内容纵向铺开、重复指标抢占阅读空间。
- 原因或分析：当前实现虽已有发现优先和锚点导航，但诊断、历史及费用仍全部铺在同一长页；发现筛选和反馈仍为存量控件，缺少明确的阅读主次。
- 处理与改进：拟采用任务概览、发现优先的分区工作区与次级任务信息，统一 Ant Design 交互；保留有效结论/初审、部分覆盖、费用未知及操作权限边界。
- 代码修改：尚未修改业务代码；保留工作区既有台账修改。全局 ~/.codex/comment-standards.md 不存在，按项目中文注释规范执行。
- 本地验证：已读取实施流程、前端规范、现有详情与发现组件及隔离测试说明；尚未运行本轮代码检查。
- 部署生效：未部署，未修改 frontend/dist 或重启服务。
- 关联文件或证据：用户本轮截图；frontend/src/pages/JobDetailPage.tsx、FindingsPanel.tsx、JobExecution.tsx。
- 遗留与下一步：完成组件设计、合成数据测试、桌面/窄屏浏览器检查；追加实际结果并执行来源同步只读核验，不扩大聊天采集范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-001｜追加：依据新版截图停止重设计，撤回未发布实验

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：本轮评估结束；用户补充当前新版截图并询问是否仍需改造，建议保留现状、暂缓进一步重设计。
- 关联记录：PI-20261108-001 本轮受理；PI-20261107-011 已发布的任务详情布局。
- 现象或目标：新版已将评审发现提前并提供分区定位导航，主要阅读顺序问题已有改善；不再依据最初旧版截图继续大改。
- 原因或分析：当前新版仍有顶部留白偏多和零发现结论不够突出的小问题，但不构成立即重做信息架构的必要性；导航为页内锚点而非隐藏其他内容的标签切换。
- 处理与改进：停止继续实现与发布，撤回本轮未发布的工作台、侧栏、标签、筛选及对应测试实验，只保留本轮台账记录。未来如实际使用反馈仍有定位或阅读障碍，再按本编号追加小范围改进。
- 代码修改：本轮曾试作任务详情、发现控件与导航，并新增概览/侧栏/工作区；现已仅撤回本轮 8 个已跟踪文件修改和 5 个新建实验文件。开始时已有的台账修改与历史追加均保留，没有回退用户业务改动或创建提交。
- 本地验证：撤回前实验版实际 `cd frontend && npx tsc -b && npm run lint && npm test -- --reporter=dot && npx vite build --outDir /tmp/ocr-job-detail-dist --emptyOutDir` 通过（30 文件、143 项组件测试；构建仍有超过 500 kB 告警）。更早一次组件测试因未包裹中文设计上下文失败，修正后才通过。实验版实际 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-job-detail-dist npx playwright test e2e/reviewExecution.spec.ts e2e/reviewDiagnostics.spec.ts e2e/taskAuthor.spec.ts e2e/workflows.spec.ts --grep '评审原因|分层诊断|提交人|百练模型|部分结果|连续导航' --output /tmp/ocr-job-detail-e2e` 为 5 通过、5 失败：累计时间重复匹配 3 项、旧提交人选择器 1 项、历史报告入口等待超时 1 项，不能称为浏览器验收通过；新增的实验测试尚未运行即撤回。上述结果仅为已撤回实验，不代表当前线上新版验证。撤回后以 git status 与 git diff --check 核对无业务源码差异，不再开展新一轮改造验证。
- 部署生效：本轮未部署，未改 frontend/dist 或重启 API、Worker、monitor；用户截图所示现行新版不受本轮实验影响。
- 关联文件或证据：用户第二张新版截图；本轮 Git 状态、组件测试及隔离 Playwright 输出；docs/problem-improvement-log.md 本编号两条记录。
- 遗留与下一步：当前不需继续大改；只读核验本编号两条记录与页面同步，未通过则明确未同步。不把已撤回实验的局部测试通过当作交付验收，也不扩大聊天采集范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"deferred","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-002｜任务列表精简与问题处理进度展示评估

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：已受理，排查中；本轮先评估展示方案与现有事实来源。
- 关联记录：PI-20261107-011 全站体验改造；PI-20261108-001 任务详情阅读体验评估。本事项独立关注任务列表。
- 现象或目标：用户希望任务列表更简洁，并直接知道任务发现的问题有没有处理，询问如何设计更合适。
- 原因或分析：截图中的评审完成状态与问题处置状态易混淆；费用、耗时明细和重复覆盖说明占用较多列表空间，具体数据能力待核对。
- 处理与改进：先核对任务列表、问题反馈模型与查询接口，再提出主次信息和状态口径，不把评审完成或飞书已发送等同于问题已解决。
- 代码修改：尚未修改业务源码；保留本轮开始时已有台账更改，仅追加本受理记录。
- 本地验证：已实际读取项目规范、实施流程、台账和混合记录说明；业务测试尚未运行。全局注释规范文件不存在，遵循项目规范。
- 部署生效：未部署；不修改静态产物、不重启 API、Worker 或 monitor。
- 关联文件或证据：用户本轮任务列表截图；当前项目工作区。
- 遗留与下一步：核对问题处理事实可否按任务聚合；追加评估结果后执行规定的只读同步核验，不扩大聊天采集范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-002｜追加：完成任务列表精简与问题处置口径评估

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：本轮评估完成，提出小范围优化建议；未开始业务代码实施。
- 关联记录：PI-20261108-002 本轮受理；PI-20261108-001 保留现行详情布局的评估。
- 现象或目标：让列表直接回答任务是否审完、还有哪些发现待处理，降低重复说明及执行费用明细的干扰。
- 原因或分析：JobsTable 将来源分四行，评审结果逐行重复覆盖说明，耗时完整铺开且表格最小横向宽度为 1440；task-search 已提供发现数量和最高级别，但没有问题处置分组数量。review_issues 已持久化 open/fixed/ignored/merged，发现反馈通过事务同步关联问题；helpful 不代表关闭。有效补审结论会替换发现范围，不能直接累计全部尝试。
- 处理与改进：建议默认列为任务/项目、提交人、评审状态、问题处理、通知、操作；任务来源压为两行，费用/耗时明细移至详情或次级展开；常用筛选聚焦全部、待处理问题、运行中、异常。独立展示待处理/已修复/已忽略数量，只有完整覆盖且零发现才显示本次未发现问题；部分覆盖零发现仍提示覆盖不完整。所有已处置不等于全部已修复；已合并问题须解析目标状态后去重，关联缺失显示未知。推荐点击问题数量进入该任务发现并定位待处理项，首版不增加整任务一键修复。
- 代码修改：未修改业务源码，仅追加本编号两条评估记录；保留本轮开始已有台账修改。后续实施需后端按当前有效版本和稳定发现身份批量聚合，并同步前端契约、筛选和缓存刷新，不能仅做前端样式假统计。
- 本地验证：实际读取 JobsPage.tsx、TaskFilters.tsx、jobs/JobsTable.tsx、tasks.py、review_effective.py、review_issues.py、review_issue_actions.py、review_finding_feedback.py、feedback_issues.py 和 FindingsPanel.tsx；实际 `git diff --check` 通过，`git status --short` 仅显示台账修改。本轮是静态评估，未运行组件、后端或浏览器业务测试，不宣称实现验收通过。
- 部署生效：未部署；未修改 frontend/dist、数据库业务事实或服务状态。
- 关联文件或证据：用户截图及上述当前源码；本轮静态阅读和 Git 检查输出。
- 遗留与下一步：评估建议交付用户；若实施，补充当前有效版本/重审/补审、重复与合并问题、关闭后重开、未知关联、部分覆盖及筛选分页一致性测试。等待正常 monitor 周期后执行 `PYTHONPATH=backend .venv/bin/python -m ocr_manager.improvement_log_check --database .local-data/local/app.db --source-id PI-20261108-002 --minimum-entries 2`；以实际输出说明同步结果，不强制抓取或覆盖页面。
- 同步状态：{"kind":"improvement","category":"experience","status":"deferred","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-002｜追加：受理保留耗时、尝试与创建时间的规划修订

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：继续规划中；同一事项追加，不新建问题编号。
- 关联记录：PI-20261108-002 前两条评估记录。
- 现象或目标：用户明确要求列表保留耗时 / 尝试和创建时间，参考新提供的 Bug 分析页面，再给出规划文案。
- 原因或分析：上一版建议移走耗时不符合用户日常扫描需求；参考页的紧凑行、状态数量和短标签值得借鉴，但不能搬用其他业务的阶段、负责人或反馈口径。
- 处理与改进：修订为保留关键字段、减少重复文案的紧凑列表；核对现有时间组件，规划独立的评审状态、问题处理和通知状态，以及筛选数量口径。
- 代码修改：尚未修改业务源码；本轮仅受理规划修订，保留既有台账修改。
- 本地验证：实际读取 git status、现有台账、JobExecution.tsx 和前端规范；确认当前耗时主值是初审累计执行、尝试分初审与补审，不将其改称全任务执行时间。尚未运行本轮文档检查或业务测试。
- 部署生效：未部署；未更改 frontend/dist 或服务。
- 关联文件或证据：用户本轮参考截图；frontend/src/pages/JobExecution.tsx。
- 遗留与下一步：形成持久化规划文档，追加交付记录并按本编号累计四条执行只读同步核验。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-002｜追加：完成参考页风格的任务列表修订规划

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：本轮规划文案已完成；尚未实施业务代码。
- 关联记录：PI-20261108-002 本轮规划修订受理及前两条评估。
- 现象或目标：保留用户要求的耗时 / 尝试和创建时间，借鉴参考页紧凑表格与带数量状态导航，同时直观看到问题是否处理。
- 原因或分析：简洁应来自减少重复长文和合并信息，不应删除日常判断耗时与任务时序的关键字段；当前初审执行时间不能冒充包括补审的全任务耗时。
- 处理与改进：新增规划文档，明确默认八个业务列及选择列、两行紧凑信息、状态导航、项目与问题筛选、创建时间、初审 / 补审次数、处置数量和当前有效版本统计口径；费用保留在详情。规定参考边界、统计分面、合并去重、未知关联、部分覆盖、待处理直达、缓存刷新与隔离验收范围。
- 代码修改：未修改业务源码；新增 docs/task-list-redesign-plan.md，并追加本轮两条台账记录，不覆盖已有历史。
- 本地验证：实际 `git diff --check` 通过；实际完整回读规划并核对 `git status --short`，仅台账修改和新增规划文档。本轮为文案规划，未运行后端、组件或浏览器业务测试，不宣称实现验证通过。
- 部署生效：未部署；未修改 frontend/dist、业务数据库或重启任何服务。
- 关联文件或证据：docs/task-list-redesign-plan.md；用户本轮参考图；frontend/src/pages/JobExecution.tsx 的现有时间口径。
- 遗留与下一步：后续实施按数据聚合、列表展示与直达、隔离测试顺序推进；规划文案完成不等于功能上线。等待 monitor 正常周期后，以本编号累计四条运行规定只读同步核验，不强制采集或覆盖页面事实。
- 同步状态：{"kind":"improvement","category":"experience","status":"deferred","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-002｜追加：受理任务列表规划实施

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：用户确认实施，进入开发；沿用原编号。
- 关联记录：PI-20261108-002 四条规划记录及 docs/task-list-redesign-plan.md。
- 现象或目标：落实紧凑任务列表、问题处置统计与筛选，保留耗时 / 尝试和创建时间。
- 原因或分析：现有列表缺少当前有效发现关联问题的去重统计；需要先统一后端版本、分页和筛选，再改造前端。
- 处理与改进：先实现批量问题摘要和状态数量、查询及详情定位，再调整 Ant Design 表格与筛选，最后开展隔离自动化验证。
- 代码修改：本段仅追加实施受理；保留开始时已有台账修改和规划文件。
- 本地验证：实际核对 git status、规划和任务详情源码；本轮测试尚未运行。
- 部署生效：未部署；不将本地验证视为部署确认。
- 关联文件或证据：用户本轮实施授权；docs/task-list-redesign-plan.md。
- 遗留与下一步：实施并及时追加结果，收尾以本编号本轮累计实际条数执行只读台账核验。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-002｜追加：完成任务列表开发，进入完整浏览器回归

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：核心代码与首轮验证完成；完整浏览器回归进行中，不预报最终通过。
- 关联记录：PI-20261108-002 规划与实施受理。
- 现象或目标：精简任务列表，保留耗时 / 尝试及创建时间，直接查看当前有效发现对应问题的处置情况。
- 原因或分析：评审完成不等于问题修复；补审、重审、合并链和缺失关联会影响当前处置统计，必须统一服务端口径。
- 处理与改进：增加共享只读投影、状态分面、问题 / 通知组合筛选与详情最终目标映射；列表改紧凑八业务列和窄屏摘要，待处理数量直达任务发现，反馈 / 处置后刷新列表和邻项缓存。
- 代码修改：已修改后端查询及契约、前端列表 / 筛选 / 发现直达和相关测试；新增 task_issue_summary.py、聚合测试及浏览器用例，更新 OpenAPI。未变更数据库 Schema、Worker 调度或外部调用边界。
- 本地验证：实际后端全量 `.venv/bin/pytest -q backend/tests` 为 715 passed、1 skipped、1 warning；`.venv/bin/mypy backend/ocr_manager` 为 124 文件通过；`npx tsc -b`、`npm run lint`、`npm test -- --reporter=dot`（30 文件 145 项）、隔离 Vite 构建通过。已完成的定向 Playwright 为 11 passed，覆盖任务处置直达 / 返回 / 重开、状态数量、五种宽度、键盘 / UTC / 失败恢复。首次浏览器旧断言与新列结构不符，已适配后复跑；全量 102 项浏览器回归仍在执行。最新增加的保守状态展示组件测试尚未运行，不能沿用先前 145 项作为新增测试结果。实际重新生成并校验 OpenAPI、全后端 Ruff 与 git diff --check 通过。构建仍有超过 500 kB 告警。
- 部署生效：未部署；构建仅输出 /tmp/ocr-task-list-dist，不覆盖 frontend/dist，不重启本机 API、Worker 或 monitor。
- 关联文件或证据：docs/task-list-redesign-plan.md；backend/tests/test_task_issue_summary.py；frontend/e2e/taskList.spec.ts；本轮隔离命令输出及 /tmp/ocr-task-migration 截图。
- 遗留与下一步：完成全量浏览器回归和新增组件测试，修复真实回归后记录实际结果，再按累计条数执行只读同步核验；不扩大聊天采集范围，不将本地通过代替上线。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-002｜追加：任务列表实施与本地验收完成，尚未部署

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：本轮代码实施及本地验收完成；部署状态单独保留为未部署。
- 关联记录：PI-20261108-002 前六条规划、受理与开发进展。
- 现象或目标：实现简洁任务列表，并保留耗时 / 尝试、创建时间，直接展示问题有无处理。
- 原因或分析：列表以评审状态、问题处置和飞书通知三个独立维度表达事实；当前有效补审、合并最终目标、去重问题与未知关联必须在列表、筛选和直达详情保持一致。完成但缺少可信当前结果显示待核实，不显示成功零发现。
- 处理与改进：完成带全量分面数量的状态导航、项目 / 问题主筛选及高级通知筛选、八业务列与手机摘要；问题摘要来自 SQLite 当前有效发现，补审 / 重审不混入过期版本。点击待处理数量进入本任务开放发现，处置 / 重开同步刷新列表，返回保留原查询。费用移至详情，初审耗时不冒充全任务耗时，初审 / 补审次数分开。
- 代码修改：新增后端 task_issue_summary.py 与 7 项聚合测试、新增任务列表浏览器测试及 8 项展示边界组件测试，修改任务查询 / 契约 / 详情映射及前端列表、发现筛选和缓存失效，更新 docs/openapi.json 与 docs/task-list-redesign-plan.md。未改 Schema、后台调度、Git / 模型 / 飞书外部调用规则；无提交，无回退用户原有修改。
- 本地验证：最终实际 `.venv/bin/pytest -q backend/tests` 为 717 passed、1 skipped、1 warning（72.14 秒；现有 Starlette/httpx 弃用提示）；`.venv/bin/ruff check backend`、`.venv/bin/mypy backend/ocr_manager`（124 文件）、`PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract`、`git diff --check` 通过。实际 `cd frontend && npx tsc -b && npm run lint && npm test -- --reporter=dot && npx vite build --outDir /tmp/ocr-task-list-final-dist --emptyOutDir` 通过，31 文件 153 项组件测试；入口 750.40 kB / gzip 250.17 kB，仍有超过 500 kB 告警。完整浏览器实际 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-task-list-dist npx playwright test` 为 84 passed、18 skipped；再以最终构建显式开启 `OCR_BROWSER_REVIEW_RECOVERY=1` 运行 e2e/reviewRecovery.spec.ts 为 12 passed，独立恢复普通环境运行 e2e/taskList.spec.ts 与 e2e/taskMigration.spec.ts 为 11 passed。覆盖 1440 / 1280 / 768 / 390 / 320px、键盘 / UTC / 返回、批量冻结与只提交一次、错误恢复、处置直达 / 重开、补审及真实只读角色边界；跳过项不算通过，不宣称真实外部系统或生产负载已验收。
- 排查与无效尝试：初轮测试中因新增路由依赖与旧列 / 筛选定位失败，分别改为显式传入初始视图及更新真实交互定位后复跑通过。开发进展追加时状态枚举不符合台账契约导致 source_conflict；先只读核对页面仍只有前五条，修正尚未同步的第六条枚举后，正常 monitor 已导入六条且最近错误为空，未改写已同步历史或强制采集。未安装全局 python，辅助脚本改用项目 .venv/bin/python。
- 部署生效：未部署；隔离产物未覆盖 frontend/dist，未重启本机 API、Worker 或 monitor。手动截图仅运行并已关闭 8791 临时合成服务，不操作真实业务库；正式入口不能据此宣称已生效。
- 关联文件或证据：docs/task-list-redesign-plan.md 含可执行检查命令；backend/tests/test_task_issue_summary.py；frontend/src/test/jobsTable.test.tsx；frontend/e2e/taskList.spec.ts；/tmp/ocr-task-list-final-e2e 与 /tmp/ocr-task-list-recovery；.local-data/task-list-preview/desktop.png 和 mobile.png 为合成数据预览，已实际目视核对。
- 遗留与下一步：后续发布需同步覆盖前后端范围，保持现行服务的备份、回滚与实际入口核验边界；本轮没有发布事实。等待正常 monitor 周期后，实际执行 `PYTHONPATH=backend .venv/bin/python -m ocr_manager.improvement_log_check --database .local-data/local/app.db --source-id PI-20261108-002 --minimum-entries 7`，以返回结果说明来源与页面同步是否一致；不扩大已授权聊天范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261108-002｜追加：受理本机生效步骤确认

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：同一事项继续确认部署步骤；用户询问如何在本机生效，尚未请求实际执行发布。
- 关联记录：PI-20261108-002 已完成代码与本地验收，前七条记录。
- 现象或目标：明确当前实例需要更新哪些产物和进程，避免只刷新浏览器或只换前端导致摘要不可用。
- 原因或分析：本次同时新增后端问题摘要 / 筛选契约与前端显示，正式页面读取 frontend/dist；必须配套生效，启动方式待只读确认。
- 处理与改进：只读核对部署说明、监听进程、launchd 注册与业务库结构，不重启服务或写业务任务。
- 代码修改：本轮尚未修改业务代码；仅追加台账受理。
- 本地验证：已实际读取 docs/deployment.md 并核对 git status；本轮业务测试未运行，既有测试结果不冒充本轮部署验证。
- 部署生效：未执行发布、覆盖产物或重启服务。
- 关联文件或证据：用户本轮询问；docs/deployment.md；本机只读状态核对待执行。
- 遗留与下一步：提供适用于当前实例的发布 / 回滚步骤，追加确认结果并以累计九条执行同步核验。
- 同步状态：{"kind":"improvement","category":"deployment","status":"investigating","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261108-002｜追加：确认本机生效方式，仅提供步骤未执行发布

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：部署操作说明确认完成；仍未部署。
- 关联记录：PI-20261108-002 本轮步骤确认受理及既有实施验收。
- 现象或目标：明确让当前本机 8781 任务列表生效的最小必要操作与安全边界。
- 原因或分析：当前 API 与 Worker 从项目目录的两个独立终端启动，未查到 open-code-review 的 launchd 注册；库为 schema 49，本次不增加迁移。新摘要与筛选由 API 读取提供，静态页由 frontend/dist 提供，必须更新两端，单刷新无效。
- 处理与改进：建议先备份现有静态产物、数据库与私有配置，重新构建前端到 frontend/dist，在原 API 终端正常停止并用既有 private.json 重启 API；只针对本次列表变更，无需重启 Worker / monitor。刷新后核对新列、筛选、接口摘要和健康，不重新生成主密钥、不修改业务库或批量重跑评审。若另外包含 Schema / 调度发布，须按整体部署流程，不套用本次最小步骤。
- 代码修改：本轮未改业务源码、静态产物或配置；仅追加两条台账，不修改前七条已同步历史。
- 本地验证：实际 lsof 确认 127.0.0.1:8781 的监听 API；ps 确认独立 API / Worker / monitor 和父终端；launchctl list 未检出本项目注册。项目 Python mode=ro 查询 schema=49、初审 / 补审 queued 或 running 均为空；curl -fsS http://127.0.0.1:8781/api/health 返回 status=ok、auth_mode=dev、worker=running。只读结果为查询时刻，不保证后续持续空闲。实际读取部署说明与 StaticFiles 挂载位置；本轮不重跑业务测试，既有通过结论不替代部署验证。
- 部署生效：未执行发布、备份、构建、停启或浏览器正式入口验收；当前运行实例不能宣称已加载本轮改动。
- 关联文件或证据：docs/deployment.md；backend/ocr_manager/api.py 中 frontend/dist 挂载；本轮只读进程、SQLite 和健康检查输出。
- 遗留与下一步：用户若要求实际发布，再在执行时复核并完成备份、静态切换、API 重启与正式入口验证；本轮等待正常 monitor 周期后以累计九条运行只读同步核验，不强制同步或扩大聊天绑定。
- 同步状态：{"kind":"improvement","category":"deployment","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261108-003｜全项目列表统一体验梳理与规划

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：已受理，排查中；本轮仅梳理和规划，不实施业务页面。
- 关联记录：PI-20261108-002 任务列表精简与问题处置展示；PI-20261107-011 全站体验改造。
- 现象或目标：用户希望以新版任务列表为参考，评估整个项目其他列表是否也能统一优化，并给出全局规划方案。
- 原因或分析：各列表可能已采用 Ant Design，但筛选结构、信息密度、分页、详情入口和业务状态口径仍有差异；不能仅按旧规划推断当前实现或把所有列表套成任务状态。
- 处理与改进：盘点路由、主列表及内嵌记录，核对源码与查询契约，划分统一规则、逐页信息方案、后端缺口、实施批次和验收边界。
- 代码修改：保留本轮开始已有的任务列表相关源码 / 测试修改与文档；尚未改业务源码，本段仅追加受理。
- 本地验证：实际核对根 AGENTS.md、前端规范、git status、既有全站规划及源码文件目录；尚未运行本轮业务测试或全站视觉验收。
- 部署生效：未部署；不覆盖 frontend/dist、不重启服务、不改写业务状态。
- 关联文件或证据：用户本轮全局梳理请求；docs/task-list-redesign-plan.md；docs/whole-site-ux-redesign-plan.md；frontend/src/pages。
- 遗留与下一步：完成源码与契约盘点后新增专项规划文档，追加实际结果；等待正常 monitor 周期后按本编号至少两条执行只读同步核验。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-003｜追加：完成全项目列表盘点与分批规划，尚未实施页面

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：专项规划完成；处理进展为已完成方案，业务页面未实施。
- 关联记录：PI-20261108-003 本轮受理；PI-20261108-002 任务列表基准；PI-20261107-011 全站体验规划。
- 现象或目标：评估其他列表能否采用新版任务列表的简洁结构，给出全局范围、逐页字段、数据缺口、实施顺序与验收要求。
- 原因或分析：静态盘点覆盖 11 类主列表（含任务基准、其他 10 类）及内嵌日志 / 报告 / 证据；部分页面虽已使用 Ant Design，但筛选、分页和信息密度仍不一致。问题记录与优化历程仍用长卡片；配置历史、MR 补扫和告警投递仅最近 100 条；除任务外的五类业务查询尚无同等列表状态分面，不能仅改样式或用当前页凑全量数字。
- 处理与改进：新增 docs/global-list-redesign-plan.md，按业务工作列表、轻配置列表、内嵌记录与报告统一体验；明确默认列、状态范围、字段去向、移动端、空错与返回上下文。建议先保护任务基准和基础组件，再迁移待跟进问题 / 合并前审查 / 合并事件，随后平台问题记录 / 优化历程、配置与权限、内嵌区域；配置历史真实分页可前置。任务耗时 / 尝试及创建时间保持可见，台账代码修改 / 本地验证 / 部署生效分别展示，不把评审完成推断成问题修复或部署成功。
- 代码修改：本轮仅新增专项规划、更新 docs/README.md 索引、主动追加本编号两条台账；未修改业务源码、测试、配置或运行产物，保留开始时已有的未提交工作。建议组件与接口仍是待实施方案，不宣称已经创建或支持。
- 本地验证：实际读取路由、列表组件、查询契约与前端规范；实际 git diff --check 通过；实际 `.venv/bin/python -` 内联文档检查通过，核验 51 个源码 / 测试路径、3 个文档链接、11 类主列表、10 项必需主题、索引入口及新文件行尾空白 / LF / 末尾换行。额外使用 git diff --no-index --check 检查新文件时命令因存在差异返回 1、无文本诊断，导致后续链未执行；随后改用独立 Python 检查并实际复跑通过。不将文档检查视为业务测试：本轮未运行 pytest、前端类型 / lint / 组件测试、构建或全站逐页浏览器 / 真实数据 / 完整角色验收；规划列出的命令仅供后续实施执行。
- 部署生效：未部署；不覆盖 frontend/dist，不重启 API / Worker / monitor，不改写任务 / 配置业务状态，不触发 GitLab、模型或飞书调用。规划完成不等于页面已优化或本机已生效。
- 关联文件或证据：docs/global-list-redesign-plan.md；docs/README.md；本轮静态查询与文档核验输出；frontend/src/app/App.tsx 及专项文档列出的前后端源码路径。
- 遗留与下一步：后续按批次补分面 / 摘要 / 真实历史分页、前端迁移与自动化用例，各批单独记录代码、本地验证和部署。等待正常 monitor 周期后实际执行 `PYTHONPATH=backend .venv/bin/python -m ocr_manager.improvement_log_check --database .local-data/local/app.db --source-id PI-20261108-003 --minimum-entries 2` 核对来源与页面，不强制同步、不扩大聊天授权；最终同步结论以只读命令返回为准。
- 同步状态：{"kind":"improvement","category":"experience","status":"planned","code_state":"not_applicable","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261108-003｜追加：受理全项目列表实施

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：用户确认按专项规划全部实施，进入开发；沿用同一编号。
- 关联记录：PI-20261108-003 前两条规划记录；PI-20261108-002 任务列表基准。
- 现象或目标：完成规划内主列表与内嵌记录的统一体验、必要的分面 / 摘要 / 历史分页与回归验证。
- 原因或分析：不能只调整 CSS；需要保持全量数字、独立业务状态、密钥按需、草稿及批量冻结语义。开始时已有上一轮未提交修改，保留并在其基础上增量实现。
- 处理与改进：按公共展示、后端查询、业务列表、配置列表、内嵌记录、统一验证推进；不重做业务状态机，不扩大聊天授权，不直接发布。
- 代码修改：本段仅追加受理，业务实现尚未开始。
- 本地验证：实际核对 git status、根约定、专项规划、实施流程与后端规范；本轮测试未运行。
- 部署生效：未部署；不覆盖 frontend/dist，不重启现有服务。
- 关联文件或证据：docs/global-list-redesign-plan.md；用户本轮实施请求。
- 遗留与下一步：逐批实施并补测试，完成后追加实际结果，按本编号累计实际条数运行只读同步核验。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-003｜追加：完成主体迁移，进入交互与数据边界回归

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：开发中，尚未完成验收；关联本编号前三条。
- 现象或目标：让任务以外的业务列表、配置与内嵌记录使用统一紧凑展示，同时保护独立状态事实。
- 原因或分析：单纯替换表格会遗漏分页总数、筛选分面、敏感字段与关联版本；旧测试也依赖已移除的卡片、原生选择器和批量栏常驻布局。
- 处理与改进：已实现共享表格 / 筛选 / 时间 / 分页、五类状态分面、安全合并前摘要、配置历史真实分页，以及主列表和多数内嵌列表迁移；正在补剩余表格、窄屏和聊天关联版本刷新，再新增专项并完整回归。
- 代码修改：已修改前后端查询和页面；保留开始时已有工作，不增加数据库迁移，不扩大聊天授权范围。
- 本地验证：实际执行后端六文件定向 pytest 为 53 passed；前端最新 `npx tsc -b && npm run lint` 通过。首次组件回归 143 passed、10 failed，失败涉及旧列数、原生选择器、Router 包装和批量栏断言，尚未全部修复；未运行完整后端、浏览器和正式入口验收，不宣称整体通过。
- 部署生效：未部署；未覆盖 frontend/dist、未重启 API / Worker / monitor。
- 关联文件或证据：docs/global-list-redesign-plan.md；frontend/src/ui/ListTable.tsx；backend/ocr_manager/premerge_summary.py；本轮命令输出。
- 遗留与下一步：补专项、修交互与回归，隔离构建并实测桌面 / 窄屏；全部检查结束后追加实际结果并运行规定同步核验。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"failed","deployment_state":"not_deployed"}

### PI-20261108-003｜追加：主范围与数据回归通过，专题验收继续

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：全批次源码完成，主范围回归通过，专题与文档收口中；关联本编号前四条。
- 现象或目标：验收 11 类主列表和内嵌区域，并防止简化导致业务事实丢失、全量统计失真或敏感字段提前加载。
- 原因或分析：浏览器实际发现手机隐藏表头后缺全选入口、长条件标签撑宽、历史复选框触控高度不足；另有旧用例仍依赖原生控件、旧卡片与最近历史结构，均需区分真实问题与定位适配。
- 处理与改进：已修复以上真实布局与交互；聊天关联成功后采用写入返回版本，后台刷新不覆盖编号草稿，工具折叠停止轮询；配置历史真实翻到百条之外并保护脱敏 / 恢复；事件拒绝混合时区错误输入。补充分面、范围、权限、响应体积、返回上下文及五档视口用例，更新规划实施章节与使用说明。
- 代码修改：已完成全部规划批次，新增安全摘要、五类全量分面、全历史接口和通用轻量组件；不增加迁移，保持任务耗时 / 尝试、创建时间与三维交付事实，保留开始时已有工作。
- 本地验证：实际 `.venv/bin/ruff check backend`、`.venv/bin/mypy backend/ocr_manager`（125 文件）、OpenAPI 校验通过；最新 `.venv/bin/pytest -q -rs` 为 731 passed、1 skipped（外部 OCR CLI 探测未授权执行）、1 Starlette 弃用警告。最新前端 tsc / lint、组件 160 项与隔离构建通过。完整普通浏览器 90 passed、18 skipped；最终细调后 19 项跨屏 / 对齐 / 工作流复跑通过，聊天 / 补审 / HTTP 独立专题正在继续，跳过不计通过。百行合成摘要响应 54,786 字节，相比完整 6,369,586 字节约减 99.1%，固定三条 SELECT，不宣称生产性能。构建仍提示共享 chunk 超 500kB，未掩盖告警。
- 部署生效：未部署；构建仅 `/tmp/ocr-global-list-dist`，未覆盖 frontend/dist 或重启本机服务，测试只操作临时 SQLite 与 8791 合成服务，不调用真实外部系统。
- 关联文件或证据：docs/global-list-redesign-plan.md 第 10 节；docs/configuration-guide.md 新增使用说明；backend/tests/test_list_queries.py；frontend/src/test/globalLists.test.tsx；frontend/e2e/globalLists.spec.ts；实际检查输出与隔离截图。
- 遗留与下一步：完成独立专题和最后完整浏览器复跑、核对无动画截图，追加最终实际结果；按累计条数运行 improvement_log_check，不强制同步或扩大授权；真实部署与外部链路仍不在本轮验收范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261108-003｜追加：全批次实施与本地验收完成，尚未发布

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：用户授权的全部列表实施批次完成，本地自动化与文档收口完成；部署独立待执行，关联本编号前五条。
- 现象或目标：全站列表参考任务页统一为简洁、可扫描的结构，同时保留耗时 / 尝试、创建时间、问题处置与各领域独立事实。
- 原因或分析：不能以表格替换代替完整查询范围、不能把评审完成推断为问题已修复，也不能把代码 / 本地验证替代部署确认。手机全选、长条件、历史恢复与聊天关联版本等真实回归已修复并复跑；旧控件定位按当前交互更新，不删除业务断言。
- 处理与改进：完成 11 类主列表及内嵌记录统一、共享筛选 / 分页 / 窄屏单元格、五类全量状态分面、安全审查摘要、全量配置历史与脱敏差异、按需密钥、白名单返回上下文；保留草稿、冲突、批量冻结、权限与低频轮询边界。同步更新使用指南、专项规划第 10 节及前端交互检查，不覆盖前轮历史结论。
- 代码修改：前后端、OpenAPI、自动化用例和文档已修改；无新增依赖、数据库迁移或 Worker 状态机修改。保留开始时已有未提交工作，未提交 Git、未回退用户修改。
- 本地验证：实际 `.venv/bin/ruff check backend`、`.venv/bin/mypy backend/ocr_manager`（125 文件）、`PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract` 通过；`.venv/bin/pytest -q -rs` 为 731 passed、1 skipped、1 warning（外部 OCR CLI 探测未开启，Starlette/httpx 弃用提示）。实际前端 `npx tsc -b`、`npm run lint`、`npm test`（32 文件 / 160 项）及 `npx vite build --outDir /tmp/ocr-global-list-dist --emptyOutDir` 通过；最新完整 `OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-global-list-dist npx playwright test --output /tmp/ocr-global-list-complete` 在指定本机 Chrome 下为 90 passed、19 skipped、0 failed，耗时 5.1 分钟。独立显式开启 `OCR_BROWSER_CHAT_CAPTURE=1`、`OCR_BROWSER_REVIEW_RECOVERY=1`、`OCR_BROWSER_HTTP_COMPAT=1` 运行对应专题分别 4 / 12 / 3 项通过，不把默认跳过算通过；最终跨屏 / 对齐 / 工作流定向另有 19 项通过，不简单相加为独立用例总数。实测 11 类列表五档宽度、百条外历史分页及返回；实际目视核对手机问题 / 项目与桌面平台表。最后 `git diff --check`、三份相关文档本地链接与行尾检查通过。
- 性能与验证边界：百行合成摘要 54,786 字节，相对完整 6,369,586 字节约减 99.1%，固定三条 SELECT；仅本地合成输入，不保证生产延迟。只读导出本地 Git HEAD 提交作包体基线（非本轮开始时未提交源码），全部 assets 原始 1,676,004 / 1,697,234 字节、逐文件 gzip 552,313 / 552,461 字节（约 +1.27% / +0.03%）。Table 整合改变加载形状，当前主共享 JS 1,097.69 kB / gzip 355.89 kB，仍有超过 500kB 警告，未提高阈值或宣称首屏性能已验收。未覆盖真实外部系统、生产负载与所有角色 / 状态组合。
- 排查与无效尝试：额外手工截图因等待不存在的平台记录超时，未产出截图；随后使用完整套件实际截图完成目视，不将该手工命令报为通过。首次包体统计误用临时基线下 frontend/dist 路径导致空集合，已核对构建日志改用实际 dist 并检查非空后复算，最终采用上述真实数值。
- 部署生效：未部署；全部测试为临时 SQLite、8791 与合成替身，未调用真实模型、GitLab 或飞书，未覆盖 frontend/dist、未重启 API / Worker / monitor，不扩大聊天读取或绑定范围。正式实例不能宣称已经加载这些改动。
- 关联文件或证据：docs/global-list-redesign-plan.md；docs/frontend-interaction-checks.md；docs/configuration-guide.md；backend/tests/test_list_queries.py；frontend/src/test/globalLists.test.tsx；frontend/e2e/globalLists.spec.ts；/tmp/ocr-global-list-complete.log、/tmp/ocr-global-chat.log、/tmp/ocr-global-recovery.log、/tmp/ocr-global-http.log 与 /tmp/ocr-global-list-complete 截图。
- 遗留与下一步：代码和本地验收完成，正式生效需按部署流程配套更新前端产物、重启 API 并核对实际入口；仅此次列表改动无需重启 Worker，若合并其他发布则另按其范围评估。等待正常 monitor 周期后实际执行 `PYTHONPATH=backend .venv/bin/python -m ocr_manager.improvement_log_check --database .local-data/local/app.db --source-id PI-20261108-003 --minimum-entries 6`，以只读返回报告同步，不强制采集或修改已同步历史。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261108-004｜运行概览页面 impeccable 体验审查

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：已受理，排查中；本轮只审查和建议，不实施界面。
- 关联记录：PI-20261108-003 全项目列表统一；PI-20261108-002 任务列表与问题处置口径。
- 现象或目标：用户提供运行概览截图，要求使用 impeccable 审查页面并给出建议。
- 原因或分析：需要区分截图中的视觉层级、数字与待办口径、操作入口及当前源码，不能仅凭截图推断实际数据错误或交互已验证。
- 处理与改进：按 impeccable 的产品操作界面审查方法，结合截图与相关源码，形成按优先级排序的发现、保留项和建议结构。
- 代码修改：本段仅追加受理；保留已有未提交工作，不修改业务源码或运行产物。
- 本地验证：已实际读取根约定、impeccable 技能、git status 与既有台账；正在加载技能上下文，尚未开展页面源码核对或浏览器验证。
- 部署生效：未部署，不覆盖前端产物，不重启服务。
- 关联文件或证据：用户本轮运行概览截图；frontend/src/pages/OverviewPage.tsx；/Users/seakoi/.codex/skills/impeccable/SKILL.md。
- 遗留与下一步：完成静态审查，记录真实范围与限制；收尾以本编号至少两条执行只读同步核验，不将建议视为已实施。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：完成审查准备，等待双代理流程授权

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：审查准备完成，尚未形成正式评估；关联本编号受理记录。
- 现象或目标：按用户指定的 impeccable 方法审查运行概览，不以单次目视代替其完整独立评估流程。
- 原因或分析：该技能 critique 明确要求设计评估与技术证据由两个独立子代理完成；在 Codex 中尚无用户明确子代理授权时，必须先询问一次再继续。技能引擎首次下载持续无返回，不能宣称上下文命令或自动检测已成功。
- 处理与改进：实际查看用户截图、读取 OverviewPage.tsx 与 critique / operate 方法；确认 PRODUCT.md、DESIGN.md、忽略清单不存在。终止本轮持续未返回的下载与启动器，下载暂存文件已清理。下一步先征询子代理许可，未启动代理、自动检测、浏览器服务或报告快照写入。
- 代码修改：仅主动追加本编号两条进展；未修改业务源码、设计上下文、运行产物或已有历史。
- 本地验证：实际执行技能 context 启动尝试、读取方法与页面源码、检查上述文档是否存在及暂存清理；引擎上下文未完成。未运行本轮业务测试、构建、响应式浏览器、自动检测或可访问性检查；既有通过结论不沿用为本轮审查结果。
- 部署生效：未部署、不重启服务、不覆盖 frontend/dist。
- 关联文件或证据：frontend/src/pages/OverviewPage.tsx；/Users/seakoi/.codex/skills/impeccable/reference/critique.md 的 Codex 子代理授权门槛；用户截图与本轮命令输出。
- 遗留与下一步：获授权后执行两个独立评估并综合建议；若用户拒绝，则按技能要求显式声明单上下文降级。引擎仍不可用时明确自动检测限制，不把缺少证据推断为通过。等待正常 monitor 周期后实际执行 `PYTHONPATH=backend .venv/bin/python -m ocr_manager.improvement_log_check --database .local-data/local/app.db --source-id PI-20261108-004 --minimum-entries 2`，以只读结果说明同步，不强制采集。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：取得双代理授权并开始独立评估

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：用户明确授权，恢复同一事项审查；关联本编号前两条。
- 现象或目标：分别完成设计体验评估与技术证据核对，再形成可执行的分级建议。
- 原因或分析：两个评估需要保持独立，设计评估结束前不向综合上下文引入检测结论；自动检测引擎不可用时必须明确证据边界。
- 处理与改进：已启动 overview_design_review 与 overview_technical_review 两个独立上下文代理，分别读取截图 / 源码和尝试检测 / 浏览器验证；技术结论待设计评估完成后再汇总。准备只连接临时 SQLite 的隔离预览，不操作真实业务实例。
- 代码修改：仅追加进展，不修改页面、依赖、配置、既有历史或运行产物。
- 本地验证：实际核对目标、浏览器测试启动器、隔离构建是否存在及 8791 端口空闲；本轮独立评估和浏览器检查仍进行中，不预报通过。
- 部署生效：未部署，不覆盖 frontend/dist，不重启业务 API / Worker / monitor。
- 关联文件或证据：用户本轮明确授权；frontend/src/pages/OverviewPage.tsx；backend/tests/browser_app.py；frontend/playwright.config.ts。
- 遗留与下一步：隔离检查完成后停止临时服务、形成审查建议及归档（如引擎支持），追加实际结果并按累计条数核验同步；不扩大聊天绑定或采集范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：完成双代理运行概览审查，建议尚未实施

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：本轮审查完成，形成改进建议；关联本编号前三条。页面缺陷与建议未修复，不以审查完成代表问题解决。
- 现象或目标：从信息架构、待办口径、视觉密度与真实交互证据评估用户截图中的运行概览。
- 原因或分析：执行异常任务与开放代码问题是两类独立事实，目前相近的待处理名称容易引发误读；同一异常重复占据首屏。技术复核另在隔离健康查询失败场景复现 Worker 未知却仍提示未运行的缓存状态矛盾。
- 处理与改进：设计评估 A 与技术证据 B 使用独立上下文；A 完成后才读取 B 的检测与浏览器结果。建议优先明确运行异常 / 代码处置两条工作轴并修正健康缓存告警，其次收紧重复摘要、补手动刷新与上次成功时间、补趋势图数值替代。保留现有 Ant Design、处置摘要、直达筛选与响应式基础，不建议全页视觉重做。设计人工启发式为 24/40，仅作本次审查判断，不是自动检测或 WCAG 等级。
- 代码修改：本轮仅追加本编号进展；未修改业务源码、设计上下文、依赖、入口 HTML、运行产物或已同步历史。检测引擎不可用导致目标 slug 命令退出 127，按技能跳过官方快照与趋势归档，不伪造 `.impeccable/critique` 格式或历史评分。
- 本地验证：实际运行 `PYTHONPATH=backend OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-global-list-dist .venv/bin/python backend/tests/browser_app.py` 提供临时 SQLite / 8791；两个代理各自新建 Chrome browser/context，只读检查 1440 / 390 / 320px 与源码，未见整页横向溢出，刷新按钮具备 44px 触控区域、可访问名称和可见键盘焦点。通过浏览器路由模拟 1600ms 延时、503 与 401，证实刷新缺进行中反馈、缓存无更新时间和健康告警矛盾；初始加载及失败重读提示存在。趋势图存在内部滚动而非页面溢出，可聚焦滚动容器，不误报完全不可键盘访问；数值未进入等价可访问呈现。合成数据与用户截图数字不同，未核实真实实例计数。主代理实际查看截图与代理浏览器证据；本轮未运行 pytest、前端类型 / lint / 组件测试或构建，不沿用前轮通过结论。
- 检测与限制：B 实际单次执行 `/Users/seakoi/.codex/skills/impeccable/scripts/impeccable detect --json frontend/src/pages/OverviewPage.tsx`，25 秒无输出后终止进程组，退出 143；没有有效 JSON，规则、发现数与误报统计未知，不算零发现或扫描通过。浏览器临时脚本注入预检成功后已移除并恢复 title；没有启动 live-server、没有 detect.js overlay 或用户可见标注。PRODUCT.md、DESIGN.md 和忽略清单不存在，未擅自初始化或修复。真实读屏、生产角色与外部系统未验收。
- 部署生效：未部署、不覆盖 frontend/dist、不重启真实 API / Worker / monitor。临时服务已正常结束，两个代理浏览器均关闭；删除本轮两个临时检查脚本，保留 `/tmp` 报告 / JSON / 截图作证据，下载缓存目录检查为空。未扩大聊天读取或绑定。
- 关联文件或证据：frontend/src/pages/OverviewPage.tsx:39、:41、:45、:48；frontend/src/pages/ReviewEffectivenessSection.tsx:68；frontend/src/pages/jobs/TaskIssueSummary.tsx:16；/tmp/ocr-assessment-b-report.md；/tmp/ocr-assessment-b-detector.json；/tmp/ocr-assessment-b-browser.json；/tmp/ocr-b-extra.json；/tmp/ocr-a-desktop.png、/tmp/ocr-a-mobile.png 与 B 的隔离截图。
- 遗留与下一步：向用户交付分级审查与建议结构，再确认首页首要工作目标；建议尚未实施。等待正常 monitor 周期后实际执行 `PYTHONPATH=backend .venv/bin/python -m ocr_manager.improvement_log_check --database .local-data/local/app.db --source-id PI-20261108-004 --minimum-entries 4`，仅按只读结果报告同步，不强制采集；若后续实施则继续关联本编号并独立验证。
- 同步状态：{"kind":"improvement","category":"experience","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：受理运行概览修复规划

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：用户认可两条工作流分开与压缩重复卡片的方向，要求形成规划修复方案；本轮仅规划。
- 关联记录：PI-20261108-004 前四条审查记录；PI-20261108-003 全项目列表统一。
- 现象或目标：将审查发现转为可执行的页面结构、业务口径、文案、接口复用、实施批次和验收标准。
- 原因或分析：不能只给视觉建议；需明确 Worker 缓存可信度、异常任务与去重代码问题的范围、独立查询更新时间和趋势数据的可访问替代。
- 处理与改进：在既有审查和用户确认的方向内核对当前源码，新增专项修复规划及文档入口；不重新启动审查代理或展开整站重设计。
- 代码修改：本段仅追加受理，不修改业务源码、运行产物或已同步历史；以本轮开始时工作区状态为准。
- 本地验证：实际执行 git status、读取既有台账、文档索引、列表规划与 impeccable shape 方法；本轮业务测试、构建和浏览器检查尚未运行。
- 部署生效：未部署，不覆盖 frontend/dist、不重启 API / Worker / monitor。
- 关联文件或证据：用户本轮规划请求；frontend/src/pages/OverviewPage.tsx；docs/global-list-redesign-plan.md；既有双代理审查结论。
- 遗留与下一步：完成专项规划、静态文档检查及真实结果追加，以本编号累计六条执行只读同步核验；不将方案完成视为缺陷修复或发布。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：完成运行概览分批修复规划，尚未实施

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：用户认可方向后的规划交付完成；关联本编号前五条。缺陷修复与发布尚未执行。
- 现象或目标：将运行异常 / 代码问题分流、Worker 状态可信度、首屏重复、刷新反馈与趋势可访问性转为可落地方案。
- 原因或分析：仅改文案和卡片不足以保证可信；源码还显示概览事件 / 合并前启用范围与默认列表范围不同，活动任务统计需包括补审并与入口一致，问题变更后也需补概览缓存失效。这些为源码核对出的实施边界，不冒充本轮运行复现。
- 处理与改进：新增 docs/overview-repair-plan.md 并更新索引，包含页面结构、文案、五项发现、异常各类型单位、全量去重开放问题与分级、目标入口范围、兼容扩展 issue_todo / activity、Worker 缓存状态机、读取时间、手动刷新、趋势等价数据表、预计修改位置、四批顺序、验收矩阵、检查命令及发布 / 回滚边界。保留 Ant Design、任务耗时 / 尝试和创建时间，不引入进程控制或自动问题处置。
- 代码修改：本轮仅新增专项规划、更新 docs/README.md、主动追加本编号两条规划记录；未改业务源码、接口、测试、数据库、运行产物或已同步历史。文中拟议 API 字段、范围参数和新文件均明确待实施。
- 本地验证：实际执行 git diff --check 通过；实际运行 `.venv/bin/python -` 内联文档检查通过，核对 6 个本地链接、15 个现有源码 / 测试 / 文档路径、3 个明确待新增路径、18 个关键主题、索引入口及 LF / 末尾换行 / 行尾空白；实际 git diff --name-only 与未跟踪文件列表仅涉及本轮三份文档。核对现有查询、路由、缓存及工程规范。未运行 pytest、前端类型 / lint / 组件测试、构建、浏览器或真实读屏，规划命令不算已通过，前轮审查证据不沿用为本轮业务验收。
- 部署生效：未部署；未覆盖 frontend/dist，未重启 API / Worker / monitor，未改写业务状态或触发外部服务。
- 关联文件或证据：docs/overview-repair-plan.md；docs/README.md；frontend/src/pages/OverviewPage.tsx；backend/ocr_manager/workspace_queries.py；backend/ocr_manager/tasks.py；backend/ocr_manager/event_search.py；本轮文档静态检查输出。
- 遗留与下一步：后续按可信状态 → 查询与工作流 → 首屏布局 → 趋势及完整验收四批实施；代码和本地验证完成后另行发布。等待正常 monitor 周期后实际执行 `PYTHONPATH=backend .venv/bin/python -m ocr_manager.improvement_log_check --database .local-data/local/app.db --source-id PI-20261108-004 --minimum-entries 6`，以返回说明来源与页面同步，不强制采集或扩大授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"planned","code_state":"not_applicable","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：受理运行概览修复实施

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：用户确认按规划直接实施，进入开发；沿用同一编号，关联前六条规划与审查记录。
- 现象或目标：完成运行异常 / 代码问题分流、Worker 状态可信度、刷新反馈、首屏重排和趋势可访问数据表。
- 原因或分析：实施必须同步维护 SQLite 口径、URL 范围、React Query 缓存、Ant Design 交互和错误 / 权限状态，不能只改文案和 CSS。
- 处理与改进：按四批顺序实现；先写失败 / 延迟边界测试，再改后端摘要与范围参数，最后落地前端布局及趋势表。
- 代码修改：本段仅追加受理，业务代码尚未修改；保留已有未提交工作，不覆盖正式产物。
- 本地验证：本轮实施测试尚未运行。
- 部署生效：未部署，不重启 API / Worker / monitor，不改写业务状态。
- 关联文件或证据：docs/overview-repair-plan.md；用户本轮实施授权；frontend/src/pages/OverviewPage.tsx。
- 遗留与下一步：完成代码、测试、隔离浏览器回归后追加真实结果；按本编号累计条数执行只读台账核验。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：完成概览四批代码，进入完整隔离回归

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：开发完成、验证进行中；关联本编号前七条，尚不宣称验收闭环。
- 现象或目标：让运行异常、代码问题待处置、最近任务与效果趋势各自表达真实范围。
- 原因或分析：概览与列表必须共用启用范围；人工问题状态与执行状态独立，缓存健康失败不能沿用停止结论。
- 处理与改进：新增开放问题与活动任务聚合、事件和合并前 actionable_only 范围；紧凑双工作区、最近任务时间尝试、独立读取时间与手动刷新反馈、趋势等价数据表；补问题变更后的 overview 失效。
- 代码修改：已修改前后端业务代码与测试，更新 OpenAPI，未引入数据库迁移或外部调用；原规划文档保留原历史结论。
- 本地验证：实际 `.venv/bin/pytest -q -rs` 为 735 通过、1 跳过（外部 OCR CLI 探针未开启）；`.venv/bin/ruff check backend`、`.venv/bin/mypy backend/ocr_manager`、OpenAPI 更新后校验通过。前端 `npx tsc -b`、`npm run lint`、`npm test` 通过（164 项），Vite 产物输出到 /tmp/ocr-overview-repair-dist；主包仍有大于 500kB 提示。首页五档视口、延迟和健康失败、旧响应/读者共七个浏览器用例通过；范围清除测试最初用错可访问名称，已修为真实按钮名称，完整回归运行中。已目视桌面及手机合成长名称截图；未运行真实读屏。
- 部署生效：未部署；未覆盖 frontend/dist，未重启真实 API / Worker / monitor，浏览器只用临时 SQLite 与 8791 服务。
- 关联文件或证据：backend/ocr_manager/workspace_queries.py；frontend/src/pages/OverviewPage.tsx；frontend/src/pages/overview/；/tmp/ocr-overview-repair-e2e；/tmp/ocr-overview-browser.log。
- 遗留与下一步：完成全量浏览器、显式专题、性能测量与文档收口，追加最终实际结果，再以累计条数核验同步；真实 VoiceOver、生产负载和正式发布单独标注限制。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：概览修复代码与隔离自动回归完成，未部署

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：四批业务代码完成并通过隔离自动回归；真实读屏及放大验收未完成，不宣称所有人工门槛已通过，关联本编号前八条。
- 现象或目标：消除健康缓存矛盾与混合待办误读，让问题处置、执行异常、时间尝试和趋势数据在概览中可判断、可定位。
- 原因或分析：运行异常与开放代码问题是不同对象；健康、概览、效果各自读取，不能以部分成功代表整页已更新。开放问题与活动任务聚合、目标范围和缓存必须形成闭环。
- 处理与改进：已落地双工作区、各类型精确入口及启用范围、全量去重开放问题分级、包含补审的活动统计、最近评审耗时尝试与创建时间、可信 Worker 状态、独立成功读取时间、手动刷新防重复与部分失败、UTC 同源趋势语义数据表。问题变更后失效 overview；旧响应缺摘要单区降级，读者不出现管理导航。更新操作指南、验收说明和规划实施章节。
- 代码修改：前后端与新增测试已修改，OpenAPI 已更新；无新依赖、数据库迁移、Worker 调度或外部系统调用，未提交 Git。原规划与已同步历史不覆盖。
- 本地验证：实际 `.venv/bin/ruff check backend`、`.venv/bin/mypy backend/ocr_manager`（126 文件）、`PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract` 通过；最新 `.venv/bin/pytest -q -rs` 为 736 passed、1 skipped，跳过外部 OCR CLI 探针，已有 httpx 弃用提示。前端 `npx tsc -b`、`npm run lint`、`npm test` 通过（33 文件 / 167 项），隔离 Vite 构建通过。完整普通 Playwright 98 passed / 19 skipped；分别显式开启聊天 / 补审 / HTTP 专题为 4 / 12 / 3 passed；最终概览 / 导航 / 任务列表 / 工作流再跑 22 passed，不重复相加为独立用例。所有浏览器只用临时 SQLite、8791 和合成响应。git diff --check 与四份文档本地链接检查通过。
- 性能与视觉：5000 条合成开放问题下读取 SQL 23→23、响应 2220→2226 字节、单次本地 7.87→8.43ms，无问题正文返回，不代表生产负载。对比此前隔离产物 assets 约 +0.44%、gzip 约 +0.27%，主包仍有大于 500kB 警告。五档视口自动断言通过并实际目视桌面 / 手机截图，未见整页横溢；核心时间事实、入口和趋势表可读。真实 VoiceOver / 同等读屏、200% 浏览器放大未实测；impeccable 官方引擎未产出有效 JSON，不能称自动设计扫描通过。
- 部署生效：未部署；未覆盖 frontend/dist、未重启真实 API / Worker / monitor、未改写正式业务状态或扩大聊天读取授权。临时浏览器服务已退出。正式生效仍需同版前端与 API 配套发布并验收实际入口；仅本批无需 Worker 重启。
- 关联文件或证据：docs/overview-repair-plan.md 第 9 节；docs/configuration-guide.md；docs/frontend-interaction-checks.md；frontend/e2e/overview.spec.ts；/tmp/ocr-overview-backend.log、/tmp/ocr-overview-components.log、/tmp/ocr-overview-browser.log、/tmp/ocr-overview-chat.log、/tmp/ocr-overview-recovery.log、/tmp/ocr-overview-http.log、/tmp/ocr-overview-final.log；截图 /tmp/ocr-overview-final 与 /tmp/ocr-overview-repair-complete。
- 遗留与下一步：真实读屏 / 放大及正式发布另行验收；不以未执行项目冒充通过。追加后等待正常 monitor 周期，实际执行 `PYTHONPATH=backend .venv/bin/python -m ocr_manager.improvement_log_check --database .local-data/local/app.db --source-id PI-20261108-004 --minimum-entries 9`，只依据返回说明同步，不强制采集或扩大授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"modified","verification_state":"blocked","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：受理首页转向数据总览的信息架构反馈

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：同一首页事项的新一轮方向评估，已受理；关联本编号前九条，不把前轮实现视为当前方向已获认可。
- 现象或目标：用户认为首页应是项目门面，以整体数据与评审效果为主，而不是最近任务和运行异常工作台，要求评估布局并给出改法。
- 原因或分析：上一版优先服务运行恢复与具体任务定位，和本轮明确的数据总览定位不一致；需要调整信息优先级，而不只是加卡片或换色。
- 处理与改进：本轮仅评估截图与现有聚合口径，拟定数据指标、趋势、分布、项目对比的层级；不直接实施尚未确认的新结构。
- 代码修改：本段仅追加台账；未修改业务代码或产物，开始时 git status --short 为空。
- 本地验证：本轮业务测试、构建、浏览器和真实数据核验未运行；前轮通过结果不作为本轮验证。
- 部署生效：本轮未部署；用户截图所示入口和当前实例部署版本未核验，不推断前轮改动已由本轮发布。
- 关联文件或证据：用户本轮截图和反馈；docs/overview-repair-plan.md；frontend/src/pages/OverviewPage.tsx；backend/ocr_manager/review_effectiveness.py。
- 遗留与下一步：提出以数据为主、运行异常为辅、任务详情回归任务页的建议；明确现有字段可复用及新增统计所需口径，形成方向建议后追加结论并核验同步。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：形成数据总览优先的首页调整建议，待确认实施

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：本轮方向评估完成、建议待确认；关联本编号第十条。旧版代码存在不表示本轮数据首页已经实施。
- 现象或目标：首页首先展示整体评审规模、发现与人工处置、趋势和项目差异，任务明细不再主导首屏。
- 原因或分析：截图中当前工作区及最近任务占据上半页，效果指标和图表后移；页面偏值班工作台，缺少数据首页的主次。生成 / 发布、反馈误报比例适合作为二级分析，不能压过本期评审和当前开放问题；不能混用当前存量和期间流量生成处置率。
- 处理与改进：建议将标题改为项目总览，顶部放项目和时间筛选；四个主指标为本期终态评审、本期新问题、当前待处置、期间人工标记修复，明确期间 / 当前口径。主体以问题趋势与当前开放严重级别分布、项目概况、类别横向条形分布为主。运行异常缩为紧凑状态入口，当前开放与运行状态不随时间筛选伪装为期间统计；项目筛选若作用这些区块，需新增对应聚合支持。默认移除首页完整最近任务表，保留任务页入口与既有耗时 / 尝试 / 创建时间。详细定义、精确数表、样本分母按需展开；保留失败与过期可信提示。
- 代码修改：本轮只追加本事项两条台账记录，业务源码、UI、接口、依赖及运行产物均未修改；未改写已同步段落或原实施历史。
- 本地验证：实际核对用户截图、OverviewPage、ReviewEffectivenessSection、review_effectiveness 聚合源码及 impeccable shape / Operate 参考；git diff --check 通过。现有接口可复用部分指标、问题趋势、类别和项目数据，按天评审量、项目评审指标与项目范围的当前汇总需补查询，不能仅靠前端搬布局承诺已有支持。本轮未运行业务测试、构建、浏览器、自动设计引擎或真实数据核验，不沿用前轮验收为本轮结果。
- 部署生效：本轮未部署；未覆盖 frontend/dist，未重启 API / Worker / monitor，未核实截图对应部署版本。
- 关联文件或证据：本轮用户截图与首页定位反馈；frontend/src/pages/OverviewPage.tsx；frontend/src/pages/ReviewEffectivenessSection.tsx；backend/ocr_manager/review_effectiveness.py。
- 遗留与下一步：向用户交付推荐布局与数据边界；本轮不直接实施新的页面结构。等待正常 monitor 周期后执行 `PYTHONPATH=backend .venv/bin/python -m ocr_manager.improvement_log_check --database .local-data/local/app.db --source-id PI-20261108-004 --minimum-entries 11`，只依据返回报告同步；不扩大聊天授权，不将建议视为发布完成。
- 同步状态：{"kind":"improvement","category":"experience","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-005｜模型与访问权限页视觉一致性核查

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：已受理，排查中。
- 关联记录：PI-20261108-003 全项目列表统一；PI-20261107-011 全站迁移。
- 现象或目标：用户反馈 Agent 模型与访问权限页不同于其他页面，要求确认是否漏改；截图可见操作纵向堆叠、编辑文字换行、认证区域重复容器及控件风格混用。
- 原因或分析：待核对当前源码、列表统一规划和部署资源，不能仅凭截图判定整页遗漏或旧版本缓存。
- 处理与改进：先检查两页布局、共享列表样式和采用边界；本轮以核查为主，不擅自重设计页面或变更模型/认证业务。
- 代码修改：尚未修改业务代码；开始时仅 docs/problem-improvement-log.md 有既有修改，保留原记录。
- 本地验证：已读取项目约定及设计技能；尚未运行业务测试、构建、浏览器或发布校验。
- 部署生效：未部署，未修改 frontend/dist 或重启服务，截图的资源版本尚未核实。
- 关联文件或证据：用户本轮两张截图；本轮工作区状态。
- 遗留与下一步：核对差异原因及受影响范围，追加结论并执行本编号至少两条来源同步核验；不扩大聊天授权范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-005｜追加：确认属于局部迁移与视觉验收遗漏，不是整页未改

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：核查完成，局部修复待实施；本轮未获明确重做页面指令，不直接修改业务代码或发布。
- 关联记录：PI-20261108-005 本轮受理；PI-20261108-003 全项目列表统一。
- 现象或目标：解释两页相对其他列表的不一致，区分已有迁移与仍需补齐的细节，避免将截图中的缺陷归因于用户缓存。
- 原因或分析：两页均已接入 ListTable、ListSearch 与 useLocalList，模型还有 ListStatusNav，因此非整页遗漏。模型操作列 width=132，三个默认尺寸 text Button 放在允许 flex-wrap 的 row-actions 中，容易纵向撑高；账号操作列 width=72，而公共 .compact-list-table .ant-btn 允许 white-space:normal 与 height:auto，结合单元格留白和按钮内边距使“编辑”可断为两行。认证区域以 Ant Design Card 包裹自身带边框/内边距的旧 inline-setting，形成重复容器；认证 checkbox、新增按钮及编辑器仍存在旧控件。模型状态仍是纯文本，账号状态则使用既有 Status，展示未统一。模型单价属于配置核心事实，账号认证方式是独立管理设置，这些业务差异不应被强行抹平。
- 处理与改进：建议仅补局部收尾：为短文字操作预留足够宽度并禁止断字，常用操作横排、低频危险动作明确收纳；消除认证区重复边框并按 Ant Design 边界统一当前新增/重设计控件；统一表格状态与间距，保留模型保存/启用/测试分离、密钥草稿和账号会话失效等既有语义。无需重做两页或撤回已完成的列表能力。
- 代码修改：无业务源码、样式或测试修改；只追加本编号两条台账，保留开始时已有台账修改；未更改 PRODUCT.md、DESIGN.md 或技能配置。
- 本地验证：实际读取 SettingsPage.tsx、UsersPage.tsx、ListTable.tsx、ListControls.tsx、lists.css、styles.css、统一列表规划及 globalLists.spec.ts。已有五档列表 E2E 主要断言核心字段、加载完成、页面无横向溢出，未专门断言短操作不换行、多按钮行高或双层边框，因此旧测试结果不能证明这些视觉细节没有遗漏。本轮实际 Python urllib 只读请求 http://127.0.0.1:8781/，入口资源为 index-CqboQcO9.js / index-BM3pPffx.css，首页内容与当前 frontend/dist/index.html 完全相同；这仅核对本机入口，不证明截图浏览器使用同版资源或 dist 与当前源码逐文件一致。git diff --check 通过。本轮未运行组件测试、构建或浏览器复现，不引用历史测试为本轮通过。impeccable context 启动器因无法下载 engine 0.1.19 失败，已回退阅读现有源码和 Operate 指引；项目根目录未找到 PRODUCT.md、DESIGN.md，不臆造设计上下文或宣称自动扫描通过。
- 部署生效：未部署，未修改 frontend/dist、真实配置或认证状态，未重启 API / Worker / monitor。本机只读首页核验不是修复上线。
- 关联文件或证据：frontend/src/pages/SettingsPage.tsx:108-117；frontend/src/pages/UsersPage.tsx:66-71；frontend/src/styles/lists.css:31-32；frontend/src/styles.css:138；frontend/e2e/globalLists.spec.ts；本轮用户两张截图及本机 HTTP 首页比较结果。
- 遗留与下一步：待实施局部修复并补桌面/手机、短文字操作单行及多模型行高验收；若涉及认证控件替换，另外验证未知/失败状态不误显关闭、取消不写入和现有登录边界。等待正常 monitor 周期后执行本编号 --minimum-entries 2 的只读核验，不强制同步或扩大聊天授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：受理数据优先的项目首页实施

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：用户确认按最新建议实施，沿用本编号第十、十一条方向反馈。
- 现象或目标：将首页改为项目总览，以评审规模、问题趋势、当前风险和项目分布为主，最近任务退回任务页。
- 原因或分析：需要统一项目筛选与统计口径，区分期间流量、当前存量和全平台运行状态，不能只搬动卡片。
- 处理与改进：实现顶部筛选、四项主指标、趋势与严重级别、项目与类别分布，辅助展示运行摘要和更多效果分析；保留缓存失败、权限及刷新保护。
- 代码修改：本段仅追加受理，业务代码尚未修改；保留既有台账及 PI-20261108-005 的独立记录。
- 本地验证：本轮业务测试、构建和浏览器验证尚未运行，不沿用历史通过结果。
- 部署生效：未部署；不覆盖 frontend/dist，不重启真实 API、Worker 或 monitor。
- 关联文件或证据：用户本轮实施授权；docs/overview-repair-plan.md；frontend/src/pages/OverviewPage.tsx。
- 遗留与下一步：完成前后端和隔离回归，追加实际结果并核验本编号累计来源同步。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：首页数据结构与聚合实现完成，进入收尾验证

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：已实现数据优先项目首页，进入完整工程验证与文档收尾；关联本编号前十二条及本轮新受理记录。
- 现象或目标：首页以项目数据为主，减少最近任务表和运行摘要对首屏的占用，并让筛选范围一致可信。
- 原因或分析：项目指标、当前开放问题和平台健康有不同时间与项目边界；需要服务端同一读取快照提供当前分级与项目级汇总，不可在 UI 造数。
- 处理与改进：首页已改为四项主指标、趋势、严重级别、项目与类别分布；项目/时间进入 URL 并刷新查询；运行状态独立标示全平台；任务入口返回任务页。补齐趋势坐标轴、精确键盘数据表、项目统计和当前问题分级，收纳低频分析。更新使用指南、规划新章节与专项验收说明。
- 代码修改：前后端统计/UI/API类型/测试和相关说明已修改；移除首页专用最近任务组件，不修改任务页耗时、尝试或创建时间字段。未加依赖、迁移或外部调用。另有已由用户明确要求保留的设置页相关工作区修改，本事项不触碰。
- 本地验证：`.venv/bin/pytest -q backend/tests/test_review_effectiveness.py` 3 passed；`.venv/bin/ruff check backend`、`.venv/bin/mypy backend/ocr_manager`（126 源文件）、`PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract` 通过。`frontend` 的 `npx tsc -b`、`npm run lint`、`npm test`（33 文件 / 167 项）通过；隔离构建 `/tmp/ocr-project-overview-dist` 成功但共享 JS 仍大于 500kB。专项 Playwright 项目总览/导航在隔离服务 8791 运行 9 passed，包括五档视口、筛选与运行范围、Worker 失败、旧 URL；第一次运行测试选择器仍引用旧命名/字段未完全通过，修正合成断言后复跑全过。实际查看桌面和手机全页图；未连接正式业务实例。
- 部署生效：未部署；未覆盖 `frontend/dist`、未重启真实 API / Worker / monitor；专项浏览器只使用隔离 SQLite 和 8791。正式页面生效仍需后续发布。
- 关联文件或证据：`backend/ocr_manager/review_effectiveness.py`；`frontend/src/pages/OverviewPage.tsx`；`frontend/src/pages/ReviewEffectivenessSection.tsx`；`frontend/src/pages/overview/`；`docs/overview-repair-plan.md` 第 10 节；`/tmp/ocr-project-overview-dist`；`/tmp/ocr-project-overview-e2e`。
- 遗留与下一步：重跑最终源码构建和浏览器、完整前端/后端工程套件，核对文档链接与差异；据实际结果追加结束记录，再等待正常 monitor 周期并执行只读来源核验。真实读屏、200% 放大和部署未执行。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-005｜追加：受理两页局部修复实施

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：用户已明确要求修复，开始实施；关联本编号前两条核查记录。
- 现象或目标：修复模型页操作纵向堆叠、账号编辑断字、认证重复边框和可见控件不一致。
- 原因或分析：沿用前轮确认的列宽、允许按钮换行和旧容器嵌套原因；不重新设计业务流程或扩大为整站改造。
- 处理与改进：调整两页操作布局与局部样式，统一可见新增按钮、认证复选框和状态展示；保留模型启用/测试/密钥草稿和账号认证确认、读取失败及会话失效语义。
- 代码修改：业务修改尚未开始；本轮开始已有首页/聚合及 workflows 等未提交修改，均视为既有工作保留，不回退、不混入本次交付。
- 本地验证：已重读当前源码、前端规范、设计约束及组件测试；本轮检查尚未运行。沿用本会话已确认的设计技能启动器不可用边界，不宣称设计引擎通过。
- 部署生效：未部署，计划只输出隔离构建，不覆盖 frontend/dist 或重启服务。
- 关联文件或证据：frontend/src/pages/SettingsPage.tsx、UsersPage.tsx；本轮 git status；前两条核查。
- 遗留与下一步：补短操作单行、同排多按钮、认证未知/失败与确认取消、桌面/窄屏测试；完成后追加实际结果并核验本编号累计条数。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-005｜追加：两页局部视觉修复完成，专项验证通过但尚未部署

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：本轮源码修复与范围内验证完成；关联本编号前三条，不把本地通过视为正式页面已生效。
- 现象或目标：修复 Agent 模型操作堆叠、账号编辑断字、认证双层边框及可见新增控件不一致，保留原有列表、模型配置和认证行为。
- 原因或分析：操作列宽度不足且继承公共可换行按钮样式；旧 inline-setting 嵌套 Card 产生重复边框。采用两页局部约束，不改变所有列表的长内容换行策略。
- 处理与改进：模型操作列扩至 200px、账号至 104px，短文字操作使用小号链接按钮与不换行布局；模型使用既有状态标识，保留“未启用”语义。新增按钮和认证复选框采用 Ant Design，认证区去掉内部边框并保留手机纵向排版。未改模型 API、编辑器草稿、密钥不回显、测试与启用分离、认证确认和切换成功重载语义。
- 代码修改：修改 SettingsPage.tsx、UsersPage.tsx，新增作用域样式 configuration-lists.css；扩展 configurationFacts.test.tsx，新增 configurationPolish.spec.ts，补充 frontend-interaction-checks.md 的可执行回归说明。既有首页、后端聚合、导航及 workflows 等独立改动全部保留，未提交 Git、未新增依赖或迁移。
- 本地验证：实际运行 `cd frontend && npx tsc -b`、`npm run lint`、`npm test -- --reporter=dot`，通过 33 文件 / 169 项组件测试；`npx vite build --outDir /tmp/ocr-config-polish-dist --emptyOutDir` 通过，保留共享包大于 500kB 警告。`git diff --check` 通过。默认 Playwright 因 8791 占用未启动，不停止或复用该服务；用临时包装与配置监听 57262，实际运行 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-config-polish-dist npx playwright test --config /tmp/ocr-config-polish.playwright.config.ts e2e/configurationPolish.spec.ts e2e/workflows.spec.ts --grep '模型与账号|认证控件确认|百练模型' --output /tmp/ocr-config-polish-browser-complete`，最终 7 passed。覆盖五档尺寸、同排不换行、桌面行高、无页面横溢、键盘编辑/取消不写入、密钥不回显、认证确认登录、只读账号 API 403、模型单价流程；组件覆盖认证读取失败、取消不写入、请求中锁定、409 后原状态且无自动重试。实际目视两页桌面与 320px 截图。
- 验证限制：初次专项测试误将手机资料卡按桌面行高断言，新增登录用例又误用 check() 要求异步受控复选框立即变更；已修正测试语义并复验，不改业务逻辑掩盖。另运行既有“账号模式登录与只读界面”时，账号创建编辑、认证切换和读者登录成功，随后首页旧版“评审效果”区域断言失败；未改写独立首页工作或该测试，不宣称完整工作流/全站浏览器通过。真实读屏、200% 放大及真实外部模型未测；impeccable 引擎不可用边界不变。
- 部署生效：未部署；未覆盖 frontend/dist，未重启真实 API、Worker 或 monitor，未修改业务实例模型/账号状态。浏览器仅写临时 SQLite 和合成响应，独立测试服务已随检查退出；正式页面仍需发布后验收。
- 关联文件或证据：上述两页源码、作用域样式和测试；docs/frontend-interaction-checks.md 本编号章节；/tmp/ocr-config-polish-browser-complete、/tmp/ocr-config-polish-browser-final 截图；本轮终端实际输出。临时证据不承诺长期保留。
- 遗留与下一步：等待正常 monitor 同步周期后，实际执行 `PYTHONPATH=backend .venv/bin/python -m ocr_manager.improvement_log_check --database .local-data/local/app.db --source-id PI-20261108-005 --minimum-entries 4`；只依据只读结果说明来源与页面状态，不强制采集或扩大聊天授权。发布和首页独立工作流验收不属于本轮完成范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：受理参考图的信息层级调整

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：同一首页事项的布局补充，用户提供参考图并授权继续优化；不另建无关编号。
- 现象或目标：借鉴参考页的顶部状态带、四项指标、全宽趋势及诊断分区，让首页更像项目数据总览。
- 原因或分析：参考页属于其他业务，完成率、定位率、环比、Token 消耗及流程开关不能照搬为本项目事实。
- 处理与改进：仅借鉴结构与密度，使用现有评审/问题统计；运行摘要收为顶部全平台状态带，趋势扩展为全宽，严重级别/类别放入诊断区，保留项目概况与精确数据表。
- 代码修改：进入第二轮布局优化；保留用户明确要求保留的设置页改动。前轮进展同步状态中使用了非法枚举 in_progress，已在其尚未成功投影时纠正为 not_run；不修改业务状态模型或已同步历史。
- 本地验证：上一轮全量后端为 736 passed / 1 failed / 1 skipped，失败为本事项新台账非法枚举，修正后相关测试 32 passed。前端类型/lint/169 单测通过。普通浏览器中断于新截图反馈，73 passed / 3 failed / 1 interrupted / 16 skipped / 29 did not run；三个失败均为旧复选框对齐用例查找已替换的认证 checkbox，未修改或声称全量通过。本轮布局尚未验证。
- 部署生效：未部署；继续只生成 /tmp 产物，不重启正式服务。
- 关联文件或证据：用户本轮参考截图；frontend/src/pages/OverviewPage.tsx；frontend/src/pages/overview/RuntimeSummary.tsx；docs/overview-repair-plan.md 第 10 节。
- 遗留与下一步：落地新版结构并重跑首页回归、全量后端和前端检查；如无关测试受保留改动影响，明确报告，不擅自更改设置页测试。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：参考布局首页完成并通过范围内隔离验收，未部署

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：数据优先首页及参考布局调整完成；关联本编号前十四条，最终结果以本条所列实际范围为准，不将本地验证等同于部署。
- 现象或目标：首页以项目数据为门面，借鉴用户参考页的状态带、指标、主趋势和诊断层级，同时保持本项目业务事实。
- 原因或分析：参考页的其他业务指标不适用本平台，因此沿用真实评审数、新问题、当前开放和人工标记修复；不制造环比、修复验证率或成本曲线。
- 处理与改进：已完成分段时间选择、统一项目范围、顶部全平台运行状态带、四项指标、全宽量化趋势及区块内滚动的精确表、严重级别/类别诊断、项目风险排序与低频分析。首页移除最近任务明细，任务页原耗时/尝试/创建时间不变。健康失败不沿用旧停止结论，初始未知不伪装为零；旧 API 缺新增字段降级；读者和手动刷新边界保持。同步操作指南、规划第 10 节和验收说明；用户要求保留的设置页改动未回退或覆盖。
- 代码修改：本批前后端、首页相关测试及文档已完成；新聚合用同一 SQLite 读取事务和分组查询，不新增依赖、迁移、外部调用或首页写操作，未提交 Git。
- 本地验证：实际 `.venv/bin/ruff check backend`、`.venv/bin/mypy backend/ocr_manager`（126 文件）、OpenAPI 契约校验通过；最新 `.venv/bin/pytest -q -rs` 737 passed / 1 skipped（外部 OCR CLI 探针未启用），有既有 httpx 弃用提示。`cd frontend && npx tsc -b && npm run lint && npm test` 通过（33 文件 / 169 项），隔离 Vite 构建成功。最终首页/导航/任务列表/工作流 Playwright 21 passed；显式聊天/补审/HTTP 专题分别 4/12/3 passed，不重复累加。初次新控件测试误用隐藏 radio.check()、动态按钮旧名称及工作流模糊名称，按真实交互/精确名称修正后复验通过，未改业务行为掩盖。
- 验证范围与限制：较广浏览器命令排除旧复选框对齐用例后实际 99 passed / 1 failed / 19 skipped，唯一失败为“评审任务”模糊匹配，修正并包含于最终 21 项复跑；未再重跑较广套件，不改报全量通过。三个旧对齐用例前轮实际失败于设置页认证开关旧名称，与用户保留的独立修改相关，本事项未改。最终五档尺寸无整页横溢，已目视桌面和手机合成数据截图；真实读屏/200% 放大/生产负载未测，impeccable 官方引擎仍无有效 JSON。共享 JS 约 1,109.49kB / gzip 359.76kB，保留大于 500kB 警告。文档本地链接检查和 git diff --check 通过。
- 部署生效：未部署；未覆盖 frontend/dist、未重启真实 API / Worker / monitor、未改正式任务/配置或扩大聊天授权。浏览器使用 /tmp 构建、隔离临时 SQLite 和 8791，测试服务随检查退出。正式生效需要后续同版前端/API 发布与实际入口验收，本批不要求 Worker 重启。
- 关联文件或证据：docs/overview-repair-plan.md 第 10 节；docs/frontend-interaction-checks.md 本编号章节；backend/ocr_manager/review_effectiveness.py；frontend/src/pages/OverviewPage.tsx 及 overview/；/tmp/ocr-project-backend.log、ocr-project-components.log、ocr-project-build.log、ocr-project-browser-full.log、ocr-project-browser-final.log、ocr-project-chat.log、ocr-project-recovery.log、ocr-project-http.log；截图 /tmp/ocr-project-reference-e2e，均为临时证据。
- 遗留与下一步：正式发布、真实读屏/放大和独立设置页旧测试适配仍单独验收，不宣称所有人工门槛或全站浏览器已闭环。追加后等待正常 monitor 周期，实际运行 `PYTHONPATH=backend .venv/bin/python -m ocr_manager.improvement_log_check --database .local-data/local/app.db --source-id PI-20261108-004 --minimum-entries 15`，只依返回说明同步，不强制采集或扩大授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：受理以人工反馈衡量评审质量的首页再规划

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：同一首页事项的方向补充，已受理、口径核对中；本轮用户要求重新规划，不直接实施。
- 现象或目标：用户希望首页明确展示有帮助、已忽略等值，用于判断评审价值和后续优化方向，而非仅展示发现与修复数量。
- 原因或分析：人工反馈与问题处置可能采用不同统计粒度和时间口径，需要先核对实际存储与查询；不能将忽略直接认定为误报，或将有帮助等同于已修复。
- 处理与改进：核对反馈枚举、历史记录、问题状态、聚合与下钻能力，再追加质量优先的信息结构、指标定义、实施顺序及验收规划。
- 代码修改：本轮尚未修改业务代码，仅追加本受理记录；保留既有首页与独立设置页修改，不回退、不覆盖。
- 本地验证：本轮业务测试、构建、浏览器及真实数据核验均未运行；不沿用前轮验收结果。
- 部署生效：未部署；不覆盖 frontend/dist，不重启 API、Worker 或 monitor。
- 关联文件或证据：用户本轮问题趋势截图及质量分析诉求；docs/overview-repair-plan.md；backend/ocr_manager/review_effectiveness.py。
- 遗留与下一步：交付规划并记录事实依据，结束前等待正常同步周期并核验本编号累计来源；不扩大聊天授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：评审质量可见化规划完成，暂不实施

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：规划完成；围绕“有帮助、误报、已修复反馈、未标记”与“已忽略等问题处置状态”分别建模，等待用户确认后再实施。
- 现象或目标：首页不仅回答发现了多少、修复了多少，还要能判断评审是否有价值、哪些项目或类别需要优化。
- 原因或分析：反馈枚举为 `helpful`、`false_positive`、`fixed`；问题状态另有 `open`、`fixed`、`ignored`、`merged`。反馈按发现粒度，问题按去重问题粒度；现有查询按发现所属评审时间统计，不能冒充反馈操作日历史。已忽略不自动等于误报，有帮助也不等于已修复。
- 处理与改进：在 `docs/overview-repair-plan.md` 第 11 节追加质量优先方案：质量摘要卡、反馈构成、处置分流、项目/类别优化方向表、分母与样本不足规则、Q1–Q4 实施批次及验收风险；本轮不修改接口、数据库、前端或构建产物。
- 代码修改：无业务代码、测试、迁移、依赖或静态资源修改；保留本轮之前全部首页与设置页改动。
- 本地验证：实际读取反馈枚举、同步问题状态、当前反馈查询、详情筛选和现有效果聚合；`git diff --check` 待本轮文档追加后执行。未运行业务测试、构建、浏览器、真实数据或读屏，不沿用前轮结果作为本轮通过。
- 部署生效：未部署；未覆盖 `frontend/dist`，未重启 API、Worker、monitor，未修改业务数据库或正式配置。
- 关联文件或证据：`backend/ocr_manager/review_feedback_queries.py`、`backend/ocr_manager/review_finding_feedback.py`、`backend/ocr_manager/feedback_issues.py`、`backend/ocr_manager/review_issues.py`、`backend/ocr_manager/review_effectiveness.py`、`frontend/src/pages/FindingsPanel.tsx`、`frontend/src/pages/ReviewFeedbackPanel.tsx`、`docs/overview-repair-plan.md` 第 11 节。
- 遗留与下一步：用户确认后先实施 Q1/Q2，再按真实下钻能力实施 Q3；Q4 另行评审迁移与审计。等待 monitor 正常同步周期后执行 PI-20261108-004 只读来源核验，未扩大聊天授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：质量规划收口与文档检查结果

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：本轮规划交付完成，关联本编号第十六、十七条；不覆盖前条形成时的事实。
- 现象或目标：在用户圈出的图表位置直接看到反馈价值与已忽略数量，同时保持首页简洁。
- 原因或分析：只在旧图表下新增多组卡片会继续堆叠信息；现有 generated 包含历史出现记录，不能直接作为当前有效发现的未标记分母。
- 处理与改进：规划最终收口为原“问题变化”升级“评审质量与处置”，默认反馈质量、次级保留问题变化；紧凑显示有帮助/误报/已修复反馈/未标记及当前已忽略，原项目/类别区域改造为优化方向，不新增重复报表。补充稳定身份有效发现集合、同集合分母、按发现产生日展示当前反馈而非历史评价量、缺失数据不可补零及真实下钻参数建设要求。完整方向以规划第 11 节为准，不是已经上线。
- 代码修改：本轮只修改规划并主动追加台账；业务代码、测试、数据库迁移、依赖及构建产物未改，全部既有改动保留。
- 本地验证：实际运行 `git diff --check` 通过；用 `.venv/bin/python` 核对规划文档本地 Markdown 链接，目标文件均存在。业务测试、构建、浏览器、真实数据库样本、读屏与生产性能未运行，不把文档检查等同于业务验收。
- 部署生效：未部署；未覆盖 frontend/dist，未重启真实 API、Worker 或 monitor，未写业务配置或反馈记录。
- 关联文件或证据：docs/overview-repair-plan.md 第 11 节；本轮文档检查终端输出；前两条所列源码证据。
- 遗留与下一步：用户确认实施后按 Q1–Q3 完成接口、图表、处置摘要和样本下钻，Q4 历史事件独立评审。追加后等待正常 monitor 周期并实际执行 `PYTHONPATH=backend .venv/bin/python -m ocr_manager.improvement_log_check --database .local-data/local/app.db --source-id PI-20261108-004 --minimum-entries 18`；只依返回报告同步，不强制采集或扩大授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：受理评审质量与处置可见化实施

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：用户确认按第 11 节规划实施，开始处理；沿用本编号前十八条，不另建独立事项。
- 现象或目标：默认展示有帮助、误报、已修复反馈与未标记，已忽略始终可见，保留问题变化并提供项目/类别样本下钻。
- 原因或分析：需先建立当前有效发现集合与统一分母，区分发现反馈和去重问题状态，不能用历史出现总量减反馈数。
- 处理与改进：按 Q1–Q3 补聚合/分页明细、首页质量图与处置摘要、优化方向和真实下钻，覆盖旧接口降级、权限与失败；可选反馈事件历史 Q4 不在本批。
- 代码修改：本轮尚未修改业务源码，仅追加受理；保留既有首页和设置页全部修改。
- 本地验证：已核对工作区与现有聚合/首页结构，本轮测试、构建、浏览器尚未运行，不引用历史结果为本轮通过。
- 部署生效：未部署；不覆盖 frontend/dist，不重启真实 API、Worker 或 monitor，不写正式反馈或配置。
- 关联文件或证据：用户本轮实施授权；docs/overview-repair-plan.md 第 11 节。
- 遗留与下一步：完成同集合计数与下钻后进行隔离测试、文档和来源同步核验；不扩大聊天采集授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：质量统计与首页主体实现，进入样本及最终验证

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：Q1–Q3 主体实现，正在补样本下钻与最终回归，不视为部署完成。
- 现象或目标：让人工反馈及已忽略默认可见，同时保持发现反馈和问题状态分别计数。
- 原因或分析：质量集合仅取当前终态根尝试和已验证有效补审主身份，旧初审镜像只计一次；历史生成数仍保留其原语义，不能充当质量分母。
- 处理与改进：新增质量读取模块与分页样本 API；首页默认质量堆叠图、四类反馈、比例分母、固定当前处置、项目/类别优化方向；样本 URL 保留项目、窗口、反馈、类别和分页，抽屉按需查询。旧 API 缺字段明确待升级，问题变化仍可切换。
- 代码修改：业务统计、首页相关组件/样式、服务类型、专项测试和 OpenAPI 已修改；无依赖或迁移，独立设置页既有改动保留。正补充样本严重级别筛选及文档，不提交 Git。
- 本地验证：实际首轮后端全量 `.venv/bin/pytest -q -rs` 742 passed / 1 skipped（外部 OCR CLI 探针未启用）；Ruff、Mypy（127 文件）、OpenAPI 契约通过。前端 tsc/lint/既有 169 项及新增质量 6 项分别通过；隔离构建成功，共享 JS 约 1145.23kB，保留大包警告。首页/导航隔离浏览器 9 passed，覆盖五档宽度，实际目视 1440px 与 390px 合成截图。新增筛选后仍需最终复验，不能沿用这些阶段结果宣称最终全绿。
- 部署生效：未部署；仅使用 /tmp/ocr-quality-dist、临时 SQLite 与 8791；未覆盖 frontend/dist，未重启真实 API、Worker、monitor。
- 关联文件或证据：backend/ocr_manager/review_quality.py；frontend/src/pages/overview/Quality*.tsx；/tmp/ocr-quality-backend-full.log、ocr-quality-build.log、ocr-quality-browser.log、ocr-quality-browser 截图。
- 遗留与下一步：完成同集合样本端到端、异常来源、重复补审及性能检查，更新指南和最终台账后再核验累计同步。不把真实读屏、生产负载或发布计为已验收。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：评审质量与处置实施完成，隔离验证通过，未部署

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：Q1–Q3 代码实施与范围内验证完成；关联本编号前十九条，未将隔离通过等同正式页面已生效。
- 现象或目标：首页默认展示有帮助、误报、已修复反馈、未标记和分子/分母，已忽略等问题处置固定可见；支持按项目/类别查看真实样本。
- 原因或分析：质量计数使用当前终态有效发现集合；初审按完成时间、有效补审主身份按来源出现时间入窗，同一镜像/附加重复来源/历史尝试不双计；问题状态按去重问题编号独立统计。
- 处理与改进：新增 `review_quality.py` 及 `/api/review-effectiveness/findings` 只读分页服务，提供质量趋势、类别/项目分组、严重级别筛选和来源待核实计数；首页接入默认反馈质量/问题变化切换、当前处置、优化方向表、Ant Design 样本抽屉；URL 保存窗口、项目、反馈、类别、级别、分页，旧接口缺字段不补零。同步操作指南、交互检查和 OpenAPI。
- 代码修改：修改后端效果聚合与测试、前端总览/API/质量组件/样式/单测/E2E、OpenAPI 与文档；无数据库迁移、依赖或外部调用，既有首页及设置页修改保留。Q4 反馈操作历史事件表未实施。
- 本地验证：实际 `.venv/bin/pytest -q -rs` **745 passed / 1 skipped**（外部 OCR CLI 探针未启用，已有 httpx 弃用提示）；`.venv/bin/ruff check backend`、`.venv/bin/mypy backend/ocr_manager`（127 文件）及 `PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract` 通过；前端 `npx tsc -b`、`npm run lint`、`npm test` **34 文件 / 175 项**通过；`npx vite build --outDir /tmp/ocr-quality-dist --emptyOutDir`成功，共享 JS 约 1,145.65kB / gzip 370.32kB，保留大包警告；隔离 Playwright 25 passed，覆盖首页五档宽度、样本抽屉 1440/390/320、失败重试、分页/URL 往返、真实临时 API 反馈读写回收和原有任务工作流。质量聚合合成 1 与 2000 条发现均 5 条 SQL，响应约 1186/1210 字节，本机约 1.17/21.19ms；仅为隔离证据，非生产 SLA。`git diff --check` 通过。
- 验证限制：之前一次样本级别选择器用例误定位 Ant Design 下拉，已改为键盘选择并复跑；没有用业务逻辑绕过。真实读屏、200% 放大、生产数据/负载、正式 API 与部署入口未测。
- 部署生效：未部署；未覆盖 `frontend/dist`，未重启真实 API、Worker、monitor，未修改正式反馈或配置。仅隔离 `/tmp/ocr-quality-dist`、临时 SQLite 与 8791 服务，服务已随 Playwright 退出。
- 关联文件或证据：`backend/ocr_manager/review_quality.py`；`backend/ocr_manager/review_effectiveness.py`；`frontend/src/pages/overview/QualityOverview.tsx`、`QualityTrend.tsx`、`QualityBreakdown.tsx`、`QualitySamples.tsx`；`frontend/e2e/overview.spec.ts`；`frontend/src/test/qualityOverview.test.tsx`；`docs/configuration-guide.md`；`docs/frontend-interaction-checks.md`；`/tmp/ocr-quality-final-browser`。
- 遗留与下一步：发布前需配套更新 API 与前端并用正式入口做一次真实数据验收；如要按“反馈操作日”趋势，另行评审 Q4 事件表迁移。等待 monitor 正常同步后执行本编号来源只读核验，不扩大聊天授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：受理反馈趋势并排柱优化

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：同一首页质量改进的后续体验优化，已受理，开始处理；关联本编号前二十一条。
- 现象或目标：用户希望参考图二，同一天显示多根独立柱，不将四类反馈堆叠在一起，并判断是否需要增加其他指标。
- 原因或分析：堆叠柱便于看总量，但未标记数量较大时，不利于直接比较其他反馈；问题处置和 Token 消耗不应混入同一反馈数量坐标。
- 处理与改进：计划改为有帮助、误报、已修复反馈、未标记四类并排柱，保留图例、精确数据表和独立处置摘要；窄屏保留局部横向阅读，不增加无关业务指标。
- 代码修改：本轮尚未修改业务代码，仅追加受理记录；既有全部改动保留。
- 本地验证：已读取现有图表、样式和验证入口；本轮测试、构建、浏览器尚未运行。
- 部署生效：未部署；不覆盖 frontend/dist，不重启真实 API、Worker 或 monitor，不写正式业务数据。
- 关联文件或证据：用户本轮两张参考截图；frontend/src/pages/overview/QualityTrend.tsx。
- 遗留与下一步：实现后验证柱位、比例和窄屏滚动，追加实际结果并执行本编号只读同步核验，不扩大聊天授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261108-004｜追加：反馈趋势并排柱完成，隔离回归通过，未部署

- 记录日期：2026-11-08（北京时间）。
- 类型与进展：本轮反馈图布局优化实施完成；关联本编号前二十二条，不覆盖既有堆叠柱规划及实施历史。
- 现象或目标：参考用户图二，在同一天独立显示多根反馈柱，避免堆叠妨碍比较，并明确其他指标是否应加入。
- 原因或分析：反馈数量可以共用数量坐标；已忽略是问题处置、Token 是成本，不能直接混入反馈分类。并排后纵轴应取单类最大值，不再取当天总量。
- 处理与改进：有帮助、误报、已修复反馈、未标记四类按固定顺序并排，共用零基线，零值不制造假柱；保留图例、UTC 每日/七天桶、精确数据表及样本下钻。窄屏只在图表内滚动，纵轴固定并支持聚焦后的方向键。覆盖率、误报占比和当前已忽略继续独立显示，本批不新增其他业务指标。
- 代码修改：修改 QualityTrend.tsx、overview.css 与首页 E2E/质量组件测试；更新操作指南、规划追加节及交互检查。无后端、数据库迁移或依赖改动；保留之前全部未提交修改，不提交 Git。
- 本地验证：实际运行前端 `npx tsc -b`、`npm run lint`、`npm test`，34 文件 / 176 项通过；`npx vite build --outDir /tmp/ocr-quality-grouped-dist --emptyOutDir` 成功，共享 JS 约 1145.83kB / gzip 370.39kB，保留既有大包警告。通过指定本机 Chrome 与隔离产物，实际 `npx playwright test e2e/overview.spec.ts e2e/navigation.spec.ts --output /tmp/ocr-quality-grouped-browser` 15 passed；测量四柱横向独立、共同基线与数值比例，覆盖五档宽度、键盘滚动/固定纵轴、7/90 天小数量/零值、原有筛选与样本/失败恢复；目视 1440px、320px 与 7 天小数量截图。`git diff --check`、三份修改文档的本地链接目标检查通过。后端本轮未改，未重跑后端全量测试；真实读屏、200% 放大、生产数据/负载/入口未验证。
- 部署生效：未部署；只生成 /tmp/ocr-quality-grouped-dist，浏览器使用临时 SQLite 与 8791，服务已随测试退出。未覆盖 frontend/dist，未重启真实 API、Worker、monitor，未写正式反馈或配置。
- 关联文件或证据：frontend/src/pages/overview/QualityTrend.tsx；frontend/src/styles/overview.css；frontend/src/test/qualityOverview.test.tsx；frontend/e2e/overview.spec.ts；docs/overview-repair-plan.md 第 13 节；/tmp/ocr-quality-grouped-browser.log 及同名目录截图。
- 遗留与下一步：正式页面需发布前端产物后按真实入口验收，不能将本轮隔离通过等同已经生效。等待正常 monitor 周期后实际执行 `PYTHONPATH=backend .venv/bin/python -m ocr_manager.improvement_log_check --database .local-data/local/app.db --source-id PI-20261108-004 --minimum-entries 23`；仅据返回报告同步结果，不扩大采集授权或强制同步。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261109-001｜受理：评审任务与跟进问题历史清理范围核对

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：独立数据维护请求，已受理/排查中；关联首页统计改进 PI-20261108-004，不混入其历史结论。
- 现象或目标：用户希望清理以前的数据，从今天开始重新计算统计，仅处理评审任务和跟进问题。
- 原因或分析：任务、反馈、去重问题、补审和投递存在关联；直接删除任务可能留下残留或触发旧事件重新生成。需明确北京时间当天边界和今天已有数据是否保留。
- 处理与改进：本轮仅只读核对现有清理能力、关联范围和统计口径，给出可执行边界，删除前明确确认；不将问题与改进台账视为待跟进问题。
- 代码修改：尚无业务代码修改，仅追加受理；保留已有全部工作区改动。
- 本地验证：已读取工作区状态并检索清理入口；尚未执行数据删除、业务测试或构建。
- 部署生效：未部署、未清理；未停止或重启服务，未修改正式业务数据或配置。
- 关联文件或证据：用户本轮请求；backend/ocr_manager/operations_api.py；docs/configuration-guide.md。
- 遗留与下一步：核对关联表和现有维护能力，明确历史重放及备份保护要求后请用户确认清理范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261109-001｜追加：历史清理边界核对完成，待确认后执行

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：本轮可行性与安全范围核对完成；仅方案，删除尚未授权到明确边界，未执行。
- 现象或目标：仅重置评审任务和待跟进问题的历史，使今天开始的新统计不再受历史评审影响，保留配置及其他模块。
- 原因或分析：现有 /api/maintenance/prune 只删旧工件、保留 SQLite 任务与统计，不能满足本请求。任务关联尝试、反馈、补审、有效结论、投递与问题出现记录；问题可能跨多次任务复用，不能只按问题首次发现日期整行删除。合并事件保留幂等事实，任务 ID 序列也不能回退；旧事件重新入队可能重新生成历史任务，执行前需核对在途和重试。
- 处理与改进：建议以北京时间 2026-11-09 00:00:00（UTC 2026-11-08 16:00:00）为清理边界，默认保留今日任务；备份后在受控维护窗口清理旧任务及关联本地记录，按保留出现记录重建跨日问题的统计边界，今天无保留来源的旧问题及处置记录一并清理。保留项目/模型/规则/飞书/账号配置、合并事件、合并前审查、运维审计、平台问题与改进和任务 ID 序列；不删除已发送到 GitLab/飞书的远端内容。若今日任务仍引用旧任务或在途依赖，先列明影响、再确认，不静默扩大范围。
- 代码修改：无业务代码或清理脚本修改，仅主动追加本事项两条台账，既有工作区修改保留。
- 本地验证：实际只读检查 operations_api.py、monitoring.py、storage.py、review_issues.py、review_finding_migration.py、review_recovery_migration.py、maintenance_migration.py 与 review_effectiveness.py；确认维护入口保留数据库历史、关联表与序列边界、当前问题与期间统计不同口径。将运行 `git diff --check` 及本编号至少两条来源同步核验；未运行数据删除、演练、业务测试、构建或正式库完整性检查，不宣称清理验证通过。
- 部署生效：不适用本轮方案；未部署、未备份、未清理，未停止或重启服务，未修改正式业务数据与配置。
- 关联文件或证据：上述只读源码与 docs/deployment.md 备份说明；用户本轮请求；本编号首条受理。
- 遗留与下一步：请用户确认“保留今天数据，清理北京时间今天零点之前的评审任务及关联跟进数据”；确认后核对本机实际服务/数据目录、关联影响数量和在途任务，先做受保护备份及隔离演练再清理，不清空整库、不重置身份序列。等待正常 monitor 同步并执行只读核验，结果如实向用户说明，不扩大聊天采集授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261109-002｜受理：代理域名配置保存返回 502 及同类接口排查

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：用户反馈的新独立问题，已受理/排查中。
- 现象或目标：截图显示编辑飞书配置保存时提示管理服务或访问代理返回 502，本地运行正常；用户要求检查其他接口并一并处理同类问题。
- 原因或分析：尚未确认，需核对浏览器请求、代理转发、后端路由及错误处理，不凭截图认定保存成功或失败。
- 处理与改进：先登记，再检查修改类接口及代理配置，按实际证据修复并增加自动化回归。
- 代码修改：尚未修改业务代码；保留开始时已有的未提交改动。
- 本地验证：已读取项目约定、规范、台账和工作区状态；尚未运行业务测试或代理复现。
- 部署生效：未部署，未重启服务，未写正式业务配置。
- 关联文件或证据：用户本轮截图；docs/problem-improvement-log.md。
- 遗留与下一步：定位差异，验证受影响接口，追加实际进展并运行来源同步核验；不扩大聊天采集授权。
- 同步状态：{"kind":"problem","category":"integration","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261109-002｜追加：复现穿透入口带请求体 PATCH 断连，开始兼容修复

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：定位到传输方法差异，修复中；关联本编号受理记录。
- 现象或目标：本机带 JSON 的 PATCH 返回正常 404/422；同一 HTTP 穿透入口带 JSON 的 PATCH 返回 RemoteProtocolError/ReadError；无请求体 PATCH 可返回后端 404。POST、PUT、DELETE 的无效输入或不存在目标探测正常到达后端。
- 原因或分析：证据指向穿透链路对带请求体 PATCH 的处理异常，非飞书外部调用；截图中的 502 是网关错误，不能据此认定写入失败。HTTPS 探测还返回无后端请求 ID 的网关 403，不能假定当前域名已具备可用 HTTPS。
- 处理与改进：计划给全部五类 PATCH 编辑资源增加共用同一处理函数的显式 POST 更新入口，前端改走兼容入口，保留原接口及权限、校验和错误不重试边界；PUT/DELETE 不据此盲目改动。
- 代码修改：本阶段尚未修改业务代码；既有未提交改动保留。
- 本地验证：实际使用 httpx、trust_env=False 对比本机与配置中的穿透入口，只发送不存在目标、空对象或必然无效的输入；没有更改正式飞书/模型/仓库配置，探测产生正常管理审计记录。只读核对 SQLite 最近飞书审计及五类 PATCH 路由。
- 部署生效：未部署、未重启服务；尚无修复生效结论。
- 关联文件或证据：backend/ocr_manager/api.py、auth.py、review_issues.py；frontend/src/pages/FeishuHooksPage.tsx；本轮脱敏探测输出。
- 遗留与下一步：增加路由等价、鉴权和客户端回归，隔离构建验证；发布后仍需通过真实入口核验，不将当前复现等同已修复。
- 同步状态：{"kind":"problem","category":"integration","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261109-002｜追加：同类编辑接口兼容完成，隔离回归通过，尚未部署

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：本轮代码修复及隔离验证完成；关联本编号前两条，线上入口尚未发布验收。
- 现象或目标：修复穿透入口带请求体 PATCH 断连引起的飞书保存故障，检查其他编辑接口，避免只修提示文字。
- 原因或分析：实际对比确认本机带 JSON PATCH 正常返回，现有 HTTP 穿透入口对同类请求断连；POST、PUT、DELETE 安全探测能到达后端。无请求体 PATCH 也能返回，因此不是后端完全不支持 PATCH；尚未取得隧道内部日志，不能进一步断定其具体组件缺陷。模型编辑已有 POST 兼容，其他四类未覆盖。
- 处理与改进：飞书、仓库基础接入/启停、账号、问题状态增加与原 PATCH 共用处理函数的 POST 更新入口，四处页面同步改用 POST；保留模型已有兼容、原 PATCH、权限、请求校验、凭据省略、管理员保护、撤销会话、问题事件和审计。PUT、DELETE 与 webhook 不盲目改写，不增加失败自动重试。更新 OpenAPI 及部署说明。
- 代码修改：修改 backend/ocr_manager/api.py、auth.py、review_issues.py 和对应前端四个页面；增加 test_proxy_updates.py、feishuProxy.test.tsx，扩展既有生命周期测试及浏览器工作流。无数据库迁移、新依赖或真实外部调用；保留开始时全部未提交修改，未提交 Git。
- 本地验证：最终实际 `.venv/bin/pytest -q -rs` 757 passed / 1 skipped（未启用外部 OCR CLI 探针，保留已有 httpx 弃用提示）；`.venv/bin/ruff check backend`、`.venv/bin/mypy backend/ocr_manager`（127 文件）、`PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract`、`git diff --check` 均通过。前端 `npm test` 35 文件 / 178 项通过，`npm run lint`、`npx tsc -b` 通过；新增飞书测试修正类型后单独复跑 2 项通过。`npx vite build --outDir /tmp/ocr-proxy-compat-dist --emptyOutDir` 成功，保留既有共享 JS 约 1145.83 kB / gzip 370.39 kB 大包警告。指定本机 Chrome 及隔离产物实际运行 `npx playwright test e2e/workflows.spec.ts --output /tmp/ocr-proxy-compat-browser` 10 passed；网络层显式拒绝 PATCH，验证仓库编辑/恢复/删除、飞书 POST 编辑/删除、账号编辑与只读模式、原有评审/反馈及窄屏流程。后端校验五类路由共用处理函数、请求模型及依赖，并覆盖未登录/只读拒绝、凭据保留、无效飞书输入不写入、最后管理员及会话撤销、问题状态与审计。
- 排查与无效尝试：首轮新增测试错误引用内部字段，已修正为公开 OpenAPI 模型及实际密文字段；首轮全量因本轮未同步台账 category 使用不合法 bug 失败，核对本编号未导入后仅将本轮两条修为 integration，未改已同步历史。第二轮全量出现 OCR 退出子进程 killpg PermissionError，未改无关进程代码；该组及相关测试单独 60 项通过，最终无并发负载重跑全量 757 项通过，不能据此保证运行环境不再抖动。新增前端测试的 exact 类型错误已修正并重跑类型检查。
- 部署生效：未部署；未覆盖 frontend/dist、未重启真实 API、Worker 或 monitor；隔离浏览器使用临时 SQLite/8791，随测试退出。安全探测没有修改正式业务配置，只产生正常管理审计。不宣称当前域名保存已恢复；前后端须配套发布，不能只换前端或直接使用未更新的运行中 API。
- 关联文件或证据：backend/tests/test_proxy_updates.py；backend/tests/test_notification_targets.py；frontend/src/test/feishuProxy.test.tsx；frontend/e2e/workflows.spec.ts；docs/deployment.md；/tmp/ocr-proxy-backend-final.log；/tmp/ocr-proxy-compat-browser。
- 遗留与下一步：发布须先核对现有未发布改动与业务运行状态，避免顺带发布用户其他工作；随后通过真实穿透入口验收。当前 HTTP 域名未提供传输加密，HTTPS 探测为网关 403，不以本次兼容冒充 HTTPS 已修复。等待正常 monitor 同步后对本编号三条运行只读核验；不新增绑定、不强制导入、不扩大聊天授权。
- 同步状态：{"kind":"problem","category":"integration","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}
### PI-20261109-003｜受理：发现卡片区分忽略与误报并优化阅读层级

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：用户提出的新独立改进，已受理/排查中。
- 关联记录：无。
- 现象或目标：任务发现卡片只有有帮助、误报、已修复操作，用户希望单独忽略而不等同误报；描述拥挤，希望用分类、顺序、颜色和留白突出重点。
- 原因或分析：截图显示长段落与操作区层级较弱；具体状态与接口边界待核对，不以截图推断业务事实。
- 处理与改进：先登记，随后核对发现反馈与问题处置模型，在既有灰白蓝视觉和 Ant Design 规则内优化，保护原始描述及权限边界。
- 代码修改：尚未修改业务代码；本次仅追加受理，保留开始时已有的未提交改动。
- 本地验证：已读取项目约定、前后端规范、台账及工作区状态；尚未运行本事项业务测试、构建或浏览器验证。
- 部署生效：未部署，未重启服务，未修改正式业务数据或配置。
- 关联文件或证据：用户本轮三张截图；frontend/src/pages/FindingsPanel.tsx；docs/problem-improvement-log.md。
- 遗留与下一步：核对忽略与误报语义，实施卡片改进及自动化验证，完成后追加进展并核验来源与页面同步；不扩大聊天采集授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}


### PI-20261109-003｜追加：完成方案核对，发现并行修改后停止实施待确认

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：阶段方案核对完成，业务实现未开始；发现执行期间的外部修改后停止，等待用户指示。
- 关联记录：PI-20261109-003 首条受理；并行追加涉及 PI-20261109-002，不合并两项业务结论。
- 现象或目标：新增独立忽略操作，同时降低发现描述密度、突出分类和重点。
- 原因或分析：现有反馈仅含 helpful、false_positive、fixed，问题处置另有 ignored；可以复用问题批量更新接口以单项目标及 expected_status 独立提交忽略，不新增误报反馈。描述目前直接展示长段原文。期间再次读取台账时发现 PI-20261109-002 新增了本轮未写入的收尾记录；依照执行约束停止业务编辑，避免干扰并行工作。
- 处理与改进：拟保留灰白蓝设计与现有字体，使用 Ant Design 操作与筛选；为发现增加原始序号和已有类别，按已有标签划分触发条件、代码依据、实际后果、修复建议和补充，重点区分后果与建议，并增加行距和留白；展示分区不改写模型原始描述。忽略只改问题状态，不新增或替换发现反馈。上述均为方案，尚未实施。
- 代码修改：未修改业务代码或样式；本轮仅主动追加本事项两条台账，保留初始及并行工作区改动。
- 本地验证：实际只读检查 FindingsPanel.tsx、JobDetailPage.tsx、EffectiveReview.tsx、reviewIssues.ts、review_issue_actions.py、review_finding_feedback.py 与 feedback_issues.py，确认反馈与处置的接口边界；未运行单元测试、构建、浏览器回归或部署验收。收尾执行本编号至少两条的只读来源同步核验，结果以命令输出为准。
- 部署生效：未部署，未覆盖 frontend/dist，未重启 API、Worker 或 monitor，未修改正式业务配置与评审数据。
- 关联文件或证据：用户本轮截图；上述只读源码；本轮前后读取台账时 PI-20261109-002 条目数量发生变化。
- 遗留与下一步：请用户确认是否允许在保留并行改动的前提下继续本事项；确认后重新核对文件状态，只实施本事项并增加语义、并发、权限和响应式验证。当前不宣称实现完成或验证通过；不新增聊天绑定、不强制同步、不扩大采集授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"planned","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261109-003｜追加：用户确认保留并行改动后继续实施

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：用户已明确回复继续，恢复本事项实施。
- 关联记录：PI-20261109-003 前两条。
- 现象或目标：按已确认的独立忽略、描述分区及留白方案实施。
- 原因或分析：重新核对工作区，发现卡片和两个详情调用入口保持此前读取版本；已知并行改动继续保留，不覆盖其他事项。
- 处理与改进：复用带状态快照的问题处置接口，不扩充误报反馈类型；为初审与有效结论提供同一处置入口，增加确认、失败保留与相关缓存刷新。
- 代码修改：本阶段尚未修改业务代码，仅追加恢复进展。
- 本地验证：实际重新读取 git status、FindingsPanel.tsx、EffectiveReview.tsx、reviewIssues.ts 和现有测试；本轮业务验证尚未运行。
- 部署生效：未部署，未重启服务，未修改正式业务数据或配置。
- 关联文件或证据：用户本轮“是的，继续”；本编号前两条。
- 遗留与下一步：完成实现、自动化及浏览器验证后追加结果，再运行本编号完整条数的只读同步核验；不扩大采集授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261109-003｜追加：独立忽略与描述层级本地实现、回归完成，尚未部署

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：用户确认继续后的本轮实现与本地验证完成；关联本编号前三条，正式发布尚未执行。
- 关联记录：PI-20261109-003；保留并行事项已有改动，不合并其验收与部署结论。
- 现象或目标：将本次不处理与认为发现有误区分，缓解发现描述拥挤、缺少重点与分类的问题。
- 原因或分析：原有卡片只有 helpful、false_positive、fixed 反馈；ignored 属于关联问题的独立处置，不应新增为误报反馈。原始描述整段展示、操作按钮连在一起，缺少阅读层级；独立人工决定不会被原反馈接口覆盖，忽略后需要先恢复再确认修复，避免仅改反馈却暗示处置已变更。
- 处理与改进：新增忽略及恢复待处理，复用现有单目标批量处置 POST 与 expected_status 快照，冻结确认目标、提示共享问题影响、支持选填说明；失败保留说明、不自动重试，不新增、替换或撤销既有反馈。初审与有效补审统一接通，使用已解析问题编号，不误投聚合下标；成功刷新任务、问题及总览。确认期间锁定筛选，轮询使目标不再符合待处理条件时仍保持卡片与说明，取消后再应用新状态。按钮按反馈/处置分组；发现显示原始序号、严重级别及已有类别。描述只按明确行首标签分区，保持来源顺序，后果用浅橙、建议用浅蓝；增加行距、段距与卡片留白，代码标识单独展示，未知段落及不可信 HTML 保持文本，不改写持久化原文。
- 代码修改：修改 FindingsPanel.tsx、JobDetailPage.tsx、EffectiveReview.tsx；新增 FindingActions.tsx、FindingDescription.tsx、findingContent.ts、useFindingDisposition.ts 与 findings.css，通用交互采用 Ant Design。新增前后端回归与浏览器专项，扩展有效补审组件测试，追加可执行检查说明。未修改后端业务接口、数据库结构、Worker 或外部调用；未提交 Git，保留开始时全部无关改动。
- 本地验证：最终实际 `npm --prefix frontend run lint` 对应前端目录 `npm run lint`、`npx tsc -b`、`npm test` 均通过（37 文件、193 项）；`.venv/bin/pytest -q backend/tests/test_finding_disposition.py backend/tests/test_feedback_issues.py backend/tests/test_issue_batch.py backend/tests/test_review_finding_feedback.py` 53 passed，覆盖原有事务/权限/幂等、独立忽略与恢复保持四类既有反馈、共享任务状态、并发拒绝、补审稳定反馈及同集合质量计数不变，保留既有 httpx 弃用提示。`.venv/bin/ruff check backend/tests/test_finding_disposition.py` 与 `git diff --check` 通过。前端目录 `npx vite build --outDir /tmp/ocr-findings-dist --emptyOutDir` 成功，共享 JS 约 1145.92 kB / gzip 370.44 kB，保留既有大于 500 kB 警告。显式使用本机 Chrome、OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-findings-dist，最终 `npx playwright test e2e/findings.spec.ts e2e/workflows.spec.ts e2e/navigation.spec.ts --output /tmp/ocr-findings-final-browser` 17 passed；覆盖真实临时 SQLite 处置/取消/恢复/刷新、原有误报与修复工作流、只读界面、键盘确认/Escape/焦点返回、1440/768/390/320 像素无整页横溢和按钮不重叠。已查看最终桌面卡片、390 像素分区及此前同版布局的 320 像素卡片/确认截图。impeccable detect 对修改展示文件返回空数组；扫描不代替语义与视觉验收。
- 排查与无效尝试：新增测试初次误用旧初审响应不存在的 finding_feedback 字段，改用 SQLite 镜像事实并补充真实补审响应验证；组件测试初次受 Ant Design 双中文自动空格、加载图标可访问名称及 Portal 替换旧节点影响，补充稳定 aria-label 并重新查询当前节点；修正测试不支持的 exact 参数、未使用参数及 Python 导入排序后重跑通过。后续针对轮询筛选卸载确认草稿的风险增加保留卡片与冲突回归，最终结果为上述最新运行，不把初轮失败冒充通过。
- 部署生效：未部署；未覆盖 frontend/dist，未重启真实 API、Worker 或 monitor，未修改正式评审状态、配置或外部 GitLab/飞书记录。浏览器只操作临时 SQLite/8791 隔离服务，测试结束服务退出。本地构建与验证不能替代正式入口生效确认。
- 关联文件或证据：上述前端文件；backend/tests/test_finding_disposition.py；frontend/src/test/findingDisposition.test.tsx、findingContent.test.tsx、reviewRecovery.test.tsx；frontend/e2e/findings.spec.ts；docs/frontend-interaction-checks.md；/tmp/ocr-findings-final-browser；/tmp/ocr-findings-build.log。临时文件不承诺长期保留。
- 遗留与下一步：发布前仍需核对并行未发布改动及正式环境，避免顺带上线其他工作，再验收真实页面；本轮未运行全量后端、全量浏览器、真实读屏、200% 浏览器放大、生产数据或负载验证。等待既有 monitor 同步并对本编号四条运行只读核验；不新增聊天绑定、不强制导入、不扩大采集授权，不宣称语义零遗漏。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261109-003｜追加：受理去除按钮前反馈与处置标签

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：同一发现卡片改进的后续微调，已受理；关联本编号前四条，不覆盖已同步历史。
- 关联记录：PI-20261109-003。
- 现象或目标：用户要求去掉操作区的“反馈”“处置”文字，只保留按钮。
- 原因或分析：此前分组标签增加了操作区的文字密度；本轮只简化呈现，不合并忽略与误报语义。
- 处理与改进：拟移除可见分组标签，统一按钮间距，窄屏自然换行；保留原操作顺序、权限、确认及状态逻辑。
- 代码修改：本轮尚未修改业务代码或样式，仅主动追加受理；保留既有全部未提交改动。
- 本地验证：已核对工作区与本编号历史；本轮针对性测试、类型检查及浏览器验证尚未运行。
- 部署生效：未部署，未覆盖 frontend/dist，未重启服务，未修改正式业务数据或配置。
- 关联文件或证据：用户本轮请求；frontend/src/pages/FindingActions.tsx；frontend/src/styles/findings.css。
- 遗留与下一步：实施小范围展示调整，运行针对性验证并追加实际结果，再核验本编号六条来源同步；不扩大聊天采集授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261109-003｜追加：操作区仅保留按钮，针对性验证完成，未部署

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：用户后续展示微调实现和本地验证完成；关联本编号前五条，不覆盖历史结论。
- 关联记录：PI-20261109-003。
- 现象或目标：去掉发现操作区的“反馈”“处置”文字，只保留按钮，减少视觉密度。
- 原因或分析：分组标签和分组容器并非操作必需；展平按钮布局后可以统一间距并在窄屏自然换行，无须调整忽略与误报的业务语义。
- 处理与改进：移除两处可见标签和分组容器；按钮继续按有帮助、误报、忽略、已修复排列，恢复待处理和同步处理仍按原条件显示。保留可访问名称、按钮状态、权限、确认目标及全部提交逻辑。
- 代码修改：仅调整 FindingActions.tsx 的展示结构与中文说明、findings.css 的按钮间距和窄屏布局，删除不再使用的分组样式；追加交互检查说明。未改后端业务、接口、数据库或依赖，保留既有无关改动，未提交 Git。
- 本地验证：实际运行 `npm --prefix frontend run lint`；前端目录 `npx tsc -b`、`npm test -- --run src/test/findings.test.tsx src/test/findingDisposition.test.tsx`，2 文件 / 16 项通过；`npx vite build --outDir /tmp/ocr-findings-buttons-dist --emptyOutDir` 成功，共享 JS 1145.92kB / gzip 370.44kB，保留既有大于 500kB 警告。指定本机 Chrome 和 OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-findings-buttons-dist，实际 `npx playwright test e2e/findings.spec.ts --output /tmp/ocr-findings-buttons-browser` 5 passed，覆盖独立忽略/取消/恢复/刷新、1440/768/390/320px 无整页横溢或按钮重叠、Escape 和焦点返回；已目视最终桌面卡片及 320px 截图。代码修改后 `git diff --check` 通过，检索确认旧分组类已无引用；追加文档后再运行差异检查及本编号六条的只读同步核验。未重跑后端或前端全量测试，未验证真实读屏、200% 放大或正式入口。
- 部署生效：未部署；仅生成 /tmp 隔离产物，未覆盖 frontend/dist，未重启真实 API、Worker 或 monitor，未修改正式业务数据与配置；浏览器使用临时 SQLite/8791，测试结束后退出。
- 关联文件或证据：frontend/src/pages/FindingActions.tsx；frontend/src/styles/findings.css；docs/frontend-interaction-checks.md；/tmp/ocr-findings-buttons-browser，临时证据不承诺长期保留。
- 遗留与下一步：正式生效仍需发布前端并经真实入口验收。等待正常 monitor 周期后实际执行 `PYTHONPATH=backend .venv/bin/python -m ocr_manager.improvement_log_check --database .local-data/local/app.db --source-id PI-20261109-003 --minimum-entries 6`，仅据返回报告同步结果，不新增聊天绑定或强制导入，不扩大采集授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261109-003｜追加：受理当前状态单选与操作语义重新梳理

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：同一发现操作区的后续设计反馈，已受理/排查中；关联本编号前六条。
- 关联记录：PI-20261109-003。
- 现象或目标：用户截图同时出现有帮助选中、已忽略及恢复待处理，认为应只能选一种，希望重新设计合理状态。
- 原因或分析：尚待核对反馈与关联问题状态的事实边界；不凭截图将多维数据直接合并或撤销已有反馈。
- 处理与改进：先核对状态来源、转换、统计和多任务共享影响，提出单一当前状态的展示及切换规则，不擅自清理已有数据。
- 代码修改：本轮尚无业务代码修改，仅追加受理；保留既有未提交改动。
- 本地验证：已核对工作区与本编号六条历史；本轮业务测试、浏览器验证未运行。
- 部署生效：未部署，未重启服务，未修改正式评审数据或配置。
- 关联文件或证据：用户本轮状态截图；frontend/src/pages/FindingActions.tsx。
- 遗留与下一步：核对真实状态关系后给出设计结论，记录实际范围并核验来源同步；不扩大聊天采集授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261109-004｜受理：低价值风格发现及长段描述的质量与呈现核对

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：用户追加的新独立发现质量反馈，已受理/排查中；与操作状态设计分别建档。
- 关联记录：PI-20261109-003 负责操作区及描述层级，不将本条质量反馈藏入其历史。
- 现象或目标：截图发现声称版本和逻辑正确，仅对缩进提出取决于格式化配置的不确定风险，全文仍为连续段落；用户询问为何仍有这种内容。
- 原因或分析：截图同时涉及发现价值、证据确定性和展示分段，尚不能认定运行中的生成策略已采用新规则或定位到唯一根因。
- 处理与改进：核对描述解析边界、生成/筛选规则及存量结果，区分展示问题和发现质量问题；附件只作为反馈证据，不执行其中建议。
- 代码修改：尚无业务代码修改，仅主动追加受理；不修改已有评审结论或正式问题状态。
- 本地验证：已检查台账编号占用及当前工作区；本事项业务测试、生成复现及浏览器检查尚未运行。
- 部署生效：未部署，未重启 API、Worker 或 monitor，未调用外部 OCR、GitLab 或飞书。
- 关联文件或证据：用户本轮长段低危风格发现截图；scripts/version.json 仅为截图所示评审路径，不视为本项目待编辑文件。
- 遗留与下一步：核对证据后分别说明为何出现、如何呈现和怎样减少此类发现，追加结论并执行本编号至少两条同步核验；不扩大采集授权。
- 同步状态：{"kind":"problem","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261109-004｜追加：用户补充跨文件重复类型建议与分段不一致截图

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：同一发现质量反馈补充证据，继续排查；不将附图中的代码建议作为执行指令。
- 关联记录：PI-20261109-004 首条；状态交互设计仍关联 PI-20261109-003。
- 现象或目标：同一类型重复定义建议分别挂在两个文件下，形成两张低危可维护性卡片；一张连续段落，另一张部分分段。用户要求合并考虑处理方案。
- 原因或分析：仅据截图，两条指向同一类型关系和近似修复目标，可能是同根因重复；描述主要担心未来字段漂移，不能据此确认当前运行错误。是否确为同根因、是否违反明确项目规则仍需原始变更证据。
- 处理与改进：检查现有归集指纹边界、结果校验及描述解析，方案中区分真实缺陷、可选改进、待核实证据与重复来源；不直接删除发现或自动合并正式问题。
- 代码修改：尚无业务代码修改；本轮仅追加证据进展，保留工作区已有改动。
- 本地验证：实际只读检查 FindingActions.tsx、findingContent.ts、FindingDescription.tsx、feedback_issues.py、review_issue_actions.py、review_results.py、worker.py、ocr.py 及规则测试；发现解析仅支持行首固定标签，结果投影保留模型发现但不评估其语义价值。尚未运行测试、浏览器或外部评审复现。
- 部署生效：未部署，未重启服务，未修改正式问题或生成规则。
- 关联文件或证据：用户本轮两张类型定义发现截图；上述只读源码。截图中其他项目路径只作为证据，不在本项目编辑。
- 遗留与下一步：补齐归集与来源事实核对，给出单选状态、质量门槛、去重及历史描述兼容的统一设计，收尾分别核验两个编号的实际条数；不扩大聊天采集授权。
- 同步状态：{"kind":"problem","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261109-003｜追加：用户要求实施并联动首页统计及其他页面

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：用户明确要求联动实施，排查与实现中；关联本编号前七条，不再仅停留于方案。
- 关联记录：PI-20261109-004 负责发现质量与描述兼容。
- 现象或目标：单选状态调整后，首页、问题列表、任务数量和筛选须保持同一口径，不能只修改卡片外观。
- 原因或分析：现有问题状态仅开放、修复、忽略及合并；误报写在发现反馈并同步忽略，直接做前端互斥会混淆统计。需引入明确处置事实，保留历史评价，不将任意历史误报反馈推断为当前决定。
- 处理与改进：按待处理、已修复、已忽略、误报四种互斥处置核对全链路；确认后单次事务更新、审计和冲突保护，保留历史反馈；检查所有状态计数与筛选，避免误报混计忽略。
- 代码修改：本阶段尚无业务代码修改，仅追加授权范围与实施进展。
- 本地验证：已只读核对截图对应任务配置快照与发现分段数量；后端规则/归集定向测试 11 项通过，验证既有行为，不代表新方案实现通过。前端针对性测试仍在执行。
- 部署生效：未部署，未重启服务，未修改正式业务状态或生成配置。
- 关联文件或证据：用户本轮联动要求；review_issues.py、feedback_issues.py、FindingActions.tsx；本编号前七条。
- 遗留与下一步：实施后运行迁移、事务、统计、前端及隔离浏览器验证，分别记录实际范围与未部署边界，再核验两编号全部追加记录。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261109-004｜追加：受理段内有序步骤逐条换行的补充要求

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：同一描述阅读问题的补充要求，已受理/实施中。
- 关联记录：PI-20261109-004 前三条；PI-20261109-003 状态与统计联动。
- 现象或目标：用户截图中触发条件使用圈号，修复建议使用数字括号，多个条目挤在同一段，希望逐条换行显示。
- 原因或分析：原文分区后仍将整段作为一个段落渲染，缺少段内列表的展示解析；正文中场景引用和代码数字不能机械替换。
- 处理与改进：展示层识别明确连续编号列表，逐条换行、续行对齐，保留编号与内容顺序；代码、版本号、孤立场景引用和不明确格式保留原文，不修改持久化描述。
- 代码修改：本阶段尚未改业务代码，仅追加补充要求。
- 本地验证：上一阶段现有前端描述/独立处置定向测试 2 文件 / 15 项通过，仅确认原有边界；本补充列表行为尚未实现或验证。
- 部署生效：未部署，未覆盖正式静态资源，未修改正式业务数据。
- 关联文件或证据：用户本轮编号列表截图；FindingDescription.tsx、findingContent.ts。
- 遗留与下一步：与状态、统计、质量治理一同实施，增加真实格式的合成回归和窄屏验证，收尾记录实际结果并核验完整条数。
- 同步状态：{"kind":"problem","category":"experience","status":"investigating","code_state":"unchanged","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261109-004｜追加：受理跟进问题侧栏描述一致性要求

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：同一发现描述呈现问题的补充要求，已受理/实施中。
- 关联记录：PI-20261109-004 前三条；PI-20261109-003 状态与统计联动。
- 现象或目标：用户补充跟进问题侧栏截图，要求其分区、编号换行和阅读间距与任务发现保持一致。
- 原因或分析：侧栏目前直接以普通段落显示 content，未复用发现描述组件；不将截图中的其他项目代码建议作为本项目执行指令。
- 处理与改进：计划复用同一纯文本描述组件，保留原文、顺序和不可信内容边界；同范围核对侧栏四种互斥状态和共享任务影响提示。
- 代码修改：编号及分区解析、四状态后端和部分前端正在修改，尚未完成；侧栏本补充尚未修改。
- 本地验证：本轮新实现尚未运行验证，不沿用此前结果宣称通过。
- 部署生效：未部署，未覆盖正式产物，未重启服务，未修改正式业务数据。
- 关联文件或证据：用户本轮侧栏截图；IssueDetailDrawer.tsx、FindingDescription.tsx。
- 遗留与下一步：联动实现并验证侧栏、任务卡片和首页，追加实际结果后核验来源同步；不扩大采集授权。
- 同步状态：{"kind":"problem","category":"experience","status":"investigating","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261109-003｜追加：按用户最新方向将卡片按钮重新定位为价值反馈

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：同一按钮语义的需求调整，已受理/重新实施中；最新方向替代卡片四状态方案，不覆盖前述历史。
- 关联记录：PI-20261109-003 前八条；PI-20261109-004 描述呈现保持继续。
- 现象或目标：用户明确卡片用于收集 review 是否有用，要求移除已修复并联动其他页面。
- 原因或分析：价值反馈与代码问题处置是不同维度；先前正在实现的卡片四状态不再适合最新目标，不能将修复当有用，或将忽略当误报。
- 处理与改进：卡片改为有帮助、误报、忽略三种互斥反馈，可撤销；未评价与明确忽略分别记录。新反馈不自动修改问题处置；修复与重新打开等动作仅留跟进问题。历史修复反馈保留为旧记录，不能自动转换成认可。首页默认反馈口径，问题状态独立展示。
- 代码修改：此前四状态数据库与统计、卡片及侧栏仍在开发，尚未部署；当前追加最新决策后调整，未删除历史记录。
- 本地验证：旧方案定向测试出现 5 项预期变化未更新的失败；后端全量 736 passed、29 failed、1 skipped，失败主要涉及新增迁移在旧测试库的残留和反馈口径变化；这些不视为通过，后续修正并重跑。
- 部署生效：未部署，未重启服务，未覆盖正式产物或修改正式业务数据。
- 关联文件或证据：用户本轮按钮截图与新请求；FindingActions.tsx、IssueDetailDrawer.tsx、review_quality.py；/tmp/ocr-all-tests.log。
- 遗留与下一步：按新方向完成独立价值反馈、历史兼容、统计、权限和界面验证；记录实际结果及部署边界，再执行来源同步核验。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"modified","verification_state":"failed","deployment_state":"not_deployed"}

### PI-20261109-003｜追加：价值反馈与旧修复统计分离，进入最终回归

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：同一按钮语义调整继续实施，代码已修改，最终回归中；不覆盖既有同步历史。
- 关联记录：本编号前九条；PI-20261109-004 描述与生成质量治理。
- 现象或目标：发现卡片只表达 review 的有用性，不能让“已修复”继续充当评价选项或质量图表类别。
- 原因或分析：价值判断与问题处置相互独立；旧修复反馈既不能自动转为认可，也不能据此认定当前问题已修复。
- 处理与改进：卡片仅有帮助、误报、忽略三选一且可撤销；新反馈不修改问题状态。首页质量趋势、分组、样本和规则页统计不再单列修复反馈，历史 fixed 原值留存，当前价值视为未评价；旧筛选地址兼容为未评价。处置页面保留待处理、已修复、已忽略、误报以及确认审计。
- 代码修改：已调整三类反馈 API/写入约束、schema 50/51、问题状态统计、任务初审与有效补审入口、首页与规则页统计、类型、筛选、中文指南及回归用例；保留工作区其他已有改动，未提交 Git。
- 本地验证：本轮此前全量后端实际 767 passed / 1 skipped，Ruff、Mypy 129 文件、OpenAPI 通过；前端此前 lint、37 文件 / 207 项、TypeScript 与 /tmp/ocr-value-feedback-dist 构建通过。收窄旧修复统计后重新运行四份后端专项 48 passed，Ruff、Mypy 与 OpenAPI 再通过；前端专项 13 passed / 1 failed，失败是合成未评价从 3 变成 5 后纵轴预期仍为 4，现已修正为实际刻度 8，尚未重跑。最终全量与浏览器回归待执行，不以上述较早结果冒充最终通过。
- 部署生效：未完成配套发布；此前本轮曾执行默认构建并生成 frontend/dist，之后构建改用 /tmp 隔离产物。未重启业务 API、Worker 或 monitor，未迁移正式数据库、修改正式发现或问题；不能将单独静态构建视为整版部署生效。
- 关联文件或证据：FindingActions.tsx、FindingsPanel.tsx、QualityOverview.tsx、QualityTrend.tsx、QualitySamples.tsx、ReviewFeedbackPanel.tsx、review_quality.py、review_finding_feedback.py、storage.py；/tmp/ocr-value-feedback-pytest.log、/tmp/ocr-value-feedback-targeted.log。
- 遗留与下一步：重跑最终检查、隔离桌面与窄屏浏览器并目视，分别追加本编号和 PI-20261109-004 的真实结论；等待正常 monitor 周期并按实际来源条数只读核验，不强制同步、不扩大聊天范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"modified","verification_state":"failed","deployment_state":"not_deployed"}

### PI-20261109-003｜追加：隔离浏览器发现旧验收语义与弹窗定位冲突

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：同一反馈改造的最终回归进展，代码已修改，浏览器失败正在修正。
- 关联记录：本编号前十条；PI-20261109-004 描述与编号列表。
- 现象或目标：按价值反馈与问题处置分离的新规则验证任务、跟进问题、首页及旧入口，不沿用旧“误报同步关闭”预期。
- 原因或分析：首次隔离浏览器 25 passed / 7 failed；其中五项用未限定名称的 dialog 同时匹配 Ant Design Drawer 和确认 Modal，两项仍试图在发现卡片点击已修复或期待误报关闭问题。失败不能报为通过。
- 处理与改进：将确认定位限定为准确标题；任务列表回归改为进入跟进问题确认修复及恢复后返回原任务筛选；工作流断言反馈持久化且问题仍待处理。移除重复忽略配色声明，修正当前操作指南的旧修复统计与比例口径。
- 代码修改：本次仅调整浏览器验收、重复样式和中文指南；保留三按钮互斥及问题侧栏四状态实现，未修改正式数据。
- 本地验证：最终后端全量实际 767 passed / 1 skipped / 1 个 Starlette 弃用警告，日志 /tmp/ocr-value-feedback-pytest-final.log；Ruff、Mypy 129 源文件、OpenAPI、git diff --check 再次通过。前端 ESLint、37 文件 / 207 项、TypeScript 和 /tmp/ocr-value-feedback-dist 构建再次通过；共享 JS 1150.41 kB / gzip 371.09 kB，保留大包警告。修正后的隔离浏览器正在运行，尚不能宣称通过。
- 部署生效：未完成配套部署；本轮较早默认构建曾生成 frontend/dist，后续均为 /tmp 隔离构建。未重启真实 API、Worker、monitor，未迁移正式数据库，不能视为整版已生效。
- 关联文件或证据：frontend/e2e/findings.spec.ts、taskList.spec.ts、workflows.spec.ts；docs/configuration-guide.md；/tmp/ocr-value-feedback-browser.log、/tmp/ocr-value-feedback-browser-final.log。
- 遗留与下一步：获取修正后浏览器结果、检查桌面及手机截图，补审另用显式隔离模式；完成后追加真实收尾并等待正常 monitor 周期核验，不强制同步或扩展采集。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"modified","verification_state":"failed","deployment_state":"not_deployed"}

### PI-20261109-003｜追加：继续跨页与补审回归，保留实际失败记录

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：用户要求继续，沿用原事项排查和收尾，不新建需求编号。
- 关联记录：本编号前十一条；PI-20261109-004 阅读呈现。
- 现象或目标：确保反馈、问题处置、任务返回及补审的验收流程相互独立，不以合成状态残留冒充产品缺陷或通过。
- 原因或分析：第二轮浏览器 31 passed / 4 failed；首项在任务数据未就绪时点到页面通用跟进入口而非发现卡片链接，剩余失败受未恢复的临时问题状态影响。限定卡片入口、等待发现显示并显式准备合成状态后，第三轮 34 passed / 1 failed，失败为尝试删除不存在的反馈返回非成功；已移除不必要删除。补审与普通浏览器同时启动曾因同用 8791 被拒绝，补审尚未执行，不报告通过。
- 处理与改进：任务回归明确从发现卡片进入问题侧栏；相关流程准备临时问题为待处理，保留返回筛选验收。补审新增三按钮、忽略替换和撤销、不改变问题映射的断言，将在普通回归结束后串行启动独立夹具。
- 代码修改：修改 e2e/taskList.spec.ts、workflows.spec.ts、reviewRecovery.spec.ts；本次未改产品业务实现，未操作业务库或服务。
- 本地验证：ESLint 和 TypeScript 在追加补审断言后实际通过；35 项普通回归正在重跑。已目视隔离构建的桌面发现、320px 发现及问题侧栏、1440px 与 320px 首页截图；分区、四项编号逐条换行、按钮互斥与无整页横溢在已查看截图中符合要求。浏览器最终结论待后续记录。
- 部署生效：未完成配套部署；较早默认构建生成 frontend/dist 的事实不变，此后构建均用 /tmp，未重启真实 API、Worker、monitor 或迁移正式数据库。
- 关联文件或证据：/tmp/ocr-value-feedback-browser-final.log、/tmp/ocr-value-feedback-browser-complete.log、/tmp/ocr-value-feedback-browser-release.log、/tmp/ocr-value-feedback-recovery-browser.log；隔离截图目录 /tmp/ocr-value-feedback-browser-complete。
- 遗留与下一步：串行取得最终普通及补审结果；追加代码、本地验证与部署三维收尾，正常等待 monitor 并执行只读来源核验。真实模型生成、读屏及生产入口不在本轮验收范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"modified","verification_state":"failed","deployment_state":"not_deployed"}

### PI-20261109-003｜追加：价值反馈与问题处置分离完成本地回归

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：代码与本地回归阶段完成，部署待执行；不以本地通过替代运行实例生效。
- 关联记录：本编号前十二条；PI-20261109-004 描述、编号及质量约束。
- 现象或目标：发现卡片仅收集 review 是否有价值，移除已修复并使首页、筛选、规则反馈统计、任务列表和问题侧栏使用一致事实边界。
- 原因或分析：有帮助不等于修复，忽略不等于误报；价值反馈与问题处置独立，不能用历史修复反馈推断认可或当前修复。旧值只读兼容，新选择只接受三类。
- 处理与改进：有帮助、误报、忽略互斥且再点撤销，按钮前不显示反馈/处置分组。新反馈不会创建或修改问题处置；已修复仅保留在跟进问题四状态、确认、审计及独立问题统计。首页趋势、样本、优化方向和项目反馈统计移除旧修复类别，旧值当前分析归未评价，数据库原值不删除；旧固定筛选地址兼容未评价。误报比例只以有帮助与误报为分母，至少五条才显示百分比，不是模型准确率。
- 代码修改：前后端三类写入约束、schema 50/51、独立问题状态投影与审计、任务摘要、初审/有效补审、首页及规则页反馈统计、中文指南和回归用例已修改。保留工作区其他改动，未提交 Git；正式数据库未迁移。
- 本地验证：实际运行 PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q，767 passed / 1 skipped，外部 OCR CLI 探针未运行，保留 Starlette 弃用警告；.venv/bin/ruff check backend、.venv/bin/mypy backend/ocr_manager（129 文件）、PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract 均通过。frontend 中 npm run lint、npm test（37 文件 / 207 项）、npx tsc -b、npx vite build --outDir /tmp/ocr-value-feedback-dist --emptyOutDir 通过。使用该隔离产物及临时 SQLite，Playwright findings、overview、navigation、taskList、workflows、reviewFindingSources 六份用例共 35 passed；随后 OCR_BROWSER_REVIEW_RECOVERY=1 的 reviewRecovery 专项 12 passed，覆盖反馈替换、撤销、刷新及问题映射不变。已目视桌面与 320px 卡片、问题侧栏和首页；此前失败已在前两条保留，完整复验命令见 frontend-interaction-checks.md。
- 部署生效：未完成同版发布。此前默认构建曾生成 frontend/dist，后续构建均为 /tmp；未重启真实 API、Worker 或 monitor，未迁移正式数据库、修改真实发现或问题，不宣称整版生效。
- 关联文件或证据：FindingActions.tsx、FindingsPanel.tsx、IssueStateActions.tsx、IssueDetailDrawer.tsx、review_quality.py、storage.py、feedback_value_migration.py、issue_disposition_migration.py；/tmp/ocr-value-feedback-pytest-final.log、/tmp/ocr-value-feedback-browser-release.log、/tmp/ocr-value-feedback-recovery-browser-final.log；docs/frontend-interaction-checks.md、docs/overview-repair-plan.md 第 15.1 节。
- 遗留与下一步：共享 JS 1150.41 kB / gzip 371.09 kB，保留大包警告；真实读屏、200% 放大及生产入口未验证。后续授权发布时先备份并在副本验证迁移，再配套更新 API/Worker/前端并核验。现在等待正常 monitor 周期并执行 13 条来源只读核验，失败如实报告，不强制同步或扩大聊天采集。
- 同步状态：{"kind":"improvement","category":"experience","status":"resolved","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261109-004｜追加：任务与跟进问题描述统一并完成本地验证

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：描述呈现本地实施与回归完成；生成质量仅落实约束，真实模型效果仍待后续观察。
- 关联记录：本编号前四条；PI-20261109-003 最新三按钮及统计边界。
- 现象或目标：发现说明过于紧凑，明确区分触发条件、代码依据、实际后果和修复建议，连续 1、2、3、4 步骤逐条换行；跟进问题侧栏采用相同呈现，减少纯格式及假设性评审噪声。
- 原因或分析：原文整段显示缺乏层次；任务与侧栏不共用解析会出现展示差异。模型生成质量不能靠颜色、文字相似度或删除历史结果保证，须以当前证据和行动性约束生成。
- 处理与改进：两入口复用 FindingDescription 及纯文本解析，识别明确标签、连续编号并保留来源顺序；实际后果用风险底色，修复建议用蓝色底色，增加行距与段间距，窄屏自然重排。代码、版本号和不明确场景引用不机械拆分，HTML 不作为可信内容执行。版本化 finding_policy 约束接入后续初审/合并前背景与配置快照：排除纯格式、主观重构及无当前证据的未来风险，同根因同修复仅报一次；不同根因不自动合并，不删除历史发现。
- 代码修改：FindingDescription.tsx、findingContent.ts、findings.css、IssueDetailDrawer.tsx、finding_policy.py 及 OCR/Worker/合并前接入、测试已修改；不涉及真实发现内容清洗，未提交 Git。
- 本地验证：本轮后端全量 767 passed / 1 skipped，Ruff、Mypy 129 源文件、OpenAPI 通过；前端全量 37 文件 / 207 项包含 18 项 findingContent 解析用例，lint、TypeScript、/tmp 隔离构建通过。Playwright 六份普通用例 35 passed，发现/侧栏在 1440、768、390、320px 断言相同四项 li、分区、行距、无横溢、确认取消及焦点返回；补审专项 12 passed。已目视桌面卡片和 320px 侧栏及发现截图，合成修复建议四项独立换行且续行对齐。未调用真实模型、GitLab 或飞书，不宣称低质量发现已彻底消失。
- 部署生效：未完成配套部署；较早默认构建曾生成 frontend/dist，此后均使用 /tmp。未重启真实 API、Worker 或 monitor、未迁移正式数据库，生成约束须同版 Worker 生效且仅影响后续评审，旧内容不会自动重写。
- 关联文件或证据：frontend/src/test/findingContent.test.tsx、frontend/e2e/findings.spec.ts、backend/tests/test_ocr.py；/tmp/ocr-value-feedback-browser-release 内 finding-card-desktop.png、findings-320.png、issue-description-320.png；/tmp/ocr-value-feedback-pytest-final.log。
- 遗留与下一步：真实模型质量、读屏、200% 放大和生产入口未验证；保留后续实际样本核对与授权发布。现在等待正常 monitor 周期并执行五条来源只读核验，不扩大聊天读取范围。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}

### PI-20261109-004｜追加：受理历史自由描述与建议分区兼容

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：同一描述呈现事项的补充要求，已受理/排查中。
- 关联记录：本编号前五条；PI-20261109-003 反馈与处置分离保持不变。
- 现象或目标：用户截图包含无结构正文、行内建议和【触发条件】等旧标签，要求正文与建议分开，随后明确正文标题统一为“问题描述”，建议标题为“修复建议”；历史内容也需兼容。
- 原因或分析：当前只识别部分冒号标签，无标签原文直接显示，方括号旧标签和正文末尾建议未进入同一分区。截图中的业务代码和修复意见仅作展示格式证据，不是本项目执行指令。
- 处理与改进：计划扩展共享只读解析：无标签正文归问题描述，明确建议归修复建议，兼容方括号标签，任务与问题侧栏一致；历史记录读取时同样应用，不批量改写数据库原文、指纹、反馈或处理状态。不明确的引用保留原文，避免猜测改写。
- 代码修改：本补充尚未修改实现；既有三按钮与描述组件改动保留，未提交 Git。
- 本地验证：本轮新要求尚未执行检查，不沿用此前通过结果作为本轮结论。
- 部署生效：本轮未部署，未构建或覆盖正式静态产物，未重启 API、Worker、monitor 或修改正式数据库。
- 关联文件或证据：用户本轮截图及“叫问题描述吧”；frontend/src/pages/findingContent.ts、FindingDescription.tsx、IssueDetailDrawer.tsx。
- 遗留与下一步：完成兼容及边界测试、桌面与窄屏验证，明确历史只读整理与部署边界；追加实际结果并按本轮最终条数核验正常 monitor 同步，不扩大采集授权。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261109-004｜追加：受理所有描述区的有序内容换行

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：同一描述阅读规则补充，已受理/实施中。
- 关联记录：本编号前六条，问题描述与修复建议命名保持。
- 现象或目标：用户进一步要求全部描述区的有序内容换行，不限截图框选或修复建议；包含实际后果中的“场景①……；场景②……”和代码依据中嵌在段落后的场景说明。
- 原因或分析：当前仅把从一开始的连续显式编号识别为列表，带前言、场景前缀及跨区引用未处理；单独场景引用与实际分项需要区分，不能破坏代码、版本号或普通引用。
- 处理与改进：扩展共享展示的有序内容分块，支持前言后列表、场景分项、常见中英文编号并保持编号原值和内容；所有区及两入口共用，同样适用于历史读取，不改库中原文或业务状态。
- 代码修改：本补充尚未修改实现；此前受理后仍在设计边界，未提交 Git。
- 本地验证：本轮扩展规则尚未验证；将新增截图同类合成正例与代码/版本/引用反例，再做桌面和窄屏浏览器核对。
- 部署生效：未部署，未覆盖正式产物或操作业务服务及数据库。
- 关联文件或证据：用户最新有序内容截图；frontend/src/pages/findingContent.ts、FindingDescription.tsx 及相关测试。
- 遗留与下一步：与上一条历史分区补充一并实施验证，记录真实结果并按最终八条以上核验正常 monitor 同步。
- 同步状态：{"kind":"improvement","category":"experience","status":"investigating","code_state":"modified","verification_state":"not_run","deployment_state":"not_deployed"}

### PI-20261109-004｜追加：历史描述及所有分区有序内容统一展示完成本地验证

- 记录日期：2026-11-09（北京时间）。
- 类型与进展：本轮补充需求实施和本地验证完成，部署待执行；保留此前历史结论。
- 关联记录：本编号前七条；PI-20261109-003 价值反馈与问题处置分离不变。
- 现象或目标：所有描述区的有序内容均逐条换行，不限截图框选或修复建议；旧正文统一“问题描述”，明确建议归“修复建议”，历史数据及其他完整描述入口一致。
- 原因或分析：仅从一开始的连续列表解析不能覆盖前言后的编号和场景分项；任务、侧栏及历史报告对比若使用不同渲染会再次遗漏。独立建议及尾注不能错误继承上一项的编号，代码、版本和普通引用不能按数字机械拆开。
- 处理与改进：共享分块支持数字、圈号、中文及字母编号、跳号、非一开始的升序项、场景分项和前言后列表；各项独占一行、续行对齐。兼容冒号与括号旧标签，无标签正文归问题描述，明确建议集中为修复建议并与既有编号列表保留段落边界；不明确的文字仍留原处。任务卡片、跟进问题和历史报告新增/不再出现对比统一使用 FindingDescription。历史读取时适用，不批量写回数据库或改写下载报告。
- 代码修改：已修改 findingContent.ts、findingLists.ts、FindingDescription.tsx、findings.css、AttemptReports.tsx、对应组件和浏览器测试及配置指南；未改本轮后端业务实现，保留已有工作区变更，未提交 Git。另已只读核对两条本轮受理尚未导入但误置于旧条目之前，将这两条原文不变移至末尾；脚本逐一确认既有五条同步摘要和所有其他编号摘要不变，没有覆写已同步历史或页面事实。
- 本地验证：frontend 中实际执行 npm run lint、npm test（37 文件 / 227 项，其中解析 38 项）、npx tsc -b、npx vite build --outDir /tmp/ocr-history-description-dist --emptyOutDir，全部通过。PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH 指定本机 Chrome、OCR_BROWSER_FRONTEND_DIST 指向隔离产物，实际运行 npx playwright test e2e/findings.spec.ts --output /tmp/ocr-history-description-browser-final，5 passed，覆盖 1440/768/390/320px 三入口描述一致、所有区共 11 项逐条换行、建议独立段落、横溢、互斥反馈及处置确认；已目视桌面卡片、320px 卡片与历史对比，并查看本轮侧栏窄屏截图。git diff --check 通过。首次专项 16 passed / 2 failed 为旧不允许跳号预期，首次 TypeScript 有过滤器类型错误，均已修正复验；目视发现独立建议并入最后一项后也已修正补测。共享 JS 1150.41 kB / gzip 371.10 kB，保留大包警告。后端全量、补审专项、真实模型、读屏及正式入口本轮未运行，不沿用此前结果冒充本轮验证。
- 部署生效：未部署；本轮仅构建 /tmp 隔离资源，未覆盖正式产物，未重启真实 API、Worker 或 monitor，未迁移正式数据库或修改历史发现原文、指纹、反馈及问题状态。此前阶段曾默认生成 frontend/dist 的事实不变，不能据此宣称配套发布完成；旧记录的新展示须新版前端发布后生效。
- 关联文件或证据：frontend/src/pages/findingLists.ts、findingContent.ts、FindingDescription.tsx、AttemptReports.tsx；frontend/src/test/findingContent.test.tsx、frontend/e2e/findings.spec.ts；docs/frontend-interaction-checks.md；/tmp/ocr-history-description-frontend-final.log、/tmp/ocr-history-description-browser-final.log 及最终浏览器截图目录。
- 遗留与下一步：等待独立 monitor 正常周期，按本编号实际八条执行 improvement_log_check 只读核验，不强制导入、重启或扩大聊天采集；核验失败如实报告。运行实例与真实历史样本仍待授权配套发布后核对；本轮未改变统计口径或发现生成内容。
- 同步状态：{"kind":"improvement","category":"experience","status":"verifying","code_state":"modified","verification_state":"passed","deployment_state":"not_deployed"}
