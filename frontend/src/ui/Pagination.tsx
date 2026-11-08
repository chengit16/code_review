/** @description 存量列表分页兼容入口；分页状态仍由父页维护。 */
import type { ComponentProps } from "react";

import { ListPagination } from "./ListPagination";

/** 统一 Ant Design 分页控件，不改变各页的查询与写入范围。 */
export function Pagination(props: ComponentProps<typeof ListPagination>) {
  return <ListPagination {...props} />;
}
