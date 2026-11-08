/** @description 任务分页保留兼容入口；统一展示不改变 URL、选择范围或加载锁定。 */
import type { ComponentProps } from "react";

import { ListPagination } from "../../ui/ListPagination";

/** 保护任务分页的可访问名称与既有属性契约。 */
export function JobsPagination(props: ComponentProps<typeof ListPagination>) {
  return <ListPagination {...props} label="任务分页" />;
}
