# 前端交互回归

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
