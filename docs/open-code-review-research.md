# Alibaba Open Code Review 调研笔记

> 调研时间：2026-09-25；核对的官方仓库提交为 [`486022daaf14f7142275eddb9b3cacc3cc5dadfa`](https://github.com/alibaba/open-code-review/commit/486022daaf14f7142275eddb9b3cacc3cc5dadfa)。本文只记录 Alibaba 官方仓库、官方文档和仓库内集成文件中可以核实的事实；“建议”部分是针对本项目“Mac Mini 监控 Git、OCR 审查、飞书通知”的设计判断。

## 结论摘要

- **本项目首选 `ocr review --format json --audience agent`。** OCR 自己选择 Git diff 文件、解析规则、调用配置的 LLM 并输出逐行评论；Mac Mini 只需要负责 Git 触发、结果校验和飞书投递。[官方 README](https://github.com/alibaba/open-code-review/blob/main/docs/i18n/README.zh-CN.md) [官方 CLI 文档](https://open-codereview.ai/docs/cli-reference)
- **`ocr delegate` 保留为以后切换到 Codex 宿主模型的可选项。** 该模式只输出范围和规则，不调用 OCR 的 LLM；若启用它，需要另行实现 Agent 审查、覆盖统计和结果格式化。[官方 Delegation Skill](https://github.com/alibaba/open-code-review/blob/main/plugins/open-code-review/skills/open-code-review-delegate/SKILL.md) [官方命令实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/delegate_cmd.go)
- **官方集成清单未列出飞书通知。** 官方提供本地 CLI、Coding Agent 插件及多种 CI/CD 集成；本项目需要小型编排层读取 OCR JSON 并调用飞书机器人或应用 API。[官方集成清单](https://github.com/alibaba/open-code-review/blob/main/docs/i18n/README.zh-CN.md) [官方 CI/CD 文档](https://open-codereview.ai/docs/cicd)

## 1. 两种执行模式

| 模式 | OCR 做什么 | 谁调用模型 | 适合本项目吗 |
| --- | --- | --- | --- |
| 默认 `ocr review` | 选择 diff 文件、匹配规则、调用工具、定位和过滤评论，输出结构化结果 | OCR 配置的 LLM | **首选**：可直接给飞书编排层提供 JSON 评论和覆盖信息。[官方 README](https://github.com/alibaba/open-code-review/blob/main/docs/i18n/README.zh-CN.md) [官方 JSON 输出实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/output.go) |
| `ocr delegate` | 只输出审查范围、引用信息和按内容分组的规则，不需要 LLM 配置 | 宿主 Agent | 未来需要用 Codex 订阅额度或独立 Agent 审查时再启用。[官方 Delegation Skill](https://github.com/alibaba/open-code-review/blob/main/plugins/open-code-review/skills/open-code-review-delegate/SKILL.md) |

Delegation Mode 的可选流程是：

1. `ocr delegate preview --format json` 输出 `mode`、`from`、`to`、`commit`、`merge_base`、可审查文件和排除文件；每个文件包含状态、增删行数以及排除原因。[官方命令实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/delegate_cmd.go)
2. 将第一步的可审查路径传给 `ocr delegate rule --format json <path...>`；OCR 会把使用同一规则文本的文件分到同一组，并返回 `group_id`、规则来源、匹配模式、文件列表和规则正文。[官方命令实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/delegate_cmd.go)
3. 宿主 Agent 根据 `mode` 和引用信息自行执行 `git diff`、`git show` 或读取工作区文件，然后逐文件审查；官方 Skill 要求每个 preview 文件最终标记为已审查或带原因跳过。[官方 Delegation Skill](https://github.com/alibaba/open-code-review/blob/main/plugins/open-code-review/skills/open-code-review-delegate/SKILL.md)
4. 宿主 Agent 输出包含 `path`、`content`、可选 `start_line`/`end_line`、`category`、`severity` 的 finding；类别包括 `bug`、`security`、`performance`、`maintainability`、`test`、`style`、`documentation`、`other`，严重性包括 `critical`、`high`、`medium`、`low`。[官方 Delegation Skill](https://github.com/alibaba/open-code-review/blob/main/plugins/open-code-review/skills/open-code-review-delegate/SKILL.md) [官方模型定义](https://github.com/alibaba/open-code-review/blob/main/internal/model/review.go)

**限制：** Delegation Mode 的 `--format` 只支持 `text` 和 `json`，不支持 `sarif`；它本身也不会替宿主 Agent 生成最终评论或调用飞书 API。[官方共享参数](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/shared_flags.go) [官方 Delegation Skill](https://github.com/alibaba/open-code-review/blob/main/plugins/open-code-review/skills/open-code-review-delegate/SKILL.md)

## 2. 安装与运行环境

- Git `>= 2.41` 是官方前置条件，OCR 依靠 Git 生成 diff、搜索代码和读取仓库内容。[官方中文 README](https://github.com/alibaba/open-code-review/blob/main/docs/i18n/README.zh-CN.md)
- npm 全局安装方式为 `npm install -g @alibaba-group/open-code-review`，安装后提供全局 `ocr` 命令；npm 包声明 Node.js `>=14`，并通过平台可选依赖携带原生二进制。[官方中文 README](https://github.com/alibaba/open-code-review/blob/main/docs/i18n/README.zh-CN.md) [官方 package.json](https://github.com/alibaba/open-code-review/blob/main/package.json)
- **固定版本时必须处理 npm 自动更新。** 官方安装文档称 npm wrapper 默认每次运行都在后台检查新版本，发现后自动升级；生产部署可用 `npm install -g @alibaba-group/open-code-review@<version>` 固定初始版本，并设置 `OCR_NO_UPDATE=1` 停用自动更新。静态二进制不参与 npm wrapper 的自动更新。[官方安装文档](https://github.com/alibaba/open-code-review/blob/main/pages/src/content/docs/zh/installation.md) [官方 npm 启动器](https://github.com/alibaba/open-code-review/blob/main/bin/ocr.js)
- 官方安装文档还列出 Homebrew、macOS/Linux 安装脚本、Windows PowerShell 安装脚本、GitHub Release 二进制和源码构建方式。[官方安装文档](https://open-codereview.ai/docs/installation) [官方安装脚本](https://github.com/alibaba/open-code-review/blob/main/install.sh) [官方 Windows 脚本](https://github.com/alibaba/open-code-review/blob/main/install.ps1)
- `install.sh` 默认安装到 `/usr/local/bin`，可用 `OCR_INSTALL_DIR` 指定目录、`OCR_VERSION` 固定版本；脚本下载发布资产和 `sha256sum.txt` 后校验 SHA-256。设置 `OCR_GITHUB_MIRROR` 会走非官方镜像，脚本明确警告此时 checksum 完整性不保证。[官方安装脚本](https://github.com/alibaba/open-code-review/blob/main/install.sh)
- 官方安全策略说明发布二进制和 checksum 还提供 GitHub Artifact Attestations，可用 `gh attestation verify` 校验；生产机器应优先固定版本并做校验。[官方安全策略](https://github.com/alibaba/open-code-review/blob/main/.github/SECURITY.md)
- 安装后可运行 `ocr version` 检查版本、提交和构建日期，并用 `ocr --help`、`ocr review --help` 确认命令和参数。[官方安装文档](https://github.com/alibaba/open-code-review/blob/main/pages/src/content/docs/zh/installation.md)

## 3. `ocr review` 的输入范围

- 不带范围参数的 `ocr review` 是工作区模式，覆盖已暂存、未暂存和未跟踪变更。[官方中文 README](https://github.com/alibaba/open-code-review/blob/main/docs/i18n/README.zh-CN.md)
- `ocr review --from <ref> --to <ref>` 是基于 merge-base 的分支范围审查；`ocr review --commit <sha>` 审查单个提交相对父提交的差异。`--from/--to` 与 `--commit` 不能混用，指定一个范围端点时必须同时指定另一个。[官方 CLI 参数实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/shared_flags.go) [官方 CLI 文档](https://open-codereview.ai/docs/cli-reference)
- `ocr scan` 是全文件扫描，不依赖有意义的 diff 或 Git 历史；可以扫描仓库、目录或文件，非 Git 目录会回退到遵循 `.gitignore` 的文件系统遍历。[官方 CLI 文档](https://open-codereview.ai/docs/cli-reference)
- `--preview` 只列出审查范围和统计信息，不调用 LLM，也不产生模型费用；这适合在 OCR 正式审查前做范围确认。[官方 CLI 文档](https://open-codereview.ai/docs/cli-reference) [官方共享参数](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/shared_flags.go)
- `--background` 或 `--background-file` 可传入需求/业务上下文；相对路径从仓库根目录解析。**两者同传时，当前实现只采用文件内容，忽略 inline 文本并向 stderr 警告。** 官方中文 CLI 文档目前称“两者合并”，与实现和测试不一致；编排层应只传其中一种。文件原始大小上限为 1 MiB，清洗后内容硬上限为 8000 字符，超过 2000 字符会给出质量警告。[官方实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/background_file.go) [官方测试](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/background_file_test.go) [存在冲突的官方文档](https://github.com/alibaba/open-code-review/blob/main/pages/src/content/docs/zh/cli-reference.md)

## 4. 配置 LLM（仅默认模式需要）

- 交互式配置入口是 `ocr config provider` 和 `ocr config model`；配置文件默认位于 `~/.opencodereview/config.json`，配置向导会测试连接。[官方中文 README](https://github.com/alibaba/open-code-review/blob/main/docs/i18n/README.zh-CN.md) [官方配置文档](https://open-codereview.ai/docs/configuration)
- 官方支持 Anthropic Messages API、OpenAI Chat Completions API、OpenAI Responses API 和 AWS Bedrock；内置供应商包含 Alibaba DashScope 等，也可以配置兼容协议的自定义供应商。[官方 LLM 客户端](https://github.com/alibaba/open-code-review/blob/main/internal/llm/client.go) [官方供应商注册表](https://github.com/alibaba/open-code-review/blob/main/internal/llm/providers.go) [官方配置文档](https://open-codereview.ai/docs/configuration)
- 非交互配置可以使用 `ocr config set`，例如设置 `provider`、`model`、`providers.<name>.api_key` 或 `custom_providers.<name>.url/protocol`；API key 也可由供应商环境变量或 `api_key_cmd` 提供。[官方配置命令](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/config_cmd.go) [官方配置解析器](https://github.com/alibaba/open-code-review/blob/main/internal/llm/resolver.go)
- 端点解析优先级是配置文件，其次是 `OCR_LLM_URL`、`OCR_LLM_TOKEN`、`OCR_LLM_MODEL` 等 OCR 环境变量，再到 Claude Code 环境变量和 shell rc；由于配置路径固定在当前用户的 home 下，生产编排器适合使用专用系统用户，并确认其配置文件、环境变量和文件权限。[官方配置解析器](https://github.com/alibaba/open-code-review/blob/main/internal/llm/resolver.go) [官方配置路径](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/config_cmd.go)
- Delegation Mode 不需要 OCR LLM endpoint 或 API key，但本项目当前首选的默认 `ocr review` 模式需要可用的 LLM endpoint。[官方 Delegation Skill](https://github.com/alibaba/open-code-review/blob/main/plugins/open-code-review/skills/open-code-review-delegate/SKILL.md) [官方中文 README](https://github.com/alibaba/open-code-review/blob/main/docs/i18n/README.zh-CN.md)

## 5. 机器可读输出

`ocr review` 和 `ocr scan` 支持 `--format text|json|sarif`，`--audience agent` 只保留摘要并抑制进度输出，`--output <file>` 将结果写入 UTF-8 文件；编排层建议使用 `--format json --audience agent --output <临时文件>`，不要从终端日志中抓取评论。[官方共享参数](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/shared_flags.go) [官方输出实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/output.go)

JSON 顶层结果当前包含 `status`、`llm`、`trace_id`、`message`、`summary`、`tool_calls`、`comments`、`groups`、`warnings`、`project_summary`、`resume`、`session_id`、`manifest` 和 `retry_report` 等字段。当前 `ocr review` 生成 manifest 时，顶层 `status` 直接取 `manifest.terminal_state`，值为 `complete`、`partial`、`failed`、`skipped`；仅无 manifest 的旧/其他路径才可能出现 `success`、`completed_with_warnings`、`completed_with_errors`。官方中文 CLI 文档对 `status` 的介绍仍偏向旧路径，集成时应以当前源码和实际安装版本为准。[官方输出实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/output.go) [官方 manifest 定义](https://github.com/alibaba/open-code-review/blob/main/internal/session/manifest.go) [存在版本差异的官方文档](https://github.com/alibaba/open-code-review/blob/main/pages/src/content/docs/zh/cli-reference.md)

当前 review manifest 使用 `schema_version: "ocr.run-manifest/v1"`，包含冻结的 `input`（解析后的 base/head SHA）、`execution`（OCR 版本、provider、model、规则/运行配置 hash）和 `coverage`。`coverage.selected` 是分母，`completed`、`reused`、`failed`、`waived` 是互斥的归类；发布飞书“审查完成”前，建议要求 `manifest.terminal_state == "complete"`、`coverage.failed` 为空，并在有 `waived` 时显式披露未审查原因。`summary.budget_exceeded`、`warnings` 和 `comments` 数量也应一并呈现。[官方 manifest 定义](https://github.com/alibaba/open-code-review/blob/main/internal/session/manifest.go) [官方输出实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/output.go)

每条 OCR comment 在当前版本的字段为：

```json
{
  "path": "src/auth.go",
  "content": "问题说明和修复建议",
  "start_line": 42,
  "end_line": 44,
  "category": "security",
  "severity": "high",
  "suggestion_code": "可选替换代码",
  "existing_code": "可选原代码"
}
```

字段名、可选性和类别/严重性枚举由官方模型定义；`thinking` 也可能出现在 JSON 中，向飞书展示时应默认忽略该字段。[官方模型定义](https://github.com/alibaba/open-code-review/blob/main/internal/model/review.go)

SARIF 输出遵循 SARIF 2.1.0，适合 GitHub Code Scanning 等消费者；本项目向飞书投递时直接消费 `--format json` 的 `comments` 和 `manifest`。Delegation Mode 不支持 SARIF，未来若采用该模式须自行转换宿主 Agent 的结果。[官方 SARIF 实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/sarif.go) [官方共享参数](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/shared_flags.go)

`--max-tokens-budget` 达到上限时可能只完成部分文件；官方实现会发布部分结果，并将未分发项目记录为 `coverage.failed[].classification == "budget"`，只要有文件完成，进程仍可能退出 `0`。编排层必须依据 `manifest.terminal_state`、`coverage.failed/waived`、`summary.budget_exceeded` 和 `warnings` 判断是否需要重试或告警。[官方共享参数](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/shared_flags.go) [官方 JSON 输出实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/output.go) [官方 manifest 定义](https://github.com/alibaba/open-code-review/blob/main/internal/session/manifest.go)

Delegation Mode 的两个 JSON 输出当前都带 `schema_version: "1"`：

```json
{
  "schema_version": "1",
  "mode": "range",
  "repository": "/path/to/repo",
  "from": "main",
  "to": "feature",
  "merge_base": "<sha>",
  "total_files": 2,
  "reviewable_count": 1,
  "excluded_count": 1,
  "total_insertions": 10,
  "total_deletions": 3,
  "reviewable_files": [{ "path": "src/main.go", "status": "modified", "insertions": 10, "deletions": 3 }],
  "excluded_files": [{ "path": "dist/app.js", "status": "modified", "insertions": 0, "deletions": 0, "exclude_reason": "<reason>" }]
}
```

```json
{
  "schema_version": "1",
  "groups": [{ "group_id": 1, "source": "project", "pattern": "**/*.go", "files": ["src/main.go"], "rule": "<规则正文>" }]
}
```

以上是字段结构示意，示例路径和计数不是 OCR 的实际运行结果；字段名与可选性来自官方命令实现。`ocr delegate ... --format json` 需要 CLI v1.9.0 或更高版本；更早版本只支持文本输出。[官方命令实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/delegate_cmd.go) [官方 Delegation Skill](https://github.com/alibaba/open-code-review/blob/main/plugins/open-code-review/skills/open-code-review-delegate/SKILL.md)

## 6. 规则与范围控制

- 规则优先级为 `--rule` 指定文件，其次仓库内 `.opencodereview/rule.json`，再其次用户目录 `~/.opencodereview/rule.json`，最后是内置系统规则；项目规则还支持 include/exclude 和 `merge_system_rule`。[官方规则解析器](https://github.com/alibaba/open-code-review/blob/main/internal/config/rules/system_rules.go) [官方 Review Rules 文档](https://open-codereview.ai/docs/review-rules)
- 内置规则覆盖 40 多种语言和文件类型；规则匹配按路径和文件特征进行，适合把团队规范放在仓库的 `.opencodereview/rule.json` 中统一版本化。[官方中文 README](https://github.com/alibaba/open-code-review/blob/main/docs/i18n/README.zh-CN.md) [官方 Review Rules 文档](https://open-codereview.ai/docs/review-rules)
- OCR 对 `.env` 家族、`.ssh`、`id_rsa`、`.netrc` 等敏感路径有内置路径过滤；`.env.example`、`.env.sample`、`.env.template` 是例外。该判断只看路径，不检查文件内容，因此仍需在项目规则中显式排除公司私有配置和生成物。[官方敏感路径实现](https://github.com/alibaba/open-code-review/blob/main/internal/config/allowlist/secret_path.go) [官方敏感模式](https://github.com/alibaba/open-code-review/blob/main/internal/config/allowlist/default_secret_patterns.json)

## 7. 面向本项目的实现建议

### 推荐流水线

```text
Git webhook/定时轮询
        |
        v
Mac Mini 编排器：fetch/校验 base 与 head，准备隔离的只读审查目录
        |
        +--> ocr review --preview --format json（范围预检）
        |
        +--> ocr review --commit COMMIT_SHA --format json --output result.json
        |
        +--> 校验 exit code、manifest schema/覆盖、预算及评论位置
        |
        +--> 生成飞书卡片/线程消息，保存原始 OCR JSON 与运行元数据
```

建议将编排器实现为一个小型守护进程或定时任务，职责保持在“Git 状态和任务状态管理、子进程调用、JSON 校验、飞书投递、重试/幂等”这几件事：

1. 如果目标是**每个提交独立评审**，以 `repository + commit_sha + rule_hash` 作为幂等键，使用 `ocr review --commit <sha>`；一次 push 含多个提交时逐个排队。若业务改为“每次 push/PR 汇总一次评审”，才改用 `--from <base_sha> --to <head_sha>`，以 `repository + base_sha + head_sha + rule_hash` 去重。两种输入范围不能混用。[官方 CLI 参数实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/shared_flags.go) [官方 CLI 文档](https://open-codereview.ai/docs/cli-reference)
2. 先对同一提交或范围运行 `ocr review --preview --format json`，把审查范围和排除原因落盘；`--preview` 不调用 LLM。[官方 CLI 文档](https://open-codereview.ai/docs/cli-reference) [官方预览实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/review_cmd.go)
3. 对同一个不可变提交 SHA（或同一组 base/head SHA）运行 `ocr review --format json --audience agent --output <path>`；同次运行只传一种背景参数，并固定 OCR provider/model 与部署版本。[官方 CLI 参数实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/shared_flags.go) [官方安装文档](https://github.com/alibaba/open-code-review/blob/main/pages/src/content/docs/zh/installation.md)
4. 解析 JSON 后验证 `manifest.schema_version`、`terminal_state`、`input.resolved_base/head`、`coverage.failed/waived` 和预算字段；区分“无发现”“无可审查文件”“部分完成”和“运行失败”。[官方 manifest 定义](https://github.com/alibaba/open-code-review/blob/main/internal/session/manifest.go) [官方 JSON 输出实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/output.go)
5. 在飞书中展示状态、覆盖数、严重性计数、文件/行号、问题摘要和建议；原始 JSON、preview 与 stderr 作为受限访问的工件保存，避免卡片过长，也避免展示 `thinking` 字段。
6. 每个任务使用隔离目录和超时；审查工作只读取 Git 对象和文件，不运行被审查仓库的构建、测试、安装脚本或钩子。

### 最小调用

**OCR 直审查（首选）：**

```bash
export OCR_NO_UPDATE=1
ocr version
ocr llm test
ocr review --repo "$REPO" --commit "$COMMIT_SHA" \
  --preview --format json --output "$RUN_DIR/preview.json"
ocr review --repo "$REPO" --commit "$COMMIT_SHA" \
  --audience agent --format json --output "$RUN_DIR/ocr-result.json" \
  --background-file "$REQUIREMENTS_MD"
```

上例严格按单个提交评审。若要按一次 push 或一个 PR 汇总，两个调用都将 `--commit "$COMMIT_SHA"` 替换为 `--from "$BASE_SHA" --to "$HEAD_SHA"`；范围模式基于 merge-base，可能覆盖多个提交，不能当作逐提交结果。[官方 CLI 参数实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/shared_flags.go) [官方中文 README](https://github.com/alibaba/open-code-review/blob/main/docs/i18n/README.zh-CN.md)

`ocr llm test` 用于验证已配置的模型端点；`--preview` 在实际审查前验证文件范围。`--output` 从 OCR v1.10.0 开始可用，使用旧版时需要升级或改用 stdout 重定向。[官方 LLM 命令](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/llm_cmd.go) [官方 CLI 文档](https://open-codereview.ai/docs/cli-reference) [官方 Skill 的版本兼容说明](https://github.com/alibaba/open-code-review/blob/main/plugins/open-code-review/skills/open-code-review/SKILL.md)

**以后需要宿主 Agent 审查时的可选入口：**

```bash
ocr delegate preview --repo "$REPO" --from "$BASE_SHA" --to "$HEAD_SHA" --format json
ocr delegate rule --repo "$REPO" --format json src/main.go src/handler.go
```

直审查路径需要配置 OCR provider/model，并会把变更内容发送到对应 LLM endpoint；Delegation Mode 不需要 OCR API key，但要由宿主 Agent 自己审查和输出结果。[官方配置文档](https://open-codereview.ai/docs/configuration) [官方 Delegation Skill](https://github.com/alibaba/open-code-review/blob/main/plugins/open-code-review/skills/open-code-review-delegate/SKILL.md)

## 8. 安全、可靠性和运维注意点

- **不执行不可信代码。** 官方 GitHub Action 在审查 PR 时 checkout 可信 base，只 fetch PR head 的 Git 对象，再基于引用计算 diff，避免把不可信 PR 文件物化到工作区；Mac Mini 编排器可采用同样思路，以隔离的 Git 仓库调用 `ocr review --from/--to`。[官方 Action](https://github.com/alibaba/open-code-review/blob/main/action.yml) [官方示例工作流](https://github.com/alibaba/open-code-review/blob/main/examples/github_actions/ocr-review.yml)
- **确认数据出站范围。** 默认 `ocr review` 会将变更文件交给配置的 LLM；敏感仓库应选择公司内网/私有兼容 endpoint，配置最小权限凭据，并检查 `--background-file` 不含密钥。[官方中文 README](https://github.com/alibaba/open-code-review/blob/main/docs/i18n/README.zh-CN.md) [官方配置文档](https://open-codereview.ai/docs/configuration)
- **关闭不需要的 telemetry 内容记录。** OpenTelemetry 默认关闭，content logging 默认关闭；只有显式配置或环境变量开启后才导出，仍应在生产机审计 `OCR_ENABLE_TELEMETRY`、`OCR_CONTENT_LOGGING`、OTLP endpoint 等环境。[官方 telemetry 配置](https://github.com/alibaba/open-code-review/blob/main/internal/telemetry/config.go) [官方 Telemetry 文档](https://open-codereview.ai/docs/telemetry)
- **谨慎启用 MCP。** MCP server 以 stdio 外部进程提供工具；工具名冲突会被跳过，setup 命令有 5 分钟超时。只允许经过审计的 server，并将配置写入受限权限的 `~/.opencodereview/config.json`。[官方 MCP 文档](https://open-codereview.ai/docs/mcp)
- **锁定版本和超时。** CLI、规则格式和 JSON 字段可能随版本变化；将 OCR npm/Release 版本写入部署清单，给 Git 操作、OCR 进程、飞书请求分别设置超时，并保留原始结果用于回放。npm 安装还需设置 `OCR_NO_UPDATE=1`，才能避免后台自动升级。[官方安装文档](https://github.com/alibaba/open-code-review/blob/main/pages/src/content/docs/zh/installation.md) [官方 npm 启动器](https://github.com/alibaba/open-code-review/blob/main/bin/ocr.js)
- **不要只看进程退出码。** 预算耗尽、部分文件失败和警告可能仍有部分结果；应把 `manifest.terminal_state`、`coverage.failed/waived`、`summary.budget_exceeded`、`warnings` 和实际审查文件数写入飞书摘要。[官方 JSON 输出实现](https://github.com/alibaba/open-code-review/blob/main/cmd/opencodereview/output.go) [官方 manifest 定义](https://github.com/alibaba/open-code-review/blob/main/internal/session/manifest.go)

## 9. 最小 POC 清单

1. 在 Mac Mini 安装固定版本 `ocr`，执行 `git --version` 确认 Git >=2.41。[官方中文 README](https://github.com/alibaba/open-code-review/blob/main/docs/i18n/README.zh-CN.md)
2. 为测试仓库创建 `.opencodereview/rule.json`，加入团队的安全、接口兼容和测试要求；用 `ocr rules check <path>` 验证规则命中。[官方 Review Rules 文档](https://open-codereview.ai/docs/review-rules)
3. 实现 `preview -> ocr review -> JSON 校验 -> Feishu` 的单仓库链路，保存 Git 引用、preview、OCR JSON 和 stderr 工件。
4. 用重复 webhook、空 diff、只含排除文件、超大 diff、OCR 超时/预算耗尽和飞书限流做故障演练；只有在这组场景稳定后再扩展到多项目并发。
