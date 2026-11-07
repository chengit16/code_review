# 本地部署与联调

模型、共享飞书通道、HTTPS 仓库和统一 GitLab Webhook 的填写步骤见[后台配置与接入操作](./configuration-guide.md)。整体架构、当前页面与代码目录见[项目总览](project-overview.md)，全部资料见[文档索引](README.md)。

## 前置条件

- Python 3.12、`uv`、Node.js、Git 2.41 或更新版本。
- 固定版本的 Alibaba Open Code Review CLI，确认 `ocr version` 与 `ocr review --help` 可运行。项目既有部署示例固定使用 `1.12.9` 并安装到 `.local-tools/`；升级前应重新核对参数和输出契约。历史联调记录见[实施进度](progress.md)，不代替新环境中的模型与真实评审验收。
- GitLab 项目访问令牌、可从 GitLab 访问的 HTTPS 回调地址、飞书群机器人 webhook 和 OCR 模型 API key。

本地固定端口为 `8781`，服务仅监听 `127.0.0.1:8781`，不占用 `8080`。内网穿透用于 GitLab 回调时，只向外转发 `/api/webhooks/gitlab`；开发模式没有管理鉴权，不可将整个管理台端口公开。新项目从管理台复制统一回调地址与自动生成的 Webhook Secret 到 GitLab，并按项目开关选择 Merge request events 和 Push events。

## 安装与启动

在项目根目录执行：

```bash
uv sync --extra dev
cd frontend && npm ci && npm run build && cd ..
npm install --prefix .local-tools --no-save @alibaba-group/open-code-review@1.12.9
export OCR_APP_DATA_DIR="$PWD/.local-data"
export OCR_APP_ADMIN_TOKEN="请替换为随机长口令"
# 本地开发可改用 OCR_APP_DEV_MODE=1，并省略 OCR_APP_ADMIN_TOKEN；生产环境不要开启开发模式。
export OCR_APP_MASTER_KEY="请用 cryptography.fernet.Fernet.generate_key() 生成"
export OCR_APP_WEBHOOK_URL="https://hooks.example.com"
export OCR_APP_MANAGEMENT_URL="http://127.0.0.1:8781"
export OCR_APP_OCR_COMMAND="$PWD/.local-tools/node_modules/.bin/ocr"
export OCR_APP_REVIEW_LANGUAGE="zh-CN"
export OCR_APP_OCR_CONCURRENCY="4"
export OCR_APP_OCR_EFFORT="low"
uv run uvicorn ocr_manager.asgi:app --app-dir backend --host 127.0.0.1 --port 8781
```

模型编辑使用 POST 更新，以兼容不转发 PATCH 的内网穿透。

回调与管理入口分别配置；管理入口可使用本机地址或受控 HTTPS 地址。旧的 `OCR_APP_PUBLIC_URL` 继续作为回调地址后备值，管理入口默认本机 `8781`。这两个设置为进程配置，修改后需重启 API 与 Worker。本机开发配置如下：

```bash
export OCR_APP_DEV_MODE=1
export OCR_APP_MASTER_KEY="请替换为有效的 Fernet 主密钥"
export OCR_APP_WEBHOOK_URL="http://127.0.0.1:8781"
export OCR_APP_MANAGEMENT_URL="http://127.0.0.1:8781"
uv run uvicorn ocr_manager.asgi:app --app-dir backend --host 127.0.0.1 --port 8781
```

已有仅当前用户可读的 `.local-data/local/private.json` 时，重启本机实例应沿用该文件中的主密钥和数据目录。在两个终端分别运行以下命令，不能重新生成主密钥，否则已保存的仓库、模型和飞书凭据无法解密：

```bash
OCR_APP_CONFIG_FILE="$PWD/.local-data/local/private.json" \
  uv run uvicorn ocr_manager.asgi:app --app-dir backend --host 127.0.0.1 --port 8781
OCR_APP_CONFIG_FILE="$PWD/.local-data/local/private.json" \
  uv run python -m ocr_manager.worker
```

`127.0.0.1` 只适合本机验证，GitLab 服务器无法访问它。真正接收 GitLab webhook 时，需要把 `OCR_APP_WEBHOOK_URL` 设置为 GitLab 可访问的 HTTPS 地址，并将该地址配置到项目 Webhook。飞书卡片的详情使用 `OCR_APP_MANAGEMENT_URL`，群成员须能够访问该受控地址；只在服务机器查看时可保留本机值。“运维与审计 → 运行监控”可核对生效地址和服务状态；移除管理页面不代表停止独立 monitor 进程。项目访问令牌、模型密钥、飞书 Webhook 与 GitLab Webhook Secret 均在管理台录入，不使用旧的全局 GitLab 或模型环境变量。

采用手动环境变量启动时，另一个终端使用相同配置启动独立 Worker（已有同数据目录 Worker 时不要重复启动）：

```bash
uv run python -m ocr_manager.worker
```

需要独立异常检测、告警投递与孤立工件维护时，在第三个终端使用同一私有配置启动 monitor：

```bash
OCR_APP_CONFIG_FILE="$PWD/.local-data/local/private.json" \
  uv run python -m ocr_manager.alerts
```

monitor 与 Worker 为不同进程，隐藏或移动运行监控入口不会停止它。告警消息是否发送仍受已保存的告警开关与目标配置控制。

访问 `GET /api/health` 可分别核对 API/SQLite、鉴权模式与 Worker：`status=ok` 表示管理进程和数据库可用，`auth_mode=dev` 表示本地开发模式不要求管理口令，`auth_mode=admin` 表示共享管理口令已启用，`auth_mode=users` 表示已在管理页切换为多人账号登录；`worker=running` 表示独立 Worker 正持有单实例锁，`worker=stopped` 时即使页面仍可访问，队列也不会继续消费。概览页会显示同一状态。

开发前端可在 `frontend/` 运行 `npm run dev`，Vite 默认监听 `127.0.0.1:5173` 并代理 `/api` 到 `8781`。生产页面由 FastAPI 从 `frontend/dist` 提供。请在专用系统用户的环境中配置主密钥，限制数据目录权限，并在该用户会话验证 HTTPS Git、OCR 和飞书连接。API、Worker 和 monitor 可分别交给 `launchd` 守护；正式启用 webhook 前须确认重启后所需进程与环境变量均可恢复。

使用 `launchd` 时可将进程配置保存为仅服务用户可读的 JSON 文件，所有配置键均使用上述环境变量原名，值必须为字符串。例如：

```json
{
  "OCR_APP_DATA_DIR": "/absolute/path/to/review-data",
  "OCR_APP_ADMIN_TOKEN": "请替换为随机长口令",
  "OCR_APP_DEV_MODE": "0",
  "OCR_APP_MASTER_KEY": "请替换为有效的 Fernet 主密钥",
  "OCR_APP_OCR_COMMAND": "/absolute/path/to/project/.local-tools/node_modules/.bin/ocr",
  "OCR_APP_REVIEW_LANGUAGE": "zh-CN",
  "OCR_APP_OCR_CONCURRENCY": "4",
  "OCR_APP_OCR_EFFORT": "low",
  "OCR_APP_WEBHOOK_URL": "https://hooks.example.com",
  "OCR_APP_MANAGEMENT_URL": "http://127.0.0.1:8781"
}
```

文件属主须为实际运行的用户，权限不得宽于 `0600`。用以下命令生成 API、Worker、monitor 与每日备份四个不包含密钥的 plist；备份目录须位于业务数据目录之外：

公网入口默认必须使用 HTTPS。仅在临时受控联调且入口确实不支持 HTTPS 时，才可在私有配置中设置 `OCR_APP_ALLOW_INSECURE_HTTP=1`；该开关允许 Webhook 和管理入口使用公网明文 HTTP，不应作为正式部署配置。

```bash
uv run python -m ocr_manager.launchd \
  --project-dir "$PWD" \
  --config-file "/absolute/path/to/private.json" \
  --data-dir "/absolute/path/to/review-data" \
  --backup-dir "/absolute/path/to/review-backups" \
  --backup-hour 3 \
  --backup-minute 0 \
  --output-dir "/absolute/path/to/launchd-output" \
  --no-proxy "gitlab.example.com,127.0.0.1" \
  --node-bin-dir "/absolute/path/to/node-bin" \
  --port 8781
```

当系统代理会处理内网 GitLab 请求时，`launchd` 不会继承终端的 `NO_PROXY`；用 `--no-proxy` 明确填写需要直连的 GitLab 主机和本机地址。遗漏时 GitLab API 可能在 TLS 握手阶段报 `UNEXPECTED_EOF_WHILE_READING`。若 Node.js 安装在 nvm 等用户目录，`--node-bin-dir` 应填写包含可执行 `node` 的绝对目录；`launchd` 不加载 shell 初始化文件，遗漏时 OCR 脚本可能无法运行。生成清单后须重新加载已运行的服务，单纯改写 plist 不会更新进程环境。

生成器不会自动执行 `launchctl`。部署者先核对 plist 的绝对路径、监听端口、备份时间与文件权限，再以专用服务用户安装并启用。当前用户的本机实例可依次运行 `launchctl bootstrap gui/$(id -u) /absolute/path/to/ai.open-code-review.api.plist`、对应的 `worker.plist`、`monitor.plist` 和 `backup.plist`；随后用 `launchctl print gui/$(id -u)/ai.open-code-review.api` 与 `/api/health` 核对进程。API、Worker 和 monitor 共享配置文件，Worker 通过数据目录的文件锁保证单实例；在同一个数据目录启动第二个 Worker 会失败。备份任务由 `StartCalendarInterval` 每日启动一次，也会在加载时执行一次，所以应先启动 API 完成数据库初始化再加载备份任务。停止 Worker 时会清理当前 OCR 进程组，重启时中断尝试计入有限重试次数。

## 质量检查

```bash
uv run ruff check backend
uv run mypy backend/ocr_manager
uv run pytest -q
uv run python -m ocr_manager.openapi_contract
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
```

浏览器回归命令、隔离服务说明和窄屏检查范围见[前端交互回归](frontend-interaction-checks.md)。这些命令是检查入口，不表示每次文档更新都执行过全部检查。

模型设置可在管理台单向录入；已有 API key 不会回显。项目配置列表中的 Webhook Secret 默认遮罩，管理员可按需查看或复制；开发模式免管理员口令，因此只能在可信本机使用。模型配置、每仓库 GitLab Token、Webhook Secret 与飞书地址在 SQLite 中用环境主密钥加密。备份数据库时必须同时妥善备份主密钥。切换启用模型前必须先处理完队列中的事件和评审任务；重新评审在配置变化后会创建新的任务 ID，原结果仍保留。

升级 OCR CLI 或调整服务级评审超时时，应先处理完排队任务。Worker 会比较任务入队时的 OCR、模型与规则快照；配置变化后的旧任务会标为失败，不会用新配置静默执行，可在任务详情中按当前配置重新评审。

### 评审执行策略升级注意事项

2026-11-05 的评审优化第一阶段将数据库版本从 `34` 升至 `35`，为合并前审查增加 `execution_policy` 列；旧记录保持空值，不回填为已采用新策略。新建评审快照增加 `review_policy`，明确整体超时不自动重跑，瞬态故障最多两次完整尝试。升级前必须在副本验证迁移、凭据解密与恢复，并保留数据库及私有配置的成对备份。

第二、三阶段继续迁移 `35 → 36`，增加范围分析、原因、逐次调度与阶段计时；从 34 会依次迁移，旧值保持未知，不补造历史。新快照增加 `input_policy`，`review_policy` 升至版本 2，仍为最多两次完整尝试。配置合计上限 30 秒、预览 60 秒，均受原 OCR 总预算约束。换行分析为 `analyze_only`，自动过滤关闭，项目生产限额和 Token 预算未自动修改。范围、时间口径与兼容探针见[第二、三阶段实施记录](review-performance-phase23.md)。

后续纯换行过滤开关使用独立迁移 `36 → 37`，旧项目默认关闭，不改写 36 的迁移。当前策略版本为 `input_policy.version=2`，项目级开关进入合并前/合并后冻结快照。仅本机运行也需要先备份、处理旧队列，并协调 API 与 Worker 使用同版代码；不能只刷新页面。此次代码实现未迁移或重启本机 `8781` 业务实例。开关与验证见[过滤实施记录](review-newline-filter.md)。

第四阶段使用独立迁移 `37 → 38` 新增执行槽表。正式 Worker 入口在独占进程锁和恢复后启用单协调器、模型/事件/投递各一个执行槽；模型任务总并发仍为 1。Git/OCR 专用进程组栅栏持有 Worker 与资源锁，协调器强杀后终止受控命令组；不能凭过期心跳或删除锁文件强行恢复。无需新增服务或配置开关，同版 Worker 启动后可在“运行监控 → Worker 调度与执行槽”核对。本轮未切换业务实例，细节见[第四阶段记录](review-performance-phase4.md)。

本次发布不能直接重启所有进程：先停止产生新评审的入口并处理在途和排队任务，待 OCR 空闲后协调停止旧 API、Worker 与 monitor，以新代码完成迁移和启动检查，再恢复入口，避免新旧版本混写。未处理的旧合并后快照会按既有配置冲突机制失败；旧合并前任务也会提示“执行策略已变化”，由管理员确认后通过重新审查创建新策略任务，不能直接修改数据库快照绕过校验。终态历史结果不改写，也不自动批量重跑历史失败。

“问题与改进”第一阶段另有独立迁移 `38 → 39`，只新增平台台账及历史快照表，不导入聊天、不改写评审记录。升级前仍须成对备份数据库与私有配置，并按上述要求协调同版 API、Worker 和 monitor；新 API 启动时会执行迁移，不能让旧 Worker 继续混写新版库。迁移后需验证菜单新建、编辑与历史读取；记录中“部署已生效”只是人工填报，不是自动部署或健康检查。本轮仅操作隔离测试库，未迁移当前业务实例，详见[第一阶段记录](improvements-phase1.md)。

第二阶段由第 39 版升至第 40 版，仅新增优化主题、阶段、显式问题关联及主题历史表，不自动导入或推断历史归属。旧版代码会拒绝高版本数据库（该阶段源码目标为 40，当前第四阶段目标为 41，不代表业务库已经升级）；回退须停止相关进程，在新目录恢复升级前的成对备份，并先明确升级后新增事件、任务、通知和台账记录的补偿方案，不得降低 `user_version` 或直接覆盖活跃数据库。第一阶段快照也属于旧策略，未执行队列须同样处理，不能只检查 34 之前的任务。以上为部署前要求，本地实现不代表已经升级生产服务。

第三阶段“复盘汇总”只读现有第 40 版表，无新增迁移、后台任务或配置开关。上线需要配套 API 与前端，不能仅复制新前端到旧 API；升级后应验证管理员统计读取、只读账号拒绝、日期及分类口径和空数据/查询失败的区别。统计中的状态仍为人工记录，不自动验证部署。此轮未操作业务实例，详见[第三阶段说明](improvements-phase3.md)。

仓库设置中的“测试 Git”“测试 GitLab API”、飞书配置中的连接测试和 Agent 模型中的“测试模型”会建立独立诊断任务，由 Worker 异步执行并显示最近结果。Git 测试实际拉取目标分支；GitLab API 测试读取项目与目标分支，并核对 HTTPS Clone URL 的仓库路径；模型测试调用 `ocr llm test`，可能消耗少量模型额度；飞书测试会向已保存的目标群发送“Open Code Review 连接测试”。先保存配置，再发起测试；连接测试状态不等同于真实 MR 评审验收。失败摘要不保存外部响应或凭据。

在线备份命令如下，支持数据库以 WAL 模式运行时执行，并对副本做完整性检查。传入私有配置文件后，同批生成同名 `.private.json`，包含解密数据库凭据所需的主密钥。备份目录权限为 `0700`，快照文件权限为 `0600`；异机副本应加密保管。携带 `--config-file` 的成对备份默认保留 90 天且至少保留最近两份，可通过 `--retain-days` 调整。仅数据库备份不执行这组成对清理策略；正式部署应确认主密钥副本与保留期。

```bash
uv run python -m ocr_manager.backup \
  --data-dir "$OCR_APP_DATA_DIR" \
  --config-file "/path/to/private.json" \
  --output-dir "/path/to/review-backups"
```

恢复工具要求目标目录尚不存在，并使用同批数据库及私有配置快照生成恢复目录：

```bash
uv run python -m ocr_manager.backup \
  --restore-from "/path/to/review-backups/app-YYYYMMDD-HHMMSS.db" \
  --restore-to "/path/to/new-restore-data"
```

先核对新目录的 `app.db` 和 `private.json`，切换前停止 API、Worker 和 monitor，确保配置指向恢复后的数据目录，再按原主密钥启动并检查仓库、任务和凭据可解密。不要覆盖正在运行的 `app.db`。备份目录须在数据目录外，正式环境还应安排加密异机副本及定期恢复演练。

可先在同批备份上做隔离恢复演练。命令会在 `--output-dir` 下创建临时副本，执行 SQLite 完整性检查、数据库迁移和已保存凭据解密验证；演练结束后删除临时恢复副本，仅保留权限为 `0600` 的脱敏结果记录：

```bash
uv run python -m ocr_manager.backup \
  --drill-from "/path/to/review-backups/app-YYYYMMDD-HHMMSS.db" \
  --output-dir "/path/to/recovery-drills"
```

普通恢复会在新数据目录写入 `restore-manifest.json`，记载备份标识、数据库版本、完整性结果和操作时间。它与备份数据同样受文件权限保护。

“运维与审计 → 数据对账”按 SQLite 事件、任务、尝试、通知及工件目录报告不一致，不自动修改事件状态或删除目录。下载的诊断包仅含状态、时间、错误是否存在和关联 ID，不含凭据、评审发现正文、原始代码或模型推理内容。收到错误报告时优先提供包内的 `correlation_id`，配合响应 `X-Request-ID` 定位。

## 试点验收

先接入一个测试仓库：保存仓库与模型配置，手动在 GitLab 项目中创建 webhook，发送非合并测试投递确认鉴权与连通性，再合并测试 MR。核对事件、每个 commit 的任务、OCR JSON/preview 工件及飞书投递状态；分别演练重复 webhook、GitLab API 暂时失败、OCR 失败、通知失败和人工重发。当前自动测试用合成 GitLab/OCR/飞书服务验证本地闭环，真实 GitLab、模型和飞书验收必须在具备上述凭据的 Mac mini 环境执行。

第四阶段由第 40 版升至第 41 版，为问题、主题及历史添加归档元数据和历史动作，旧数据保持未归档，不自动整理或删除内容。归档期间禁止编辑；恢复与归档共用内容版本，历史、关联和三个交付维度不变。累计及待办仍包含归档内容。上线前需备份并验证旧库迁移、默认/归档/全部范围、两类对象归档恢复、409 冲突、只读权限、关联与复盘口径；必须配套同版前后端及共享库进程，不允许旧进程混写。源码和本地验证不代表部署完成，本轮未访问业务实例，见[第四阶段说明](improvements-phase4.md)。

## 台账同步与自动归档（42 版）

42 版只新增后台策略和 PI 来源游标，不自动启用。管理员在“问题与改进 → 自动归档与台账同步”设置；完整闭环、无遗留且连续 30 天无更新才自动收纳，恢复后重新计时。`OCR_APP_IMPROVEMENT_LOG_PATH` 在受控私有配置中指定台账文件；API 不返回路径，HTTP 不扫描来源或执行归档。独立 monitor 每 30 秒同步及维护，与告警开关无关；启用策略后须验证该进程确实运行、最近检查时间前进、错误码为空，并确认页面 PI 编号、历史和优化历程。来源或页面冲突不覆盖，整轮跳过自动归档。备份、升级、命令及故障边界见[台账维护说明](improvements-phase5.md)。


## macOS 本机只读数据库检查

本机核查发现，系统自带的 `/usr/bin/sqlite3 -readonly` 在 WAL 数据库的 `-wal`、`-shm` 旁路文件不存在时可能报 `unable to open database file (14)`；隔离合成 WAL 库可复现，同环境 DELETE 模式库不报错。该错误本身不证明业务库损坏，也不能通过改用绝对路径保证解决。不要删除数据库、旁路文件或放宽权限，也不要对运行库使用 `immutable=1` 绕过 WAL。

当前本地实例可从项目根目录使用项目虚拟环境 Python 进行只读检查；其他实例须替换为实际业务库路径，不得误用 `.local-data/app.db`：

```sh
.venv/bin/python - <<'PY'
from pathlib import Path
import sqlite3

path = Path('.local-data/local/app.db').resolve(strict=True)
connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
try:
    print('数据库版本：', connection.execute('PRAGMA user_version').fetchone()[0])
    print('完整性检查：', connection.execute('PRAGMA quick_check').fetchone()[0])
finally:
    connection.close()
PY
```

当前代码的目标数据库版本为 48；读到该版本只证明结构已升级，不代表 Worker、monitor、前端或预算诊断已就绪。`/api/health` 中 `worker=stopped` 表示独立 Worker 尚未运行，与上述只读命令错误分别处理。

## 部分评审补审的版本发布边界

人工失败子集补审默认可用，不再设置功能开关或项目白名单；来源完整性、权限、并发互斥和预算校验保留。schema 46 新增独立历史诊断表，47 增加限定会话混合记录，48 增加预算数字证据及单任务人工额度授权，需要同版 API/Worker/monitor/前端；迁移不自动扫描工件、增加额度、回填候选或发送历史补充通知。最大批次和累计批准 Token 仍有默认上限；Token 上限不代替真实费用额度，见[补审预算说明](recovery-budget.md)。运行健康或 API 单进程升级不能替代整套部署确认。

[部分评审完整恢复与上线准备](review-partial-rollout.md)提供副本迁移事实、成对备份/恢复、真实根因试点及回退步骤。先在新目录演练，再协调在途任务发布；禁止直接降低 schema 版本、让旧进程打开新库或覆盖新版本产生的业务事实。本文档不表示本轮已经部署或启用。

历史诊断批量预览、导入、审计与失效规则见[受控历史诊断导入](review-historical-diagnostic-import.md)。旧版默认关闭/项目白名单操作单只代表历史阶段，不再用于当前版本。
