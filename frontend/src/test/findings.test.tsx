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
  it.each(["helpful", "false_positive", "ignored"] as const)("只选中一个反馈且再次点击可撤销：%s", async (verdict) => {
    const onFeedback = renderFindings({ 0: verdict }, { 0: "fixed" });
    const group = within(screen.getByRole("group", { name: "发现 1 的反馈" }));
    expect(group.getAllByRole("button")).toHaveLength(3);
    expect(group.getAllByRole("button", { pressed: true })).toHaveLength(1);
    expect(group.queryByRole("button", { name: "已修复" })).not.toBeInTheDocument();
    await userEvent.click(group.getByRole("button", { pressed: true }));
    expect(onFeedback).toHaveBeenLastCalledWith(0, null);
    expect(screen.getByRole("link", { name: "跟进问题 #42 · 已修复" })).toBeVisible();
  });

  it("新反馈只提交价值选择，不改变问题状态", async () => {
    const onFeedback = renderFindings({}, { 0: "open" });
    const user = userEvent.setup();
    for (const [label, verdict] of [["有帮助", "helpful"], ["误报", "false_positive"], ["忽略", "ignored"]]) {
      await user.click(screen.getByRole("button", { name: label }));
      expect(onFeedback).toHaveBeenLastCalledWith(0, verdict);
      expect(screen.getByRole("link", { name: "跟进问题 #42 · 待处理" })).toBeVisible();
    }
  });

  it("历史修复标记不作为价值反馈选中，并归入未评价筛选", async () => {
    renderFindings({ 0: "fixed" }, undefined);
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
    expect(screen.getByRole("link", { name: "跟进问题 #42 · 待处理" })).toBeVisible();
  });
});
