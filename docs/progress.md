# 实施进度

> 更新于 2026-09-26。本文记录本地实现状态；“已实现”不代表真实 GitLab、OCR 模型或飞书环境已验收。

## 已实现

- FastAPI 接收 GitLab Merge Request webhook，校验签名或 Secret token、项目、分支与合并动作，并把事件写入 SQLite。
- Worker 通过 GitLab API 确认 MR，按普通 merge、squash 与 fast-forward 方式确定提交；Git 操作使用受控 SSH remote、完整 SHA 和隔离 worktree。
- GitLab 连接测试及每次合并事件展开都会核对项目 ID、`path_with_namespace`、目标分支与配置的 SSH remote；Worker 在拉取前再次核对 MR 目标项目 ID。
- SQLite 持久化事件、逐提交任务、评审尝试与通知投递；支持去重、同 MR 顺序、跨仓库轮转、有限退避、重启恢复和人工重试。
- SQLite 迁移按版本在单独事务中提交；中途失败会回滚该版本的 DDL 与 `user_version`。Webhook 原始请求体采用有 1 MB 上限的流式读取，超限立即拒绝。
- OCR 执行范围预览与正式评审，零可审查文件直接跳过；校验 manifest 输入及覆盖状态，保存原始工件。
- OCR 在 `summary.budget_exceeded=true` 时即使 manifest 标记 `complete` 也按 `partial` 对外呈现，避免预算耗尽被误报为完整评审。
- OCR 原始 JSON 只保留在受控工件目录；SQLite 结果索引和数据库备份只保存发现、覆盖、预览与状态摘要，不保存模型 `thinking`。
- 飞书卡片投递独立重试；React 管理台可查看仓库、事件、任务、覆盖、预览排除原因、尝试和通知状态，并操作补触发、重评审与重发。
- 飞书卡片的前三条重点发现按 `critical`、`high`、`medium` 优先展示；`low` 只保留计数和管理页详情，避免低级别评论挤占摘要位置。
- 飞书卡片及任务详情提供由 GitLab 仓库路径生成的 MR、提交链接，便于从发现跳回原始代码。
- 飞书 HTTP 429/5xx 与网络故障有限退避；HTTP 4xx、业务拒绝及本地凭据损坏直接终止自动重试，修复后仍可人工重发。
- 仓库接入设置可暂停与恢复处理、轮换 webhook/飞书凭据、记录 GitLab Webhook ID 和最近一次通过鉴权的投递时间；暂停期间已入库工作保持待处理。
- 管理写操作记录不含请求体的路由级审计日志，系统设置页可查看最近记录。
- 已提供 SQLite WAL 在线备份命令，副本经完整性检查并以 `0600` 权限保存。
- Worker 使用数据目录文件锁防止重复实例，重启恢复会记录中断尝试并遵守重试上限；OCR 超时或停止时终止启动器及其子进程组。
- `/api/health` 与概览页现在可独立显示 Worker 进程状态：API/SQLite 可用但 Worker 未持有单实例锁时显示“未运行”，OCR 长任务持锁期间仍显示“运行中”。
- 评审配置快照纳入 OCR 命令文件指纹、npm 包版本、超时和该提交内 `.opencodereview/rule.json` 的 Git blob 摘要；规则或 OCR 版本变化后重审会产生新任务，旧结论仍可追溯。
- Worker 领取任务后先核对入队配置快照；配置或 OCR 安装在排队期间变化时任务可见失败，须按当前配置重新评审。OCR preview 与正式评审共用一个整体超时预算。
- 私有 JSON 配置支持 `launchd` 无明文密钥的 plist 生成；清单需由部署者在目标服务用户下审核并安装。
- `launchd` 生成器可额外生成每日 SQLite 在线备份任务；备份目录必须位于业务数据目录之外，历史副本仍需正式部署时确定保留期。
- OCR CLI `1.12.9` 已安装到忽略目录 `.local-tools/`；`ocr version`、`ocr review --help` 与隔离 Git 仓库中的零文件/单文件 preview 已实际通过。本机真实模型连接测试已通过，正式逐提交评审仍待合并事件验收。
- OCR preview、正式评审及模型连接测试的子进程环境使用运行、代理和证书变量允许列表，不继承管理服务凭据、其他模型密钥或 Node 注入参数，并单独传入本次模型配置；manifest 覆盖分组中的重复文件 ID 会被拒绝，避免重复计数被判为完整评审。
- 管理台已提供 Git、GitLab API、模型与飞书连接测试。测试请求持久化后由 Worker 执行，最近结果可查询；同一目标的未完成测试去重，Worker 中断后不会自动重发飞书测试消息。模型测试在隔离 HOME 中配置 provider/model，并用 OCR 自身的 `llm test` 发起请求；自定义 Provider 的 API key 由环境变量提供，不写入隔离配置。
- 管理台配置入口拆为“项目配置”“飞书 Hook”“Agent 模型”三块；项目可先保存 GitLab 身份与入站回调，再按项目补录飞书机器人 Hook。Secret token 由服务端自动生成，项目列表默认遮罩并支持按需查看、复制；Signing token 仍由 GitLab 生成并录入。模型 API key 与飞书 Hook 只单向写入并通过独立连接测试验证。
- 项目配置和飞书 Hook 支持分别删除：删除 Hook 保留项目与评审历史并即时更新页面状态；项目无论是否已有事件、评审、通知或连接测试记录都可删除，关联业务记录会在同一事务中级联清理。在途 Worker 结果发现目标已删除时安全结束，不会恢复记录或退出进程。
- 增加 `OCR_APP_DEV_MODE=1` 本地开发模式：管理 API 暂时不要求管理员口令，前端会直接进入管理台；生产模式仍要求 `OCR_APP_ADMIN_TOKEN`，开发模式不影响 Fernet 主密钥和 webhook 鉴权。
- 本机固定使用 `127.0.0.1:8781`，用户配置与主密钥保存在忽略目录 `.local-data/local/`。开发模式页面返回 HTTP 200，`/api/health` 返回 `status=ok`、`worker=running`；匹配项目但缺少 Secret 的 GitLab Webhook 请求返回 401。
- 仓库数字项目 ID 可在收到合法 Webhook 或创建评审事件前于编辑窗口纠正；身份变更在 SQLite 写事务中校验，避免并发投递时改写历史事件归属。
- 2026-09-26 使用已保存配置联调：`App` 项目的完整 Git 克隆与目标分支拉取通过，已启用的 Agent 模型连接测试通过，飞书机器人连接测试消息发送成功。更新 GitLab Token 后发现项目数字 ID 误填为 331；按仓库路径查得真实 ID 为 311，修正后 GitLab API 项目、分支和路径校验通过。正式评审仍待真实入站事件验收。
- 本地检查通过：`uv run pytest -q`（88 项）、`uv run ruff check backend`、`uv run mypy backend/ocr_manager`、前端 `npm run lint` 与 `npm run build`。本机 `launchd` 试运行停在 Python 解释器加载阶段，已移除未运行的服务清单；当前 API 与 Worker 以前台进程运行，重启系统后须按部署文档重新启动。

## 待完成

- 配置可从 GitLab 访问的 HTTPS 内网穿透地址，再验证真实入站 Webhook。
- 目标机器上的 `launchd` 安装和备份计划；本机后台启动须先解决 Python 解释器加载问题。
- 在最终 Mac mini 部署用户下确认固定版 OCR CLI、模型配置与 API key 可用，并用真实 MR 输出核对 review manifest 与飞书卡片。
- 使用真实 GitLab 测试项目配置 SSH deploy key、只读 API token 与 HTTPS webhook；完成普通 merge、squash、fast-forward 和重复投递演练。
- 使用已通过连接测试的模型密钥与飞书机器人 webhook 完成真实评审投递、错误恢复和消息质量验收。
- 多仓库试运行及重启、限流、部分覆盖、版本回滚演练。

真实联调需要试点 GitLab 地址与项目 ID、目标分支、可达的 HTTPS 回调方式、OCR provider/model，以及飞书通知目标。密钥由部署环境或管理页录入，不写入文档。
