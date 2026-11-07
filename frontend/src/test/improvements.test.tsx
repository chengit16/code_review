/** @description 验证台账三个维度、草稿保护、保存失败和旧版本冲突；不连接真实服务。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ImprovementRecord } from "../api/improvements";
import { ImprovementEditor } from "../pages/ImprovementEditor";
import * as commandId from "../api/commandId";
import { ImprovementFacts } from "../pages/ImprovementFacts";
import { emptyImprovement } from "../pages/improvementFields";

const record: ImprovementRecord = { ...emptyImprovement(), id: 1, version: 3, title: "超时诊断",
  description: "保留失败证据", archived_at: null, archived_by: "", archive_reason: "", created_at: "2026-11-06T00:00:00Z", updated_at: "2026-11-06T01:00:00Z" };

function editor(existing?: ImprovementRecord) {
  const onClose = vi.fn();
  const onSaved = vi.fn();
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}><ImprovementEditor token="" record={existing} onClose={onClose} onSaved={onSaved} /></QueryClientProvider>);
  return { onClose, onSaved };
}

describe("问题与改进", () => {
  it("安全随机能力缺失只阻止保存，不使表单崩溃或丢失草稿", async () => {
    vi.spyOn(commandId, "createCommandId").mockImplementation(() => { throw new Error("合成随机能力不可用"); });
    const fetch = vi.spyOn(globalThis, "fetch");
    editor();
    fireEvent.change(screen.getByLabelText("标题"), { target: { value: "仍可编辑的草稿" } });
    fireEvent.change(screen.getByLabelText("现象或目标"), { target: { value: "合成故障" } });
    fireEvent.click(screen.getByRole("button", { name: "保存记录" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("合成随机能力不可用");
    expect(screen.getByLabelText("标题")).toHaveValue("仍可编辑的草稿");
    expect(fetch).not.toHaveBeenCalled();
  });
  it("代码修改、本地通过和未部署不混为同一状态，内容按纯文本显示", () => {
    render(<ImprovementFacts record={{ ...record, code_state: "modified", verification_state: "passed", validation_evidence: "合成测试通过", description: "<script>不执行</script>" }} />);
    expect(screen.getByText("代码已修改")).toBeVisible();
    expect(screen.getByText("本地验证通过")).toBeVisible();
    expect(screen.getByText("未部署")).toBeVisible();
    expect(screen.queryByText("部署已生效")).not.toBeInTheDocument();
    expect(screen.getByText("<script>不执行</script>")).toBeVisible();
  });

  it("保存失败保留输入，同一份新建草稿重试复用创建键", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "合成写入失败" }), { status: 503 }));
    const { onSaved } = editor();
    fireEvent.change(screen.getByLabelText("标题"), { target: { value: "连接失败" } });
    fireEvent.change(screen.getByLabelText("现象或目标"), { target: { value: "合成故障" } });
    fireEvent.click(screen.getByRole("button", { name: "保存记录" }));
    await screen.findByRole("alert");
    expect(screen.getByLabelText("标题")).toHaveValue("连接失败");
    expect(onSaved).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "保存记录" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    const first = JSON.parse(String(fetch.mock.calls[0][1]?.body));
    const second = JSON.parse(String(fetch.mock.calls[1][1]?.body));
    expect(first.client_key).toBe(second.client_key);
  });

  it("版本冲突保留草稿和进展说明，不覆盖读取版本", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "记录已被更新" }), { status: 409 }));
    const { onSaved } = editor(record);
    fireEvent.change(screen.getByLabelText("标题"), { target: { value: "待核对的新标题" } });
    fireEvent.change(screen.getByLabelText("本次进展说明"), { target: { value: "补充排查" } });
    fireEvent.click(screen.getByRole("button", { name: "保存记录" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("记录已被更新");
    expect(screen.getByLabelText("标题")).toHaveValue("待核对的新标题");
    expect(screen.getByLabelText("本次进展说明")).toHaveValue("补充排查");
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body)).expected_version).toBe(3);
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("取消放弃确认时，关闭和 Escape 均保留草稿", () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { onClose } = editor();
    fireEvent.change(screen.getByLabelText("标题"), { target: { value: "未保存" } });
    fireEvent.click(screen.getByRole("button", { name: /^关闭$/ }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(confirm).toHaveBeenCalledTimes(2);
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByLabelText("标题")).toHaveValue("未保存");
  });
});
