# 受控历史诊断导入与默认人工补审

日期：2026-11-07。关联：PI-20261106-008。当前目标 schema 46。

## 默认人工补审

部分审核任务默认显示“继续审核剩余部分”，管理员不再需要功能开关或项目试点白名单。旧 `OCR_APP_REVIEW_RECOVERY_ENABLED`、`OCR_APP_REVIEW_RECOVERY_REPOSITORY_IDS` 已从配置模型及执行链移除，遗留键不再影响资格或领取。只读角色不能创建批次；非部分任务没有新的补审按钮，已有历史仍可查看。

点击后仍须人工确认冻结的源尝试/版本、提交、失败子集和预算。只有人工提交才创建排队批次，导入诊断、启动服务、刷新页面都不会自动执行补审。源工件/结果、配置摘要、固定范围、活动批次互斥、唯一模型槽、最大批次及累计批准 Token 校验保留。来源不可信时不能为了按钮可点而执行错误提交；界面给出具体阻塞原因。

默认最多 3 批、累计批准 Token 100000，可通过原预算配置键调整；失败/取消不退还批准额度。Token 上限不是账单金额保障。需要暂停业务时使用项目停用、停止领取与活动批次停止等既有能力，不能依赖已废弃的配置开关撤销在途网络请求。

## 历史导入的控制边界

- 独立运维命令遍历所有 `partial` / `failed` 历史尝试，以及没有尝试行但仍有可信当前结果的任务；不固定 #381 或近期任务。超过 100000 个候选明确拒绝，不静默截断。
- 默认预览，显式 `--apply` 才写入；不在 HTTP、服务启动或结构迁移中扫描工件。预览允许 schema 45，实际导入要求先完成 46 版迁移。
- 只读取数据库引用的 `runs/<job_id>/` 内普通 `result.json`，拒绝符号链接、越界、非普通文件和超过 16 MiB 的工件。输入 SHA/base、覆盖分区、评论必须与历史持久化事实匹配；缺失、漂移或损坏按固定原因码跳过。
- 与工件清理和重审共用锁；解析时不占写锁，提交时重新核对源快照。每条独立短事务保存诊断、工件摘要、导入操作者/时间和审计日志，主键保证崩溃重跑幂等。原生诊断和已导入记录不覆盖，损坏来源不自动修复。
- 新表 `review_historical_diagnostics` 独立保存安全投影，不 UPDATE 初审或尝试 `result_json`。因此不会改变补审冻结摘要、有效结论指针、状态、发现、用量或通知，不触发模型、Git 或飞书。
- 详情、列表摘要、当前报告和指定历史尝试报告统一读取匹配证据。来源结果/状态、head/base 或源尝试改变后不沿用旧导入；不把旧尝试 504 带给新尝试。原始请求正文、模型推理、工具参数及响应正文不导出。

## 本机执行命令

先按既有停服/升级流程核对在途工作，成对备份数据库及原主密钥配置，并演练恢复。schema 46 只增加独立表；同版启动三个进程，不能让旧进程混写新结构。预览不隐式迁移，导入也不自动迁移。

在项目根目录、沿用原配置执行：

```sh
export OCR_APP_CONFIG_FILE="$PWD/.local-data/local/private.json"
export PYTHONPATH="$PWD/backend"
.venv/bin/python -m ocr_manager.review_diagnostic_import --preview
.venv/bin/python -m ocr_manager.review_diagnostic_import --apply
.venv/bin/python -m ocr_manager.review_diagnostic_import --preview
```

输出包含模式、按结果分类的计数以及逐任务/尝试结果，不包含工件路径、私有配置或完整外部错误。常见结果：

| 原因码 | 含义 |
| --- | --- |
| `ready` / `imported` | 证据校验通过、可导入 / 已导入 |
| `already_imported` / `native_diagnostic_present` | 已有独立记录 / 已有原生诊断，未覆盖 |
| `source_result_missing` | 未持久化可信结果，不能仅凭状态推测 |
| `artifact_missing` / `artifact_path_invalid` | 工件缺失或引用不受信任 |
| `artifact_invalid` / `artifact_too_large` | 格式/固定输入不符或超限 |
| `source_result_mismatch` / `source_changed` | 与原记录不一致 / 提交前源已改变 |
| `artifacts_busy` | 正在评审、清理或使用工件，未抢占 |
| `diagnostic_unavailable` | 没有可验证的覆盖诊断结构 |

已有导入记录再次预览显示 `already_imported`，不重新覆盖；这不等于承诺来源永远有效，页面读取仍检查来源。跳过项没有成功诊断，不能写成“全部恢复”。导入报告应保存为权限受控的本机文件，成功导入另有数据库审计。

## 验证与发布

```sh
.venv/bin/ruff check backend/ocr_manager backend/tests
.venv/bin/mypy backend/ocr_manager
.venv/bin/pytest -q backend/tests/test_review_diagnostic_import.py
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build -- --outDir /tmp/ocr-history-default-recovery-dist
cd frontend
OCR_BROWSER_REVIEW_RECOVERY=1 \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-history-default-recovery-dist \
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  npx playwright test e2e/reviewRecovery.spec.ts
```

隔离构建和临时浏览器服务不代表运行实例已发布。真实导入、备份恢复、同版重启、资格与页面读回的最终结果记录在台账，不把默认可补审等同于真实模型质量或飞书外发验收。回退不能降低 user_version 或直接覆盖升级后新增事实；协调停服，保留新事实后从成对备份恢复到新目录。
