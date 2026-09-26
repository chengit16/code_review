# 自动化 Code Review 管理平台实施流程

> 版本：实施方案 v1.3，2026-09-26。本文同时描述目标流程与分阶段验收；四块后台配置的实际填写方式见[配置指南](./configuration-guide.md)，本地启动方式见[部署说明](./deployment.md)。Open Code Review 的已确认能力和官方来源见[调研笔记](./open-code-review-research.md)。

开发阶段的代码组织、注释和质量要求见[工程规范采用说明](./governance/README.md)。

## 1. 目标与边界

系统部署在一台 Mac mini 上。GitLab 项目的 Merge Request 合并或默认分支快进 Push 后，通过项目 webhook 通知平台；平台确认提交范围，按提交 SHA 调用 Alibaba Open Code Review（以下简称 OCR），保存原始结果和覆盖情况，再向对应的飞书群发送摘要。管理员通过 Web 页面管理 Agent 模型、项目及其 GitLab Webhook、飞书配置和评审任务。第一版不定时轮询 Git 仓库。

第一版按以下约束实施：

| 项目 | 第一版决定 |
| --- | --- |
| 评审引擎 | OCR 默认模式，直接调用配置的 LLM；不调用 Codex。 |
| 评审单位 | 单个 Git commit，调用 `ocr review --commit <sha>`。 |
| 触发方式 | GitLab Merge Request 的 `merge` 事件和可选的默认分支快进 Push；页面支持按 MR 手动补触发和任务重跑。 |
| 部署范围 | 单台 Mac mini、单管理员、多个仓库、多份模型配置且同一时间启用一份。 |
| 通知方式 | 独立飞书群机器人配置可由多个仓库共享；一个仓库可关联一个通知目标。 |
| 结果保留 | SQLite 保存索引和状态，文件系统保存 OCR 原始 JSON、预览结果及诊断日志。 |
| 默认并发 | SQLite 持久化队列、单 Worker、同时只运行一个 OCR 任务；OCR 内部并发由 `--concurrency` 控制。 |

第一版不实现自动修改代码、自动提交、向 Git 平台回写行内评论、多用户权限或对公网开放管理页。这些能力需要额外的权限、审计和产品规则，待基础链路稳定后再决定。

## 2. 总体结构

```text
GitLab 项目：MR 合并或默认分支 Push → 项目 webhook
                         │ HTTPS，仅开放回调路径
                         ▼
                  FastAPI webhook 接收端 ── SQLite 事件收件箱
                         │                         │
浏览器（React 管理页）→ 管理 API ────────────────┤
                                                   ▼
后台 Worker：确认 MR / Git fetch / 排队 / 评审 / 通知
          ├── GitLab 只读 API + Git remote → 隔离工作目录
          ├── OCR CLI → JSON 结果与会话
          └── 飞书 webhook → 群消息
```

- **管理服务**提供页面、API 和轻量 webhook 接收端，不在 HTTP 请求中运行 Git 或 OCR。React 使用 Vite 构建为静态资源，由管理服务提供。
- **Worker**作为独立进程运行，负责消费已落库的合并事件、确认实际提交、执行 OCR 和重试飞书投递。管理服务重启不应中断正在运行的评审。
- **SQLite**使用 WAL 模式记录配置、任务、尝试和通知状态；第一版只有一个 Worker 实例。业务数据目录与代码目录分开。
- **launchd**分别守护管理服务和 Worker，开机或登录后启动，异常退出后重启。部署环境提供管理口令和加密主密钥；每仓库 GitLab Token、模型密钥、Webhook Secret 与飞书凭据由管理 API 加密保存。

管理页可以只监听本机地址；GitLab webhook 必须能访问稳定的 HTTPS 地址。由反向代理或受控隧道只转发 `/api/webhooks/gitlab` 到接收端。若使用 GitLab.com，私有局域网地址或仅供本机访问的地址无法直接作为回调；若使用自建 GitLab，需先验证 GitLab 所在网络能到达 Mac mini。评审只提供事后反馈，不会阻止已经完成的合并或 Push。

### 建议目录

```text
项目仓库/
  backend/             管理 API、领域逻辑、Worker
  frontend/            React 管理页面
  docs/                设计与运维文档

Mac mini 数据目录/
  app.db               SQLite 数据库
  repositories/        受控的本地 Git 仓库
  runs/<job-id>/       preview.json、result.json、stderr.log 等工件
  logs/                服务与 Worker 日志
```

数据目录不提交到 Git。实际路径在部署配置中固定，并由专用 macOS 用户持有。

## 3. 核心数据与状态

| 对象 | 关键字段 | 用途 |
| --- | --- | --- |
| `Repository` | 名称、命名空间、GitLab 实例地址、项目数字 ID、无凭据 HTTPS Clone URL、目标分支、启停状态、加密项目令牌及两个事件开关 | 确定可信项目和代码来源。 |
| `WebhookConfig` | 统一回调路径；每仓库的加密 Secret、事件开关和最近验证时间 | 在仓库配置中管理各项目 Webhook，不额外复制凭据。 |
| `MergeEvent` | 项目 ID、MR IID 或 Push 标识、投递 ID、目标分支、提交范围、接收时间、处理状态 | 持久化合并或 Push 事件及其处理证据。 |
| `ModelProfile` | 配置名称、OCR provider、model、可选 Base URL、加密密钥、启用状态 | 可保存多份，同一时间只启用一份；不保存明文 API key。 |
| `NotificationTarget` | 飞书配置名称、加密 webhook 与可选签名密钥 | 定义可共享消息去向；不保存明文 webhook。 |
| `ReviewJob` | 仓库、MR IID、commit SHA、MR 内顺序、配置快照摘要、入队时间、下次可运行时间、评审状态、结果分类 | 一个需要评审的不可变输入；可从 MR 追溯。 |
| `ReviewAttempt` | job、开始/结束时间、OCR 版本、退出码、工件路径、错误类别 | 记录每次尝试，保留失败证据。 |
| `NotificationDelivery` | job、目标、发送状态、尝试次数、响应码、最后错误 | 通知失败可独立重试，不重新消费模型额度。 |

webhook 投递按 `repository_id + webhook-id` 去重，也接受 `Idempotency-Key`；缺少投递 ID 时，MR 使用 `repository_id + mr_iid`，默认分支 Push 使用 `repository_id + after SHA` 去重。评审任务以 `repository_id + mr_iid + commit_sha + config_snapshot_hash` 去重：重复投递不重复评审，两个不同 MR 即使包含同一 SHA 也各自保留评审与通知关系。配置快照至少包含 OCR 版本、provider、model、项目规则文件内容摘要和评审参数。管理员点击“重新评审”时创建新的尝试并保留旧结果；按当前配置重新评审旧提交则形成新的任务快照。

评审状态建议为 `queued`、`running`、`complete`、`partial`、`failed`、`skipped`；飞书投递状态单独记录为 `pending`、`sending`、`sent`、`retryable_failure`、`permanent_failure`。这样“评审成功但飞书发送失败”不会被误认为需要重新评审。

## 4. 端到端业务流程

### 4.1 首次初始化

1. 在 Mac mini 安装 Git `>= 2.41` 和固定版本的 OCR，记录 `ocr version`。建议使用经校验的 Release 二进制；若使用 npm 包，设置 `OCR_NO_UPDATE=1` 防止包装器后台升级。
2. 创建专用系统用户与数据目录。在管理台新增并启用 OCR 模型；内置 provider 或兼容 OpenAI 协议的 HTTPS Base URL 均可使用，再用模型连接测试验证连通性。
3. 创建飞书群自定义机器人，在密钥存储中保存 webhook，配置签名或其他适用的安全设置，并发送一条测试消息。
4. 准备 GitLab 可访问的 HTTPS 回调地址，启动管理服务和 Worker，检查页面中的 Git、GitLab API、webhook 接收端、OCR、模型、数据库、飞书运行状态。

页面提交 API key 时，后端使用 `OCR_APP_MASTER_KEY` 加密并写入 SQLite，页面不回显明文。Worker 只在启动 OCR 子进程时把模型密钥加入该子进程环境；运行诊断对已知密钥做脱敏。可保存多份模型配置，队列存在待处理事件或任务时不能切换启用模型。加密主密钥必须由部署环境独立保管并备份；丢失后不能解密已保存凭据。

### 4.2 添加仓库

1. 管理员填写项目数字 ID、命名空间、仓库名称、无凭据 HTTPS Clone URL、目标分支、项目访问令牌、MR 与默认分支 Push 开关，并可选择已保存的飞书通知配置。新项目使用每仓库独立 GitLab Token；部署环境不再提供全局项目令牌。
2. 后端验证 Clone URL 与 GitLab 实例同源、命名空间一致并加密保存令牌。管理员在仓库设置页发起 Git 与 GitLab API 连接测试；测试请求先入 SQLite，由 Worker 验证目标分支的只读访问并初始化独立的本地仓库目录。HTTPS Git 通过临时 `GIT_ASKPASS` 使用令牌；命令参数和 Clone URL 不包含凭据。
3. 项目配置页展示统一 HTTPS 回调 URL 和各仓库由服务端生成的 Secret；管理员主动查看或复制单个 Secret，列表查询不返回明文。最近一次通过鉴权的 webhook 投递时间用于核对接入状态。**默认不补审历史 MR**；GitLab 事件页提供按 MR IID 手动补触发入口。
4. 管理员可以对某个已合并 MR 手动试评审，核对提交范围、模型结果与飞书卡片。

每个仓库的规则优先放在该仓库版本化的 `.opencodereview/rule.json` 中。页面展示规则文件是否存在及最近命中的预览结果；第一版不在页面中提供复杂的规则编辑器。

### 4.3 GitLab 项目 webhook 配置

每个接入项目都需要在 GitLab 的 **Settings > Webhooks** 中配置一条项目 webhook，操作者需具备该项目的 Maintainer 或 Owner 权限：

1. 填入管理页提供的 `https://<回调域名>/api/webhooks/gitlab`，保持 SSL 验证开启。按项目配置勾选 **Merge request events**，需要审查默认分支直接提交时再勾选 **Push events**；平台在服务端检查项目 ID、目标分支和事件开关。
2. 将 Webhook 页面显示的项目专属 Secret 填入 GitLab 的 **Secret token**。接收端恒定时间比较 `X-Gitlab-Token`；重新生成 Secret 后须同步更新 GitLab。已有 Signing token 项目仍由旧回调入口兼容，但新配置统一使用 Secret token。
3. 保存 webhook 后，在 GitLab 页面发送测试事件，确认回调返回 2xx、平台显示最近投递与鉴权结果。测试事件不满足 `action=merge` 时只验证链路，不触发 OCR。再用一个测试 MR 完成真实合并，验证整条链路。
4. 管理页记录统一回调地址、项目 Secret 与最近成功投递时间，支持轮换令牌和检查接入状态。第一版由管理员在 GitLab 中创建 webhook；未来若要由管理页自动创建，需要另外授予 GitLab webhook 管理权限。

回调路径仅用于接收事件，不向外提供管理功能。必须限制请求体大小、校验 JSON 和项目 ID；鉴权失败返回 401，数据库无法保存事件返回 5xx，成功持久化后尽快返回 2xx。GitLab 可能重投同一事件，不能在 HTTP 请求内执行 Git fetch 或 OCR。

### 4.4 接收合并事件并确定评审范围

1. 接收端核验鉴权、`X-Gitlab-Event: Merge Request Hook`、`object_kind=merge_request`、`object_attributes.action=merge`，并将 `object_attributes.target_project_id` 和 `project.id` 对照已配置的项目数字 ID，检查订阅的 `target_branch`。其他合法事件返回 2xx 并记为“已忽略”；相同投递 ID 或相同业务合并事件重复到达时不重复建任务。
2. 将项目 ID、MR IID、目标分支、`merge_commit_sha`、`squash_commit_sha`、投递 ID 和接收时间写入 SQLite 事件收件箱，事务提交后立即响应 GitLab。按事件而非仓库当前分支头处理，避免多个 MR 连续合并或 webhook 乱序时串审。
3. Worker 读取已保存事件，通过 GitLab 只读 API 重新确认该 MR 为 `merged`，获取最终合并 SHA 和必要的提交列表；执行 `git fetch` 后验证这些 SHA 存在且仍可从目标分支到达。不能仅把 webhook 中的 `last_commit.id` 或当前分支头当成合并结果。
4. 按实际合并方式生成评审任务，任务与 MR 关联：

| 合并方式 | 第一版评审范围 |
| --- | --- |
| 普通 merge commit | 以最终 merge commit 的第一父提交为基准，用 `git rev-list --reverse --topo-order <merge-sha>^1..<merge-sha>` 取本次引入的提交；包括 merge commit 本身。 |
| Squash merge | 若生成了 merge commit，评审该 merge commit 相对第一父提交的最终差异；否则评审 `squash_commit_sha`。不重复评审两者。 |
| Fast-forward 且未 squash | 从 GitLab MR commits API 取得合并后的提交列表，逐个验证其属于目标分支并按拓扑顺序入队。 |

如果合并 SHA 缺失、提交不再可达、浅克隆缺失历史、MR API 与本地 Git 状态不一致，事件进入 `needs_attention`，保留原因并供管理员手动补触发；不能退化为“审查收到事件时的目标分支 HEAD”。第一版仍是逐提交 OCR：merge commit 相对第一父提交的 diff 可能与来源提交重复，页面和飞书均标明 MR 与提交类型，在试运行中评估重复成本。

### 4.5 多任务排队与并发

多个 MR 在短时间内合并时，接收端仍只把每条 webhook 写入 `MergeEvent` 后响应。Worker 确认合并范围，将每个待审提交作为 `ReviewJob` 按 MR 内拓扑顺序持久化到 SQLite；`queued`、`running`、重试等待和终态都能在管理页查询。事件已入库但尚未展开任务时也显示在事件队列中，不因进程重启丢失。

第一版只有一个 Worker 实例，同时最多启动一个 OCR 子进程。领取时保持**同一仓库按事件接收顺序、同一 MR 按提交顺序**；不同仓库以轮转方式选择下一个可运行任务，避免某个仓库的连续合并长期占满队列。领取、状态变更和尝试记录在短事务中完成；运行 OCR 时不持有数据库事务。任务失败按错误类别设置有限重试和 `next_run_at`，等待期间可处理其他仓库；达到上限后进入可见失败状态。同一 MR 的后续提交等待前一个提交完成或最终失败，再继续执行。

OCR 结果确认后，飞书投递进入独立队列，发送失败只重试投递。页面展示各仓库排队数、任务状态和已等待时间；由于轮转、重试和模型耗时，队列位置只是估计值。先通过试运行观察积压与成本，再决定是否增加 OCR 并发；届时须重新评估 SQLite 的领取互斥与机器、模型容量。

### 4.6 执行单个评审任务

1. Worker 从队列领取最早的 `queued` 任务，写入尝试记录并设为 `running`。超时或进程异常退出后，启动恢复逻辑检查该尝试是否仍有活进程；无活进程则标记为可重试失败。
2. 为目标 commit 创建隔离的只读审查目录，使工作区文件与目标 SHA 一致；关闭不需要的 Git hooks，并禁止执行被审查仓库的构建、测试及安装脚本。Git fetch 与任务执行使用不同锁，避免工作目录被并发修改。
3. 运行 `ocr review --repo <dir> --commit <sha> --preview --format json`，保存预览文件。预览不调用 LLM。若没有可审查文件，任务进入 `skipped`，保留排除原因。
4. 运行正式 `ocr review --repo <dir> --commit <sha> --format json --audience agent --output <run>/result.json`。仅在需要需求背景时传一个 `--background` 或 `--background-file`；当前 OCR 实现两者同时传入时会忽略前者。
5. 给 OCR 进程设置整体运行截止时间，同时配置 OCR 的每组子任务超时和内部并发。超时后先请求终止，仍未退出再强制结束；保留 stderr 和部分工件。
6. 解析 JSON、校验结果，将结论及发现写入数据库，再生成一个待发送的飞书投递任务。清理隔离目录时保留 JSON 与诊断日志。

示意命令（真实实现由后端以参数数组启动，不经 shell）：

```bash
ocr review --repo "$REPO_DIR" --commit "$COMMIT_SHA" \
  --preview --format json --output "$RUN_DIR/preview.json"

ocr review --repo "$REPO_DIR" --commit "$COMMIT_SHA" \
  --format json --audience agent --output "$RUN_DIR/result.json"
```

### 4.7 判定评审结果

OCR 的退出码只能说明命令执行情况，不能单独证明所有文件都评审完成。Worker 按以下顺序判定：

| 条件 | 平台结论 | 页面与通知处理 |
| --- | --- | --- |
| 预览无可审查文件，或 OCR 返回 `skipped` | `skipped` | 显示“无可审查文件”及排除原因，不写“无问题”。 |
| JSON 无法解析、输入 SHA 不符、schema 不受支持、OCR 非零退出且无可信结果 | `failed` | 保留工件，显示错误类别，按策略重试。 |
| `manifest.terminal_state == "failed"` 或存在运行级失败 | `failed` | 保留已完成的发现及失败文件，明确标识整个运行失败。 |
| `manifest.terminal_state == "partial"`，或在未失败的运行中发现 `coverage.failed` 非空、预算耗尽 | `partial` | 保留已发现问题，明确列出未完成文件及原因，禁止显示“全部通过”。 |
| `manifest.terminal_state == "complete"` 且 `coverage.failed` 为空 | `complete` | 展示覆盖数与所有发现；仅当 `coverage.waived` 也为空且零条评论时，显示“已完成，未发现问题”。 |
| 其他状态或缺少预期 manifest | `failed`，原因标记为输出不兼容 | 停止自动发布“通过”，等待兼容性核对。 |

当前 OCR 的 `manifest.schema_version` 为 `ocr.run-manifest/v1`。校验时要求 `manifest.input.mode == "commit"`，以 `manifest.input.resolved_head` 对照任务 SHA，确认 `coverage.selected` 是 `completed`、`reused`、`failed`、`waived` 四组互斥结果的并集。`waived` 不等于“已评审”，需要单独显示；`failed` 状态的运行也应保留已经完成的发现。`start_line` / `end_line` 为 `0` 的评论保留为文件级发现，不构造伪造的行号链接。原始 OCR `thinking` 字段仅在受控工件中保留，页面与飞书默认不显示。

### 4.8 飞书投递

1. Worker 根据 `NotificationTarget` 生成一张摘要卡片：仓库、目标分支、MR 链接、commit 短 SHA 与链接、评审状态、完成/失败/跳过文件数、严重性计数、最多三条重点发现，以及管理页详情链接。
2. 默认把 `critical`、`high`、`medium` 发现放入卡片；`low` 仍保存在管理页。无发现、`partial` 和 `failed` 应使用不同的状态文案。
3. 对自定义机器人 webhook 发送 JSON，检查 HTTP 状态及响应体 `code == 0` 后标记 `sent`。在发送前按飞书当前接口限制校验消息大小与卡片结构；超限时缩短发现列表，详细评论始终保留在管理页。
4. 网络错误、限流或临时服务异常采用指数退避重试；配置错误、无权限等持久错误进入 `permanent_failure`，供页面处理。OCR 结果不因通知失败而重新运行。

飞书群自定义机器人没有可供本方案依赖的通用请求幂等键。Worker 使用本地唯一投递记录防止常规重复发送；如果请求已被飞书接收但响应丢失，重试仍可能出现重复消息。卡片中带任务 ID，便于人工识别。未来若要求更强的投递去重或单聊、跨群权限，再评估飞书应用机器人 API。

## 5. 管理页面与 API

页面采用工作台布局，优先展示可扫描的状态和可执行动作：

| 页面 | 必要信息 | 主要操作 |
| --- | --- | --- |
| 概览 | 已接入仓库数、事件与任务积压、各仓库排队数、最近投递与评审失败、模型和飞书连接状态 | 进入异常事件、任务或仓库。 |
| 项目配置 | GitLab 项目 ID、命名空间、Clone URL、目标分支、飞书关联、Webhook 回调与 Secret、事件开关、启停状态 | 添加、编辑、删除、测试 Git 和 GitLab API，查看或轮换 Webhook Secret。 |
| 飞书配置 | 通道名称、签名状态和关联项目 | 添加、编辑、删除并发送测试消息。 |
| Agent 模型 | OCR provider、模型、Base URL、启用状态 | 添加、编辑、启用、删除和测试模型。 |
| 合并事件 | MR、合并方式、接收时间、处理状态、关联任务 | 筛选、查看失败原因、按 MR 补触发。 |
| 评审任务 | 状态、提交、覆盖、发现数、耗时、模型、通知状态 | 筛选、查看、重跑、重发通知。 |
| 任务详情 | 提交信息、预览文件、发现列表、覆盖明细、尝试记录、日志摘要 | 按严重性/文件筛选，打开 Git 提交链接。 |

API 由管理服务提供，前端只访问本服务。配置资源使用 `/api/repositories`、`/api/model-profiles`、`/api/notification-targets`，业务记录使用 `/api/events` 和 `/api/jobs`；新项目的 GitLab 回调统一使用 `POST /api/webhooks/gitlab`。执行型管理接口提供按 MR 补触发、手动重审、重发通知和连接测试。所有修改配置及触发任务的动作写入审计日志，记录时间、动作、对象和结果，不记录密钥。

第一版 FastAPI 仅监听 `127.0.0.1`，由入口代理把必要的 webhook 路径提供给 GitLab，不暴露管理页和管理 API。需要在其他电脑访问管理页时，通过受控的 Tailscale/SSH 通道接入，并增加管理员认证。模型 API key、GitLab Token 与飞书 Hook 只单向更新；Webhook Secret 可由管理员在项目配置页主动查看和复制，列表接口不批量返回明文。

## 6. 失败恢复与运维

| 场景 | 处理方式 |
| --- | --- |
| Mac mini 断电或 Worker 重启 | 从 SQLite 恢复 `queued` 任务；检查超时的 `running` 尝试后重新排队或标失败。 |
| GitLab 投递时服务不可达 | 检查 GitLab webhook 投递记录并重发；平台不凭分支变更自行产生评审任务。长时间故障后，管理员按 MR IID 批量补触发。 |
| 同一事件重复投递或乱序到达 | 投递 ID 和合并事件业务键去重；各事件按自己的合并 SHA 确定范围，不依赖全局分支游标。 |
| Git 或 GitLab API 暂时不可达 | 已落库事件保持待处理状态并退避重试；达到上限后在管理页显示异常。 |
| 合并 SHA 不可达、分支被重写 | 标记事件为 `needs_attention`；记录 GitLab API 与本地 Git 的证据，等待人工确认补审范围。 |
| OCR 模型 429/5xx 或超时 | 保留尝试记录，有限次数退避重试；达到上限后标 `failed` 并通知。 |
| OCR 部分覆盖 | 保留部分发现，标 `partial`；可用 `session_id` 尝试 OCR 的兼容恢复功能，恢复前校验输入和配置。 |
| 飞书限流或网络超时 | 只重试投递，绝不因此重跑 OCR。 |
| OCR 升级后 JSON 结构变化 | schema 校验失败时暂停该版本自动发布“通过”，保留原始结果并回滚固定版本。 |

运维需监控 GitLab 最近一次成功投递、事件积压、webhook 失败或被禁用、OCR 失败率、部分覆盖数、模型消耗、飞书投递失败数和磁盘剩余空间。没有定时轮询时，平台无法自行发现从未送达的合并事件；故障恢复依赖 GitLab 投递记录的重发或管理员按 MR 补触发。SQLite 定期在线备份；按保留期清理 OCR 工件和本地会话，清理前确认无待重试任务引用。日志对 GitLab token、API key、Git 凭据、飞书 webhook 和敏感代码片段做脱敏。

## 7. 实施阶段与验收

### 阶段一：单仓库 webhook 闭环

- 完成 Git/OCR 安装、模型连接、飞书机器人测试和 GitLab 项目 webhook 配置。
- 合并测试 MR，完成 `接收事件 → 确认提交 → preview → review → JSON 校验 → 飞书发送`。
- 验收：只有已合并 MR 或已开启的默认分支快进 Push 触发任务；能区分“完整且零发现”“有发现”“无可审查文件”“部分完成”“失败”，并保存事件与原始工件。

### 阶段二：后台自动化

- 实现事件收件箱、GitLab API 确认、不同合并策略的范围计算、去重入队、单 Worker、超时与恢复、通知重试。
- 验收：一次 MR 合并带入多个 commit 时按顺序入队；重复和乱序 webhook 不重复评审；暂时断网后已落库事件能够恢复；缺失 SHA 不擅自改审分支头。

### 阶段三：管理页面

- 实现项目配置、飞书 Hook、Agent 模型、合并事件、任务和详情页面，加入连接测试、按 MR 补触发、重跑与重发入口；项目与通知配置允许分开保存。
- 验收：管理员无需查看服务器日志即可定位失败原因、核对覆盖情况和执行恢复操作。

### 阶段四：多仓库试运行

- 接入 2 至 3 个不同规模的 GitLab 项目，覆盖普通 merge、squash 和 fast-forward，观察模型成本、平均耗时、merge commit 重复情况和飞书消息质量。
- 验收：至少完成 webhook 鉴权失败、重复投递、乱序、漏投后手动补触发、空 diff、部分覆盖、模型限流、飞书限流、Mac mini 重启和 OCR 版本回滚演练，再提高并发。

## 8. 开发前需要确定的输入

以下信息只影响接入配置，不阻碍按本文搭建项目骨架：

1. GitLab 是 GitLab.com 还是自建实例、版本、试点项目 ID、只读地址、目标分支，以及 Mac mini 可被 GitLab 访问的 HTTPS 回调方式。
2. OCR 使用的 provider、model、接口所在网络，以及代码能否发送到该模型服务。
3. 飞书通知目标是固定群还是按仓库分群；是否需要在消息中展示私有代码片段。
4. Mac mini 管理页只在本机使用，还是要从其他设备通过内网访问；GitLab 项目中使用普通 merge、squash 还是 fast-forward。

GitLab Token、模型密钥和飞书 webhook 在管理台录入，`OCR_APP_MASTER_KEY` 由部署环境提供；任何密钥均不写入本文或 Git 仓库。

## 9. 依据

- [Alibaba Open Code Review 官方文档](https://open-codereview.ai/docs)
- [OCR CLI 参数与 JSON 输出](https://github.com/alibaba/open-code-review/blob/main/pages/src/content/docs/zh/cli-reference.md)
- [OCR 评审结果与覆盖 manifest 实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/output.go)
- [OCR 覆盖数据结构](https://github.com/alibaba/open-code-review/blob/main/internal/session/manifest.go)
- [OCR 单提交与 merge commit 的 Git diff 实现](https://github.com/alibaba/open-code-review/blob/main/internal/diff/git.go)
- [GitLab Merge Request webhook 事件字段](https://docs.gitlab.com/user/project/integrations/webhook_events/#merge-request-events)
- [GitLab webhook 配置、签名与投递](https://docs.gitlab.com/user/project/integrations/webhooks/)
- [GitLab Merge Request API 与提交列表](https://docs.gitlab.com/api/merge_requests/)
- [飞书群自定义机器人使用指南](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)
