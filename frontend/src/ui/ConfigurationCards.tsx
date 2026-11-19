/** @description 配置卡片列表与本地分页；只编排已加载的完整数组，不接管配置或连接测试写入。 */
import { Empty, Pagination, Spin } from "antd";
import type { ReactNode } from "react";

import type { LocalListResult } from "./useLocalList";

/** 与本地列表共享 URL 分页；查询失败保持未知，不展示成正常空列表。 */
export function ConfigurationCards<T>({ list, loading, failed, emptyText, label, renderItem }: {
  /** 完整数组的本地筛选及分页状态。 */ list: LocalListResult<T>;
  /** 刷新期间显示加载状态。 */ loading: boolean;
  /** 读取失败不展示正常空状态。 */ failed: boolean;
  /** 成功读取但没有匹配项的提示。 */ emptyText: string;
  /** 列表及分页可访问名称。 */ label: string;
  /** 以业务 ID 为 key 创建卡片，内部动作由页面维护。 */ renderItem: (item: T) => ReactNode;
}) {
  const visible = list.filtered?.slice((list.page - 1) * list.pageSize, list.page * list.pageSize) ?? [];
  return <section className="configuration-card-list" aria-label={label} aria-busy={loading}>
    <Spin spinning={loading}>
      <div className="configuration-card-grid">{visible.map(renderItem)}</div>
      {!failed && !loading && visible.length === 0 && <Empty description={emptyText} image={Empty.PRESENTED_IMAGE_SIMPLE} />}
    </Spin>
    {list.filtered !== undefined && <nav className="configuration-card-pagination" aria-label={`${label}分页`}><Pagination {...list.pagination} /></nav>}
  </section>;
}
