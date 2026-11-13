# 评审任务删除

管理员可在“评审任务”列表右侧“操作 → 删除”移除异常记录，窄屏在每条任务摘要下方提供“删除”；任务详情顶部操作栏也提供“删除任务”。只读账号不显示删除入口；排队／运行及活动补审任务显示禁用状态。确认框冻结任务编号、尝试次数、状态和完成时间；后台仍校验管理员身份，不依赖前端按钮控制权限。

## 删除范围

- 删除所选任务、初审尝试、补审记录、预算证据、发现、反馈和本地通知／发布记录。
- 仅由该任务产生的跟进问题随之移除；共享问题保留其他任务来源，并按剩余来源更新出现时间。
- 删除事实与操作人审计在同一事务提交，审计失败则整体回滚。
- 保留 GitLab 合并／Push 事件、事件去重事实、独立任务编号分配记录和原始工件。重复 webhook 不因删除而自动重新建任务；人工重新触发属于新的操作。

任务、发现、问题、反馈及费用统计在下一次查询时根据剩余记录重新计算。这不代表已经发生的模型费用得到退款，也不撤回已发送的飞书消息或 GitLab 评论。删除后原始工件由既有运维保留期和孤立工件清理机制处置，不在 HTTP 删除请求中清理文件。

## 拒绝与恢复

排队／运行任务需先取消或等待结束。存在待处理／发送中的通知、活动补审、未退出的执行槽或工件锁时返回冲突，不强制中止后台操作。确认后任务重跑、状态或尝试版本变化时也拒绝删除，需关闭确认框并刷新后重新核对。

若删除会移除人工合并关系的最后目标来源，整体拒绝，需先人工核对问题关系。不存在或已删除的任务返回 404。网络失败不会自动重试删除；先刷新确定任务是否仍存在。物理删除不能从页面恢复，误删恢复须使用成对数据库／私有配置备份，在独立目录核对后按运维恢复流程处理。

## 接口与本地检查

`DELETE /api/jobs/{job_id}` 要求 JSON 请求体包含 `expected_status`、`expected_attempts` 和 `expected_finished_at`，未知字段拒绝。成功返回任务编号及实际删除的发现、问题数量。任务版本按数据库事实核对，不接受客户端指定级联范围。

```sh
.venv/bin/pytest -q backend/tests/test_task_deletion.py backend/tests/test_task_control.py backend/tests/test_task_operations.py backend/tests/test_review_recovery.py
.venv/bin/ruff check backend/ocr_manager backend/tests
.venv/bin/mypy backend/ocr_manager
PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract
npm --prefix frontend run lint
npm --prefix frontend test -- --run src/test/taskDeletion.test.tsx src/test/taskMigration.test.tsx
cd frontend
npx tsc -b
npx vite build --outDir /tmp/ocr-task-delete-dist --emptyOutDir
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-task-delete-dist npx playwright test e2e/taskDeletion.spec.ts
```

本功能不改变 schema；需要部署配套 API 与前端。检查通过仅代表相应本地范围，当前运行实例、目标数据删除和台账同步结果分别记录于问题与改进台账。
