/** @description 验证三种价值反馈互斥、可撤销且不混入问题处置；只使用合成发现。 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { ReviewJobDetail } from "../api/types";
import { DesignProvider } from "../app/DesignProvider";
import { FindingsPanel } from "../pages/FindingsPanel";

function renderFindings(feedback: ReviewJobDetail["feedback"], issueStatuses: ReviewJobDetail["issue_statuses"], pending = false, canEdit = true) {
  const onFeedback = vi.fn();
  render(<DesignProvider><MemoryRouter><FindingsPanel comments={[{ path: "app.py", content: "合成发现" }]}
    feedback={feedback} issueIds={{ 0: 42 }} issueStatuses={issueStatuses}
    status="complete" coverageWaived={false} pending={pending} canEdit={canEdit} onFeedback={onFeedback} /></MemoryRouter></DesignProvider>);
  return onFeedback;
}

describe("发现价值反馈", () => {
  it("有帮助与撤销按已保存反馈更新处理状态，不由关联问题修复状态推断", () => {
    const props = { comments: [{ path: "app.py", content: "合成发现" }], issueIds: { 0: 42 },
      status: "complete", coverageWaived: false, pending: false, onFeedback: vi.fn() };
    const show = (feedback: ReviewJobDetail["feedback"], status: "open" | "fixed") =>
      <MemoryRouter><FindingsPanel {...props} feedback={feedback} issueStatuses={{ 0: status }} /></MemoryRouter>;
    const view = render(show({}, "fixed"));
    expect(screen.getByLabelText("发现 1 的处理状态")).toHaveTextContent("待处理");
    view.rerender(show({ 0: "helpful" }, "open"));
    expect(screen.getByLabelText("发现 1 的处理状态")).toHaveTextContent("已处理");
    expect(screen.getByRole("link", { name: "跟进问题 #42" })).not.toHaveTextContent("待处理");
    view.rerender(show({}, "open"));
    expect(screen.getByLabelText("发现 1 的处理状态")).toHaveTextContent("待处理");
  });

  it("已处理和待处理筛选按三类反馈判断，兼容旧直达 open 不再按问题状态筛选", async () => {
    render(<DesignProvider><MemoryRouter><FindingsPanel comments={Array.from({ length: 5 }, (_, index) => ({ path: `${index}.py`, content: "合成发现" }))}
      feedback={{ 0: "helpful", 1: "false_positive", 2: "ignored", 3: "fixed" }}
      issueStatuses={{ 0: "open", 1: "open", 2: "open", 3: "fixed", 4: "fixed" }}
      status="complete" coverageWaived={false} pending={false} onFeedback={vi.fn()} initialIssueState="open" /></MemoryRouter></DesignProvider>);
    expect(screen.getAllByRole("article")).toHaveLength(2);
    expect(screen.getByRole("article", { name: "发现 4" })).toBeVisible();
    expect(screen.getByRole("article", { name: "发现 5" })).toBeVisible();
    await userEvent.click(screen.getByRole("combobox", { name: "发现的处理状态" }));
    await userEvent.click(screen.getByRole("option", { name: "已处理" }));
    expect(screen.getAllByRole("article")).toHaveLength(3);
    for (const index of [1, 2, 3]) expect(screen.getByRole("article", { name: `发现 ${index}` })).toBeVisible();
    await userEvent.click(screen.getByRole("combobox", { name: "发现的处理状态" }));
    await userEvent.click(screen.getByRole("option", { name: "全部发现" }));
    expect(screen.getAllByRole("article")).toHaveLength(5);
  });

  it.each(["helpful", "false_positive", "ignored"] as const)("只选中一个反馈且再次点击可撤销：%s", async (verdict) => {
    const onFeedback = renderFindings({ 0: verdict }, { 0: "fixed" });
    expect(screen.getByLabelText("发现 1 的处理状态")).toHaveTextContent("已处理");
    const group = within(screen.getByRole("group", { name: "发现 1 的反馈" }));
    expect(group.getAllByRole("button")).toHaveLength(3);
    expect(group.getAllByRole("button", { pressed: true })).toHaveLength(1);
    expect(group.queryByRole("button", { name: "已修复" })).not.toBeInTheDocument();
    await userEvent.click(group.getByRole("button", { pressed: true }));
    expect(onFeedback).toHaveBeenLastCalledWith(0, null);
    expect(screen.getByRole("link", { name: "跟进问题 #42" })).toBeVisible();
  });

  it("新反馈只提交价值选择，不改变问题状态", async () => {
    const onFeedback = renderFindings({}, { 0: "open" });
    const user = userEvent.setup();
    for (const [label, verdict] of [["有帮助", "helpful"], ["误报", "false_positive"], ["忽略", "ignored"]]) {
      await user.click(screen.getByRole("button", { name: label }));
      expect(onFeedback).toHaveBeenLastCalledWith(0, verdict);
      expect(screen.getByRole("link", { name: "跟进问题 #42" })).toBeVisible();
    }
  });

  it("历史修复标记不作为价值反馈选中，并归入未评价筛选", async () => {
    renderFindings({ 0: "fixed" }, undefined);
    expect(screen.getByLabelText("发现 1 的处理状态")).toHaveTextContent("待处理");
    expect(screen.getByText(/旧版“已修复”标记不计入价值评价/)).toBeVisible();
    expect(screen.getByRole("group").querySelectorAll('[aria-pressed="true"]')).toHaveLength(0);
    expect(screen.getByRole("link", { name: "跟进问题 #42" })).toBeVisible();
    await userEvent.click(screen.getByRole("combobox", { name: "发现的反馈" }));
    await userEvent.click(screen.getByText("未评价", { exact: true }));
    expect(screen.getByRole("article", { name: "发现 1" })).toBeVisible();
  });

  it("保存时禁用，读者不显示反馈按钮", () => {
    renderFindings({}, { 0: "open" }, true);
    for (const button of screen.getAllByRole("button")) expect(button).toBeDisabled();
  });

  it("只读用户保留问题入口", () => {
    renderFindings({}, { 0: "open" }, false, false);
    expect(screen.queryByRole("group")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "跟进问题 #42" })).toBeVisible();
  });
});
