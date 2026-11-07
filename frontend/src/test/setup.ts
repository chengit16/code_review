/** @description 清理组件与网络替身，防止测试间共享缓存或凭据。 */
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

// 组件库的响应式订阅依赖浏览器 API，测试仅提供尺寸事件接口，不模拟业务状态。
Object.defineProperty(window, "matchMedia", { writable: true, value: (query: string) => ({
  matches: false, media: query, onchange: null, addListener() {}, removeListener() {},
  addEventListener() {}, removeEventListener() {}, dispatchEvent() { return false; },
}) });
globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };

const computedStyle = window.getComputedStyle.bind(window);
// JSDOM 不支持伪元素尺寸；真实滚动条和布局由隔离浏览器验收，不在此伪造。
beforeEach(() => { vi.spyOn(window, "getComputedStyle").mockImplementation((element) => computedStyle(element)); });
