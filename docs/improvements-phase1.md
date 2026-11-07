# 问题与改进第一阶段：记录闭环

实施日期：2026-11-06。第一阶段提供平台自身的问题与阶段改进记录，不替代 OCR 问题跟踪。仅完成本地实现和隔离验证，不代表当前业务实例已升级。

## 1. 范围与入口

- 管理员导航“运维与审计 → 问题与改进”，列表 `/improvements`、详情 `/improvements/:id`。
- 列表按标题、现象、原因、方案和功能搜索；支持类型、分类、进展筛选及每页 25 / 50 / 100 条，条件保存在 URL。
- 可新建、编辑问题或阶段改进，保存排查、解决办法、证据、后续动作及关联记录的纯文本引用。
- 代码修改、本地验证和部署生效分别建模。已解决不等于已部署；手工证据不等于平台实际执行了测试或核验了服务。
- 每次保存追加完整历史快照、操作者及说明。没有删除或覆写旧快照的 API；历史分页读取。
- 未保存草稿有离开提醒，失败和冲突保留输入；正文不渲染 HTML，不保存在浏览器持久化存储。

## 2. 持久化与权限

第 39 版迁移新增 `project_improvements`、`project_improvement_revisions`。迁移仅新增表和索引，不回填历史、不导入聊天、不触碰评审状态。台账与 OCR 问题表独立，不随关联功能或项目删除而级联消失；关联项目或功能目前为人工文字说明，不是仓库外键。

API 均要求管理员，包含列表、详情和历史查询；只读账号直接访问也返回 403。创建、更新与初始或后续历史在同一短事务中提交，历史写入失败时摘要与版本一起回滚。更新请求携带 `expected_version`，冲突返回 409，不增加历史。创建携带 UUID `client_key`，同键同初始内容可重试；同键不同内容返回 409。旧创建请求在后续编辑后重放只返回当前记录，不覆盖新内容。

接口与返回模型由 OpenAPI 快照维护：

| 方法与路径 | 用途 |
| --- | --- |
| `GET /api/improvements` | 筛选及分页查询。 |
| `POST /api/improvements` | 幂等创建记录并追加初始历史。 |
| `GET /api/improvements/{record_id}` | 当前摘要与版本。 |
| `PUT /api/improvements/{record_id}` | 按版本完整保存摘要并追加进展。 |
| `GET /api/improvements/{record_id}/history` | 逐次历史独立分页。 |

状态声明必须附带相应证据；部署未确认或验证未运行不能自动提升为成功。正文是人工输入，不具备通用敏感信息识别能力，操作者应只填写脱敏内容。管理审计不存请求体。

## 3. 可执行检查

```sh
.venv/bin/ruff check backend/ocr_manager backend/tests
.venv/bin/mypy backend/ocr_manager
.venv/bin/pytest -q backend/tests/test_improvements.py
.venv/bin/pytest -q
.venv/bin/python -m ocr_manager.openapi_contract
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm --prefix frontend run test:e2e
git diff --check
```

测试均使用临时 SQLite、随机测试密钥和合成内容。浏览器使用 8791 临时服务，不启动 Worker，不连接 8781 业务服务或真实 GitLab、模型和飞书。检查结果在完成后追加到[持续台账](problem-improvement-log.md)，未执行的项目不得按既有阶段结果声明通过。

本轮实际结果：后端全量 393 项通过（其中本功能 20 项），Ruff、Mypy（69 模块）及 OpenAPI 快照校验通过；前端 Lint、59 项单元测试、TypeScript 构建与 Vite 打包通过；完整浏览器回归 45 项通过。新增浏览器用例覆盖写入真实临时 SQLite、编辑历史、刷新持久化、草稿关闭与路由保护、空结果和失败区分，以及 390/320 像素无横向溢出；已人工查看桌面详情、320 像素详情及表单截图。

后端初次沙箱内全量检查中 3 个既有进程栅栏测试因无法运行 `ps` 失败，授权沙箱外重跑后全部通过；浏览器也在授权后使用 8791 临时服务完成。后端保留一条 Starlette 的 `httpx` 弃用提示，未修改依赖以消除此既有提示。测试开发中修正了一个不适用于 Testing Library 的 `exact` 参数，最终构建通过；这些过程不代表业务部署发生变更。

## 4. 生效与后续边界

没有操作当前业务 SQLite，没有重启或部署 API、Worker、monitor。应用升级须先备份并协调同版进程，详见[部署说明](deployment.md)。旧程序会拒绝第 39 版库，不允许降低版本号来回退。

本会话每次处理完成后的记录先继续追加到 `docs/problem-improvement-log.md`，这是开发过程的持续入口；页面中的记录以 SQLite 为准。当前不自动同步两处，也不扫描其他聊天或终端。不向业务库静默导入已有记录，后续导入需要明确来源、保留原编号，并提供去重和冲突处理。

未交付：优化主题与阶段关联、复盘统计、自动归档、历史批量导入、任意附件上传、富文本和自动部署核验。后续按记录闭环、优化主题、汇总能力、自动归档的顺序推进。
