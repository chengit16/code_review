# HTTP 域名操作与浏览器能力兼容

关联事项：PI-20261107-002；补审业务前序为 PI-20261106-008。代码、验证与实际发布进度以问题台账追加记录为准。

## 现象与原因

普通 HTTP 域名不是安全上下文。localhost 的开发例外使本机访问能够使用 `crypto.randomUUID`，不能由此推断穿透域名也可使用。页面直接调用缺失的方法，会在请求发出前抛错；这不是补审接口拒绝请求。剪贴板同样需要能力检查。

本轮审计覆盖前端手写生产源码中的安全上下文能力、随机键、复制、请求取消/超时和固定结构草稿克隆；不承诺兼容所有老旧浏览器或第三方浏览器插件。现有 Vite 与框架的现代浏览器基线保持不变。

| 入口 | 修复与边界 |
| --- | --- |
| 补审确认、问题新建、主题新建 | 统一 `createCommandId`；优先原生 UUID，否则用 `crypto.getRandomValues` 生成 UUID v4。绝不退回 `Math.random`。两种安全能力均缺失时显示错误并保留草稿，不发送写请求。 |
| 幂等命令重试 | 同一表单/确认命令保留创建键；响应丢失不能换键重新创建。请求层不自动重试写操作。 |
| 回调地址、隐藏及明文令牌复制 | 统一 `copyText`；优先异步剪贴板，必要时尝试受控临时节点复制。用后清除、恢复焦点与选择；复制失败明确提示手动选择，不假报成功，不持久化令牌。 |
| 全部 API 请求 | 用基础 `AbortController`、监听与计时器组合取消和超时，不依赖 `AbortSignal.timeout/any`。超时覆盖响应体读取，结束即清理资源，主动取消与超时分开。 |
| 审核规则草稿 | 按固定 JSON 类型复制规则对象和数组，不依赖 `structuredClone`，不共享缓存中的可变数组。 |
| 后续防回归 | ESLint 禁止生产调用点直接使用上述敏感 API，能力封装及测试除外。 |

兼容修复不会把 HTTP 变成加密连接，不改变服务端鉴权或授权。跨不可信网络应使用 HTTPS 和受保护的管理入口；不要通过关闭浏览器安全机制解决问题。

## 补审批次失败是另一条链路

当前只读证据表明 #381 两次补审都完成 0/5，工件标记 `budget_exceeded`，失败覆盖分类为 `budget`；预算各为 1000，总用量分别记录 550、584。预算保护会在继续派发前判断可用额度，因此不能把中止等同于已记录用量必然超过预算，也不能凭上述数值断言某个更高额度必成功。计划与正式审核共用累计额度，必须由用户核对后人工决定预算和是否再试。

- 新批次的 `child_not_usable`、`budget_unconfirmed`、`no_progress` 归为执行失败；来源版本或输入失效仍归为失效。
- 旧批次保留原始 `stale`，页面明确注明旧分类含义，并显示固定原因码与安全的完成数、预算/超时摘要；不直接展示模型原文、任意失败正文或工件路径。
- 读取历史不会重写初审、历史状态、有效结论、费用、通知和剩余批次数。
- 此预算中止与初审曾有的 HTTP 504 是不同故障；浏览器兼容、诊断展示不等于上游网关超时已经修复。

## 验证命令与安全边界

```sh
npm --prefix frontend run lint
npm --prefix frontend test
cd frontend
npx tsc -b
npx vite build --outDir /tmp/ocr-http-recovery-fix-dist
OCR_BROWSER_HTTP_COMPAT=1 OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-http-recovery-fix-dist npx playwright test e2e/httpCompatibility.spec.ts
OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-http-recovery-fix-dist npx playwright test
OCR_BROWSER_REVIEW_RECOVERY=1 OCR_BROWSER_FRONTEND_DIST=/tmp/ocr-http-recovery-fix-dist npx playwright test e2e/reviewRecovery.spec.ts
```

本机未安装 Playwright 自带 Chromium 时，可显式传入 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` 指向本机 Chrome。合成域名通过测试浏览器的 host resolver 映射到隔离服务 8791，不修改系统 hosts，不操作业务端口 8781。

HTTP 兼容与补审使用独立验收通道；默认浏览器套件会切换多人鉴权，不能与它们共享临时数据库后假定仍为开发模式。规则兼容用例使用响应替身保护生产的在途任务配置锁，仅验证请求、草稿复制与放弃行为；问题/主题和补审幂等则在独立临时后端实际持久化核验。

真实业务域名验收只读取历史或在浏览器路由层拦截补审 POST 并返回合成响应，不能为了验收消耗真实补审次数、调用付费模型、自动增加预算或触发外发。实际执行结果与本地发布范围分别追加台账，不将这些命令清单本身视为已通过。

## 为什么问题页面没有自动出现

monitor 每 30 秒同步显式台账追加，不抓取聊天。同一 PI 编号会进入已有记录的版本历史，不自动创建新事项；本轮 HTTP 问题此前没有追加，是记录遗漏，现以独立 PI-20261107-002 建档并关联原补审事项。正在处理、失败或受阻也应及时记录，不必等修复结束。同步异常先核对来源摘要、页面版本及冲突，不强制覆盖网页人工事实。
