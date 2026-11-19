# 双评审阶段二实施与验证

阶段二将 Agent 作为独立模型任务接入现有 Worker。使用同一任务的固定 Git 范围，关联 Alibaba OCR 的初审尝试及其原始结果版本 `revision=0`。可从本机命令提交、取消、读取每次 Agent 尝试及其对应 OCR 结果。正式对比页与人工裁定在工作包 3。

## 本地复现

在项目根目录执行。测试使用临时 SQLite、真实 Git 对象、现有 Worker 调度器和环回地址上的脚本模型，OCR 初审结果是合成夹具。

```sh
uv sync --locked --inexact
.venv/bin/python -m pytest -q -s \
  backend/tests/test_agent_review_worker.py::test_scheduler_timeout_partial_and_single_side_rerun
```

测试会打印 `agent-comparisons.json` 的实际位置。由临时库导出的三份比较为同一长 diff 的历史记录，依次显示超时并保留可能已计费调用、只核对 5/25 条差异记录、核对 25/25 条且在 `orders.py` 新侧第 24 行找到预设证据。三份报告均引用原 OCR 尝试。测试还核对重复请求键只返回原编号，飞书投递仍为初审建立的一条，GitLab 行内发布没有新增。

查看全部专项验证，包括进程恢复、单侧取消、并发去重、预算、响应格式、证据、MR 版本复核与数据库迁移：

```sh
.venv/bin/python -m pytest -q backend/tests/test_agent_review_worker.py \
  backend/tests/test_review_prototype.py
```

脚本模型只用于验证接线、状态和账目，真实端点兼容性与缺陷识别效果需要单独跑验收。真实模型用例应包含可从差异确认的保护与触发条件，并隐藏预设答案。

## 一条任务如何流转

1. **提交。** 本机命令从业务 SQLite 读取当前 OCR 尝试和该任务执行时保存的预检范围，在写锁下固定 OCR 尝试、两个 Git 对象标识、配置与背景摘要以及 Agent 模型配置。重复的请求键返回原编号。新的运行使用新请求键，重跑还需指定当前 OCR 版本的上一条 Agent 尝试。
2. **领取。** 空闲模型槽先尝试正式评审、补审和模型诊断。都没有可领取任务时再领取 Agent。Agent 占用同一个模型池，并与同仓库的模型任务互斥。Worker 重读试点权限和任务状态，从本地 Git 缓存读取固定对象。合并前任务在执行前和提交结论前使用只读 GitLab API 复核 MR。
3. **逐页评审。** LangGraph 按冻结的文本差异清单调用本地 `read_diff`，把页交给 Chat Completions 适配器。适配器装入证据与重试幂等检查提示，模型返回候选和行号。程序从实际交付页取证据，确认后才提高覆盖并保存进度。当前仅提供差异页，OCR 的选文件策略、规则正文和 MR 描述不发送给 Agent；报告明确保留两侧各自的覆盖和配置。无文本差异的文件列为排除路径。
4. **确定失败与恢复。** 每次发送前用独立调用编号登记预算。超时或响应丢失通常只能记录 `unknown`。Worker 重启时，仅当已发调用均有用量且对应页已核对并保存进度，才从下一页继续；其他情况保存中断终态。Agent 取消或 MR 失效后，结果不作为有效结论，已登记的调用仍保留。
5. **读取比较。** 报告给出 OCR 初审版本和原结果、Agent 终态与原因、固定范围、覆盖、证据、节点轨迹，以及每个已登记调用的位置、用量和供应商返回的模型标识。Token 数以供应商回执为准；调用费用金额未定价，记录为空。

数据库版本 55 只添加 Agent 任务和调用表。旧任务无预检范围、本地 Git 对象被清理或 MR 版本无法验证时，需要核对来源；不会改用当前分支。历史报告随所属初审和任务的清理策略一起删除。

## 接入一个端点

已发布第三阶段管理入口的实例，可从[双评审对比页](review-agent-phase3-walkthrough.md)启用仓库并复用现有项目模型。以下私有配置用于独立试跑、自定义预算及专用端点。

先在独立测试实例验证。确认端点、允许发送的仓库与代码范围、单次和总调用预算后，再设置以下私有配置。现有服务配置文件需要由当前运行用户持有且权限不超过 `0600`，模型凭据不得提交到仓库或写入命令参数。

复用现有项目模型时，将 `OCR_APP_AGENT_MODEL_SOURCE` 设为 `project` 并配置试点仓库 ID。模型、HTTPS API 根地址和密钥从项目当前生效的配置取得，项目覆盖优先于全局启用配置。Agent 入队冻结档案 ID 和版本，Worker 执行时才解密。档案变更后，已排队任务将显示配置变化，需按新配置创建尝试。现有模型的历史 OCR 结果可能来自较早配置，比较时需核对两侧设置。

现有模型复用其供应商账户和额度，Agent 的调用、预算和评审结果仍单独记录。复用名称为 `zt` 的模型档案时，新入队的 Agent 尝试免除单页 Token 限额、单次尝试及同一 OCR 版本的累计 Token 预算，也免除单次尝试的页数上限和总时限。Agent 按固定 Git 差异清单逐页核对，请求不指定输出 Token 上限，实际用量照常记账。供应商额度、单次 HTTP 的各阶段超时和人工取消继续生效。首轮先用合成输入确认网关能返回 JSON 与用量。使用独立端点时保持 `dedicated`，再设置对应的模型、端点和密钥。

| 配置键 | 用途 |
| --- | --- |
| `OCR_APP_AGENT_MODEL_SOURCE` | 默认 `dedicated`。设为 `project` 时复用项目模型，省略下列三个独立端点字段。 |
| `OCR_APP_AGENT_ENDPOINT` | 完整的 `/chat/completions` 端点。外部端点使用 HTTPS，环回测试可用 `127.0.0.1` 或 `::1` 的 HTTP。未设置或 Agent 配置错误时关闭影子运行。 |
| `OCR_APP_AGENT_MODEL` | 端点接受的模型标识。端点需要支持 JSON 对象结果与用量回执。 |
| `OCR_APP_AGENT_API_KEY` | Agent 专用密钥；外部端点必填。 |
| `OCR_APP_AGENT_OUTPUT_LIMIT_FIELD` | 默认 `max_completion_tokens`。确认网关使用 `max_tokens` 时可显式调整。 |
| `OCR_APP_AGENT_REPOSITORIES` | 允许发送差异的内部仓库 ID，多个使用逗号分隔。 |
| `OCR_APP_AGENT_MAX_READS` | 单次最多处理的页数，默认 8。 |
| `OCR_APP_AGENT_PAGE_LINES` | 每页最多交付的差异记录，默认 40。 |
| `OCR_APP_AGENT_MAX_OUTPUT_TOKENS` | 单次 API 请求的输出上限，默认 512。 |
| `OCR_APP_AGENT_MAX_TOTAL_TOKENS` | 单次尝试的 Token 调用门槛，默认 64000。先以请求长度加余量保守预留，已确认的调用改用实际计数。不同模型的分词与计费有差异，费用仍需以供应商配额和账单为准。 |
| `OCR_APP_AGENT_MAX_SOURCE_TOKENS` | 同一 OCR 尝试关联的全部 Agent 运行共用的 Token 门槛，默认 128000。状态未知的调用按预留额占用后续重跑预算。 |
| `OCR_APP_AGENT_TIMEOUT_SECONDS` | 运行截止预算，默认 90 秒。模型调用前与读取响应时检查，HTTP 各阶段有单独超时。 |

使用项目的隔离实例配置运行 Worker。对已有实例先按[部署手册](deployment.md)备份数据库和工件，再迁移；CLI 不会迁移数据库。示例的编号以实际任务和输出为准：

```sh
PYTHONPATH=backend .venv/bin/python -m ocr_manager.worker
```

在另一个终端加载同一隔离实例配置，执行：

```sh
PYTHONPATH=backend .venv/bin/python -m ocr_manager.agent_review_cli \
  enqueue --job-id 1 --request-key pilot-first
PYTHONPATH=backend .venv/bin/python -m ocr_manager.agent_review_cli report --id 1
PYTHONPATH=backend .venv/bin/python -m ocr_manager.agent_review_cli \
  enqueue --job-id 1 --request-key pilot-rerun --previous-id 1
PYTHONPATH=backend .venv/bin/python -m ocr_manager.agent_review_cli cancel --id 2
```

先等首次尝试结束再重跑。报告含代码证据，仅在获准的本机环境读取。MCP、跨文件取证及按 MR 变更意图分组属于后续工作。
