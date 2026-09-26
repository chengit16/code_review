/** @description 页面标题和命令区保持一致的工作台布局。 */

import type { ReactNode } from "react";

/** 在紧凑页面标题右侧放置必要操作。 */
export function PageHeader({ title, subtitle, actions }: {
  /** 页面名称。 */ title: string;
  /** 与当前数据相关的简短说明。 */ subtitle?: string;
  /** 页面命令控件。 */ actions?: ReactNode;
}) {
  return <header className="page-header"><div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div><div className="page-actions">{actions}</div></header>;
}
