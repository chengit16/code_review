/** @description 归档确认、失败草稿、固定版本、禁重复提交与成功缓存失效；只模拟服务端边界。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import * as api from "../api/improvements";
import { ImprovementArchiveControl } from "../pages/ImprovementArchiveControl";

function control(archived = false, resource: "records" | "themes" = "records") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const onSaved = vi.fn();
  const record = { id: 7, title: "合成对象<script>纯文本</script>", version: 3,
    archived_at: archived ? "2026-11-06T01:00:00Z" : null,
    archived_by: archived ? "合成用户" : "", archive_reason: archived ? "保留阶段结论" : "" };
  render(<QueryClientProvider client={client}><ImprovementArchiveControl token="" resource={resource} record={record} disabled={false} onSaved={onSaved} /></QueryClientProvider>);
  return { invalidate, onSaved };
}

describe("台账与主题归档", () => {
  it.each(["records", "themes"] as const)("%s 成功归档携带版本与原因，刷新关系、历史和复盘", async (resource) => {
    const change = vi.spyOn(api, "changeImprovementArchive").mockResolvedValue({ version: 4,
      archived_at: "2026-11-06T01:00:00Z", archived_by: "合成用户", archive_reason: "阶段收纳" });
    const { invalidate, onSaved } = control(false, resource);
    fireEvent.click(screen.getByRole("button", { name: "归档内容" }));
    expect(screen.getByText(/合成对象<script>纯文本<\/script>/)).toBeVisible();
    expect(screen.getByRole("button", { name: "确认归档" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("归档原因"), { target: { value: " 阶段收纳 " } });
    fireEvent.click(screen.getByRole("button", { name: "确认归档" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
    expect(change).toHaveBeenCalledWith("", resource, 7, true, 3, "阶段收纳");
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["improvement-summary"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["improvement-themes"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["improvements"] });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("恢复必须填写新原因，不以归档时的原因静默恢复", async () => {
    const change = vi.spyOn(api, "changeImprovementArchive").mockResolvedValue({ version: 4,
      archived_at: null, archived_by: "", archive_reason: "" });
    const { onSaved } = control(true);
    expect(screen.getByText(/已归档.*保留阶段结论/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "恢复内容" }));
    expect(screen.getByLabelText("恢复原因")).toHaveValue("");
    fireEvent.change(screen.getByLabelText("恢复原因"), { target: { value: "继续处理遗留" } });
    fireEvent.click(screen.getByRole("button", { name: "确认恢复" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
    expect(change).toHaveBeenCalledWith("", "records", 7, false, 3, "继续处理遗留");
  });

  it("版本冲突保留原因和固定版本，不自动重试或使缓存伪装成功", async () => {
    const change = vi.spyOn(api, "changeImprovementArchive").mockRejectedValue(new Error("版本已更新"));
    const { invalidate, onSaved } = control();
    fireEvent.click(screen.getByRole("button", { name: "归档内容" }));
    fireEvent.change(screen.getByLabelText("归档原因"), { target: { value: "尚未保存的原因" } });
    fireEvent.click(screen.getByRole("button", { name: "确认归档" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("版本已更新");
    expect(screen.getByLabelText("归档原因")).toHaveValue("尚未保存的原因");
    expect(change).toHaveBeenCalledOnce();
    expect(onSaved).not.toHaveBeenCalled();
    expect(invalidate).not.toHaveBeenCalled();
  });

  it("提交期间禁止重复提交、取消和 Escape，完成后才关闭", async () => {
    let finish: () => void = () => undefined;
    const change = vi.spyOn(api, "changeImprovementArchive").mockImplementation(() => new Promise((resolve) => {
      finish = () => resolve({ version: 4, archived_at: "2026-11-06T00:00:00Z", archived_by: "合成用户", archive_reason: "收纳" });
    }));
    control();
    fireEvent.click(screen.getByRole("button", { name: "归档内容" }));
    fireEvent.change(screen.getByLabelText("归档原因"), { target: { value: "收纳" } });
    fireEvent.click(screen.getByRole("button", { name: "确认归档" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "正在提交…" })).toBeDisabled());
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("dialog")).toBeVisible();
    expect(screen.getByRole("button", { name: "取消" })).toBeDisabled();
    expect(change).toHaveBeenCalledOnce();
    await act(async () => finish());
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("取消放弃确认时保留归档原因", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    control();
    fireEvent.click(screen.getByRole("button", { name: "归档内容" }));
    fireEvent.change(screen.getByLabelText("归档原因"), { target: { value: "不能丢失" } });
    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByLabelText("归档原因")).toHaveValue("不能丢失");
  });
});
