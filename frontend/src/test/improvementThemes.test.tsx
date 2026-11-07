/** @description 验证优化主题草稿、阶段操作、关联选择及失败重试；不连接真实服务。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import * as api from "../api/improvements";
import * as commandId from "../api/commandId";
import type { ImprovementThemeRecord } from "../api/improvements";
import { ImprovementThemeEditor } from "../pages/ImprovementThemeEditor";
import { emptyImprovement } from "../pages/improvementFields";

const theme: ImprovementThemeRecord = { id: 1, version: 3, title: "有界调度", category: "stability",
  status: "active", scope: "平台", objective: "避免任务互相阻塞", rationale: "", outcome: "",
  next_steps: "", references: "", phases: [], improvement_ids: [7],
  archived_at: null, archived_by: "", archive_reason: "", created_at: "2026-11-06T00:00:00Z", updated_at: "2026-11-06T01:00:00Z" };

function editor(record?: ImprovementThemeRecord) {
  vi.spyOn(api, "listImprovements").mockResolvedValue({ total: 1, page: 1, page_size: 25, items: [
    { ...emptyImprovement(), id: 7, version: 1, title: "合成待关联问题", archived_at: null, archived_by: "", archive_reason: "", created_at: "", updated_at: "" },
  ] });
  const onClose = vi.fn();
  const onSaved = vi.fn();
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <ImprovementThemeEditor token="" record={record} onClose={onClose} onSaved={onSaved} />
  </QueryClientProvider>);
  return { onClose, onSaved };
}

describe("优化主题", () => {
  it("安全请求键不可用时保留主题与阶段，不在渲染阶段崩溃", async () => {
    vi.spyOn(commandId, "createCommandId").mockImplementation(() => { throw new Error("合成随机能力不可用"); });
    const save = vi.spyOn(api, "createImprovementTheme");
    editor();
    await screen.findByRole("checkbox", { name: /合成待关联问题/ });
    fireEvent.change(screen.getByLabelText("主题名称"), { target: { value: "保留主题" } });
    fireEvent.change(screen.getByLabelText("总体目标"), { target: { value: "保留目标" } });
    fireEvent.click(screen.getByRole("button", { name: "添加阶段" }));
    fireEvent.change(screen.getByLabelText("阶段名称"), { target: { value: "保留阶段" } });
    fireEvent.change(screen.getByLabelText("阶段目标"), { target: { value: "合成阶段目标" } });
    fireEvent.click(screen.getByRole("button", { name: "保存主题" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("合成随机能力不可用");
    expect(screen.getByLabelText("阶段名称")).toHaveValue("保留阶段");
    expect(save).not.toHaveBeenCalled();
  });
  it("阶段可增删，放弃确认取消后保留草稿和阶段", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { onClose } = editor();
    fireEvent.change(screen.getByLabelText("主题名称"), { target: { value: "新优化" } });
    fireEvent.click(screen.getByRole("button", { name: "添加阶段" }));
    fireEvent.change(screen.getByLabelText("阶段名称"), { target: { value: "先隔离" } });
    fireEvent.click(screen.getByRole("button", { name: /^关闭$/ }));
    expect(confirm).toHaveBeenCalledOnce();
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByLabelText("阶段名称")).toHaveValue("先隔离");
    fireEvent.click(screen.getByRole("button", { name: "删除阶段 1" }));
    expect(screen.queryByLabelText("阶段名称")).not.toBeInTheDocument();
    await screen.findByRole("checkbox", { name: /合成待关联问题/ });
  });

  it("失败保留阶段与显式关联，新建重试复用同一个幂等键", async () => {
    const save = vi.spyOn(api, "createImprovementTheme").mockRejectedValue(new Error("合成失败"));
    const { onSaved } = editor();
    fireEvent.change(screen.getByLabelText("主题名称"), { target: { value: "新主题" } });
    fireEvent.change(screen.getByLabelText("总体目标"), { target: { value: "明确边界" } });
    fireEvent.click(await screen.findByRole("checkbox", { name: /合成待关联问题/ }));
    fireEvent.click(screen.getByRole("button", { name: "保存主题" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("合成失败");
    fireEvent.click(screen.getByRole("button", { name: "保存主题" }));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
    expect(save.mock.calls[0][2]).toEqual([7]);
    expect(save.mock.calls[0][3]).toEqual(save.mock.calls[1][3]);
    expect(screen.getByLabelText("主题名称")).toHaveValue("新主题");
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("版本冲突保留进展说明、阶段与原关联，不静默覆盖读取版本", async () => {
    const update = vi.spyOn(api, "updateImprovementTheme").mockRejectedValue(new Error("主题已更新"));
    const { onSaved } = editor(theme);
    await screen.findByRole("checkbox", { name: /合成待关联问题/ });
    fireEvent.change(screen.getByLabelText("本次进展说明"), { target: { value: "补充排查" } });
    fireEvent.click(screen.getByRole("button", { name: "保存主题" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("主题已更新");
    expect(screen.getByLabelText("本次进展说明")).toHaveValue("补充排查");
    expect(update.mock.calls[0].slice(3)).toEqual([[7], 3, "补充排查"]);
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("搜索没有命中也不清除已有跨页选择", async () => {
    editor(theme);
    await screen.findByRole("checkbox", { name: /合成待关联问题/ });
    vi.mocked(api.listImprovements).mockResolvedValue({ total: 0, items: [], page: 1, page_size: 25 });
    fireEvent.change(screen.getByLabelText("搜索可关联记录"), { target: { value: "不存在" } });
    fireEvent.click(screen.getByRole("button", { name: "搜索问题" }));
    await screen.findByText("没有匹配的记录，已有选择仍保留。");
    expect(screen.getByRole("button", { name: "取消关联记录 7" })).toBeVisible();
  });
});
