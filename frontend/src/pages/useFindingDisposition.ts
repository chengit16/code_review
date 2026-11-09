/** @description 跟进问题的独立处置；只修改显式问题编号，不新增或撤销发现反馈。 */
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { updateReviewIssues } from "../api/reviewIssues";
import type { IssueActionStatus, IssueBatchTarget } from "../api/reviewIssues";

/** 单个冻结问题的处置请求；备注保留操作者对本次决定的说明。 */
export interface FindingDisposition {
  /** 点击时复制的问题编号及状态，不随轮询改写。 */ target: IssueBatchTarget;
  /** 四种处置互斥，历史评价保持不变。 */ status: IssueActionStatus;
  /** 用户填写的说明，不包含凭据或代码。 */ note: string;
}

/** 使用现有鉴权及并发校验接口；失败不自动重试，成功刷新所有共享问题的视图。 */
export function useFindingDisposition(token: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ target, status, note }: FindingDisposition) => updateReviewIssues(token, [target], status, note),
    retry: false,
    onSuccess: async () => {
      // 一个问题可能关联多个任务；处置和反馈仍分别从服务端重读，不能互相推断。
      await Promise.all(["jobs", "job-neighbors", "job", "review-issues", "review-issue", "review-effectiveness", "overview"].map((key) =>
        client.invalidateQueries({ queryKey: [key] })));
    },
  });
}
