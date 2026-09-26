# 工程规范采用说明

本目录将 KnowSpace 的前后端代码规范应用到本项目。保留其模块边界、命名、类型、注释、测试和质量要求；把知识库业务、工作区权限、检索与导入规则替换为 GitLab webhook、逐提交 OCR 评审和飞书投递的边界。以下文件是当前仓库的执行版本，源项目文件不随之自动更新。

| 来源 | 当前项目规范 |
| --- | --- |
| KnowSpace `docs/2026-09-23/开发基线/governance/backend-code-standards.md`，SHA-256：`31065661528193d97962401f099c1d2515e3316aef0b18386a2df31c5b52c6b0` | [后端代码规范](backend-code-standards.md) |
| KnowSpace `docs/2026-09-23/开发基线/governance/frontend-code-standards.md`，SHA-256：`f0771802a2a4c051d568201b4c31080ee4bcde910baa67094148d09d1bd62042` | [前端代码规范](frontend-code-standards.md) |

| 主题 | 采用方式 |
| --- | --- |
| FastAPI 的路由、应用用例、领域规则、外部适配职责；Python 类型、事务与迁移 | 沿用结构和质量要求，改用当前项目的仓库、合并事件、评审任务与通知领域。 |
| React + TypeScript 的目录职责、状态所有权、严格类型与组件约束 | 沿用；页面范围改为仓库、Webhook 配置、合并事件、评审任务和系统设置。 |
| Python 模块与公开接口 docstring，TS/TSX 文件头与公开导出 JSDoc，复杂流程中文注释 | 完整迁入 KnowSpace 的前后端注释章节，包括示例、逐类要求、有效代码行定义和 TODO 约束；并遵守用户的全局中文注释规范。 |
| 工作区权限、文档导入、RAG、SSE、Tiptap、AG Grid、Celery、Redis、PostgreSQL 与 pgvector | 不适用；当前方案使用 FastAPI、SQLite、独立 Worker 和 React/Vite。 |
| KnowSpace 的 `G-03`、`accept-feature`、CI、阶段验收报告及已经通过的门禁 | 不继承。开发时再为本仓库建立真实命令和验收记录。 |

当前仓库已建立后端 Ruff、mypy、pytest 和前端 TypeScript 构建、ESLint 的本地检查命令，运行方式见[部署说明](../deployment.md)。CI 尚未接入；若实施流程或技术选型变化，同步修订本目录，不继续引用过期规则。

注释章节保留源规范中的工作区、SSE、Outbox、文档等示例词汇，以保持规则完整；这些例子只有在当前项目实现相应能力时才要求按原场景执行。当前项目对应的复杂业务包括 GitLab webhook 鉴权、MR 合并范围、持久化队列、OCR 覆盖判定、飞书投递与恢复，同样按章节中的文件头、公开接口和复杂流程规则编写中文注释。
