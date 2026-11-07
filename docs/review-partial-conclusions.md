# 部分评审治理：统一结论读取与稳定发现身份

记录日期：2026-11-07。关联事项：PI-20261106-008。承接[第三步补审核心](review-partial-phase3.md)。

> 后续核查更正：第一节中“当前业务库为 schema 42”的表述不准确，2026-11-07 只读核查实际为 schema 43；运行 API 已有补审路由但尚无统一结论路由，迁移发起方无法确认。本轮后续的稳定身份反馈与问题关联已隔离实现，原“尚未实现”描述仅代表此前阶段，详见[运行核查与反馈实施](review-partial-feedback.md)。已同步台账保留原记录并追加更正。

## 1. 交付范围

- **代码修改：**新增统一只读结论模块、OpenAPI 与前端契约；在列表、详情、报告、首页与运维接入同一候选选择规则，提供版本化发现来源与版本费用复核。
- **本地验证：**结论专项 23 项、后端全量 559 项通过（另 1 项真实 CLI 探针跳过），前端 82 项和既有诊断/执行浏览器回归 6 项通过；具体命令见第五节。
- **部署生效：**未部署、未重启服务、未迁移业务库、未调整业务参数或调用真实模型。无新增迁移，开发结构仍为 schema 43，当前业务库只读核对为 schema 42。

本次完成第三步中的读取基础，不宣称有效结论消费者全部接入。`consumer_integration_ready` 仍固定为 `false`，补审开关仍关闭。候选不改写初审状态、原反馈、问题出现记录、GitLab 发布或飞书投递；旧页面也不提前把候选渲染成任务 complete。

## 2. 一套版本选择规则

`review_conclusions.py` 负责只查询 SQLite；不读原始工件，不运行 Git/OCR，不创建反馈、问题、通知或发布。调用方在同一读事务中选择版本。

- 当前候选必须属于当前 `job.attempts`，父任务仍为 partial 且未请求取消，选择该根尝试最大的聚合 revision。
- 全量重审刚进入 queued、attempts 尚未增加时，当前候选已隐藏；新尝试结束后不沿用旧候选。历史仍可显式读取。
- `revision=0` 是根尝试，正整数是该根尝试的候选版本；不能只传旧 `source_attempt` 而省略 revision，让默认选择误指向其他版本。
- 初审状态采用平台持久化的已验证尝试状态，不能被原 manifest 的 complete 覆盖；预算不确定而判 partial 的根尝试不会在新读取入口恢复成 complete。
- 候选完整读取验证根 selected 身份、原完成项、豁免/复用项、分区与终态、原发现前缀，以及每条发现实际来自哪个合法批次；损坏证据返回 409，不回退成无发现或成功。

列表/详情的 `conclusions` 并列返回 initial 和 candidate 摘要，均包含根尝试、版本、覆盖数量和发现数量；不会把完整评论、配置、执行令牌或工件路径加载进列表。每 500 条一块，仅两个摘要查询，不逐行查询。首页与运维新增独立 `conclusion_candidates` 状态计数，不把候选 complete 计成一次初审成功或成功执行耗时。

## 3. 发现身份与版本费用

`GET /api/jobs/{job_id}/conclusion` 继承管理员鉴权，返回白名单版本文档并设置 `Cache-Control: no-store`。默认读取当前根尝试的最新候选；没有候选时读取根尝试。显式 `source_attempt` 和 `revision` 可读取历史，返回 `is_current_source=false`，不会将历史复活为当前结果。

| 身份 | 格式 | 稳定边界 |
| --- | --- | --- |
| 根发现 | `j{job}:a{attempt}:c{index}` | 不与新根尝试复用身份。 |
| 补审发现 | `j{job}:a{attempt}:r{recovery}:c{index}` | 索引属于原独立批次，不属于聚合数组。 |
| 精确重复发现 | 保留首个身份，追加 `also_seen_in` | 校验新增来源评论内容相同，不创建另一条主身份。 |

来源校验拒绝负数/布尔索引、错误根尝试、未知或未来批次、不同父任务/根尝试、失效批次、重复主身份、伪造根评论和覆盖冲突。最多 10000 条发现、20000 条主/附加来源；超限显式拒绝，不截断为完整结论。

`execution_usage` 只累计根尝试和截止目标版本 `usage_through_recovery_id` 的所有独立批次，包含期间失败/取消的批次，使用各批次保存的价格快照。未知用量不补零，币种分开；后续失败或补审批次不会改变旧版本的这份费用。它不代表全任务、全历史或真实账单，原任务的 `cumulative_usage` 本轮仍保持旧的初审尝试口径。

旧 `/feedback/{comment_index}` 继续只认初审评论索引，不接受聚合下标或新 finding_id。新来源身份目前只读，尚无补审反馈写入口，也未把补审发现录入问题跟踪。

## 4. 报告与消费者接入矩阵

原 `/report` 保留初审发现和费用，附统一只读摘要；`/report?attempt=N` 不附后来候选。管理员显式添加 `recovery_revision=R` 时，在 `requested_conclusion` 并列导出目标版本，不替换初审评论。该附加文档与原报告一同经过已有已知凭据脱敏，不包含原始推理、完整配置或工件。

| 消费者 | 本轮已接入 | 尚未接入 |
| --- | --- | --- |
| 任务列表与详情 | 同一 initial/candidate 摘要与版本选择 | 提升有效结论、补审按钮与候选发现交互。 |
| 首页与运维 | 独立候选计数 | 用恢复后有效结论替换原状态统计、耗时与费用口径。 |
| 报告 | 显式不可变版本、来源与截止费用 | 平台有效结论默认导出。 |
| 反馈与问题跟踪 | 为后续提供已验证稳定来源，旧语义不变 | 版本化写入、迁移、同事务出现记录与历史关联。 |
| 飞书与 GitLab | 无新副作用 | 独立补充投递、发现去重及未支持路径禁用。 |

下一步应先设计并实现稳定身份的反馈/问题出现记录及其迁移、同事务写入和回归，再统一有效结论提升与统计/费用/导出口径。完成后才能进入页面按钮与独立补充通知，不能仅新增摘要便开启生产补审。真实 CLI 复杂规则组合、受控网关调查和上线演练仍按原计划独立验收。

## 5. 实际检查与限制

```sh
.venv/bin/ruff check backend/ocr_manager backend/tests
.venv/bin/mypy backend/ocr_manager
.venv/bin/pytest -q backend/tests/test_review_conclusions.py
.venv/bin/pytest -q
PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract --update
PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build -- --outDir /tmp/ocr-partial-conclusions-dist
cd frontend
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-partial-conclusions-dist \
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  npx playwright test e2e/reviewDiagnostics.spec.ts e2e/reviewExecution.spec.ts
```

结果：Ruff、严格 mypy（99 个源码文件）、OpenAPI、ESLint 和 TypeScript/隔离构建通过；结论专项 23 项、后端全量 559 项、前端 82 项通过；既有诊断/执行浏览器回归 6 项通过（1280/390/320px）。普通全量未设置真实 CLI 探针变量，该项跳过；没有运行完整浏览器套件、真实模型、真实 CLI 新组合或生产部署验收。构建仍有主包超过 500 kB 和临时目录不会自动清空提示，后端仍有 Starlette/httpx 弃用提示，浏览器仍有 NO_COLOR/FORCE_COLOR 环境提示。

初轮新测试误将默认“最新候选”请求当作初审，以及误用 `next_job` 领取前投影的 attempts 判断递增；已改为显式 revision=0 及核对 SQLite 持久化次数。另一次构造失败批次测试未推进源 revision，触发预期的 source_changed；已修正测试并重跑。没有修改业务校验绕过失败。
