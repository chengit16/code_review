# 补审预算预检、历史诊断与人工额度调整

## 为什么用量不到上限也会失败

OCR 1.12.9 在派发下一组正式审核之前比较的是“已用 Token + 下一组预估 Token”，而非单独的实际用量。任务 #381 第三批的可核对数字是 `573 + 127524 = 128097 > 1000`，因此没有文件完成。127524 是下一组估算，不是已发生费用，也不是所有剩余文件的总预算。本次失败不能证明原初审的 HTTP 504 已解决，也不是域名访问导致。

旧版固定预填 1000 Token 和 30 秒，容易让人把过小默认值当作足够预算。新版不预填本批 Token，必须人工决定；超时沿用原快照上限，可以下调。预算保护继续保留，不通过关闭保护或自动涨额度掩盖问题。

算法依据为上游 [v1.12.9 estimate.go](https://github.com/alibaba/open-code-review/blob/v1.12.9/internal/agent/estimate.go) 和 [agent.go](https://github.com/alibaba/open-code-review/blob/v1.12.9/internal/agent/agent.go)。非删除、非空 diff 的估算是 `diffTokens*8 + 21300`，常量来自 `2000 + 400 + 2000*7 + 700*7`。平台仅对已验证版本使用该保守最低参考，不猜未知版本。SHA、规则、预览范围和 OCR 版本仍由 Worker 校验。

## 管理员怎样继续

1. 打开部分审核任务，查看“本任务补审额度”和历史预算算式。失败、取消仍占批准批次和累计 Token；这些不是实际账单，不自动退还或清零。
2. 额度不足时点击“调整本任务补审额度”。表单沿用当前值，不自动提高，必须填写原因并显式保存；只读账号无入口且服务端拒绝写入。
3. 保存额度仅追加授权审计，不排队、不调用模型、不改变历史。版本冲突保留草稿；刷新资格并关闭旧表单后重新核对，不自动重放。
4. 再点击“继续审核剩余部分”，核对冻结范围、模型/规则、预算和超时，显式填写本批预算后排队。最低启动参考只是上次门槛或保守下界，不是推荐预算；计划变化、后续组和工具调用都可能提高需求。
5. 等待新批次形成有效覆盖；“已保存”“已排队”不代表完成。补充通知独立处理，通知失败不需要重跑模型。

#381 当前三批各批准 1000：默认已用 3/3 批，累计批准 3000/100000，剩余 97000，小于上次门槛 128097。若决定再执行，批次上限至少允许第 4 批，累计上限须容纳“已有 3000 + 新批实际批准预算”。**131097 不是全批完成保证**，应根据费用边界及完整范围自行留余量。本次修复不替真实任务保存授权、创建第四批或付费试跑。

## 服务端与历史边界

- schema 48 新增独立整数证据表和逐任务递增版本授权表；迁移只建结构，不扫描工件、不自动增额。
- 排队事务重新读取累计计数、批准 Token、最新授权及相同冻结来源/快照的历史门槛，拒绝明显不足预算。同键重放返回原批次，不重复占额度。
- 旧来源诊断不阻塞新范围，但历史批准继续累计。任务授权不能覆盖原始快照的单批 Token/超时上限，不能绕过来源、配置和范围核验。
- Worker 在已验证版本正式审核前再拦截明显低于 21300 的预算。新预算失败优先归类 `budget_unconfirmed`；旧 `child_not_usable`/`stale` 不重写，用独立证据解释。
- 管理员接口 `PUT /api/jobs/{job_id}/recovery-budget` 要求 `expected_version`、`max_batches`、`max_total_tokens`、`reason`。人工批次范围 1～100，累计 Token 最高 100000000，不能低于历史已占用值。环境默认仍为 3 批、100000 Token，逐任务授权优先；不改私有配置或其他任务。

## 受控导入

先检查空闲、协调停止入口及执行进程、成对备份数据库/私有配置并演练恢复，再显式迁移 48、发布同版 API/Worker/monitor/前端。源码更新或单 API 重启不等于生效。

```bash
# 默认只预览，要求已有数据库且版本正确，不隐式建库或迁移。
PYTHONPATH=backend .venv/bin/python -m ocr_manager.recovery_budget_import \
  --data-dir .local-data/local

# 核对后追加独立证据，可幂等重放。
PYTHONPATH=backend .venv/bin/python -m ocr_manager.recovery_budget_import \
  --data-dir .local-data/local --apply
```

仅接受实例内 `runs/<job>/recoveries/<id>/result.json` 既有终态工件；拒绝符号链接、越界、超过 16 MiB、SHA/覆盖/评论/用量或预算不一致。严格匹配已知诊断并核算，只公开整数，留存工件摘要，不公开 warnings 原文、私有路径、代码或响应。提交前复核批次事实，旧 JSON、状态、费用和批准预算不变。缺失或不可信工件报告 `evidence_unverified`，不猜数字。

## 验证命令

```bash
.venv/bin/ruff check backend/ocr_manager backend/tests
.venv/bin/mypy backend/ocr_manager
.venv/bin/pytest -q backend/tests/test_recovery_budget.py backend/tests/test_review_recovery.py
PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract
npm --prefix frontend run lint
npm --prefix frontend test
```

浏览器以 `OCR_BROWSER_REVIEW_RECOVERY=1` 使用独立 SQLite 合成服务和结果推进，不安装到业务服务，不调用真实模型。覆盖 1280/320px 算式、额度保存不排队、再次确认、有效覆盖、权限和 HTTP 幂等。实际通过及部署以 PI 台账为准，本文不是验收结论。
