/** @description 保护发现原文分区、顺序、未知段落与不可信内容的纯文本边界。 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FindingDescription } from "../pages/FindingDescription";
import { presentFindingContent, splitFindingContent, splitFindingList } from "../pages/findingContent";
import { splitFindingBlocks } from "../pages/findingLists";
import * as clipboard from "../ui/clipboard";

describe("发现描述分区", () => {
  it("无换行的旧标签及别名分区，代码和引用标签不拆", () => {
    expect(splitFindingContent("摘要。触发条件：打开；后果：丢失；建议：确认").map((section) => section.label)).toEqual([null, "触发条件", "实际后果", "修复建议"]);
    expect(splitFindingContent("触发条件：打开；实际后果：丢失；修复建议：确认").map((section) => section.label)).toEqual(["触发条件", "实际后果", "修复建议"]);
    const quoted = '说明 `触发条件：x；后果：y` 和「建议：z」不构成分区';
    expect(splitFindingContent(quoted)).toEqual([{ label: null, content: quoted }]);
  });

  it.each(["① 打开；② 关闭；③ 再次打开；④ 核对", "1）打开；2）关闭；3）核对", "1) 打开\n2) 关闭", "1) 打开\n\n2) 关闭", "1. 打开；2. 关闭", "1、打开；2、关闭"])("连续编号逐条换行：%s", (content) => {
    const items = splitFindingList(content);
    expect(items).not.toBeNull();
    render(<FindingDescription content={`触发条件：${content}`} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(items?.length ?? 0);
    expect(screen.getByRole("list")).toHaveClass("finding-ordered-list");
    expect(items?.map((item) => `${item.marker}${item.content}`).join("").replace(/\s/g, "")).toBe(content.replace(/\s/g, ""));
  });

  it.each(["场景①和场景②都存在", "1.2.3 与 2.0.0 版本", "① 只引用一项", "`1) 代码；2) 代码`", "```text\n1) 代码\n2) 代码\n```", "① 一；“② 引用”"])("不误拆数字、代码和普通引用：%s", (content) => {
    expect(splitFindingList(content)).toBeNull();
  });
  it("按明确行首标签保留原始顺序、多行与重复标签", () => {
    const sections = splitFindingContent("原始摘要\n触发条件：点击关闭\n第二行\n代码依据：`close()` 提前返回\n实际后果：内容丢失\n修复建议：确认后再关闭\n补充：第一点\n补充：第二点");
    expect(sections).toEqual([
      { label: null, content: "原始摘要" }, { label: "触发条件", content: "点击关闭\n第二行" },
      { label: "代码依据", content: "`close()` 提前返回" }, { label: "实际后果", content: "内容丢失" },
      { label: "修复建议", content: "确认后再关闭" }, { label: "补充", content: "第一点" }, { label: "补充", content: "第二点" },
    ]);
  });

  it("兼容明确列表和加粗标签，不把正文内提及的标签当分区", () => {
    expect(splitFindingContent("- **触发条件：** 点击\n2. **修复建议**: 确认；实际后果：这仍是建议正文")).toEqual([
      { label: "触发条件", content: "点击" }, { label: "修复建议", content: "确认；实际后果：这仍是建议正文" },
    ]);
  });

  it("代码围栏内的标签不参与拆分，未知与无标签内容不丢失", () => {
    const content = "说明\n```text\n实际后果：代码中的示例\n```\n其他说明：保留\n修复建议：下一步";
    expect(splitFindingContent(content)).toEqual([
      { label: null, content: "说明\n```text\n实际后果：代码中的示例\n```\n其他说明：保留" },
      { label: "修复建议", content: "下一步" },
    ]);
    expect(splitFindingContent("暂无分区\n原始第二行")).toEqual([{ label: null, content: "暂无分区\n原始第二行" }]);
  });

  it("标题可导航、行内标识用 code，HTML 仍是文本", () => {
    const { container } = render(<FindingDescription content={'实际后果：<img src=x onerror=alert(1)>\n修复建议：调用 `confirmDialog()`'} />);
    expect(screen.getByRole("heading", { name: "实际后果" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "修复建议" })).toBeVisible();
    expect(container.querySelector("code")).toHaveTextContent("confirmDialog()");
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeVisible();
  });

  it("结构化转义换行恢复段落与建议代码块，复制不包含 Markdown 围栏", async () => {
    const copy = vi.spyOn(clipboard, "copyText").mockResolvedValue();
    const { container } = render(<FindingDescription content={"触发条件：打开。\\n实际后果：样式缺失。\\n修复建议：保留 styles 定义。\n参考改法：\n```ts\nconst styles = StyleSheet.create({\n  descStyle: { fontSize: 14 },\n});\n```"} />);
    const code = container.querySelector(".finding-code-block code");
    expect(screen.getByRole("heading", { name: "修复建议" })).toBeVisible();
    expect(screen.getByText("ts")).toBeVisible();
    expect(code).toHaveTextContent("const styles = StyleSheet.create");
    expect(screen.getByRole("button", { name: "复制代码" })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "复制代码" }));
    expect(copy).toHaveBeenCalledWith("const styles = StyleSheet.create({\n  descStyle: { fontSize: 14 },\n});");
    expect(screen.getByText("已复制")).toBeVisible();
    copy.mockRestore();
  });

  it("只把有结构证据的转义换行当作分隔符，保留普通代码字符串", () => {
    const { container } = render(<FindingDescription content={'const value = "\\n";'} />);
    expect(container.querySelector(".finding-code-block")).toBeNull();
    expect(screen.getByText('const value = "\\n";')).toBeVisible();
  });

  it("真实与字面换行混用时仅拆标签前分隔符，保留行内代码和引用中的转义", () => {
    expect(presentFindingContent('触发条件：打开。\\n代码依据：`const s = "\\n修复建议：示例"`；“\\n实际后果：引用”。\n实际后果：失败。\\n修复建议：检查 `value.split("\\n")`。').map((part) => part.label))
      .toEqual(["触发条件", "代码依据", "实际后果", "修复建议"]);
    expect(presentFindingContent('触发条件：打开。\\n代码依据：`const s = "\\n修复建议：示例"`。')[1].content)
      .toContain('"\\n修复建议：示例"');
  });

  it.each(["```\nconst value = '\\n';\n```", "~~~ts\nconst value = '\\n';\n~~~", "```ts\nconst value = '\\n';", "````ts\n```\nconst value = 1;\n````"])("围栏、长围栏及未闭合代码保留正文：%s", (content) => {
    const { container } = render(<FindingDescription content={`修复建议：参考实现。\n${content}`} />);
    expect(container.querySelectorAll(".finding-code-block")).toHaveLength(1);
    expect(container.querySelector("pre code")?.textContent).toContain("const value");
    expect(screen.getByRole("button", { name: "复制代码" })).toBeVisible();
  });

  it("Markdown 段落、加粗和列表可读，危险链接与 HTML 不执行、图片不请求", () => {
    const { container } = render(<FindingDescription content={'修复建议：**先校验**。\n\n- 检查输入\n- 核对权限\n\n[文档](https://example.com/doc) [危险](javascript:alert%281%29)\n\n<img src=x onerror=alert(1)>\n\n![外部截图](https://example.com/image.png)'} />);
    expect(container.querySelector("strong")).toHaveTextContent("先校验");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "文档" })).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.queryByRole("link", { name: "危险" })).toBeNull();
    expect(container.querySelector("img, script")).toBeNull();
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeVisible();
  });

  it("复制失败后仍保留代码并允许重试，不显示成功", async () => {
    const copy = vi.spyOn(clipboard, "copyText").mockRejectedValueOnce(new Error("合成拒绝")).mockResolvedValue(undefined);
    render(<FindingDescription content={'修复建议：\n```ts\nconst value = "\\n";\n```'} />);
    const button = screen.getByRole("button", { name: "复制代码" });
    await userEvent.click(button);
    expect(screen.getByRole("status")).toHaveTextContent("复制失败，请手动选择代码复制。");
    expect(screen.queryByText("已复制")).toBeNull();
    await userEvent.click(button);
    expect(copy).toHaveBeenLastCalledWith('const value = "\\n";');
    expect(screen.getByRole("status")).toHaveTextContent("代码已复制");
    copy.mockRestore();
  });

  it("代码示例与旧中文编号共处同一区时，仍保留逐项布局和代码正文", () => {
    const { container } = render(<FindingDescription content={'修复建议：先检查：① 核对样式；② 补齐定义。\n\n```ts\nconst label = "修复建议：保留";\n```'} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(container.querySelector("pre code")?.textContent).toBe('const label = "修复建议：保留";');
  });

  it("无标签历史正文统一问题描述，句尾建议独立显示且原文不变", () => {
    const content = "catch 中仍保留 `console.log(error)` 调试输出，异常被静默吞掉。建议删除调试输出，并统一为消息提示或结构化日志。";
    expect(presentFindingContent(content)).toEqual([
      { label: "问题描述", content: "catch 中仍保留 `console.log(error)` 调试输出，异常被静默吞掉。" },
      { label: "修复建议", content: "建议删除调试输出，并统一为消息提示或结构化日志。" },
    ]);
    render(<FindingDescription content={content} />);
    expect(screen.getByRole("heading", { name: "问题描述" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "修复建议" })).toBeVisible();
    expect(content).toContain("。建议删除");
  });

  it("括号标签及冒号别名均兼容，建议集中且只出现一个标题", () => {
    const content = "【触发条件】用户点击确认。【代码依据】`done()` 提前执行。【实际后果】内容丢失。【建议】等待保存完成。\n补充：回调重复，建议抽取公共方法。";
    const sections = presentFindingContent(content);
    expect(sections.map((section) => section.label)).toEqual(["触发条件", "代码依据", "实际后果", "修复建议", "补充"]);
    expect(sections.find((section) => section.label === "修复建议")?.content).toBe("等待保存完成。\n\n建议抽取公共方法。");
    expect(splitFindingContent("[问题描述] 内容丢失\n[建议] 请确认")).toEqual([
      { label: "问题描述", content: "内容丢失" }, { label: "修复建议", content: "请确认" },
    ]);
  });

  it("编号问题内的括号建议和句尾建议移入修复建议，不吞掉括号后的问题", () => {
    const content = "可维护性：1）类型过宽（建议用 `ref<T>()` + 泛型 `(request: () => Promise<T>) => Promise<T>`）；2）同一逻辑重复实现，修改时需两处同步，建议抽到公共方法复用。";
    const sections = presentFindingContent(content);
    expect(sections).toHaveLength(2);
    expect(sections[0].label).toBe("问题描述");
    expect(sections[0].content).toContain("修改时需两处同步");
    expect(sections[0].content).not.toContain("建议");
    expect(sections[1].content).toContain("1） 建议用 `ref<T>()` + 泛型 `(request: () => Promise<T>) => Promise<T>`");
    expect(sections[1].content).toContain("2） 建议抽到公共方法复用。");
  });

  it.each(["① 一；③ 三", "2）二；3）三", "（1）先核对；（2）再关闭", "一、核对；二、关闭", "a) 核对；b) 关闭", "场景①已填写内容丢失；场景②产生孤儿草稿。"])("所有明确升序分项换行且保留原编号：%s", (content) => {
    const items = splitFindingList(content);
    expect(items).toHaveLength(2);
    expect(items?.map((item) => `${item.marker}${item.content}`).join("").replace(/\s/g, "")).toBe(content.replace(/\s/g, ""));
  });

  it("所有区均支持前言后的列表，代码依据的场景说明也独立一行", () => {
    const content = "先说明当前行为；而在场景②下 `getId()` 仍返回 null，弹窗关闭后留下不可见草稿。";
    expect(splitFindingBlocks(content)).toEqual([
      { kind: "paragraph", content: "先说明当前行为；" },
      { kind: "list", items: [{ marker: "而在场景②", content: "下 `getId()` 仍返回 null，弹窗关闭后留下不可见草稿。" }] },
    ]);
    render(<FindingDescription content={[
      "触发条件：打开弹窗：① 填写；② 关闭。",
      `代码依据：${content}`,
      "实际后果：场景①内容丢失；场景②留下草稿。",
      "补充：其他事项：1) 第一项；2) 第二项。",
    ].join("\n")} />);
    expect(screen.getAllByRole("list")).toHaveLength(4);
    expect(screen.getAllByRole("listitem")).toHaveLength(7);
  });

  it("分项正文只有代码或引用时仍保留分项，中文逗号也可分隔编号", () => {
    const content = "① `first()`，② 「第二项」，③ `third()`。";
    expect(splitFindingList(content)).toEqual([
      { marker: "①", content: "`first()`，" },
      { marker: "②", content: "「第二项」，" },
      { marker: "③", content: "`third()`。" },
    ]);
  });

  it("不同编号组、前言和尾注原文完整保留", () => {
    const content = "前言：1) 甲；2) 乙。\n另一组：a) 丙；b) 丁。\n尾注：只作说明。";
    const blocks = splitFindingBlocks(content);
    const rebuilt = blocks.map((block) => block.kind === "paragraph" ? block.content : block.items.map((item) => item.marker + item.content).join("")).join("");
    expect(rebuilt.replace(/\s/g, "")).toBe(content.replace(/\s/g, ""));
    expect(blocks.filter((block) => block.kind === "list")).toHaveLength(2);
  });

  it("编号项仅含建议时不遗留空的问题编号", () => {
    expect(presentFindingContent("1) 建议删除调试输出。\n2) 建议统一日志。"))
      .toEqual([{ label: "修复建议", content: "1) 建议删除调试输出。\n\n2) 建议统一日志。" }]);
  });

  it("建议后的独立事实不随建议一起移动", () => {
    expect(presentFindingContent("日志仍存在，建议删除调试输出；异常也被静默吞掉。"))
      .toEqual([
        { label: "问题描述", content: "日志仍存在，异常也被静默吞掉。" },
        { label: "修复建议", content: "建议删除调试输出；" },
      ]);
  });

  it("空行后的段落不继承上一编号，围栏内空行不参与分段", () => {
    expect(presentFindingContent("1) 甲；2) 乙。\n\n重复实现，建议抽取公共方法。"))
      .toEqual([
        { label: "问题描述", content: "1) 甲；\n2) 乙。\n\n重复实现，" },
        { label: "修复建议", content: "建议抽取公共方法。" },
      ]);
    const fenced = "```text\n1) 示例\n\n2) 示例\n```";
    expect(splitFindingBlocks(fenced)).toEqual([{ kind: "paragraph", content: fenced }]);
  });

  it.each([
    "请参考场景①和场景②，不是分项定义。",
    "版本 1.2.3；版本 2.0.0 不同。",
    "示例 `建议删除 x；1) a；2) b` 仅为代码。",
    "说明「建议删除按钮」只是文案引用。",
    "```text\n建议删除示例\n【建议】示例\n1) a\n2) b\n```",
    "这里的建议不明确，保留原文。",
  ])("模糊建议、代码、引用与版本不误拆：%s", (content) => {
    const sections = presentFindingContent(content);
    expect(sections).toEqual([{ label: "问题描述", content }]);
    expect(splitFindingList(content)).toBeNull();
  });
});
