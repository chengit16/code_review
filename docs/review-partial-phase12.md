# 部分评审治理第一、二步实施记录

记录日期：2026-11-07。关联事项：PI-20261106-008。依据：[五步实施方案](review-partial-review-plan.md)。

## 1. 交付范围与未交付内容

- **代码修改：**已实现安全分层诊断、任务列表摘要、详情与历史报告、单工件只读诊断命令，以及真实 OCR CLI 的本机合成恢复探针。
- **本地验证：**已完成后端、前端和隔离浏览器验证，命令与结果见第六节。探针只使用临时 Git/HOME、本机随机端口和合成凭据。
- **部署生效：**未部署、未重启 API/Worker/monitor，未覆盖业务使用的 `frontend/dist`。没有迁移、生产参数调整、历史摘要回填、真实模型调用或历史任务重审。

本轮没有上线“继续审核剩余部分”按钮，没有实现补审批次、队列、聚合、通知或真实端点试点。源头超时原因仍需后续链路证据，不能将新增诊断等同于根因修复。

## 2. 分层诊断如何工作

`review_diagnostics.py` 在既有输入及覆盖校验后提取 `platform.failure-analysis/v1`，由 `project_review_result` 写入任务结果及逐次尝试。详情读取持久化投影，列表只读取摘要，不逐行访问原工件；当前报告和指定历史尝试报告使用对应结果，不沿用最新尝试。

诊断分别保留覆盖 timeout/budget、失败分组、逻辑请求摘要、plan/main、HTTP 状态、context 标签、响应头计时和退避；固定类别记录工具搜索上限及缺失依赖路径。它们可以共存，不推断唯一因果关系。现有 partial 状态及整批重试策略不变。

安全边界：

1. 分组成员只能来自该次已校验 manifest；请求的逗号串只与完整已知分组序列匹配，路径包含逗号、拼接歧义时不拆分猜测。
2. 请求标识仅接受 64 位小写十六进制摘要；不透传 provider/model、原始错误、工具参数、响应正文、prompt 或推理。HTTP/类别/计时均按允许集合或有界数值投影。
3. 覆盖集合上限 5000、分组 1000、逻辑请求 1000、每请求尝试 64；展示最多各 50 条分组/请求，聚合计数保留。损坏请求报告丢弃该报告的请求信号；缺失、未知版本和截断显式标记。
4. 历史无投影时页面显示未知，不在 GET 中读取原工件或回填。成功请求 P95、完整组时间线、实际上下文 token 等现有报告未提供的指标继续未知。

## 3. 历史任务的只读核对

本轮从 SQLite 只读取得指定任务的固定 SHA 及工件引用，经新只读诊断校验，不修改原工件或数据库。这是对三个指定历史任务的复核，不是重新统计当前所有任务。

| 任务 | 覆盖 | 失败分组 | 本轮只读诊断证据 |
| --- | --- | --- | --- |
| #321 | 23/29 | 1 | 6 项覆盖 timeout、2 条 context timeout；没有 HTTP 状态证据 |
| #343 | 14/29 | 2 | 15 项覆盖 timeout、3 条 context timeout；没有 HTTP 状态证据 |
| #381 | 40/45 | 1 | 5 项覆盖 timeout、6 次 HTTP 504、1 条 context timeout、1 次搜索上限及 4 次缺失依赖信号 |

没有 HTTP 状态证据不等于没有网络故障；有 504 不等于已识别具体网关。分组失败和固定约 60 秒请求期限的因果仍需网关/请求关联证据，不默认归咎于文件体积。

管理员可显式复核单份受控工件，不调用模型、不回填：

```sh
PYTHONPATH=backend .venv/bin/python -m ocr_manager.review_diagnostic_report \
  --result /absolute/path/to/result.json --head <原始head-SHA> --base <原始base-SHA>
```

commit 模式省略 `--base`；范围来自 SQLite，不用当前分支头替代。命令最多读取 16 MiB，输入 SHA、schema 或覆盖分区不符时非零退出。不要把完整原工件粘贴进台账或普通日志。

## 4. 恢复兼容矩阵

实测版本：`open-code-review v1.12.9 (bccbc15)`。脱敏输出见 [合成探针报告](review-resume-probe.json)。两个独立大差异文件分别分组，其中一个路径含逗号及方括号；先完成 alpha、令 beta 返回 HTTP 400，再恢复合成端点。

| 能力 | commit / range 实测 | 实施含义 |
| --- | --- | --- |
| 原生恢复覆盖 | 两种模式均仅调用 beta，alpha 为 reused；固定输入与覆盖分区校验通过 | 具备覆盖复用能力，不代表可直接上线 |
| 保留初审发现 | 两种模式均保留 alpha 发现，并加入 beta 发现 | 原生结果发现集合可保留 |
| 重复执行同一 session | 两种模式均再次调用 beta，不是零调用 | 平台必须有持久化幂等及完成资格检查 |
| 更换模型 | 两种模式均未拒绝，继续复用旧结果 | 平台必须校验模型及完整配置快照，不能依赖 CLI 拒绝 |
| 更换有效规则 | 两种模式均非零退出且没有模型请求 | 仅说明本次规则用例被拒绝，不推断所有参数都被检查 |
| session 缺失、损坏 | 两种模式均非零退出且没有模型请求 | 不允许自动回退为全量评审 |
| 复制到另一 checkout | 两种模式原生恢复均失败、没有模型请求 | 原生恢复不能直接用于平台隔离目录复制方案 |
| 取消第二组请求 | 平台进程组取消后没有可信最终 JSON，用量未知；本报告两种模式恢复均失败 | 另一次合成运行曾出现 range 可恢复，属于时序相关表现，不批准取消会话原生恢复 |
| 正常恢复用量 | 初审 6、恢复 6；恢复 6 等于本次三次成功响应的合成用量，而非累计 12 | 本次观测为增量；不是实际账单、失败请求费用或缓存计费保证 |
| 独立失败子集 | 两种模式在新 checkout 用原 SHA、精确规则排除 alpha；预览与正式 selected 均仅 beta，模型调用也仅 beta | 独立批次路线具备最小执行可行性，不伪造临时 commit |

取消阶段已到达端点但未返回的请求不能据端点记录估算实际费用；探针将该次最终用量及合成成功 token 均标为未知。

## 5. 下一步路线裁定

**第三步优先采用独立失败子集批次＋平台聚合，不直接封装 `--resume`。** 原生复用虽然成功，但配置、重复调用、目录及中断语义未满足直接使用要求。

第三步先实现资格和不可变源快照，再做排队幂等、Worker 执行及覆盖聚合；新批次固定原 base/head，服务端推导剩余集合，预览与正式 manifest 均严格匹配，任何漂移都拒绝，不降级为全量。保留父结果，独立记录新增发现和用量，聚合版本通过事务裁决；列表、统计、反馈、导出与通知统一读取有效结论。

仍须补充：项目/全局/仓库规则优先级与复杂特殊路径、跨文件上下文、重复发现来源、执行与清理竞争、工件保留、取消和迟到写回等第三步验收。合成两个文件不证明真实模型质量，也不证明复杂规则已全部覆盖。按钮及补充通知留到第四步，真实网关调查和有预算试点留到第五步。

## 6. 已执行检查与复现命令

以下结论只对应本轮实际命令，不替代部署验收：

```sh
.venv/bin/ruff check backend/ocr_manager backend/tests
.venv/bin/mypy backend/ocr_manager
OCR_RESUME_PROBE_COMMAND=.local-tools/node_modules/.bin/ocr .venv/bin/pytest -q
PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract --update
PYTHONPATH=backend .venv/bin/python -m ocr_manager.openapi_contract
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build -- --outDir /tmp/ocr-partial-phase12-dist
PYTHONPATH=backend .venv/bin/python -m ocr_manager.ocr_resume_probe \
  --command .local-tools/node_modules/.bin/ocr
cd frontend
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-partial-phase12-dist \
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  npx playwright test e2e/reviewDiagnostics.spec.ts e2e/reviewExecution.spec.ts
```

结果：Ruff、mypy、OpenAPI、ESLint 和隔离构建通过；后端 485 项通过（显式包含真实本机 CLI 探针；不设置环境变量时该项跳过），前端 82 项通过，诊断与原执行展示浏览器回归 6 项通过，覆盖 1280/390/320px，截图人工核对无横向溢出。完整浏览器套件本轮未运行。构建仍有主包超过 500 kB 的提示，后端仍有 Starlette/httpx 弃用提示，不影响本轮通过结论，但不描述为无警告。

初轮验证曾发现详情遗漏新投影字段、历史报告测试误用了不存在的路径，以及合成子集规则错误增加前导 `/`；均已修正并重跑。正式工件、持久化及规则行为未通过伪造覆盖、改写历史或忽略失败来绕过检查。
