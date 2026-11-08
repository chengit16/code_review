/** @description 保留 React Router 内存会话的 Ant Design 路由按钮；不替代服务端权限。 */
import { Button } from "antd";
import type { ReactNode } from "react";
import { useLinkClickHandler } from "react-router-dom";

/** 保持链接与组合键打开语义，普通点击不整页刷新或清空内存凭据。 */
export function RouteButton({ to, children }: {
  /** 应用内目标地址。 */ to: string;
  /** 可读链接文字。 */ children: ReactNode;
}) {
  const navigate = useLinkClickHandler<HTMLAnchorElement>(to);
  return <Button href={to} onClick={navigate}>{children}</Button>;
}
