# 纯换行过滤验证与项目开关

> 日期：2026-11-05。范围：补齐第二阶段暂缓的过滤兼容验证和项目级开关，不实施第四阶段调度并发。本次仅修改代码、文档及隔离测试，未迁移或重启本机 `8781` 业务实例，未批量开启已有项目。

## 1. 开关位置与行为

进入 **项目配置 → 编辑 → 评审参数 → 自动过滤纯换行文件**，勾选后点击 **保存评审参数**。API 字段为 `newline_filter_enabled`，默认 `false`；没有新增全局环境变量，避免误把所有项目同时开启。

- 关闭：保持原先仅分析行为，不因纯换行自动免审，不增加过滤专用版本查询或第二次预览。
- 开启：仅排除固定 Git 对象确认 CRLF/LF 归一化后字节完全一致、原 OCR 预览确实选中、且能安全编码的路径。
- 逻辑、缩进、其他空格、末尾换行、权限、类型、增删变化，以及符号链接、子模块、二进制与无法确认的内容不免审。控制字符、绝对/不规范路径和首尾空白路径保守保持纳入。
- `max_files` 按过滤后的实际候选检查；201 个候选过滤 1 个后可通过 200 上限，但不截取前 200 个文件，也不改变项目限额。
- 有合并后任务、合并前审查或事件排队/运行时拒绝保存，返回 409；页面保留草稿，等队列空闲后重试。服务端鉴权不依赖复选框是否可见。

首次使用需让本机 API、Worker 加载同一版代码及 schema 37，不能只刷新前端。已有队列属于原策略，不能静默升级，需保留历史并按新配置重新入队。以上是本机启用条件，不是本轮已执行的操作。

## 2. 验证结论

实际 CLI 为 `open-code-review v1.12.9 (bccbc15) darwin/arm64`。探针使用临时 Git 仓库、独立 HOME、合成密钥和只监听 `127.0.0.1` 随机端口的合成模型响应，不读取真实模型凭据，不访问 GitLab、飞书或业务数据库。

| 验证 | 实际结论 |
| --- | --- |
| CLI `--exclude` 对照 | 前导 `/` 的简单路径不生效；不采用依赖逗号分隔的任意路径拼接 |
| JSON `exclude` 数组 | 15 个特殊/对照路径逐个验证，只排除目标，没有误伤同名或近似路径 |
| 路径类别 | 根/嵌套同名、空格、逗号、方括号、反斜杠、星号、问号、井号、感叹号、中文；保留 `x1.py` 等对照文件 |
| 规则优先级 | 默认、全局、仓库、项目四组真实 CLI 预览均通过；项目 > 仓库 > 全局，原有 include/exclude 语义保持 |
| 正式失败路径 | 本机 HTTP 400 合成响应，`failed` manifest 的 selected 集合与同参数预览、预期集合完全一致 |
| 正式成功路径 | 本机合成 `task_done` 工具响应，commit/range 两种模式均 `complete`，manifest 与预览、预期一致 |
| 全量排除 | 正式 CLI `skipped`，selected 为空，本机模型请求数为 0；平台同样在零候选预览后跳过正式命令 |

这不是所有 OCR 版本、所有文件名或真实模型效果的无条件保证。运行时仍校验具体集合；未知 OCR 构建直接以 `scope_filter` 失败，不悄悄改变为其他过滤方式。

## 3. 运行时安全边界

1. 从固定 base/head 只读预检，不改 checkout、提交或 Git 配置，不执行外部 diff/textconv。
2. 先运行原规则预览，仅取“已选中路径 ∩ 已确认纯换行路径”。保留 `original-preview.json`。
3. 复制实际生效规则到本次受控目录 `newline-filter-rule.json`，只追加转义后的精确相对路径；拒绝仓库规则符号链接与超大规则，不改原文件。
4. 使用合成规则再次预览。必须与预期集合精确相等，原始文件集合也必须不变，否则模型零调用、明确失败，不能降级为跳过。
5. 两次预览共用 60 秒上限，配置共用 30 秒；均扣减同一个 OCR 总预算。通过校验后更新策略排除数，再检查文件限额。
6. 正式 OCR 复用最终预览的 SHA、规则、模型及背景。原始 manifest 保持不变，selected 必须等于冻结候选；不一致不得发布成功结论。

数据库结果安全投影保存 `input_filter.excluded_count`，范围分析区分原始变更、策略排除、OCR 原有规则排除和实际候选。纯换行导致的跳过使用独立原因 `newline_filtered`，不误写为 OCR 原规则排除。合并后页面、合并前详情和飞书均披露排除；有策略排除的零发现通知不显示全范围绿色通过。

schema 37 是独立追加迁移，旧项目默认关闭，未改写已共享的 36 版迁移。开关和策略版本 2 进入合并后快照哈希及合并前 `execution_policy`；旧任务不能被当前开关静默重解释。迁移失败回滚及再次迁移在临时库验证，不补造旧任务的过滤事实。

## 4. 可执行验证

```sh
.venv/bin/ruff check backend/ocr_manager backend/tests
.venv/bin/mypy backend/ocr_manager
.venv/bin/pytest -q
.venv/bin/python -m ocr_manager.openapi_contract
npm --prefix frontend run lint
npm --prefix frontend run test
npm --prefix frontend run build
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm --prefix frontend run test:e2e
.venv/bin/python -m ocr_manager.ocr_filter_probe --command .local-tools/node_modules/.bin/ocr
```

探针需要本机监听权限；任何特殊路径、规则优先级或正式终态核对失败都会非零退出。浏览器只操作隔离的 `8791` 服务，不操作 `8781` 业务数据。脱敏的实测集合摘要见[探针结果](review-newline-filter-probe.json)。

自动化重点覆盖原规则不变、特殊路径、无法编码保留、逻辑混合仍纳入、误排除前模型零调用、manifest 漂移拒绝、全量跳过、先过滤再限额、关闭行为兼容、开关默认值与快照变化、在途冲突、旧合并前策略拒绝及迁移恢复。前端验证旧接口默认关闭、保存冲突草稿保留、成功保存与范围披露；浏览器覆盖 1280/390/320 三种宽度。

本轮实际结果：后端 `351 passed`、前端单测 `52 passed`、浏览器 `42 passed`；Ruff、严格 mypy、ESLint、TypeScript/Vite 构建、OpenAPI 契约及 `git diff --check` 均通过。后端有一条既有 Starlette/httpx 弃用提示，不影响本轮通过结果；未在本轮升级依赖。

不把合成模型验证当作真实供应商性能验证；真实项目的耗时、Token 和费用改善需在本机按项目启用后，用新产生的持久化记录比较。本轮不自动重跑历史失败任务，也不宣称排队调度问题已由此解决。
