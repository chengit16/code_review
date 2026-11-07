# 台账同步与自动归档

## 规则与边界

第 42 版迁移新增后台策略与来源游标，保留 39～41 版原迁移。新安装默认关闭自动归档，默认期限 30 天；本机实例按用户要求显式开启。

- 问题必须已解决，方案、验证与部署证据齐全，验证通过或明确不适用，部署确认或明确不适用，遗留为空，连续指定天数无更新。
- 主题必须已完成、有结果、无遗留，至少一个阶段且所有阶段均闭环；所有关联问题同样满足闭环条件。主题与问题独立归档，不级联。
- 每类每轮最多 100 条。筛选、内容版本、归档元数据和历史同一短写事务提交；失败整批回滚。恢复更新当前时间，重新计算期限。
- 归档不删除历史，不自动解决问题，也不生成“验证通过”或“部署生效”结论。未解决、待部署、受阻或有遗留内容不会按时间收起。

## 持续记录与页面同步

服务器私有配置 `OCR_APP_IMPROVEMENT_LOG_PATH` 指向本项目台账的绝对路径。浏览器只能查看是否配置，不能读取或更换任意服务器文件路径。独立 `python -m ocr_manager.alerts`（monitor）每 30 秒先同步，再处理自动归档，与飞书告警开关无关。

来源格式为 `### PI-YYYYMMDD-NNN｜标题` 及中文事实字段，模板代码块不导入。同一编号可反复追加；源文件上限 5 MiB，读取期间发生变化则等待下轮。当前摘要、每次历史、来源游标同事务保存；首次导入保留原 PI 编号和多次进展，重放不生成重复版本，不触发评审、模型或通知。

`同步状态` 可选单行 JSON 只接受 `kind/category/status/code_state/verification_state/deployment_state`。缺失时不从长文本猜测通过或部署事实。原始文字和额外事实字段保存在各版快照中；后续部署确认必须追加，不能改写历史上的未部署结论。

来源历史被修改、删除，页面被人工编辑或归档后又有新追加时，对应来源冲突并保留页面内容；其余独立来源可继续导入，但整轮自动归档停止。先比较页面历史与来源，追加核对说明；如需要重新接管来源游标，应由维护者在备份后人工处理，不能删除页面记录、重建游标或强制覆盖来绕过冲突。

页面入口为“问题与改进 → 自动归档与台账同步”。可查看策略、最近检查/成功时间、错误码对应提示、冲突编号、上轮实际计数及当前候选；管理员可保存策略（带版本冲突保护）。保存成功不表示已经执行。列表、主题、复盘与运行状态每 30 秒读取更新；编辑草稿不随刷新覆盖。monitor 停止时，页面时间不再前进，不应称为持续同步正常。

## 运维与验证

先按[部署说明](deployment.md)成对备份数据库与私有配置，在隔离副本迁移和解密核验，再停止接收新评审，等待任务空闲，协调同版 API、Worker、monitor 升级至 42。不能只更新前端或混跑旧 Worker。私有配置沿用原主密钥，添加来源路径时保留全部原值和 0600 权限。

```bash
# 以下命令继承已配置的 OCR_APP_CONFIG_FILE，不自动迁移或创建业务库。
.venv/bin/python -m ocr_manager.improvement_maintenance --preview
.venv/bin/python -m ocr_manager.improvement_maintenance --enable --days 30 --once
```

`--preview` 只读且不能与修改/执行参数混用。`--once` 有运行错误码时非零退出。monitor 使用原有文件锁维持单实例；维护失败记录稳定错误码，不输出私有文件正文，不终止原有告警循环。

```bash
.venv/bin/pytest -q backend/tests/test_improvement_maintenance.py
.venv/bin/ruff check backend/ocr_manager backend/tests
.venv/bin/mypy backend/ocr_manager
.venv/bin/python -m ocr_manager.openapi_contract
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm --prefix frontend run test:e2e
```

本轮实际命令结果、业务备份位置与部署验收以[台账 PI-20261106-007](problem-improvement-log.md)的追加事实为准，不沿用以前阶段的通过结论。

## 当前本机运行说明（2026-11-07）

当前业务库已迁移至 42 版，API、Worker 与 monitor 使用同版代码运行，自动归档已显式启用为 30 天。真实业务页面已只读核对记录、历史、主题关联、复盘统计及桌面与窄屏呈现；该验收不触发评审、模型调用或归档写入。

本次尝试通过 launchd 管理进程时，系统对虚拟环境 Python 的 `posix_spawn` 返回 `Operation not permitted`，相关服务已卸载，现沿用后台进程运行。当前健康和同步周期正常不代表开机自启已建立；退出运行环境或重启后，须按部署说明重新启动 API、Worker 和 monitor，再检查健康接口及维护成功时间持续前进。后续排查系统启动权限时应单独记录，不能通过关闭系统安全保护绕过限制。
