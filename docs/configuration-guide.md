# 后台配置与接入操作

本文依据飞书《Review后台配置操作手册》的四块配置流程编写，并按本项目的 Alibaba Open Code Review（OCR）评审引擎调整模型设置。配置保存在 `OCR_APP_DATA_DIR/app.db`，凭据使用 `OCR_APP_MASTER_KEY` 加密；修改后台配置后无需重启 API 或 Worker。

## 1. 新增并启用模型

打开管理台的 **Agent 模型**，点击“新增模型”，填写配置名称、OCR Provider、精确模型标识和 API Key。使用 OCR 内置 Provider 时，Base URL 留空；连接 OpenAI 兼容服务时填写无凭据的 HTTPS API 根地址，通常以 `/v1` 结尾，不能填写只返回网页的站点首页。平台会在隔离的 OCR 配置目录中建立自定义 Provider。保存后在列表中点击“启用”，再运行“测试模型”。模型可在列表中编辑；编辑时 API Key 留空表示保留原密钥。系统同一时间只启用一个模型；首次启用可处理此前积压的事件，后续切换或修改启用模型时须先让队列清空，避免旧任务使用不同配置运行。

本项目使用 OCR CLI，不使用文档中的 Codex 登录认证或 Responses API 配置。因此模型标识和 API Key 是必填项，自定义 Base URL 需兼容 OCR 的 OpenAI 协议。模型密钥不会出现在列表、审计日志或评审工件中。

## 2. 新增飞书配置

在接收审核通知的飞书群中添加自定义机器人，复制完整 Webhook URL。建议在机器人安全设置中启用签名校验，并复制同一机器人的签名密钥。打开管理台的 **飞书配置**，填写配置名称、Webhook URL 和可选签名密钥并保存。

一个飞书配置可以关联多个仓库。修改该配置后，后续投递和连接测试会读取新值；删除配置会解除所有仓库关联，仓库及其评审历史仍保留。关联仓库后，可在飞书配置的编辑窗口发起连接测试；测试会向目标群发送一条消息。

## 3. 新增仓库

先在 GitLab 项目的 **Settings / Access Tokens** 创建项目访问令牌，设置到期时间，并授予读取代码和调用项目 API 所需的最低角色及 `api`、`read_repository` scope。令牌创建后应立即复制。

打开 **项目配置**，填写：

| 字段 | 填写方式 |
| --- | --- |
| 项目数字 ID | GitLab 项目首页或 Settings / General 显示的数字 ID。 |
| 仓库名称 | 管理台显示名称。 |
| 仓库路径 | 完整命名空间，例如 `team/order-service`。 |
| Clone URL | GitLab 的无用户名、密码和 Token 的 HTTPS 地址，例如 `https://gitlab.example.com/team/order-service.git`。 |
| 目标分支 | GitLab 默认分支，例如 `main`。 |
| GitLab Token | 上一步创建的项目或群组访问令牌。每仓库建议独立。 |
| Webhook Secret | 保存仓库时由服务端自动生成，随后在项目配置列表查看。 |
| 飞书配置 | 选择第 2 步创建的通知通道。 |
| Merge Request 审核 | 需要审查已合并 MR 时开启。 |
| 默认分支 Push 审核 | 需要审查直接推送到默认分支的提交时开启。 |

保存后立即加入运行时配置；飞书配置可暂不关联，之后在仓库编辑窗口关联。编辑窗口预填仓库名称、GitLab 地址、数字 ID、仓库路径、Clone URL、目标分支、飞书关联和事件开关，并提供 Git 与 GitLab API 连接测试。GitLab Token 和 Webhook Token 不在编辑表单回填明文，前者可单向替换，后者可按需查看、复制或轮换。项目数字 ID 或 GitLab 地址录错时，可在收到合法 Webhook 或产生评审事件之前直接修正；有待处理事件或评审任务时，暂不允许修改仓库来源或分支。HTTPS Git 拉取通过临时 `GIT_ASKPASS` 读取项目令牌；令牌不写入 Clone URL、Git 命令参数或本地 Git 配置。旧数据库中的 SSH 项目可读取历史记录，但继续运行前需要在项目编辑窗口补录独立 GitLab Token；管理台新建项目只使用上述字段。

## 4. 配置 GitLab Webhook

在 **项目配置** 页面复制统一回调地址，并从对应仓库行查看或复制 Webhook Secret。进入对应 GitLab 项目的 **Settings / Webhooks**：

1. URL 填写管理台给出的 HTTPS 回调地址，路径为 `/api/webhooks/gitlab`。
2. Secret token 填写该仓库的 Webhook Secret。列表默认遮罩，可按需查看和复制。重新生成后必须同步更新 GitLab。
3. 开启 Merge Request 审核时勾选 **Merge request events**；开启默认分支 Push 审核时再勾选 **Push events**。
4. 保持 SSL verification 开启并保存。

GitLab 必须能访问回调地址。`127.0.0.1` 只适合本机开发，正式部署应由受控 HTTPS 入口仅转发 `/api/webhooks/gitlab`。不匹配的项目、分支或未启用事件返回 HTTP 204；匹配项目的错误 Secret 返回 HTTP 401。MR 只在合并后入队；默认分支 Push 只审查快进更新，首次创建分支、删除分支和强制改写历史不会自动审查。

## 5. 验收与安全

在 **审核规则** 页面选择“全局规则”或具体项目后，可添加按文件路径匹配的审核内容，并配置额外纳入或排除的路径。规则条目按页面顺序匹配，首条命中生效；“同时保留 OCR 内置语言规则”对应 `merge_system_rule`。项目页面规则优先于仓库提交的 `.opencodereview/rule.json`，全局页面规则是仓库文件之后的兜底。保存后仅影响后续任务；已有排队或运行中评审时，系统会拒绝修改适用规则。页面下方保留最近 50 个规则版本，删除配置也会生成历史版本；恢复旧版本会新增一条恢复记录，同样受待处理任务保护。核对仓库文件规则时使用 `ocr rules check <文件路径>`；核对页面项目规则时，可将任务运行目录中的 `managed-rule.json` 传给 `ocr rules check --rule <规则文件> <文件路径>`。

在 GitLab 项目的 Webhooks 页面发送测试事件，确认管理台的项目配置列表最近验证时间更新；随后合并测试 MR 或向默认分支推送测试提交。到 **GitLab 事件** 和 **评审任务** 查看逐提交状态，确认飞书群收到通知。当前 OCR 工作流不向 GitLab MR 写 note；MR 结果可在管理台和飞书查看，Push 结果只发送飞书通知。

开发模式 `OCR_APP_DEV_MODE=1` 仅适用于可信本机；正式环境必须设置 `OCR_APP_ADMIN_TOKEN`，并限制管理页网络访问。`OCR_APP_MASTER_KEY`、数据库和备份都应按敏感文件保护。不要把 GitLab Token、Webhook Secret、飞书 URL、签名密钥或模型 API Key 写入 Git、截图、Issue 或日志。

飞书手册的 `service.env`、`projects.yaml` 和 `CODEX_*` 首次导入命令属于另一套实现；本项目当前通过管理台和 `OCR_APP_*` 进程配置接入，不会读取这些文件。运行服务和 Worker 的步骤见[部署说明](./deployment.md)。
