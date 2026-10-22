/** @description 管理当前页勾选快照、批量确认和缓存刷新；HTTP 与角色授权由独立层负责。 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { updateReviewIssues } from "../api/reviewIssues";
import type { IssueActionStatus, IssueBatchTarget } from "../api/reviewIssues";

/** 批量动作与确认提示共用的中文标签。 */
export const issueActionLabels = { open: "恢复待处理", fixed: "标记已修复", ignored: "标记已忽略" };

/** 当前列表最小选择事实；已合并问题仅供查看。 */
export interface IssueSelectable {
  /** 持久化问题编号。 */ id: number;
  /** 最新服务端状态，勾选时复制为并发快照。 */ status: IssueActionStatus | "merged";
}

/** 返回当前页有效勾选、确认动作及保存状态；筛选分页切换时由页面重新挂载。 */
export function useIssueBatch(token: string, items: IssueSelectable[]) {
  const [selected, setSelected] = useState<Record<number, IssueActionStatus>>({});
  const [note, setNote] = useState("");
  const queryClient = useQueryClient();
  const selectable = items.filter((item) => item.status !== "merged");
  // 刷新后不再可见的行不参与提交，仍可见的行保留勾选时快照用于冲突检查。
  const targets: IssueBatchTarget[] = selectable.flatMap((item) =>
    selected[item.id] ? [{ id: item.id, expected_status: selected[item.id] }] : []);
  const mutation = useMutation({
    mutationFn: ({ targets, status, note }: { targets: IssueBatchTarget[]; status: IssueActionStatus; note: string }) =>
      updateReviewIssues(token, targets, status, note),
    onSuccess: async () => {
      setSelected({});
      setNote("");
      // 问题可能被多个任务引用，批量结果同步刷新列表、详情、卡片和成效统计。
      await Promise.all(["review-issues", "review-issue", "job", "review-effectiveness"].map((key) =>
        queryClient.invalidateQueries({ queryKey: [key] })));
    },
  });
  function toggle(item: IssueSelectable, checked: boolean) {
    if (mutation.isPending || item.status === "merged") return;
    const next = { ...selected };
    if (checked) next[item.id] = item.status; else delete next[item.id];
    setSelected(next);
  }
  function selectAll(checked: boolean) {
    if (mutation.isPending) return;
    const next: Record<number, IssueActionStatus> = {};
    if (checked) for (const item of selectable) if (item.status !== "merged") next[item.id] = item.status;
    setSelected(next);
  }
  function submit(status: IssueActionStatus) {
    if (mutation.isPending || targets.length === 0) return;
    if (!window.confirm(`确认将所选 ${targets.length} 条问题${issueActionLabels[status]}？\n仅处理当前页勾选项，不包含其他页。关联任务将同步显示新的问题状态。`)) return;
    mutation.mutate({ targets, status, note });
  }
  return { targets, selectableCount: selectable.length, allSelected: targets.length > 0 && targets.length === selectable.length,
    note, setNote, toggle, selectAll, submit, mutation };
}
