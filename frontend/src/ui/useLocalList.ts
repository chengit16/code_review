/** @description 完整配置数组的本地筛选与 URL 分页；不用于服务端分页或最近记录接口，不接管编辑草稿。 */
import type { TablePaginationConfig } from "antd";
import { useSearchParams } from "react-router-dom";

/** 完整配置数组在当前 URL 范围内的只读视图；undefined 保留查询未确认的事实。 */
export interface LocalListResult<T> {
  /** 已提交关键词。 */ q: string;
  /** 当前独立状态，all 不增加约束。 */ status: string;
  /** 夹限到筛选后范围的正整数页码。 */ page: number;
  /** 每页 25、50 或 100 条。 */ pageSize: number;
  /** 已搜索并按状态过滤的完整数组，交给表格分页。 */ filtered: T[] | undefined;
  /** 忽略自身状态、保留关键词的完整范围计数。 */ counts: Record<string, number> | undefined;
  /** 只修改指定前缀的参数；非翻页操作清除本列表页码。 */ update: (key: string, value: string) => void;
  /** Ant Design 受控分页配置，不用于服务端分页。 */ pagination: TablePaginationConfig;
}

/** 本地计数仅在完整数组已取得时可用；每个列表使用独立参数前缀。 */
export function useLocalList<T>(items: T[] | undefined, searchOf: (item: T) => string,
  statusOf: (item: T) => string = () => "all", prefix = ""): LocalListResult<T> {
  const [params, setParams] = useSearchParams();
  const q = params.get(`${prefix}q`) ?? "";
  const status = params.get(`${prefix}status`) ?? "all";
  const pageSize = [25, 50, 100].includes(Number(params.get(`${prefix}page_size`))) ? Number(params.get(`${prefix}page_size`)) : 25;
  const searched = items?.filter((item) => searchOf(item).toLocaleLowerCase().includes(q.trim().toLocaleLowerCase()));
  const counts: Record<string, number> | undefined = searched ? { all: searched.length } : undefined;
  for (const item of searched ?? []) {
    const key = statusOf(item);
    if (counts && key !== "all") counts[key] = (counts[key] ?? 0) + 1;
  }
  const filtered = searched?.filter((item) => status === "all" || statusOf(item) === status);
  const requested = Math.max(1, Math.floor(Number(params.get(`${prefix}page`))) || 1);
  const page = Math.min(requested, Math.max(1, Math.ceil((filtered?.length ?? 0) / pageSize)));
  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value && value !== "all") next.set(`${prefix}${key}`, value); else next.delete(`${prefix}${key}`);
    if (key !== "page") next.delete(`${prefix}page`);
    setParams(next);
  }
  return { q, status, page, pageSize, filtered, counts, update,
    pagination: { current: page, pageSize, total: filtered?.length,
      showSizeChanger: true, pageSizeOptions: [25, 50, 100],
      showTotal: (total: number) => `共 ${total} 条`,
      onChange: (nextPage: number, size: number) => size !== pageSize ? update("page_size", String(size)) : update("page", String(nextPage)),
    },
  };
}
