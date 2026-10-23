/** @description 验证运维对账呈现只读差异并提供诊断导出。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReconciliationPanel } from "../pages/ReconciliationPanel";

describe("数据对账", () => {
  it("展示状态差异和诊断下载入口，不提供自动修复操作", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      generated_at: "2026-10-23T00:00:00+00:00",
      issue_count: 1,
      checked: { events: 4, jobs: 3, deliveries: 3, artifact_directories: 2 },
      orphan_artifact_directories: 1,
      issues: [{ code: "artifact_without_job", object_type: "artifact", object_id: 99, detail: "工件目录没有对应的评审任务记录。" }],
    })));
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><ReconciliationPanel token="" /></QueryClientProvider>);
    expect(await screen.findByText("artifact_without_job")).toBeVisible();
    expect(screen.getByText(/工件目录没有对应/)).toBeVisible();
    expect(screen.getByRole("button", { name: "下载诊断包" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: /自动修复/ })).not.toBeInTheDocument();
  });
});
