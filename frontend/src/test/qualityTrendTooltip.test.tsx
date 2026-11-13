/** @description 保护图表提示的四类数量、占比分母、零值、日期切换和键盘关闭；全部使用合成数据。 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfigProvider } from "antd";
import { expect, it } from "vitest";

import type { ReviewQuality } from "../api/effectiveness";
import { DesignProvider } from "../app/DesignProvider";
import { QualityTrend } from "../pages/overview/QualityTrend";

const quality: ReviewQuality = {
  summary: { total: 10, helpful: 4, false_positive: 1, ignored: 0, unmarked: 5 },
  since: "2026-11-07 00:00:00", until: "2026-11-14 00:00:00", unavailable_sources: 0,
  categories: [], projects: [], trend: [
    { day: "2026-11-07", total: 0, helpful: 0, false_positive: 0, ignored: 0, unmarked: 0 },
    { day: "2026-11-08", total: 10, helpful: 4, false_positive: 1, ignored: 0, unmarked: 5 },
  ],
};

function show(data = quality, days = 7) {
  // JSDOM 不执行布局动画，实际命中、滚动与触控由隔离 Chrome 验证。
  return render(<ConfigProvider theme={{ token: { motion: false } }}><DesignProvider><QualityTrend quality={data} days={days} /></DesignProvider></ConfigProvider>);
}

it.each([7, 30])("%s 天视图按当天总数显示数量与占比，零样本不显示零百分比", async (days) => {
  show(quality, days);
  const user = userEvent.setup();
  await user.hover(screen.getByRole("button", { name: "查看 2026-11-08 反馈数据" }));
  const tip = await screen.findByRole("tooltip");
  expect(tip).toHaveTextContent("2026-11-08（UTC）");
  expect(tip).toHaveTextContent("占当天总发现（含未评价）");
  expect(within(tip).getAllByRole("definition").map((node) => node.textContent)).toEqual(["4 条（40.0%）", "1 条（10.0%）", "0 条（0.0%）", "5 条（50.0%）", "10 条"]);
  await user.hover(screen.getByRole("button", { name: "查看 2026-11-07 反馈数据" }));
  await waitFor(() => expect(screen.getAllByRole("tooltip")).toHaveLength(1));
  expect(screen.getByRole("tooltip")).toHaveTextContent("2026-11-07（UTC）");
  expect(screen.getByRole("tooltip")).toHaveTextContent("当天暂无发现，占比不适用");
  expect(within(screen.getByRole("tooltip")).getAllByRole("definition").map((node) => node.textContent)).toEqual(["0 条（—）", "0 条（—）", "0 条（—）", "0 条（—）", "0 条"]);
});

it("键盘聚焦打开提示，Escape 关闭且保留焦点，滚动关闭旧位置", async () => {
  show();
  const user = userEvent.setup();
  const target = screen.getByRole("button", { name: "查看 2026-11-08 反馈数据" });
  target.focus();
  expect(await screen.findByRole("tooltip")).toHaveTextContent("总发现10 条");
  await user.keyboard("{Escape}");
  await waitFor(() => expect(screen.queryByRole("tooltip")).not.toBeInTheDocument());
  expect(target).toHaveFocus();
  fireEvent.focus(target);
  await screen.findByRole("tooltip");
  fireEvent.scroll(screen.getByRole("region", { name: "反馈趋势图，可横向滚动" }));
  await waitFor(() => expect(screen.queryByRole("tooltip")).not.toBeInTheDocument());
});

it("90 天周桶提示保留完整起止日期和同源求和", async () => {
  show({ ...quality, trend: Array.from({ length: 8 }, (_, index) => ({
    day: `2026-11-${String(index + 1).padStart(2, "0")}`,
    total: 1, helpful: 1, false_positive: 0, ignored: 0, unmarked: 0,
  })) }, 90);
  await userEvent.hover(screen.getByRole("button", { name: "查看 2026-11-01 至 2026-11-07 反馈数据" }));
  const tip = await screen.findByRole("tooltip");
  expect(tip).toHaveTextContent("2026-11-01 至 2026-11-07（UTC）");
  expect(tip).toHaveTextContent("占本区间总发现（含未评价）");
  expect(within(tip).getAllByRole("definition").map((node) => node.textContent)).toEqual(["7 条（100.0%）", "0 条（0.0%）", "0 条（0.0%）", "0 条（0.0%）", "7 条"]);
});

it("90 天占比按区间数量求和计算，不平均每日占比，末组保留实际日期", async () => {
  show({ ...quality, trend: Array.from({ length: 90 }, (_, index) => ({
    day: new Date(Date.UTC(2026, 10, 1 + index)).toISOString().slice(0, 10),
    total: index === 0 ? 1 : index === 1 ? 9 : 0,
    helpful: index === 0 ? 1 : 0, false_positive: index === 1 ? 9 : 0, ignored: 0, unmarked: 0,
  })) }, 90);
  const user = userEvent.setup();
  expect(screen.getAllByRole("button", { name: /^查看 .* 反馈数据$/ })).toHaveLength(13);
  await user.hover(screen.getByRole("button", { name: "查看 2026-11-01 至 2026-11-07 反馈数据" }));
  expect(within(await screen.findByRole("tooltip")).getAllByRole("definition").map((node) => node.textContent)).toEqual(["1 条（10.0%）", "9 条（90.0%）", "0 条（0.0%）", "0 条（0.0%）", "10 条"]);
  await user.hover(screen.getByRole("button", { name: "查看 2027-01-24 至 2027-01-29 反馈数据" }));
  await waitFor(() => expect(screen.getAllByRole("tooltip")).toHaveLength(1));
  expect(screen.getByRole("tooltip")).toHaveTextContent("2027-01-24 至 2027-01-29（UTC）");
  expect(screen.getByRole("tooltip")).toHaveTextContent("本区间暂无发现，占比不适用");
});

it("悬停和聚焦后的点击仍保持打开，重复点击不误关提示", async () => {
  show();
  const user = userEvent.setup();
  const target = screen.getByRole("button", { name: "查看 2026-11-07 反馈数据" });
  await user.hover(target);
  target.focus();
  await user.click(target);
  expect(await screen.findByRole("tooltip")).toHaveTextContent("总发现0 条");
  await user.click(target);
  expect(screen.getAllByRole("tooltip")).toHaveLength(1);
  expect(screen.getByRole("tooltip")).toHaveTextContent("2026-11-07（UTC）");
});
