# 问题与改进第二阶段：优化主题与阶段历程

实施日期：2026-11-06。第二阶段在问题台账上增加主题化的优化历程；只完成本地实现和隔离验证，不代表当前业务实例已升级。

## 1. 页面能力

- “问题与改进”下增加“优化历程”视图；支持主题名称、目标、背景、结果、分类、状态、分页及问题编号筛选。
- 优化主题可包含最多 50 个有序阶段；阶段分别记录目标、处理办法、代码修改、本地验证、部署生效证据和遗留动作。
- 主题编辑可以从问题台账分页搜索并显式选择最多 500 条关联；反向链接可在问题详情查到关联主题。关联不更改任一记录状态，不自动推断主题成效。
- 每次主题保存追加完整主题、阶段和当时关联列表快照；乐观版本冲突保留用户草稿。历史独立分页，允许调整每页数量。
- 完成主题需有整体结果且每个阶段均完成；完成阶段须写处理办法，验证及部署结论遵守各自证据约束。

## 2. 持久化与权限

第 40 版迁移在第 39 版基础上新增 `improvement_themes`、`improvement_theme_phases`、`improvement_theme_links` 和 `improvement_theme_revisions`。不自动回填主题、不从标题猜测问题关联、不改写第一阶段台账或 OCR 任务。迁移事务失败应整体回滚。

所有列表、详情、历史和写入 API 均为管理员专用。写入将主题摘要、阶段、有序关联、版本和历史置于短事务；创建 UUID 幂等键防重放，更新携带 `expected_version` 防并发覆盖。问题编号必须指向现有平台台账记录，外键和事务保护引用完整性。

## 3. 接口

| 方法与路径 | 用途 |
| --- | --- |
| `GET /api/improvement-themes` | 按状态、分类、文字和关联问题筛选及分页。 |
| `POST /api/improvement-themes` | 幂等创建主题、阶段、问题关联和初始快照。 |
| `GET /api/improvement-themes/{theme_id}` | 读取当前有序阶段与关联编号。 |
| `PUT /api/improvement-themes/{theme_id}` | 按版本替换主题、阶段和关联，并追加完整历史。 |
| `GET /api/improvement-themes/{theme_id}/history` | 分页读取完整主题/阶段/关系快照。 |

## 4. 检查与边界

第二阶段检查命令及实测结果追加在[问题与改进台账](problem-improvement-log.md)。浏览器验收只使用临时 SQLite，不启动 Worker，不访问当前业务实例、GitLab、模型或飞书。完整 UI 测试和部署只有在实际运行后才报告通过。

本阶段实际执行：

```sh
.venv/bin/ruff check backend/ocr_manager backend/tests
.venv/bin/mypy backend/ocr_manager
.venv/bin/pytest -q
.venv/bin/python -m ocr_manager.openapi_contract
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm --prefix frontend run test:e2e
git diff --check
```

最终结果：Ruff、Mypy（73 模块）、OpenAPI 校验和差异空白检查通过；后端全量 409 项通过（新增主题 16 项）；前端 63 项单元测试、Lint 和构建通过；完整浏览器回归 46 项通过。主题用例覆盖权限、幂等、冲突、事务回滚、旧版迁移、关联不改变问题状态、历史、失败重试及 390/320 像素布局；已人工查看 320 像素主题详情与编辑表单截图。

保留 Starlette 的 `httpx` 弃用提示和 Vite 主包体积提示。首次沙箱内全量后端检查因 `ps` 限制有 3 项失败，授权后重跑全部通过；浏览器服务绑定同样经授权后运行。开发中的测试预期或定位器错误修正后重新验收，详见台账。以上检查均不构成部署生效证据。

本功能不提供复盘统计、自动归档、聊天自动导入、附件上传、自动部署核验或跨会话自动采集。持续会话记录仍按根目录执行约定追加台账；页面数据以业务 SQLite 为准，二者没有静默同步。

升级第 40 版前备份 SQLite 与私有配置，协调 API、Worker 和 monitor 同版升级；回退不得降低 `user_version`，按部署说明恢复成对备份并处理升级期间产生的新事实。
