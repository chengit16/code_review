# Open Code Review 项目执行约定

本项目的实现依据为[实施流程](docs/implementation-flow.md)。新增或修改代码时，后端遵守[后端代码规范](docs/governance/backend-code-standards.md)，前端遵守[前端代码规范](docs/governance/frontend-code-standards.md)；规范的来源与适配范围见[采用说明](docs/governance/README.md)。

## 适用原则

1. 所有新增或修改的文档和代码注释使用中文；代码标识符、配置键、命令及官方产品名称保留原文。代码注释同时遵守 `~/.codex/comment-standards.md`，以更具体、更严格的项目规则为准。
2. 业务事实以 SQLite 中持久化的事件、任务和投递记录为准。GitLab webhook 只负责触发，HTTP 接收端不执行 Git、OCR 或飞书调用；独立 Worker 执行耗时操作。
3. GitLab 合并事件、OCR 结果与飞书投递分别建模和重试。涉及鉴权、幂等、提交范围、部分覆盖、凭据或重试的改动，应有与风险相称的自动化验证。
4. 新增工程检查时提供可执行命令；只有实际运行过的检查才能报告为通过。不得沿用 KnowSpace 的任务编号、脚本、数据库或业务验收结论。
