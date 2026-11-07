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
