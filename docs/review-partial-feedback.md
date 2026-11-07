# 部分评审治理：运行核查与稳定身份反馈

记录日期：2026-11-07。关联事项：PI-20261106-008。承接[结论读取与发现身份](review-partial-conclusions.md)，本轮只继续第三步的反馈和问题关联基础，不开启生产补审。

## 1. 先核查的事实与更正

本轮只读核查使用 SQLite `mode=ro`、`ps`、`lsof`，以及本机运行 API 的健康和 OpenAPI GET，没有导入业务 `create_app`、执行业务迁移或重启服务。

- 业务库实际 `user_version=43`，`review_recoveries` 和 `review_recovery_aggregates` 均为空。上轮台账与结论文档中“当前业务库仍为 42”的表述不准确，本轮追加更正，不修改已同步历史。
- API PID 10068 在 2026-11-07 06:25:29 启动，监听 8781，输出连接本机终端。Worker PID 87408、monitor PID 87409 的启动时间分别为 2026-11-06 23:22:17、23:22:18，不能视为同版整套部署。
- 运行 OpenAPI 已有 `/api/jobs/{job_id}/recoveries`，尚无 `/api/jobs/{job_id}/conclusion`。健康检查返回 200，Worker 报告运行中；不以健康存活证明新功能验收通过。
- 当前源码的 `api.create_app` 在启动时执行 `store.migrate()`，API 重启与 schema 43 的出现吻合，但没有充分日志确定迁移的具体发起方或操作人，不把推测写成已证实根因。

本轮没有部署下面的 schema 44 或反馈入口。补审开关仍默认关闭，没有重审历史任务、调整生产模型参数或调用真实模型。运行版本不一致应在正式上线窗口协调 API、Worker、monitor 与前端，而不是为消除表面差异直接重启。

## 2. 出现记录与反馈模型

新增独立的 **44 版迁移**，没有改写已可能生效的 43 版迁移。重建 `review_issue_occurrences` 时保留旧 ID、问题关联、时间和评论字段，新增可空 `recovery_id`、数据库生成的唯一 `finding_id`；复合外键强制补审批次与任务、根尝试一致。

- 根身份：`j{job}:a{attempt}:c{index}`。原接口的序号只属于当前根尝试，不能用于聚合数组。
- 补审身份：`j{job}:a{attempt}:r{recovery}:c{index}`。两个批次的第 0 条发现不会互相覆盖。
- 精确重复保留首个主身份和附加来源，仅捕获主身份的出现，不重复建问题或反馈。
- 候选、批次、新发现出现记录与问题创建在同一终态事务提交；失败整体回滚。取消、失败、失效批次不捕获未采纳的新发现。
- `review_finding_feedback` 按稳定身份存 verdict、可信操作者及更新时间；旧反馈只按当前尝试对应的真实出现记录迁移，未知原操作者明确记为“历史反馈迁移”，不冒充实际用户。

反馈与问题状态及审计同事务。撤销只重开该来源拥有的关闭决定，不能覆盖问题页面或其他发现之后的人工决策。重复相同 verdict 不重复生成问题关闭事件；它不是完整的逐次反馈事件流，反馈表保留最新反馈，问题状态变化另有事件记录。

不自动追溯回填 43 版历史候选的新发现。若历史候选没有出现记录，新反馈返回 `finding_occurrence_missing`，不能拿旧评论下标猜测关联。本轮核查到的业务补审表为空，因此未触碰这类历史数据；未来需要时另做显式、可核查的回填工具。

## 3. 版本化入口与兼容边界

| 入口 | 行为 |
| --- | --- |
| `GET /api/jobs/{job_id}/finding-feedback?source_attempt=N&revision=R` | 只读目标版本可见主身份的最新人工反馈，允许历史版本，设置 `no-store`。 |
| `PUT /api/jobs/{job_id}/finding-feedback/{finding_id}` | 显式传 `source_attempt`、`revision`、`verdict`，要求当前最新版本；管理员写入，未知字段拒绝。 |
| `DELETE /api/jobs/{job_id}/finding-feedback/{finding_id}?source_attempt=N&revision=R` | 同样要求最新版本，缺失反馈返回 404，过期来源返回冲突。 |

新写入口随 `review_recovery_enabled` 默认关闭，没有新增生产启用入口。只读角色可查询，但不能写入或撤销。重审排队、旧尝试、旧 revision、取消来源、非主身份或损坏证据均不写入。

根反馈同时维护旧 `review_feedback` 投影，旧 PUT/DELETE 同事务镜像稳定身份；不会把补审发现塞进旧下标表。全量重审继续清空旧的当前反馈投影，但稳定身份反馈保留供历史审计，不复制到新尝试。

原任务详情的 `issue_ids`、`issue_statuses` 及任务列表发现数量/最高级别仍只计算初审，避免把补审第 0 条映射到初审第 0 条。问题列表和出现记录包含已采纳补审发现，侧栏明确标注“补审 #N（候选来源）”，链接仍进入父任务，不伪装成已支持的补审详情页。

效果统计的发现数包含已持久化补审出现，但 GitLab 发布匹配只对初审来源生效，不能把初审第 0 条已发布误算给补审第 0 条。反馈率、有效结论筛选、全任务费用及默认导出等消费者仍待整体统一；旧反馈统计尚不包含补审反馈，不能将其当作全平台补审效果验收。

## 4. 实际验证与限制

```sh
.venv/bin/ruff check backend/ocr_manager backend/tests
.venv/bin/mypy backend/ocr_manager
.venv/bin/pytest -q
PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract --update
PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build -- --outDir /tmp/ocr-finding-feedback-dist
cd frontend
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-finding-feedback-dist \
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  npx playwright test e2e/reviewFindingSources.spec.ts e2e/issueAuthor.spec.ts \
    e2e/reviewDiagnostics.spec.ts e2e/reviewExecution.spec.ts
```

实际结果：Ruff、严格 mypy（102 个源码文件）、OpenAPI 和前端 lint/构建通过；反馈专项 26 项、后端全量 585 项通过（另 1 项跳过），前端 82 项、浏览器专项 10 项通过。前端构建仅写 `/tmp`，未覆盖 `frontend/dist`；浏览器只访问临时 8791 服务。补审来源标签使用合成响应，覆盖 1280/390/320px，人工核对 320px 截图，无页面横向溢出，不冒充真实模型端到端补审验收。

迁移覆盖空库、代表性 43 版记录、旧反馈保留、DDL 失败回滚及可重复迁移；并发写入、读角色权限、过期版本、损坏来源、精确重复、取消/失败/失效、问题审计和候选事务失败均使用临时库验证。完整浏览器套件、真实 CLI 新规则组合、网关调查、业务库副本上线演练和部署验收本轮未执行；普通后端全量中的真实 CLI 探针未设置启用变量，保持跳过。

现有 Starlette/httpx 弃用、构建主包超过 500 kB、隔离输出目录不自动清空、浏览器颜色环境变量提示仍存在，不描述为零警告。

## 5. 接续顺序

1. 统一有效结论提升、筛选/统计、补审反馈率、全任务费用和默认报告口径，维持同一版本选择及可追溯初审。
2. 实现补审页面、确认预算/剩余范围与取消，以及独立补充通知；未支持的 GitLab 新来源发布继续禁用。
3. 在有预算的真实链路试点中关联网关 504、context/tool 和请求时序，定位源头原因；不能把补审能力视为根因已解决。
4. 准备备份、业务库副本 43→44 演练和恢复检查，协调同版部署并只读验收后再开放功能，不在隔离开发阶段自动执行。
