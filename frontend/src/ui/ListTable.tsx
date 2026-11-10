/** @description 紧凑列表的表格外观与窄屏标签；查询、列定义、选择与权限仍由调用页负责。 */
import { Table } from "antd";
import type { TableProps } from "antd";
import { useSyncExternalStore } from "react";
import type { TdHTMLAttributes } from "react";

import { detailRowProps } from "./detailRow";

/** 详情入口可选；调用页决定目标，其他行事件及权限不由通用表格推断。 */
type DetailTableProps<T extends object> = TableProps<T> & {
  /** 点击非交互区域或行焦点按 Enter 时打开只读详情。 */ onOpenRow?: (record: T) => void;
  /** 提供包含业务身份的行名称；默认使用“查看详情”。 */ rowLabel?: (record: T) => string;
};

function ListCell({ children, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td {...props}><div className="list-cell-content">{children}</div></td>;
}

function subscribe(listener: () => void) {
  const media = window.matchMedia?.("(max-width: 600px)");
  media?.addEventListener("change", listener);
  return () => media?.removeEventListener("change", listener);
}
function snapshot() { return window.matchMedia?.("(max-width: 600px)").matches ?? false; }

/** 与表格卡片布局使用相同断点；订阅在卸载时清理，不缓存业务状态。 */
export function useNarrowList() {
  return useSyncExternalStore(subscribe, snapshot, () => false);
}

/** 沿用 Ant Design 表格语义；窄屏逐行展示全部业务字段，不隐藏状态与时间。 */
export function ListTable<T extends object>({ onOpenRow, rowLabel, ...props }: DetailTableProps<T>) {
  const narrow = useNarrowList();
  const columns = props.columns?.map((column) => ({ ...column,
    onCell: (record: T, index?: number) => ({ ...column.onCell?.(record, index),
      "data-label": typeof column.title === "string" ? column.title : "" }),
  }));
  return <Table<T> {...props} columns={columns} size={props.size ?? "small"}
    onRow={onOpenRow ? (record) => detailRowProps(() => onOpenRow(record), rowLabel?.(record) ?? "查看详情") : props.onRow}
    components={{ ...props.components, body: { cell: ListCell, ...props.components?.body } }}
    className={`compact-list-table ${props.className ?? ""}`} scroll={narrow ? undefined : props.scroll} />;
}
