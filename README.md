# Open Code Review 管理平台

面向 GitLab 项目的自动化代码评审与问题跟进平台，使用 Alibaba Open Code Review CLI 执行评审，以 SQLite 保存业务事实，并通过飞书发送摘要。

支持 MR 合并后的逐提交评审、默认分支 Push 范围评审，以及独立的合并前 MR 差异审查。平台不会自动修改代码，也不会阻止 GitLab 合并。

## 文档入口

- [项目总览](docs/project-overview.md)：功能、架构、目录、业务流程、状态边界和后续维护。
- [文档索引](docs/README.md)：全部文档的用途、阅读顺序与历史记录说明。
- [后台配置与接入操作](docs/configuration-guide.md)：模型、飞书、项目、规则、问题处理与账号权限。
- [本地部署与联调](docs/deployment.md)：依赖安装、API / Worker / monitor、主密钥、备份和恢复。
- [前端交互回归](docs/frontend-interaction-checks.md)：草稿、批量操作、分页和窄屏布局检查。
- [项目完善实施路线](docs/implementation-roadmap.md)：四轮优先级、实施进度及后续验收边界。
- [工程规范](docs/governance/README.md)：前后端规范与项目执行约定。

## 核心功能

| 页面 | 主要用途 |
| --- | --- |
| 运行概览 | 查看队列、异常、通知状态与评审效果。 |
| 评审任务 | 筛选任务、查看覆盖和发现、补触发 MR、重审及独立重发通知。 |
| 待跟进问题 | 跨任务跟踪问题，单项或批量处理、合并重复问题、查看历史。 |
| 合并前审查 | 查看 MR 最新版本及历史审查，不作为合并门禁。 |
| 项目配置 | 管理 GitLab 接入、评审参数、发布审查和接入诊断。 |
| 系统设置 | 集中配置 Agent 模型、飞书通知和审核规则。 |
| 访问权限 | 管理账号、管理员 / 只读角色及多人登录模式。 |
| 运维与审计 | 查看运行与数据对账、导出脱敏诊断包、核对配置和管理操作。 |

## 本地使用

- 管理台：[http://127.0.0.1:8781](http://127.0.0.1:8781)。
- 前端开发：在 `frontend/` 执行 `npm run dev`，默认端口 `5173`，API 代理到 `8781`。
- 浏览器测试：临时服务使用 `8791`，与本机业务数据隔离。

首次安装请按[部署说明](docs/deployment.md)完成依赖、配置和进程启动；已有环境应继续使用原有私有配置和主密钥，不要重新初始化或启动重复 Worker。开发模式无管理鉴权，仅可用于可信本机，不得把整个端口暴露到公网。

## 常用检查

在项目根目录执行：

```sh
uv run ruff check backend
uv run mypy backend/ocr_manager
uv run pytest -q
uv run python -m ocr_manager.openapi_contract
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
```

完整浏览器检查及本机 Chrome 的使用方式见[前端交互回归](docs/frontend-interaction-checks.md)。以上是可执行入口，不表示每次文档更新都重新运行全部测试；验证范围应以对应变更记录为准。
