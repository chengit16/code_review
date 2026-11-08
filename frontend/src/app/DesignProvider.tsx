/** @description 统一 Ant Design 中文与灰白蓝主题；不管理业务状态或替代权限判断。 */
import { App, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import type { ReactNode } from "react";

/** 为组件和上下文弹窗提供一致主题，不引入影响存量页面的全局重置。 */
export function DesignProvider({ children }: {
  /** 当前应用或隔离测试中的界面。 */ children: ReactNode;
}) {
  return <ConfigProvider locale={zhCN} button={{ autoInsertSpace: false }} theme={{ token: {
    colorPrimary: "#1677ff", colorText: "#262626", colorTextSecondary: "#666666",
    colorBgLayout: "#f5f5f5", borderRadius: 6, controlHeight: 40,
    fontFamily: '"DM Sans", "Noto Sans SC", sans-serif',
  }, components: { Tabs: { titleFontSizeSM: 12, horizontalItemGutter: 12 }, Select: { optionActiveBg: "#e6f4ff" } } }}>
    {/* 不创建全站 ant-app 容器，避免其链接重置覆盖尚未迁移的导航与页面。 */}
    <App component={false}>{children}</App>
  </ConfigProvider>;
}
