# 评审发现正文显示约定

关联事项：PI-20261109-009。适用于任务初审、有效补审、保留初审、历史对比、评审发现抽屉、历史问题侧栏和合并前审查的正文展示。

## 现象与原因

截图中的问题 #1362 经 SQLite 只读核对：正文有 3 个字面 `\n`，真实换行数为 0，三个字面分隔符位于分区标签前。前端现有样式支持真实换行，但旧解析器只按真实换行分区；旧正文组件只解析单反引号行内代码，不解析 Markdown 围栏。

字面 `\n` 可能由生成或中间编码环节额外转义产生；本次已确认存储形态和显示处理缺口，尚无证据确定具体哪个上游环节引入，不将推测写成已确认根因。

## 显示和兼容规则

- 保留现有问题描述、触发条件、代码依据、实际后果、修复建议及补充区，以及中文、圈号和旧行内编号的兼容整理。
- 仅在代码与引文之外、明确分区标签之前，将字面 `\n`、`\r\n` 或 `\r` 解释为显示分隔符；允许真实换行混用，不递归解码，也不写回原始字段。代码、正则、引文、普通说明中的转义原样保留。全文被重复编码的无结构文本不自动猜测解码。
- 使用 `react-markdown` 将 Markdown 转为 React 节点，支持段落、普通换行、加粗、行内代码、标准列表与代码围栏；保留旧编号的补充识别。代码围栏优先作为整体处理，内部标签、建议与编号不参与内容重排。
- 原始 HTML 作为文字，禁止 HTML 执行；外部图片仅显示替代文字，不请求资源。链接只开放 HTTP、HTTPS、站内绝对路径及锚点；外链使用 `noopener noreferrer`，其余链接目标展示为文字。
- 围栏支持反引号和波浪线，保留语言文字、缩进及代码中的转义字符；缺少结束围栏时仍展示已收到的代码。不通过规则猜测普通散文是否为代码。
- 代码区域采用灰白表面和等宽字体，右上角使用 Ant Design 复制按钮，提供复制中禁用、成功和失败反馈；复制正文不包含围栏与语言标记。失败后可重试或手动选择，兼容现有 HTTP 剪贴板降级路径。多代码块分别操作。
- 长代码在区域内横向滚动，可通过键盘聚焦；手机端保持自然正文折行和页面宽度。第一阶段不增加语法高亮、行号、下载或自动执行动作。

## 上游输出建议

生成评审正文时以实际段落和 Markdown 围栏组织内容；JSON 序列化交给标准编码器执行一次，读取时按 JSON 契约解码一次。不要手动对正文统一替换反斜杠，也不要以二次 JSON 解码修复任意历史正文。代码字符串本身的 `\n` 必须保留。后续若治理生成端，须先以原始结果和入库投影的对照证据确定引入环节，再为该边界补验证。

## 本地复验

以下检查使用合成正文、临时 SQLite 和 8791 服务，不改真实反馈、不调用外部评审服务，构建输出到隔离目录：

```sh
npm --prefix frontend run lint
npm --prefix frontend test
cd frontend
npx tsc -b
npx vite build --outDir /tmp/ocr-finding-markdown-dist --emptyOutDir
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-finding-markdown-dist \
npx playwright test e2e/findingMarkdown.spec.ts e2e/findings.spec.ts e2e/reviewFindings.spec.ts \
  --output /tmp/ocr-finding-markdown-browser
# 普通服务退出后，串行验证补审共享正文及保留初审入口。
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-finding-markdown-dist OCR_BROWSER_REVIEW_RECOVERY=1 \
npx playwright test e2e/reviewRecovery.spec.ts --output /tmp/ocr-finding-markdown-recovery-browser
```

实际通过数量、截图核对与部署边界以台账本编号后续追加为准，命令列表不代表已全部运行。部署静态资源与业务数据原文变更分别记录；本次无需数据库迁移或批量改写历史正文。
