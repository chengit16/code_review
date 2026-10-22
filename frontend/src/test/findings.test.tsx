/** @description 验证卡片原地处理、旧反馈同步与服务端状态展示，不从标记推断问题已关闭。 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { ReviewJobDetail } from "../api/types";
import { FindingsPanel } from "../pages/FindingsPanel";

function renderFindings(feedback: ReviewJobDetail["feedback"], issueStatuses: ReviewJobDetail["issue_statuses"], pending = false, canEdit = true) {
  const onFeedback = vi.fn();
  render(<MemoryRouter><FindingsPanel comments={[{ path: "app.py", content: "合成发现" }]}
    feedback={feedback} issueIds={{ 0: 42 }} issueStatuses={issueStatuses}
    status="complete" coverageWaived={false} pending={pending} canEdit={canEdit} onFeedback={onFeedback} /></MemoryRouter>);
  return onFeedback;
}

describe("发现就地处理", () => {
  it("误报和修复在卡片内提交，已选标记可撤销", async () => {
    const onFeedback = renderFindings({ 0: "false_positive" }, { 0: "ignored" });
    const user = userEvent.setup();
    const group = within(screen.getByRole("group", { name: "发现 1 的反馈" }));
    await user.click(group.getByRole("button", { name: "误报" }));
    expect(onFeedback).toHaveBeenLastCalledWith(0, null);
    await user.click(group.getByRole("button", { name: "已修复" }));
    expect(onFeedback).toHaveBeenLastCalledWith(0, "fixed");
    expect(screen.getByRole("link", { name: "跟进问题 #42 · 已忽略，无需处理" })).toHaveAttribute("href", "/issues?issue=42");
  });

  it("旧误报仍待处理时可原地同步，不冒充已关闭", async () => {
    const onFeedback = renderFindings({ 0: "false_positive" }, { 0: "open" });
    expect(screen.getByRole("link", { name: "跟进问题 #42 · 待处理" })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "同步处理" }));
    expect(onFeedback).toHaveBeenCalledWith(0, "false_positive");
  });

  it("缺少服务端状态时不按反馈伪造已处理", () => {
    renderFindings({ 0: "fixed" }, undefined);
    expect(screen.getByRole("link", { name: "跟进问题 #42" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "同步处理" })).not.toBeInTheDocument();
  });

  it("保存期间禁用全部处理动作", () => {
    renderFindings({ 0: "fixed" }, { 0: "open" }, true);
    for (const button of within(screen.getByRole("group", { name: "发现 1 的反馈" })).getAllByRole("button")) {
      expect(button).toBeDisabled();
    }
  });

  it("只读用户只能查看状态和处理记录入口", () => {
    renderFindings({}, { 0: "open" }, false, false);
    expect(screen.queryByRole("group", { name: "发现 1 的反馈" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "跟进问题 #42 · 待处理" })).toBeVisible();
  });
});
