# 单 Worker 可配置任务并发（1～10）

> 本期在第四阶段调度解耦基础上增加模型任务池，关联 PI-20261107-008。代码与隔离验证不等于本机运行实例已经切换；实际状态以台账的“部署生效”字段及运行监控为准。

## 使用入口与边界

“运维与审计 → 运行监控 → 模型任务并发设置”允许管理员保存 1～10 的整数，默认 1。不是进程环境变量，不必新增 Worker、Redis 或 Celery。首次发布新版需要整体升级，完成后日常修改容量不需要重启。

- 合并后评审、合并前审查、失败子集补审和模型连接诊断共同占模型任务总配额；事件/Git 准备、通知/行内发布保留各自一个独立槽。
- 调高后，Worker 可领取更多已经批准并排队的任务并产生模型费用。该设置不是仅影响以后创建的任务。
- 调低只停止超额领取，不中断在途任务。若从 10 调到 1，已有 10 个任务可以继续；总在途数量未低于 1 前不补新任务。高编号槽在任务退出后保留为空闲历史，不再领取。
- 同仓库的初审、预审、补审及仓库关联模型诊断互斥；已有 MR/事件顺序保护保留，跳过任务也不越过前序任务。不同仓库才可并行。因此只存在一个可运行仓库时，设置 10 也不会同时跑十个该仓库评审；无仓库归属的模型诊断仍可占空余配额。
- 取消、删除导致业务记录先进入终态或消失时，执行槽在真正退出前仍保留仓库占用。不能仅依据业务终态或心跳失联重新执行。
- 补审的明确授权、冻结 SHA/配置、批准路径、批次和 Token 预算不变；调高并发不新增补审、不增加预算、不自动重跑失败批次。

任务并发与 `OCR_APP_OCR_CONCURRENCY` 不同。后者是单任务内部并发，未配置时默认 4；任务并发和内部并发的乘积只表示潜在工作压力，不是精确 HTTP 请求数、费用或供应商 RPM/TPM 上限。首版没有新增账户级请求限速器，不承诺 10 路真实 OCR 的容量或提速倍数。建议先设 2，再根据本机内存、CPU、磁盘、限流、超时、吞吐和费用逐步调整。

## 保存版本与运行事实

- `GET /api/worker-scheduler/config` 返回 `model_task_concurrency` 与 `version`。
- `PUT /api/worker-scheduler/config` 只接受上述两个字段；数值均须是严格整数，并发范围 1～10、版本至少 1。布尔、字符串、小数、越界及额外字段拒绝。
- 保存使用短事务比较版本，并在同事务写入 `worker_scheduler_changes` 的前后容量、版本和操作者；既有管理审计继续记录请求结果。只读角色不能保存。
- 409 保留草稿及原版本，不自动重放或覆盖其他管理员设置；点击“放弃草稿并刷新配置”重新核对。
- `/api/operations` 的 `scheduler.model_task_concurrency` 是已保存期望值；`applied_concurrency`、`applied_version` 是最近有新鲜心跳的协调器确认值。停止、无记录、心跳过期时已应用值为未知，不据此授予抢占权。
- `running_model_tasks` 是持久化的模型槽执行中数量，心跳过期时不代表实时进程存活；`draining` 表示数量超过已应用上限。
- 配置保存与 Worker 下一轮应用存在短暂间隔，监控也有刷新间隔；可主动刷新监控核对版本。API 单独启动时只能确认保存，不能确认 Worker 已应用。

调度容量不加入 `configuration_snapshot` 或 `config_hash`，不会仅因调度设置变化使原有队列快照失效。内部并发仍沿用原有评审输入快照语义。

## 持久化与迁移

schema 49 在 48 基础上：

1. 将 `worker_execution_slots` 从 `lane` 唯一主键改为 `slot_id`，保存 `lane` 和 `slot_index`，保留旧单槽的 owner、代次、任务和运行证据。
2. 增加独立调度配置及变更历史，默认容量 1，不自动确认已应用或改写业务任务。
3. Worker 在取得原有独占进程锁并恢复业务任务后初始化槽。动态增加模型槽；所有模型槽共享类型轮转及仓库游标。停止时等待全部线程与受控命令组清理，再释放进程栅栏。

升级须同版 API、Worker、monitor 与前端，不允许新版 API 迁移后仍保留旧 Worker/monitor 混写。建议先停止回调接入和管理写入、确认在途任务情况并备份数据库及工件、正常停止全部共享库进程，再按部署说明迁移并启动同版进程。不得删除锁文件强行恢复；若有存活的受控子进程，先确认其结束。

迁移后的旧程序会拒绝新版数据库。回退须正常停止全部相关进程，恢复升级前的成对备份至新目录，并明确升级后新增事件、任务、通知与台账的补偿；不能降 `user_version` 或覆盖活跃数据库。首次启动保持容量 1，确认已应用后再由管理员显式调高。

## 可执行验证

所有自动化使用临时 SQLite、合成任务、受控外部进程或服务替身，不读取真实模型账单，不调用付费模型。

```bash
.venv/bin/pytest -q
.venv/bin/ruff check backend/ocr_manager backend/tests
.venv/bin/mypy backend/ocr_manager
PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract
npm --prefix frontend run lint
npm --prefix frontend test
(cd frontend && npx tsc -b && npx vite build --outDir /tmp/ocr-concurrency-dist --emptyOutDir)
(cd frontend && OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-concurrency-dist npx playwright test)
```

本机如使用已安装 Chrome，可为最后命令显式设置 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`；不要求覆盖运行实例的 `frontend/dist`。默认浏览器套件跳过独立补审及聊天夹具，这些专项需要分别设置 `OCR_BROWSER_REVIEW_RECOVERY=1`、`OCR_BROWSER_CHAT_CAPTURE=1`，不能把跳过称为通过。

关键场景包括 1/2/10 重叠执行及同仓库等待、在线 1→2→1 排空、跨类型原子领取、补审批准预算不变、模型诊断总配额、版本冲突及权限、48→49 事务回滚与证据保留、多个中断任务恢复、多个 Git/OCR 进程组停止、单任务取消不污染另一任务、桌面与 320px 页面持久化及草稿冲突。

这些验证不替代真实 OCR 版本多进程兼容性、供应商配额及本机承载能力的受控试运行；任何真实付费并发试点需另外明确授权。
