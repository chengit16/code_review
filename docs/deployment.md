# 本地部署与联调

模型、共享飞书通道、HTTPS 仓库和统一 GitLab Webhook 的填写步骤见[后台配置与接入操作](./configuration-guide.md)。

## 前置条件

- Python 3.12、`uv`、Node.js、Git 2.41 或更新版本。
- 固定版本的 Alibaba Open Code Review CLI，确认 `ocr version` 与 `ocr review --help` 可运行。当前开发机已将 `1.12.9` 安装在项目本地 `.local-tools/`，并验证空变更与单文件变更的 preview JSON；真实模型评审尚未联调。
- GitLab 项目访问令牌、可从 GitLab 访问的 HTTPS 回调地址、飞书群机器人 webhook 和 OCR 模型 API key。

默认服务仅监听 `127.0.0.1:8000`。反向代理只向 GitLab 开放 `/api/webhooks/gitlab`，管理 API 和页面通过本机或受控内网访问。新项目从管理台复制统一回调地址与自动生成的 Webhook Secret 到 GitLab，并按项目开关选择 Merge request events 和 Push events。

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
export OCR_APP_PUBLIC_URL="https://review.example.com"
export OCR_APP_OCR_COMMAND="$PWD/.local-tools/node_modules/.bin/ocr"
uv run uvicorn ocr_manager.asgi:app --app-dir backend --host 127.0.0.1 --port 8000
```

本机开发使用其他端口时，`OCR_APP_PUBLIC_URL` 必须与 API 端口一致，例如 8780：

```bash
export OCR_APP_DEV_MODE=1
export OCR_APP_MASTER_KEY="请替换为有效的 Fernet 主密钥"
export OCR_APP_PUBLIC_URL="http://127.0.0.1:8780"
uv run uvicorn ocr_manager.asgi:app --app-dir backend --host 127.0.0.1 --port 8780
```

`127.0.0.1` 只适合本机验证，GitLab 服务器无法访问它。真正接收 GitLab webhook 时，需要把 `OCR_APP_PUBLIC_URL` 设置为 GitLab 可访问的 HTTPS 地址，并将该地址配置到项目 Webhook。项目访问令牌、模型密钥、飞书 Webhook 与 GitLab Webhook Secret 均在管理台录入，不使用旧的全局 GitLab 或模型环境变量。

另一个终端使用相同环境变量启动独立 Worker：

```bash
uv run python -m ocr_manager.worker
```

访问 `GET /api/health` 可分别核对 API/SQLite、鉴权模式与 Worker：`status=ok` 表示管理进程和数据库可用，`auth_mode=dev` 表示本地开发模式不要求管理口令，`auth_mode=admin` 表示生产管理口令已启用；`worker=running` 表示独立 Worker 正持有单实例锁，`worker=stopped` 时即使页面仍可访问，队列也不会继续消费。概览页会显示同一状态。

开发前端可在 `frontend/` 运行 `npm run dev`，Vite 默认监听 `127.0.0.1:5173` 并代理 `/api` 到 8000。生产页面由 FastAPI 从 `frontend/dist` 提供。请在专用系统用户的环境中配置主密钥，限制数据目录权限，并在该用户会话验证 HTTPS Git、OCR 和飞书连接。两个进程可分别交给 `launchd` 守护；正式启用 webhook 前须确认重启后两个进程与环境变量均可恢复。

使用 `launchd` 时可将进程配置保存为仅服务用户可读的 JSON 文件，所有配置键均使用上述环境变量原名，值必须为字符串。例如：

```json
{
  "OCR_APP_DATA_DIR": "/absolute/path/to/review-data",
  "OCR_APP_ADMIN_TOKEN": "请替换为随机长口令",
  "OCR_APP_DEV_MODE": "0",
  "OCR_APP_MASTER_KEY": "请替换为有效的 Fernet 主密钥",
  "OCR_APP_OCR_COMMAND": "/absolute/path/to/project/.local-tools/node_modules/.bin/ocr",
  "OCR_APP_PUBLIC_URL": "https://review.example.com"
}
```

文件属主须为实际运行的用户，权限不得宽于 `0600`。用以下命令生成 API、Worker 与每日备份三个不包含密钥的 plist；备份目录须位于业务数据目录之外：

```bash
uv run python -m ocr_manager.launchd \
  --project-dir "$PWD" \
  --config-file "/absolute/path/to/private.json" \
  --data-dir "/absolute/path/to/review-data" \
  --backup-dir "/absolute/path/to/review-backups" \
  --backup-hour 3 \
  --backup-minute 0 \
  --output-dir "/absolute/path/to/launchd-output" \
  --port 8000
```

生成器不会自动执行 `launchctl`。部署者先核对 plist 的绝对路径、监听端口、备份时间与文件权限，再以专用服务用户安装并启用。API 与 Worker 共享配置文件，Worker 通过数据目录的文件锁保证单实例；在同一个数据目录启动第二个 Worker 会失败。备份任务由 `StartCalendarInterval` 每日启动一次，也会在加载时执行一次，所以应先启动 API 完成数据库初始化再加载备份任务。停止 Worker 时会清理当前 OCR 进程组，重启时中断尝试计入有限重试次数。

## 质量检查

```bash
uv run ruff check backend
uv run mypy backend/ocr_manager
uv run pytest -q
cd frontend && npm run lint && npm run build
```

模型设置可在管理台单向录入；已有 API key 不会回显。GitLab Webhook 页面中的 Secret 默认遮罩，管理员可按需查看或复制；开发模式免管理员口令，因此只能在可信本机使用。模型配置、每仓库 GitLab Token、Webhook Secret 与飞书地址在 SQLite 中用环境主密钥加密。备份数据库时必须同时妥善备份主密钥。切换启用模型前必须先处理完队列中的事件和评审任务；重新评审在配置变化后会创建新的任务 ID，原结果仍保留。

升级 OCR CLI 或调整服务级评审超时时，应先处理完排队任务。Worker 会比较任务入队时的 OCR、模型与规则快照；配置变化后的旧任务会标为失败，不会用新配置静默执行，可在任务详情中按当前配置重新评审。

仓库设置中的“测试 Git”“测试 GitLab API”、飞书配置中的连接测试和 Agent 模型中的“测试模型”会建立独立诊断任务，由 Worker 异步执行并显示最近结果。Git 测试实际拉取目标分支；GitLab API 测试读取项目与目标分支，并核对 HTTPS Clone URL 的仓库路径；模型测试调用 `ocr llm test`，可能消耗少量模型额度；飞书测试会向已保存的目标群发送“Open Code Review 连接测试”。先保存配置，再发起测试；连接测试状态不等同于真实 MR 评审验收。失败摘要不保存外部响应或凭据。

在线备份命令如下，支持数据库以 WAL 模式运行时执行，并对副本做完整性检查。备份目录应由专用服务用户持有；快照文件权限设为 `0600`。备份不自动删除旧文件，保留期应在正式部署时确定。

```bash
uv run python -m ocr_manager.backup \
  --data-dir "$OCR_APP_DATA_DIR" \
  --output-dir "/path/to/review-backups"
```

恢复演练时先停止 API 与 Worker，把选定快照复制到新的空数据目录并设为服务用户所有、`0600` 权限，然后使用同一主密钥启动服务并检查仓库、事件、任务与凭据可解密。不要直接覆盖正在运行的 `app.db`。每日备份清单不会自动清理历史副本；正式环境需根据磁盘容量确定保留期和异机副本位置，并定期执行恢复演练。

## 试点验收

先接入一个测试仓库：保存仓库与模型配置，手动在 GitLab 项目中创建 webhook，发送非合并测试投递确认鉴权与连通性，再合并测试 MR。核对事件、每个 commit 的任务、OCR JSON/preview 工件及飞书投递状态；分别演练重复 webhook、GitLab API 暂时失败、OCR 失败、通知失败和人工重发。当前自动测试用合成 GitLab/OCR/飞书服务验证本地闭环，真实 GitLab、模型和飞书验收必须在具备上述凭据的 Mac mini 环境执行。
