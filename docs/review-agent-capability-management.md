# 自建 Agent 能力管理操作指南

## 在已有任务上验证

1. 打开「系统设置 → 自建 Agent → Skill」。创建一个与你的样本实际文件类型匹配的检查方法，例如 `*.tsx`，填写可通过代码证据核实的检查步骤。发布后得到独立的 Skill 版本。
2. 回到「评审方案」，复制「基础逐页评审」为新草稿。选择「加载 Skill」及刚发布的版本。需要跨文件上下文时，添加「补查相关文件」，填写触发匹配式和同一仓库中读取的具体相对路径。通过上移、下移调整可选步骤。
3. 打开「项目配置 → 编辑项目 → 自建 Agent」。如该仓库试点尚未启用，可以在这里开启。Agent 模型沿用项目配置，也可以从已保存的评审模型档案中单独选择。
4. 回到方案草稿，填入任务编号，例如 `611`，点「预览命中范围」。表格显示固定提交中的匹配结果；预览无需调用模型。点「试跑此方案」并确认后，页面打开这次独立的双评审记录。
5. 在双评审展开「查看本次 Agent 配置与执行」，查看方案、模型版本、Skill 和实际步骤。打开具体发现，可以看到模型所引用、经 Worker 校验的补查或规范证据。原来的阿里 OCR 初审仍是本次对照。
6. 满意后发布草稿，并在项目设置里选择该发布版本。切回先前方案即可回退项目绑定。任务详情可按当前配置重跑；已有能力记录且属于同一 OCR 初审的比较可以作为原配置重跑的依据。历史比较继续显示保存时的版本。

## 接入只读 MCP

1. 打开「系统设置 → 自建 Agent → MCP 服务」，登记团队规范的 HTTPS Streamable HTTP 服务。当前接入使用公网 IPv4 和 443 端口，可保存一个限制在规范检索范围内的 Bearer 令牌。服务端工具需标记 `readOnlyHint: true`，支持使用一个字符串参数检索。
2. 点「测试连接并发现工具」。Worker 会协商会话并列出符合约束的工具。在服务卡中选择仓库和工具，保存授权。
3. 在方案草稿中添加「查询 MCP 规范」。选择服务和已发现的工具，填入查询参数名、固定查询词和差异文件匹配式。设置失败时继续评审并留记录，或结束本次 Agent 评审。
4. 从单个项目试跑。确认规范证据里有文档标识、版本或检索时间、内容摘要。撤销授权或停用服务会阻止后续调用。方案固定查询词会发送给 MCP，代码差异和补查文件只按 Agent 运行配置发给选定模型。

## 运行与数据口径

- 发布后的方案正文、Skill 和服务版本使用不可变记录。更新 Skill 内容或更换 MCP 端点、令牌时，登记新版本并创建新的方案。当前可选编排节点是 Skill、固定文件补查和 MCP，读取差异及证据校验始终执行。文件补查读取头提交的普通文本，模型通过页内引用指向已提供的辅助证据。
- 业务 SQLite 升级到 58 时，初始化「基础逐页评审」。新运行保存方案版本、模型档案版本、Skill 和 MCP 选择。管理页更新与试点开关使用既有项目授权，预览和 MCP 发现都由独立 Worker 执行。
- 草稿试跑和正式比较都有单独的尝试记录与状态。试跑带明确标签，既有 OCR、飞书投递和 GitLab 发布链路不会因预览、试跑或 Agent 重跑再次触发。
- MCP 的可调用工具受仓库授权、协议签名、超时及响应体大小限制。每次运行至多发送一次配置的规范查询；失败不自动重复查询。已有比较中缺少能力快照时显示「历史运行未记录能力配置」。

## 本地验证命令

```bash
.venv/bin/python -m pytest -q backend/tests/test_agent_capability_management.py
PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract
npm --prefix frontend run lint
```

浏览器验收使用隔离模型及临时 SQLite。先单独构建前端再运行测试：

```bash
npm --prefix frontend run build -- --outDir /tmp/open-code-review-agent-build
cd frontend
OCR_BROWSER_AGENT_COMPARISON=1 OCR_BROWSER_AGENT_PILOT=1 OCR_BROWSER_AGENT_CAPABILITIES=1 \
OCR_BROWSER_FRONTEND_DIST=/tmp/open-code-review-agent-build \
  ./node_modules/.bin/playwright test agentCapabilities.spec.ts
```
