# 项目文档索引

> 整理日期：2026-10-23。当前功能先看项目总览和操作指南，阶段记录用于追溯，不作为当前页面入口或最新测试结论。

## 推荐阅读顺序

1. [项目总览](project-overview.md)：了解平台用途、当前功能、目录与架构。
2. [本地部署与联调](deployment.md)：安装依赖、启动服务、管理主密钥、备份与恢复。
3. [后台配置与接入操作](configuration-guide.md)：实际配置 GitLab、模型、飞书、审核规则和权限。
4. [前端交互回归](frontend-interaction-checks.md)：复核近期页面与批量操作改动。
5. [工程规范采用说明](governance/README.md)：开发前阅读前后端规范及根目录 [AGENTS.md](../AGENTS.md)。
6. [项目完善实施路线](implementation-roadmap.md)：查看四轮优先级、当前进度与验收边界。

## 当前维护文档

| 文档 | 解决的问题 |
| --- | --- |
| [项目总览](project-overview.md) | 项目做什么、代码在哪里、业务如何流转、有哪些边界。 |
| [操作指南](configuration-guide.md) | 页面怎么配置、如何处理误报 / 已修复问题、如何批量处理。 |
| [部署说明](deployment.md) | API、Worker、monitor、launchd、私有配置、备份和恢复。 |
| [前端交互回归](frontend-interaction-checks.md) | 测试范围、执行命令、隔离数据和截图产物。 |
| [项目完善实施路线](implementation-roadmap.md) | 第一至第四轮实施范围、原第十项归属与验收边界。 |
| [OpenAPI 契约快照](openapi.json) | 管理 API 的提交版 schema；运行一致性命令检查是否漂移。 |
| [后端代码规范](governance/backend-code-standards.md) | 后端分层、持久化、鉴权、重试与自动化验证。 |
| [前端代码规范](governance/frontend-code-standards.md) | 组件、状态、异步反馈、草稿、布局、可访问性与验证。 |

## 设计依据与历史记录

| 文档 | 定位与注意事项 |
| --- | --- |
| [实施流程](implementation-flow.md) | 实现依据与分阶段目标；第一版范围不代表后续未扩展功能。 |
| [实施进度](progress.md) | 早期实现及本机联调记录；具体环境结果只对记录时有效。 |
| [第二轮功能完善](enhancement-roadmap.md) | 历史增强与当时验证结果，不作为当前菜单清单。 |
| [长期运维完善任务](operations-roadmap.md) | 运维阶段实施记录；部分当时不在范围内的能力后来已实现。 |
| [评审闭环增强实施记录](kodus-enhancements.md) | 问题跟踪、效果统计及业务上下文的阶段演进。 |
| [OCR 调研笔记](open-code-review-research.md) | OCR 模式、参数与输出的调研依据；升级前重新核对对应版本。 |

## 文档维护约定

- 页面、配置入口或业务语义改变时，同步更新操作指南与项目总览；保留旧路由不等于保留菜单。
- 安装、配置键、进程、备份策略改变时，同步更新部署说明。
- 阶段测试数量保留历史语义，不改写成当前全部测试数量；新增验证结论必须来自实际执行。
- 不记录密钥、Webhook 完整地址、私有配置内容或真实代码片段；示例使用占位值。
- 根目录说明只保留项目入口和常用命令，细节放入 `docs/`，避免多个文件重复维护完整操作步骤。
