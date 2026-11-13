# 前端交互回归

## 发现正文换行、代码与复制（PI-20261109-009）

实现规则、上游输出边界与完整复验命令见[发现正文显示约定](finding-content-display.md)。新增 `findingMarkdown.spec.ts` 以合成描述检查 1440/390/320px 的字面标签换行、多行缩进、代码区域横向滚动、右上角复制、键盘操作及复制失败后重试；既有发现分区用例增加代码块检查。安全专项覆盖 HTML 文字、危险链接、图片不请求、未闭合围栏和普通代码转义保留。实际执行结果以本事项台账追加为准，不沿用历史通过数量。

## 发现反馈即已处理的追加检查（PI-20261109-007）

最新需求覆盖下方初版双标签展示：列表恢复“发现 / 价值反馈”，移除独立处置标签；详情有帮助、误报或忽略均显示已处理，撤销回待处理。处理筛选按同一反馈口径，旧 open 直达兼容为未反馈发现，历史修复值归未评价。问题修复记录保持独立，不因反馈自动修改。

```sh
npm --prefix frontend run lint
npm --prefix frontend test
cd frontend
npx tsc -b
npx vite build --outDir /tmp/ocr-feedback-handled-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-feedback-handled-dist \
npx playwright test e2e/taskList.spec.ts e2e/workflows.spec.ts e2e/findings.spec.ts \
  --output /tmp/ocr-feedback-handled-browser
# 普通服务退出后，串行运行合成补审夹具，仍仅操作临时 SQLite。
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-feedback-handled-dist OCR_BROWSER_REVIEW_RECOVERY=1 \
npx playwright test e2e/reviewRecovery.spec.ts --output /tmp/ocr-feedback-handled-recovery-browser
```

前端全量最终 39 文件 / 244 项、普通隔离浏览器 20 项通过，ESLint、TypeScript 与隔离构建通过；已目视 1440px 列表与 320px 详情，验证有帮助显示已处理、撤销、刷新、未知和范围提示、列表无处置标签及筛选兼容。补审专项结果以台账最终追加为准。日志及截图位于 /tmp/ocr-feedback-handled-*；本轮只修改前端和文档，未发布静态资源、重启业务进程或修改真实业务记录。下方 250 项及双标签结论是前一阶段事实，不代表本轮展示方案。

## 任务反馈与处置完成标识初版（PI-20261109-007，历史阶段）

任务列名为“发现 / 反馈与处置”，使用两个 Ant Design Tag 分别显示逐条发现的反馈进度与去重问题的处置进度。验证反馈全未评价、部分和全部评价、撤销、已处理但未反馈、已反馈但待处理、合并去重、补审新增发现、未知关联、异常计数、无发现及覆盖受限；整行导航、选择隔离与返回筛选继续保留。

以下命令在隔离临时 SQLite 和静态产物中验证，不连接真实 GitLab、OCR 或飞书，也不修改正式任务状态：

```sh
npm --prefix frontend run lint
npm --prefix frontend test
.venv/bin/pytest -q backend/tests/test_task_issue_summary.py backend/tests/test_task_feedback_summary.py
cd frontend
npx tsc -b
npx vite build --outDir /tmp/ocr-completion-indicators-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-completion-indicators-dist \
npx playwright test e2e/taskList.spec.ts e2e/workflows.spec.ts \
  --output /tmp/ocr-completion-indicators-browser
```

本轮前端全量 39 文件 / 250 项通过，新增进度专项 22 项；15 项隔离浏览器通过，包含 1440/768/390/320px 反馈与处置独立更新、撤销和刷新，已目视桌面与 320px 标签布局。ESLint、TypeScript、隔离构建通过，设计机械检查输出空数组；构建共享 JS 1151.13 kB / gzip 371.40 kB，保留大包警告。临时单测日志位于 /tmp/ocr-completion-indicators-unit.log，截图在上述浏览器输出目录。后端专项结果与最终同步以本编号台账为准；未运行后端全量、真实读屏、200% 放大、真实外部服务或正式入口验收。未覆盖 frontend/dist 或重启业务进程，新标识尚未部署。

## 检查范围

- 项目配置切换页签保留草稿；关闭窗口、浏览器返回和离开页面时确认放弃。
- 配置首次读取失败不能保存默认值；重新加载与保存错误分别提示，保存成功后清除脏状态。
- 批量重审按逐项结果取消成功项勾选；失败项保留，请求期间锁定筛选、分页和选择。
- 评审任务、待跟进问题、合并前审查支持每页 25 / 50 / 100 条及跳页，筛选和条数保存在 URL。
- 任务高级筛选按需展开，生效标签可移除；问题历史默认显示最近 10 条，按需追加。
- 1280、390、320 像素视口下验证分页、表单无横向溢出，并保留截图供人工检查。
- “问题与改进”使用真实临时 SQLite 验证新建、编辑、历史保留及刷新持久化；草稿关闭与路由保护、查询失败与空结果区分、390/320 像素详情和表单无横向溢出。
- “问题与改进”支持问题和主题归档/恢复，校验原因草稿、版本冲突、只读与恢复编辑、URL 范围、刷新持久化和双向关联；复盘仍显示归档未解决事项，1280/320 像素确认弹窗无页面溢出。
- 任务列表直接显示失败/跳过原因、累计执行与首次排队，不以零发现暗示通过；详情展示固定范围、费用不完整和逐次记录，运行监控展示分组指标与样本说明。
- 运行监控展示第四阶段三个执行槽、模型并发 1 和过期心跳提示；旧 API 或空记录不宣称本机已切换，停止槽不显示成在运行。复用 `reviewExecution.spec.ts` 的三个视口检查。
- 项目总览 1440 / 1280 / 768 / 390 / 320 像素检查四项指标、趋势、当前严重级别、项目和类别分布；验证项目筛选统一作用业务图表、运行摘要保持全平台、任务入口及旧 `/effectiveness` 地址筛选兼容。趋势精确表键盘展开、移动端无整页横溢。

## 执行命令

在项目根目录执行静态检查、单元测试和构建：

```sh
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
```

运行全部浏览器回归（需已安装 Playwright Chromium）：

```sh
cd frontend
npx playwright test
```

macOS 也可显式复用已安装的 Chrome：

```sh
cd frontend
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" npx playwright test
```

检查分页与草稿时，在命令末尾加 `e2e/optimization.spec.ts`；检查第二、三阶段的原因、时间、范围与指标时加 `e2e/reviewExecution.spec.ts`。未先构建时可在根目录使用 `npm --prefix frontend run test:e2e`，该命令先构建再运行全部用例。

项目总览专项隔离回归命令（在 `frontend` 目录执行，先生成 `/tmp` 构建产物，不覆盖 `frontend/dist`）：

```sh
npx vite build --outDir /tmp/ocr-project-overview-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-project-overview-dist \
  npx playwright test e2e/overview.spec.ts e2e/navigation.spec.ts \
  --output /tmp/ocr-project-overview-e2e
```

浏览器测试使用 `backend/tests/browser_app.py` 创建临时数据库并监听 8791，不连接 8781 的本机业务数据；部分写入使用合成接口响应，“问题与改进”的记录闭环直接写入该临时数据库。截图和失败追踪输出到 `frontend/test-results/`，不提交到 Git。评审诊断新增截图为 `review-execution-list-{1280,390,320}.png`、`review-execution-detail-{1280,390,320}.png`、`review-execution-metrics-{1280,390,320}.png`。沙箱若不允许监听隔离端口，须授权后运行，不改为连接生产服务。

单独检查平台台账可在根目录执行：

```sh
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm --prefix frontend run test:e2e -- improvements.spec.ts
```

台账截图包括 `improvements-detail-desktop.png`、`improvements-detail-{390,320}.png`、`improvements-editor-{390,320}.png`；本轮检查结果及未部署边界见[第一阶段实施记录](improvements-phase1.md)。

复盘专项入口为 `npm --prefix frontend run test:e2e -- e2e/improvementSummary.spec.ts`（macOS 同样可指定上述 Chrome 环境变量）。用例直接写入隔离库，验证当前累计与历史日期活动不混淆、分类和日期刷新保留、待办/分布明细导航、失败恢复、无效日期及 1280/390/320 像素布局。图表和表格只在局部横向滚动。截图为 `improvement-summary-full-desktop.png` 与 `improvement-summary-{1280,390,320}.png`，结果与统计口径见[第三阶段说明](improvements-phase3.md)及持续台账。

归档专项入口为 `npm --prefix frontend run test:e2e -- e2e/improvementArchives.spec.ts`（可指定上述 Chrome 环境变量）。用例只写临时库，覆盖两类对象主动归档、恢复、默认与归档范围、归档期间隐藏编辑入口、历史动作、URL 刷新、关联不丢失、冲突草稿与复盘待办；桌面和 320 像素确认弹窗截图为 `archive-dialog-{1280,320}.png`。实际结果见[第四阶段说明](improvements-phase4.md)和持续台账，不将归档描述为部署或解决。


补审闭环验收使用独立夹具，先将前端构建到临时目录，再运行：

```sh
npm --prefix frontend run build -- --outDir /tmp/ocr-recovery-acceptance-dist
cd frontend
OCR_BROWSER_REVIEW_RECOVERY=1 OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-recovery-acceptance-dist \
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  npx playwright test e2e/reviewRecovery.spec.ts
```

该专项验证 1280/390/320px 的冻结范围确认、排队/停止、刷新历史、有效发现稳定身份反馈、通知失败后只重发通知。未设置 `OCR_BROWSER_REVIEW_RECOVERY=1` 时该文件显式跳过，不能把跳过当通过。生产应用不注册合成推进路由；不得将测试端口替换成业务端口。

## Ant Design 首批与运行监控

运行监控现以四个 URL 分区访问：默认 `/operations?tab=runtime`，以及 `performance`、`alerts`、`maintenance`。旧验收中的告警与审计需进入对应分区，审计需展开“管理操作审计”。性能筛选使用 `performance_repository`、`performance_status`、`performance_size`，刷新和回退保留条件。

先输出隔离产物，再运行基础接入与业务回归，不覆盖正在使用的 `frontend/dist`：

```sh
npm --prefix frontend run lint
npm --prefix frontend test -- --reporter=dot
cd frontend
npx tsc -b
npx vite build --outDir /tmp/ocr-ant-design-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-ant-design-dist \
npx playwright test operations.spec.ts workerConcurrency.spec.ts reviewExecution.spec.ts \
  theme.spec.ts alignment.spec.ts workflows.spec.ts optimization.spec.ts ux.spec.ts navigation.spec.ts
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_REVIEW_RECOVERY=1 OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-ant-design-dist \
npx playwright test reviewRecovery.spec.ts
```

`operations.spec.ts` 覆盖 1440/1024/768/375/320px 的四分区、十槽排空、原始执行口径、键盘性能筛选和 URL、无横向页面溢出、草稿切页与刷新、隐藏视图不轮询、清理取消无写入及确认冻结天数、弹窗焦点恢复。组件测试补监控读取失败、旧 API 缺失与告警后台变更不覆盖草稿。全站旧表单/批量/原生确认与额度弹窗仍由原专项验证，不能把这些旧控件的兼容检查称为已经迁移。

统一设计上下文不创建包裹存量页面的 `.ant-app` 容器，不导入全局 reset；旧 CSS 置于 `legacy` 层，基础输入与表格元素规则排除 Ant Design 控件。验收需同时检查新输入框主题尺寸和旧导航/表单样式。JSDOM 的响应式与伪元素限制仅在测试环境适配，真实焦点、Portal、尺寸与滚动由浏览器验收。

浏览器夹具仍只使用临时 SQLite 与 8791；补审专项由合成结果适配器推进，不调用真实模型或飞书。构建包体积及剩余迁移边界见 [首批接入说明](ant-design-adoption.md)。

## Ant Design 第二批：接入状态与任务列表

本批仍使用临时 SQLite、8791 和隔离构建，不通过 `test:e2e` 覆盖业务静态目录：

```sh
npm --prefix frontend run lint
npm --prefix frontend test -- --reporter=dot
cd frontend
npx tsc -b
npx vite build --outDir /tmp/ocr-site-ux-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-site-ux-dist \
npx playwright test taskMigration.spec.ts operations.spec.ts workerConcurrency.spec.ts \
  reviewExecution.spec.ts theme.spec.ts alignment.spec.ts workflows.spec.ts \
  optimization.spec.ts ux.spec.ts navigation.spec.ts taskAuthor.spec.ts \
  --output /tmp/ocr-migration-final
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-site-ux-dist OCR_BROWSER_REVIEW_RECOVERY=1 \
npx playwright test reviewRecovery.spec.ts --output /tmp/ocr-migration-recovery
```

`taskMigration.spec.ts` 新增 1440/768/390/320px、无页面横向溢出、键盘选择、UTC 时间、URL 刷新/回退与不恢复旧勾选、冻结编号不被后台轮询替换、取消无写入与焦点返回、请求中禁用和只提交一次、任务/模型/认证读取失败恢复。截图位于 `/tmp/ocr-task-migration`；有限动画在截图时完成后捕获，测试不强制点击或跳过业务断言。

## 本轮全套 Playwright 结果（2026-11-08）

使用 Chrome 和隔离浏览器服务执行：

```sh
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-site-ux-dist npx playwright test
```

最终 81 passed、18 skipped、0 failed。执行期间最初发现 4 个断言使用旧 `details`、原生表格单元格或分页 DOM 结构；更新到现有折叠与 Ant Design 控件交互后，专项 15 项及完整套件均复跑通过。18 项是配置为需专项环境开启的聊天采集、补审恢复及 HTTP 兼容测试，不计为通过。该结果基于临时 SQLite 与本地 8791 隔离服务，不调用真实 OCR、模型、GitLab 或飞书；并不覆盖所有角色/状态/外部环境。

目前接入引导、任务、评审链路、项目/系统主要展示区、账号/历史、问题与改进、首页及主题详情已有本轮布局或组件整理；复杂配置编辑器仍按原草稿状态所有权保留，不代表所有原生控件均已替换。`frontend/dist` 未覆盖，本机服务未重启，本机部署生效未确认。

组件测试 `onboarding.test.tsx`、`configurationFacts.test.tsx`、`taskMigration.test.tsx` 覆盖：配置进度与未知、回调地址不冒充接通、按目标最新记录、当前版本验证边界；认证刷新失败即使有旧缓存也不显示默认开关；辅助查询可独立恢复；筛选收起保留值、时间时区和冻结提交；付费 Mutation 显式禁止自动重试。JSDOM 弹窗用例单独关闭布局动画，不改变应用动效，真实可见性/焦点由浏览器验收。

存量任务高级业务控件、项目和系统编辑器仍保留旧组件；本批不将兼容验证描述为全部迁移。具体结果及构建体积见[接入说明](ant-design-adoption.md)第二批追加与台账。

## Ant Design 第三批：评审主链路页面子批

本地构建后使用已安装 Chrome 运行相关隔离浏览器用例；用例仅操作临时数据库和 8791：

```sh
npm --prefix frontend run lint
npm --prefix frontend test -- --reporter=dot
cd frontend
npx tsc -b
npx vite build --outDir /tmp/ocr-site-ux-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-site-ux-dist \
npx playwright test e2e/ux.spec.ts e2e/workflows.spec.ts --grep '问题|合并前|事件中心'
```

该子批的定向浏览器覆盖包括：待跟进问题筛选/侧栏 URL 与窄屏、当前页批量确认/取消/恢复、合并前失败结果语义、事件中心入口与窄屏。事件中心补扫表单位于“历史 MR 补扫与申请记录”折叠项内。未运行的其它用例或外部链路不算通过；完整配置页面、账号、配置历史、问题与改进及首页仍需独立设计和测试。

## Ant Design 继续批次：账号、问题与改进及配置历史

```sh
cd frontend
npx tsc -b && npm run lint
npx vite build --outDir /tmp/ocr-site-ux-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-site-ux-dist \
npx playwright test e2e/workflows.spec.ts e2e/improvements.spec.ts \
  e2e/improvementSummary.spec.ts e2e/improvementArchives.spec.ts \
  e2e/improvementMaintenance.spec.ts --grep '账号模式|项目新增|问题与改进|复盘|归档|维护|采集'
```

该轮实跑 6 项隔离检查，覆盖项目表单回归、账号模式与只读界面、问题/主题归档、归档中复盘口径。配置历史表格未单独建立浏览器用例；仍需补齐配置历史恢复边界及全站逐页角色和视口验收。

## 全项目列表统一实施验收（2026-11-08，PI-20261108-003）

本节为后续实施的实际结果，不覆盖前文各轮历史验证边界。范围包括任务基准及其他 10 类主列表、首页小表、告警 / 审计 / 聊天、报告 / 反馈与详情证据；复杂配置编辑器、时间线、版本及恢复历史保留领域交互，不宣称所有存量控件均已迁移。

### 实际检查命令

根目录执行后端检查：

```sh
.venv/bin/ruff check backend
.venv/bin/mypy backend/ocr_manager
PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract
.venv/bin/pytest -q -rs
git diff --check
```

前端检查与最终完整浏览器使用隔离构建：

```sh
cd frontend
npx tsc -b
npm run lint
npm test
npx vite build --outDir /tmp/ocr-global-list-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-global-list-dist \
npx playwright test --output /tmp/ocr-global-list-complete
```

普通套件默认跳过的专题分别显式开启；这些命令依次执行，不在同一 8791 端口并发启动：

```sh
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-global-list-dist OCR_BROWSER_CHAT_CAPTURE=1 \
npx playwright test e2e/chatCapture.spec.ts
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-global-list-dist OCR_BROWSER_REVIEW_RECOVERY=1 \
npx playwright test e2e/reviewRecovery.spec.ts
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-global-list-dist OCR_BROWSER_HTTP_COMPAT=1 \
npx playwright test e2e/httpCompatibility.spec.ts
```

### 结果与覆盖

- 后端 Ruff、mypy（125 文件）、OpenAPI 校验通过；pytest 为 **731 passed、1 skipped、1 warning**。跳过的是未显式配置 `OCR_RESUME_PROBE_COMMAND` 的真实外部 OCR CLI 探测；警告为 Starlette TestClient 的 httpx 弃用提示。
- 前端类型、lint、隔离构建通过；组件 **32 文件 / 160 项通过**。新增组件用例保护未知分面、URL 命名空间、返回白名单、恢复目标与时间；既有权限、批量冻结、草稿与失败恢复断言保持。
- 最新完整普通浏览器 **90 passed、19 skipped、0 failed**；聊天、补审、HTTP 专题分别 **4 / 12 / 3 项通过**，默认跳过不冒充普通套件通过。最终列表 / 对齐 / 工作流定向复跑另为 **19 passed**，不与完整套件简单相加为独立用例数。
- `globalLists.spec.ts` 覆盖 11 类主列表在 **1440 / 1280 / 768 / 390 / 320px** 的核心事实、长内容、无页面横向溢出、完整历史翻到百条之外、未知与密钥边界、详情返回。任务耗时 / 尝试、创建时间和问题处置不移除；平台记录代码 / 本地验证 / 部署分别展示。
- 真实浏览器发现并修复手机隐藏表头后的全选入口缺失、长条件标签撑宽、历史复选触控高度和多节点单元格错位；桌面详情入口不再拆行。聊天写后采用返回版本、后台轮询不覆盖草稿，折叠工具与关闭收件箱停止轮询。配置恢复冻结目标，清筛选不残留旧详情。
- 最终完整套件截图位于 `/tmp/ocr-global-list-complete`，列表截图关闭动画以避免捕捉过渡态；实际目视核对 320px 问题 / 项目列表与 1440px 平台记录，未将单一截图推断为所有状态或角色均完成视觉验收。

完整普通浏览器日志为 `/tmp/ocr-global-list-complete.log`，专题分别为 `/tmp/ocr-global-chat.log`、`/tmp/ocr-global-recovery.log`、`/tmp/ocr-global-http.log`；后端与组件日志分别为 `/tmp/ocr-global-backend-latest.log`、`/tmp/ocr-global-components-latest.log`。临时目录仅作本机检查证据，不作为长期部署产物。

### 性能与未部署边界

合成百行完整响应 6,369,586 字节，安全摘要 54,786 字节（约减 99.1%），固定三条 SELECT，无逐行查询；含解析本地查询约 9.2 / 8.7ms，不代表生产延迟。只读 Git HEAD 提交基线与当前构建全部 assets 为 1,676,004 / 1,697,234 字节（+1.27%），逐文件 gzip 合计为 552,313 / 552,461 字节（+0.03%）。基线并非开始时未提交源码，且 Table 由独立 chunk 整合到主共享包，不能只比较主 chunk 判断总增长。当前主共享 JS 为 1,097.69 kB / gzip 355.89 kB，仍有超过 500kB 的构建警告；没有调整阈值掩盖，也未完成真实网络首屏性能验收。

所有浏览器只使用临时 SQLite、8791 与合成外部替身，不调用真实模型、GitLab 或飞书，不扩大聊天读取与绑定范围。**代码与本地检查完成，部署未执行**：未覆盖 `frontend/dist`、未重启 API / Worker / monitor。此次无新增迁移；正式生效仍需前端产物与 API 配套更新，再核对实际入口，不以本地通过代替上线确认。实施范围与后续发布说明见[列表规划第 10 节](global-list-redesign-plan.md#10-后续实施落地2026-11-08pi-20261108-003)。

## 运行概览修复验收（2026-11-08，PI-20261108-004）

完整实现、统计边界、测量及未部署说明见[概览规划第 9 节](overview-repair-plan.md#9-后续实施记录2026-11-08pi-20261108-004)。本轮新增 `frontend/src/test/overview.test.tsx` 与 `frontend/e2e/overview.spec.ts`；不沿用前轮数字作为本轮通过。

```sh
.venv/bin/ruff check backend
.venv/bin/mypy backend/ocr_manager
PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract
.venv/bin/pytest -q -rs
.venv/bin/pytest -q -s backend/tests/test_workspace_queries.py -k growth
cd frontend
npx tsc -b && npm run lint && npm test
npx vite build --outDir /tmp/ocr-overview-repair-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-overview-repair-dist \
npx playwright test --output /tmp/ocr-overview-repair-complete
```

实际后端 **736 passed / 1 skipped**，组件 **167 passed**，完整普通浏览器 **98 passed / 19 skipped**。聊天 / 补审 / HTTP 专题按前节同样命令，将产物目录改为 `/tmp/ocr-overview-repair-dist` 后分别显式执行，实际 **4 / 12 / 3 passed**。所有浏览器仅使用临时 SQLite 和合成外部替身。

首页专项覆盖五档视口、核心时间和尝试、各类型跳转范围、旧服务降级与读者入口、延迟 / 部分失败、启用范围保留与清除、键盘展开语义数据表。实际目视桌面与手机截图；**真实读屏、200% 放大未实测**，不以 DOM 或 aria 检查冒充。正式页面未发布，外部 OCR CLI 探针未运行，保留大包体警告。

## 模型与访问权限局部收尾（2026-11-08，PI-20261108-005）

`configurationPolish.spec.ts` 补齐 1440 / 1280 / 768 / 390 / 320px 的短操作单行、多按钮同排、桌面紧凑行高、手机无整页横溢、认证区无重复边框和键盘取消检查；手机保留既有带标签的纵向资料卡，不强求桌面行高。另用临时后端验证创建账号、确认启用、重新登录及只读会话访问账号 API 返回 403。用例结束恢复临时实例认证模式，不操作业务实例。

可执行复验命令（默认隔离端口 8791 必须空闲，不停止或复用其他任务服务）：

```sh
cd frontend
npx tsc -b
npm run lint
npm test -- --reporter=dot
npx vite build --outDir /tmp/ocr-config-polish-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-config-polish-dist \
npx playwright test e2e/configurationPolish.spec.ts e2e/workflows.spec.ts \
  --grep '模型与账号|认证控件确认|百练模型' --output /tmp/ocr-config-polish-browser-complete
```

本轮实际类型、lint、组件 **33 文件 / 169 项**、隔离构建通过；因 8791 被占用，临时包装 `browser_app.py` 将监听端口改为 57262，临时 Playwright 配置同步修改 baseURL 与健康检查，未改仓库服务配置。实际浏览器命令是在上述命令中额外加入 `--config /tmp/ocr-config-polish.playwright.config.ts`，最终 **7 passed**。两页桌面和 320px 截图均实际目视核对，证据位于 `/tmp/ocr-config-polish-browser-final` 和最终输出目录；临时文件不作为长期产物。

组件新增取消不写入、请求中禁用、409 后保留原状态且不自动重试。初次浏览器断言误将手机资料卡限制为桌面行高、误用 `check()` 要求异步受控控件立即选中，均修正测试语义后复验。另运行既有完整账号工作流时，登录与只读入口检查已成功，但在首页旧版“评审效果”区域断言失败；首页存在独立改造，本轮未改写该测试或宣称全套工作流通过。专项账号用例独立验证本次范围，不代替首页整体验收。

保留共享包大于 500kB 警告；真实读屏与 200% 放大未测。**源码与局部验证完成，未部署**：未覆盖 `frontend/dist`，未重启真实 API、Worker 或 monitor，未调用外部模型。

## 项目总览参考布局实施验收（2026-11-08，PI-20261108-004）

本轮按用户参考图采用“全平台状态带 → 四项业务指标 → 全宽趋势 → 问题诊断 → 项目概况”，不照搬其他业务的百分比、环比、Token 消耗和流程开关。保留健康/运行/项目统计独立读取时间、失败缓存提示、手动刷新锁定和读者边界。所有产物与浏览器均隔离，不代表正式页面已生效。

- 代码检查：实际运行 `cd frontend && npx tsc -b && npm run lint && npm test`，33 文件 / 169 项通过。`npx vite build --outDir /tmp/ocr-project-overview-dist --emptyOutDir` 成功，主共享 JS 约 1,109.49kB / gzip 359.76kB，仍有大于 500kB 提示，未改阈值隐藏。
- 后端检查：`.venv/bin/ruff check backend`、`.venv/bin/mypy backend/ocr_manager`（126 文件）、`PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract` 通过。`.venv/bin/pytest -q -rs` 最新为 737 passed / 1 skipped，跳过外部 OCR CLI 探针，保留现有 httpx 弃用提示。
- 最终首页与相关流程：使用上方 Chrome 和 `OCR_BROWSER_FRONTEND_DIST` 环境变量运行 `npx playwright test e2e/overview.spec.ts e2e/navigation.spec.ts e2e/taskList.spec.ts e2e/workflows.spec.ts --output /tmp/ocr-project-reference-e2e`，21 passed。覆盖五档视口、UTC 精确数据表、项目/时间切换、全平台运行独立范围、Worker 失败、旧地址、读者导航和任务处置；实际查看最终桌面和手机截图。
- 较广回归：同版产物执行 `npx playwright test --grep-invert '复选框统一对齐' --output /tmp/ocr-project-full-e2e`，99 passed / 1 failed / 19 skipped。唯一失败为新增“查看评审任务”与侧栏“评审任务”模糊匹配冲突；将该工作流定位改为精确匹配后，在上述 21 项最终回归中通过，未改业务逻辑规避。该较广命令没有在最后一次选择器修正后再全量执行，不能改报为 100 项最终全绿。被排除的三项旧 `alignment.spec.ts` 在前一轮实际失败于认证开关的旧可访问名称，关联用户要求保留的设置页工作，本事项未修改它们。
- 显式专题：依次设置 `OCR_BROWSER_CHAT_CAPTURE=1`、`OCR_BROWSER_REVIEW_RECOVERY=1`、`OCR_BROWSER_HTTP_COMPAT=1`，分别运行 `e2e/chatCapture.spec.ts`、`e2e/reviewRecovery.spec.ts`、`e2e/httpCompatibility.spec.ts`，实际 4 / 12 / 3 passed；均只写隔离临时 SQLite，不读取或扩大正式聊天范围。与普通套件重复的用例不累加为独立总数。
- 证据：`/tmp/ocr-project-backend.log`、`/tmp/ocr-project-components.log`、`/tmp/ocr-project-build.log`、`/tmp/ocr-project-browser-full.log`、`/tmp/ocr-project-browser-final.log`、`/tmp/ocr-project-chat.log`、`/tmp/ocr-project-recovery.log`、`/tmp/ocr-project-http.log`；截图在 `/tmp/ocr-project-reference-e2e`。临时文件不承诺长期保留。
- 限制与部署：真实读屏、200% 浏览器放大、正式业务数据和生产负载未实测，impeccable 官方引擎无有效扫描结果；不宣称全站所有用例通过。未覆盖 `frontend/dist`、未重启真实 API / Worker / monitor，未改正式业务状态。

## 评审质量与处置（PI-20261108-004）

质量区默认显示有帮助、误报、已修复反馈、未标记、分子/分母比例和当前已忽略；“问题变化”仍可切换。反馈样本抽屉支持项目/UTC闭开窗口/反馈/类别/严重级别/分页，刷新与前后退保留条件，关闭和清除不修改首页项目/时间或反馈；样本提供任务与问题只读入口，重审版本需按身份复核。

```sh
cd frontend
npx tsc -b
npm run lint
npm test
npx vite build --outDir /tmp/ocr-quality-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-quality-dist \
npx playwright test e2e/overview.spec.ts e2e/navigation.spec.ts e2e/taskList.spec.ts e2e/workflows.spec.ts \
  --output /tmp/ocr-quality-final-browser
```

本轮实际通过：前端 34 个文件 / 175 项组件测试；隔离 Vite 构建成功（共享 JS 约 1,145.65kB，保留大于 500kB 警告）；上述浏览器 25 项通过，覆盖五档首页宽度、质量样本 1440/390/320、失败重试、分页、URL 往返、真实隔离 API 反馈读写回收、任务/问题入口及原有任务工作流。另有后端全量 745 passed / 1 skipped（外部 OCR CLI 探针未启用）、Ruff、Mypy（127 文件）与 OpenAPI 契约通过。截图位于 `/tmp/ocr-quality-final-browser`，仅为临时证据；真实读屏、200% 放大、生产负载和正式部署仍未验证。

### 反馈趋势并排柱追加验证（2026-11-08，PI-20261108-004）

本批仅调整反馈图的布局和纵轴范围，保留统计、反馈语义和下钻。新增浏览器断言直接测量四根柱子的横向位置、共同基线和高度比例；五档首页验证不出现页面级横向溢出，窄屏聚焦图表后方向键可滚动、纵轴位置保持不变。7/90 天专例验证未标记 40 条时 1/2 条反馈不被覆盖、零值没有假柱。

```sh
cd frontend
npx tsc -b
npm run lint
npm test
npx vite build --outDir /tmp/ocr-quality-grouped-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-quality-grouped-dist \
npx playwright test e2e/overview.spec.ts e2e/navigation.spec.ts \
  --output /tmp/ocr-quality-grouped-browser
```

本轮上述命令实际通过：34 文件 / 176 单测、15 项隔离浏览器；构建共享 JS 约 1,145.83kB / gzip 370.39kB，保留既有大包告警。目视 1440px、320px 与 7 天小数量截图通过，证据位于 `/tmp/ocr-quality-grouped-browser`，日志 `/tmp/ocr-quality-grouped-browser.log`。后端本轮未改、未重跑全量后端测试；未部署或覆盖正式静态资源，未验证真实读屏、生产数据、生产入口或负载。

## 发现卡片独立忽略与阅读分区（PI-20261109-003）

- 反馈与处置分组：忽略、恢复仅更新显式关联问题，不新增、替换或撤销 helpful、false_positive、fixed 反馈；误报仍沿用原反馈接口的同步忽略语义。
- 忽略前确认共享问题影响，允许选填说明；确认目标与状态快照冻结，失败保留说明、不自动重试。待处理筛选下后台轮询改变状态时仍保留确认卡片，取消后再应用新状态；保存时锁定重复动作与筛选。
- 已忽略问题可恢复待处理；因独立人工决定不会被反馈接口覆盖，忽略状态下须先恢复再确认已修复，避免暗示仅改反馈即已改变处置。
- 发现使用原始序号和已有类别；仅按明确行首标签拆分触发条件、代码依据、实际后果、修复建议、补充，保留来源顺序，不改写数据库原文。代码围栏不参与分区，没有标签的文字完整保留；HTML 按纯文本显示。
- 桌面 1440、平板 768、窄屏 390/320 像素检查正文行距、语义配色、长路径断行、操作不重叠、确认弹窗、Escape 与焦点返回；初审和有效补审均覆盖稳定身份与问题映射。

以下命令使用合成数据、临时 SQLite 和隔离构建，不覆盖业务静态资源，不调用真实 GitLab、OCR 或飞书：

```sh
.venv/bin/pytest -q backend/tests/test_finding_disposition.py backend/tests/test_feedback_issues.py backend/tests/test_issue_batch.py backend/tests/test_review_finding_feedback.py
.venv/bin/ruff check backend/tests/test_finding_disposition.py
npm --prefix frontend run lint
npm --prefix frontend test
cd frontend
npx tsc -b
npx vite build --outDir /tmp/ocr-findings-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-findings-dist \
npx playwright test e2e/findings.spec.ts e2e/workflows.spec.ts e2e/navigation.spec.ts \
  --output /tmp/ocr-findings-final-browser
```

截图与构建日志位于 `/tmp/ocr-findings-final-browser`、`/tmp/ocr-findings-build.log`，仅为临时证据。测试结果与部署边界以本编号台账最新追加为准；真实读屏、200% 浏览器放大、生产数据与正式部署未在上述命令内验证。

### 操作区简化追加验证（2026-11-09，PI-20261109-003）

按用户后续要求，操作区不再展示“反馈”“处置”标签，仅保留原顺序的按钮；统一按钮间距，窄屏自然换行。忽略与误报的业务区别、权限、确认和失败保留逻辑不变；前述分组展示为此前版本的记录。

```sh
npm --prefix frontend run lint
cd frontend
npx tsc -b
npm test -- --run src/test/findings.test.tsx src/test/findingDisposition.test.tsx
npx vite build --outDir /tmp/ocr-findings-buttons-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-findings-buttons-dist \
npx playwright test e2e/findings.spec.ts --output /tmp/ocr-findings-buttons-browser
```

上述命令实际通过：2 文件 / 16 项组件测试、5 项隔离浏览器检查；类型检查、ESLint、构建通过，保留既有共享 JS 大于 500kB 警告。已目视桌面卡片和 320px 截图，标签移除、按钮换行和不重叠符合本轮要求。截图位于 `/tmp/ocr-findings-buttons-browser`，仅为临时证据。本轮未改后端、未重跑后端或前端全量测试，未覆盖正式静态资源或部署，正式入口未验收。

### 发现价值反馈与跟进问题状态

最新方向覆盖此前独立忽略按钮会弹出处置确认的历史交互：发现卡片的反馈仅收集「有帮助 / 误报 / 忽略」三种互斥评价，可再次点击撤销，不触发问题处置确认。忽略表示本次不采纳，不等于误报；无选择为未评价。新反馈不会创建或修改跨任务跟进问题的状态。已修复是历史反馈值，继续保留旧记录，但新卡片和新反馈 API 均不再提供该选择，也不将历史修复自动视为有帮助。跟进问题页面独立管理待处理、已修复、已忽略、误报状态并保留审计；处置确认只在该页面的按钮触发。首页同时提供价值反馈与问题状态两种统计，前者按发现条数，后者按问题编号；误报占比只以有帮助和误报作为分母，不将忽略、未评价或历史修复算作有效评价。

发现描述与跟进问题详情共用原文分区组件。连续编号列表逐项换行且续行对齐；代码、版本号和未明确连续的场景引用保持原文。平台生成策略排除纯格式、主观建议和无当前证据的未来风险；相似跨文件建议不自动删除或合并，管理员须核实相同根因后通过问题侧栏执行手动合并。

### 价值反馈最终回归（2026-11-09，PI-20261109-003 / 004）

当前反馈为有帮助、误报、忽略、未评价，旧修复值保留在数据库但当前价值分析归入未评价，不再单列修复列。三按钮互斥可撤销；初审和有效补审均不因反馈改变跟进状态。问题侧栏独立四状态、确认和审计保持；任务列表处置数量及返回筛选来自问题事实，不能由反馈推断。

实际执行命令：

```sh
.venv/bin/ruff check backend
.venv/bin/mypy backend/ocr_manager
PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
cd frontend
npm run lint && npm test && npx tsc -b
npx vite build --outDir /tmp/ocr-value-feedback-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-value-feedback-dist \
npx playwright test e2e/findings.spec.ts e2e/overview.spec.ts e2e/navigation.spec.ts \
  e2e/taskList.spec.ts e2e/workflows.spec.ts e2e/reviewFindingSources.spec.ts \
  --output /tmp/ocr-value-feedback-browser-release
# 两种夹具共用 8791，必须在普通浏览器退出后串行执行。
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-value-feedback-dist OCR_BROWSER_REVIEW_RECOVERY=1 \
npx playwright test e2e/reviewRecovery.spec.ts --output /tmp/ocr-value-feedback-recovery-browser
```

实际结果：Ruff、Mypy 129 源文件、OpenAPI 通过；后端 **767 passed / 1 skipped**，跳过外部 OCR CLI 探针，保留 Starlette 弃用警告；前端 **37 文件 / 207 项通过**，lint、TypeScript 和隔离构建通过。普通浏览器 **35 passed**，补审专项 **12 passed**；补审覆盖 1280 / 390 / 320px 的反馈替换、忽略撤销、刷新持久化和问题映射不变。普通回归覆盖 1440 / 1280 / 768 / 390 / 320px 首页，1440 / 768 / 390 / 320px 发现与侧栏、确认取消及焦点返回、合成 API 统计与样本下钻、任务筛选返回与修复/恢复、只读权限和旧地址。

失败历史不删除：先后出现 25 passed / 7 failed、31 passed / 4 failed、34 passed / 1 failed，分别涉及旧交互预期、Drawer/Modal 定位冲突、未限定卡片入口及合成状态准备、删除不存在反馈；修正验收后上述最终命令通过。补审曾与普通服务同时启动导致 8791 占用而未执行，随后串行实际通过。临时日志见 `/tmp/ocr-value-feedback-browser-release.log`、`/tmp/ocr-value-feedback-recovery-browser-final.log` 和 `/tmp/ocr-value-feedback-pytest-final.log`。

已目视桌面与 320px 的发现卡片、跟进问题描述、首页截图：实际后果/修复建议分别强调，连续 1–4 项逐条换行，卡片无反馈/处置分组标签，按钮及长路径不产生整页横溢。以上均为合成内容；真实读屏、200% 放大、生产负载、真实模型生成质量及正式入口未验证，不能据此保证模型不再产生低质量发现。构建共享 JS 1150.41kB / gzip 371.09kB，保留大包警告。

部署未完成：本轮较早默认构建曾生成 `frontend/dist`，其后所有构建均使用 `/tmp` 隔离目录；不能将此描述为始终未覆盖静态产物，也不能将单独静态构建视为整版生效。未重启真实 API / Worker / monitor，未迁移正式数据库或修改真实发现与问题；schema 50/51 与 API / Worker / 前端仍需配套发布后核验。

### 历史描述与全部有序分项统一展示（2026-11-09，PI-20261109-004）

本轮扩展共享只读展示：无标签正文归“问题描述”，明确行动建议集中到“修复建议”，兼容【标签】及 [标签] 历史格式。所有描述区支持前言后列表、场景①/②、括号数字及中英文编号，保留来源编号；空行后的独立段落不继承上一项的编号。任务发现、跟进问题侧栏及历史报告新增/不再出现对比均复用组件，不批量改写数据库原文、指纹、反馈、问题状态或下载报告。版本号、代码和普通引用保持保护。

实际执行：

```sh
cd frontend
npm run lint && npm test && npx tsc -b
npx vite build --outDir /tmp/ocr-history-description-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-history-description-dist \
npx playwright test e2e/findings.spec.ts --output /tmp/ocr-history-description-browser-final
cd ..
git diff --check
```

最终全部通过：前端 37 文件 / 227 项，其中 findingContent 38 项；ESLint、TypeScript、隔离构建及 5 项浏览器检查通过。浏览器覆盖 1440 / 768 / 390 / 320px，触发条件、代码依据、实际后果、建议、补充共 11 个列表项，断言分项不重叠、三个入口描述一致、正文建议归位、独立建议不并入最后一个编号以及无描述横溢；保留反馈互斥、独立处置、确认取消和焦点返回验证。已目视最终桌面卡片、320px 发现与历史对比截图，并查看了本轮侧栏窄屏截图。测试仅使用合成内容及临时 SQLite，不调用真实 OCR、GitLab 或飞书。

排查过程真实失败：首次专项 16 passed / 2 failed，是旧测试要求“跳号或不从一开始不分项”，与用户本轮要求不同，调整预期后通过；首次 TypeScript 检查发现过滤器类型谓词不满足返回类型，已修正并复验通过。首次目视发现合并后的独立建议被并入最后一项，修正段落边界并补充 DOM 断言后最终通过。日志为 `/tmp/ocr-history-description-frontend-final.log`、`/tmp/ocr-history-description-browser-final.log`，截图位于 `/tmp/ocr-history-description-browser-final`。

共享 JS 1150.41 kB / gzip 371.10 kB，保留既有大包警告。本轮未改后端、未重跑后端全量或补审浏览器专项；真实读屏、200% 放大、生产数据及正式入口未验证。仅生成 `/tmp` 隔离产物，未覆盖正式静态资源，未重启业务 API / Worker / monitor，未迁移正式数据库；新版展示须发布后才会在运行实例生效。此前阶段曾默认构建生成 `frontend/dist` 的历史事实不变，不视为本轮已经部署。

### 任务价值反馈计数与整行详情入口（2026-11-09，PI-20261109-005）

本节覆盖此前“任务列表显示待处理数量并直达待处理发现”的展示约定：列表“发现 / 价值反馈”按当前有效发现显示“有帮助 N · 误报 N · 忽略 N”，不从跨任务问题处置状态推算。初审反馈镜像不双计，补审按主身份计数，历史修复归未评价，缺失反馈投影显示待核实；问题状态筛选仍独立保留。

任务、待跟进问题、合并前审查、问题记录、优化主题、聊天收件箱和质量样本移除仅用于详情的操作列，点击行内非交互区域或行获得焦点后按 Enter 打开详情。已有标题链接或按钮保留，返回仍恢复筛选。配置历史支持整行查看差异，恢复列保留。选择框、按钮、链接、文本展开、文本选择和修饰键不触发行导航；编辑、删除、重试等实际操作不移除。

本轮实际执行的检查命令如下，均使用合成数据、临时 SQLite 及隔离静态资源，不调用真实 GitLab、OCR 或飞书：

```sh
.venv/bin/ruff check backend
.venv/bin/mypy backend/ocr_manager
PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract
.venv/bin/pytest -q backend/tests
npm --prefix frontend test
npm --prefix frontend run lint
cd frontend
npx tsc -b
npx vite build --outDir /tmp/ocr-feedback-counts-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-feedback-counts-dist \
npx playwright test e2e/taskList.spec.ts e2e/globalLists.spec.ts e2e/issueAuthor.spec.ts \
  e2e/workflows.spec.ts e2e/overview.spec.ts e2e/ux.spec.ts e2e/chatCapture.spec.ts \
  --output /tmp/ocr-feedback-counts-browser-final
# 普通服务退出后，串行启动独立合成聊天夹具，不采集真实聊天。
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-feedback-counts-dist OCR_BROWSER_CHAT_CAPTURE=1 \
npx playwright test e2e/chatCapture.spec.ts --output /tmp/ocr-feedback-counts-chat-browser
```

实际结果：Ruff、Mypy 131 源文件、OpenAPI、TypeScript、ESLint、隔离构建通过；后端 778 passed / 1 skipped（外部 OCR 探针），前端 38 文件 / 228 项通过；普通浏览器 43 passed / 4 skipped（聊天需独立通道），独立聊天 4 passed。任务反馈替换、刷新、整行点击、Enter、选择隔离在 1440/768/390/320px 验证；跨页列表在 1440/1280/768/390/320px 验证，记录与主题返回保留筛选。已目视任务桌面、320px 任务及长项目名合并前列表。初次旧列数/旧表头断言、长项目名横溢和响应式动画时机失败的事实及修正见本编号台账，不覆盖历史结论。

共享 JS 1151.13 kB / gzip 371.41 kB，保留大包告警及 Starlette 弃用提示。临时日志及截图位于 `/tmp/ocr-feedback-counts-*`。本轮未运行独立补审浏览器专项、真实读屏、200% 放大、生产负载或真实服务验收；补审主身份计数由隔离后端测试覆盖。未部署、未覆盖正式静态资源、未重启进程或迁移真实数据库，发布需前后端配套，不能仅凭本地测试宣称运行入口已生效。


### 反馈柱状图整列提示（2026-11-13，PI-20261113-004）

反馈图改用 Ant Design Tooltip，每个日期整列支持悬停、键盘聚焦和点击，包括零值与柱间留白；显示同源四类反馈及总发现，90 天保留实际周桶起止日期。单一活动日期避免提示叠加，Escape、失焦与横向滚动关闭旧提示，Portal 避免提示被滚动容器裁切；原精确数据表、零基线及统计口径保持。

本轮实际执行：

```sh
npm --prefix frontend run lint
npm --prefix frontend test -- --run src/test/qualityTrendTooltip.test.tsx src/test/qualityOverview.test.tsx
git diff --check
cd frontend
npx tsc -b
npx vite build --outDir /tmp/ocr-chart-tooltip-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-chart-tooltip-dist \
npx playwright test e2e/qualityTrendTooltip.spec.ts e2e/overview.spec.ts \
  --output /tmp/ocr-chart-tooltip-browser-final
```

结果：ESLint、TypeScript、隔离构建与 diff 检查通过；组件 13 项、浏览器 20 项通过。覆盖整列顶端空白、柱底、零值、日期交界、离开关闭、Tab/Escape/焦点保留、精确表格、90 天周桶跨年范围及横向滚动，手机触屏点击日期切换与外部关闭；既有首页 1440/1280/768/390/320px、7/30/90 天及筛选下钻回归通过。已目视桌面提示与窄屏周桶提示截图，文字与数值完整、无整页横向溢出。

排查中曾发现退出动画令前后两份提示短暂重叠，已关闭此处提示过渡；触屏会合成悬停、聚焦、点击，原点击切换将刚打开的提示又关闭，现点击只打开并增加专项回归。失败记录保留，不通过放宽数量断言或移除触屏测试掩盖问题。构建仍有既有大包警告；未运行后端全量、真实移动设备或真实读屏验证。浏览器验证只使用隔离服务、临时数据库与合成数据，未执行真实评审、删除或反馈写入；本机静态发布与实际入口核验另记于本编号台账。


同次补验实际执行 `cd frontend && npx tsc -b && npx vite build --outDir /tmp/ocr-chart-tooltip-dist --emptyOutDir`，然后使用相同 Chrome 与隔离产物执行 `npx playwright test e2e/qualityTrendTooltip.spec.ts --grep '触屏' --repeat-each 3 --output /tmp/ocr-chart-tooltip-touch-repeat`，3 项通过；增加同日重复轻触后提示仍打开的断言。已目视触屏截图，并在本机 8781/8000 的桌面和移动模拟模式逐一只读核对非零／零日期提示值与同次接口响应一致，未尝试业务写请求。发布细节、已知台账同步阻塞与证据另见 PI-20261113-004。


### 图表提示占比与 90 天区间口径（2026-11-13，PI-20261113-004 续办）

日期提示在四类数量后增加 1 位小数占比：7／30 天按当天总发现，90 天按每组区间总发现（含未评价）；区间先求和再除，不平均每日比例。90 天从窗口首日每 7 日一组，13 组，最后 6 日显示实际完整日期。零样本显示“—”并说明不适用；有样本但类别为零为 0.0%。精确数据表继续展示原数量。

本轮实际执行：

```sh
npm --prefix frontend run lint
npm --prefix frontend test -- --run src/test/qualityTrendTooltip.test.tsx src/test/qualityOverview.test.tsx
git diff --check
cd frontend
npx tsc -b
npx vite build --outDir /tmp/ocr-chart-share-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-chart-share-dist \
npx playwright test e2e/qualityTrendTooltip.spec.ts e2e/overview.spec.ts \
  --output /tmp/ocr-chart-share-browser
```

结果：lint、TypeScript、隔离构建及 diff 检查通过，组件 15 项、浏览器 20 项通过；新增单日占比分母含未评价、零样本、不均匀每日样本先求和、90 天 13 组与末组跨年日期验证。保留整列命中、键盘、触屏和首页五档视口回归。已目视 90 天区间占比提示与触屏截图；提示数量及比例清楚，构建保留既有大包告警。未运行后端全量、真实移动设备或真实读屏；本机静态发布、双端口实际接口核对及台账同步状态另记本编号收尾。

### 发布审查分区与自动触发说明（2026-11-13，PI-20261113-006）

本分区沿用仓库编辑窗口的草稿和离开保护，局部开关、输入、按钮、保存反馈和折叠说明使用 Ant Design。GitLab 行内评论自动保存，合并前审查手动保存；主开关与 MR 描述选项分行，背景路径可空、多于三份或重复时提示，保存错误保留草稿。说明包含 MR 事件订阅、目标分支、接收开关、模型及 Worker 条件，诊断入口切换保留草稿。

实际运行的检查入口：

```sh
.venv/bin/pytest -q backend/tests/test_premerge.py backend/tests/test_webhook.py
.venv/bin/ruff check backend/tests/test_premerge.py
npm --prefix frontend test
npm --prefix frontend run lint
cd frontend
npx tsc -b
npx vite build --outDir /tmp/ocr-publication-settings-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-publication-settings-dist \
npx playwright test e2e/publicationSettings.spec.ts e2e/optimization.spec.ts \
  --output /tmp/ocr-publication-settings-browser-final
cd ..
git diff --check
```

本轮结果：后端专项 29 项、前端 44 文件／279 项、最终浏览器 18 项通过；lint、Ruff、TypeScript、隔离构建及差异空白检查通过。浏览器覆盖 1440／768／390／320px，验证开关分行、键盘 Space、独立保存、分区切换与草稿、读取失败恢复、关闭放弃确认、输入规范化和无横向溢出。仅使用临时服务、合成配置和临时 SQLite，不调用真实 OCR、GitLab 或飞书。构建保留共享 JS 超过 500kB 告警；后端保留 Starlette 弃用提示。

失败历史：首次组件检查中，说明 Alert 默认即时告警语义干扰错误定位，改为 note；折叠说明的动画需等可见后断言。首次浏览器 14 passed／7 failed：其中 4 项为本轮测试焦点停在折叠触发器，Escape 未发起离开确认导致后续一次性监听残留，已聚焦关闭按钮并显式等待确认事件后重验通过；另 3 项是既有 alignment.spec.ts 在未修改的账号页查找已移除的 `.inline-setting` 截图容器超时，本轮未修改该测试或声称其通过。最终命令不包含这三项旧账号页检查。已目视桌面和 320px 设置／帮助截图。真实读屏、200% 放大及移动硬件未验证；本机静态发布、实际端口核对与台账同步另见本编号收尾。
