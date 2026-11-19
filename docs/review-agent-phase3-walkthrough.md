# 第三阶段双评审对比

从「评审任务」打开一条任务，在任务详情选择「双评审对比」。已完成的比较会显示固定的 Git 基准和目标提交、原始 OCR 初审与 Agent 尝试、两侧各自的覆盖、发现与用量。覆盖的单位分别是 OCR 文件和 Agent 差异记录。暂停、失败或用量未回执均保留本次状态。

- 「比较版本」切换已保存的尝试。已打开的历史版本可通过当前任务地址中的 `agent_comparison` 参数返回。
- 选择「Agent 独有」查看尚未归入已确认同根因组的 Agent 发现。同文件同行会生成待核对提示。核对之后，可建立、编辑、合并或拆除同根因组，也可补录两侧共同漏报。
- 「查看证据」显示固定版本的行和摘录。管理员可以保存「成立」「不成立」或「证据不足」，另记是否值得处理和备注。并发更新会返回 409，编辑框保留草稿。读取最新裁定后核对同一条的当前值，再保存自己的修订。
- 「重跑 Agent」会为当前 OCR 初审追加一次 Agent 尝试，旧比较、裁定和 OCR 初审可继续查看。按钮受试点仓库、固定 Git 范围和运行状态约束。较早任务没有固定范围时显示「仅 OCR」。

管理员可在任务详情点击「启用仓库试点」，确认该任务所属仓库后保存。授权保存在 SQLite，立即生效并复用该仓库生效的评审模型。实际发送差异和用量计入发生在另一次「运行 Agent → 确认入队」之后。「关闭仓库试点」需要先等该仓库的排队和运行任务结束，已有结果和裁定仍可读。已通过私有配置授权的仓库沿用原入口。

读者可查看比较和历史。写入沿用管理员授权，只在 SQLite 登记任务或追加裁定。Worker 领取 Agent 任务，OCR 结果、飞书通知和 GitLab 发布继续由原业务流程维护。HTTP 只返回管理台所需的固定版本投影。

## 本机隔离预览

在项目根目录执行。样例服务会写入临时 Git 和 SQLite，Worker 仅使用本机环回脚本模型。浏览器测试和样例服务都复用此夹具。

```sh
preview_dir=$(mktemp -d "$PWD/.local-data/agent-comparison-preview.XXXXXX")
npm --prefix frontend run build -- --outDir "$preview_dir/dist"
OCR_BROWSER_AGENT_COMPARISON=1 OCR_BROWSER_FRONTEND_DIST="$preview_dir/dist" \
  .venv/bin/python backend/tests/browser_app.py
```

打开 `http://127.0.0.1:8791/jobs/1#job-agent-comparison`。已有 `8791` 服务时可为该命令设置 `OCR_BROWSER_AGENT_COMPARISON_PORT` 并访问对应端口。任务 1 有两路结果，任务 2 可查看仅 OCR 的旧范围状态。重跑可观察 Worker 从排队到完成，再切回旧比较检查裁定。终止样例服务会清理临时数据库。

## 契约与部署

API 位于 `/api/jobs/{job_id}/agent-comparisons`。`GET` 返回运行资格和分页历史，`POST` 以请求键和明确的 OCR 尝试登记新比较。详情通过 `/{comparison_id}` 按任务读取，`curation_version` 可定位历史裁定。`PUT /{comparison_id}/curation` 使用 `expected_version` 防止覆盖并发修改。

SQLite v56 添加比较裁定表及历史查询索引，v57 添加管理台仓库授权表。迁移保留已有 OCR 和 Agent 报告，页面授权默认关闭。正式切换应按[部署手册](deployment.md)准备数据库和工件备份，并使 API、Worker 与静态产物配套升级。启用真实仓库前，仍需核实发送范围和模型预算预留。
