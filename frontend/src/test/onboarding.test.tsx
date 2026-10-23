/** @description 验证接入引导按服务端配置展示进度并保留离开入口。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { OnboardingPage } from "../pages/OnboardingPage";

describe("首次接入引导", () => {
  it("显示清单步骤、退出入口和已保存配置进度", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/model-profiles")) return new Response(JSON.stringify([{ id: 1, enabled: 1 }]));
      if (url.endsWith("/api/notification-targets")) return new Response(JSON.stringify([{ id: 1, name: "通知" }]));
      if (url.endsWith("/api/repositories")) return new Response(JSON.stringify([]));
      return new Response(JSON.stringify([]));
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter><OnboardingPage token="" /></MemoryRouter></QueryClientProvider>);
    expect(await screen.findByText("配置评审模型")).toBeVisible();
    expect(await screen.findByText("2 / 5")).toBeVisible();
    expect(screen.getByRole("link", { name: "稍后再做" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: /前往模型设置/ })).toHaveAttribute("href", "/settings?tab=model");
  });
});
