# 前端交互回归

## 检查范围

- 项目配置切换页签保留草稿；关闭窗口、浏览器返回和离开页面时确认放弃。
- 配置首次读取失败不能保存默认值；重新加载与保存错误分别提示，保存成功后清除脏状态。
- 批量重审按逐项结果取消成功项勾选；失败项保留，请求期间锁定筛选、分页和选择。
- 评审任务、待跟进问题、合并前审查支持每页 25 / 50 / 100 条及跳页，筛选和条数保存在 URL。
- 任务高级筛选按需展开，生效标签可移除；问题历史默认显示最近 10 条，按需追加。
- 1280、390、320 像素视口下验证分页、表单无横向溢出，并保留截图供人工检查。

## 执行命令

在项目根目录执行静态检查、单元测试和构建：

```sh
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
```

运行全部浏览器回归（需已安装 Playwright Chromium）：

```sh
cd frontend
npx playwright test
```

macOS 也可显式复用已安装的 Chrome：

```sh
cd frontend
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" npx playwright test
```

只检查本轮优化时，在命令末尾加 `e2e/optimization.spec.ts`。浏览器测试使用 `backend/tests/browser_app.py` 创建临时数据库并监听 8791，不连接 8781 的本机业务数据；新增用例涉及的写入使用合成接口响应。截图和失败追踪输出到 `frontend/test-results/`，不提交到 Git。
