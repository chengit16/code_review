/** @description 管理员在任务详情确认所属仓库的试点授权。保存成功后刷新服务端运行资格。 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Modal } from "antd";
import { useState } from "react";

import { updateAgentPilot } from "../../api/agentComparisons";
import type { ComparisonPilot } from "../../api/agentComparisons";

interface PilotProps {
  /** 当前管理会话，服务端复核管理员权限。 */
  token: string;
  /** 由服务端定位所属仓库的任务。 */
  jobId: number;
  /** 当前仓库授权和用于确认的名称。 */
  pilot: ComparisonPilot;
}

/** 保存仓库试点授权，不提交此任务。 */
export function AgentPilotControl({ token, jobId, pilot }: PilotProps) {
  const client = useQueryClient();
  const [desired, setDesired] = useState<boolean | null>(null);
  const update = useMutation({
    mutationFn: (enabled: boolean) => updateAgentPilot(token, jobId, enabled),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["agent-comparisons"] });
      void client.invalidateQueries({ queryKey: ["agent-project"] });
      setDesired(null);
    },
  });

  return <>
    <Button type={pilot.enabled ? "default" : "primary"} onClick={() => {
      update.reset();
      setDesired(!pilot.enabled);
    }}>{pilot.enabled ? "关闭仓库试点" : "启用仓库试点"}</Button>
    <Modal open={desired !== null} title={desired ? "启用仓库 Agent 试点" : "关闭仓库 Agent 试点"}
      okText={desired ? "确认启用" : "确认关闭"} confirmLoading={update.isPending}
      closable={!update.isPending} mask={{ closable: !update.isPending }}
      cancelButtonProps={{ disabled: update.isPending }}
      onCancel={update.isPending ? undefined : () => setDesired(null)}
      onOk={() => desired !== null && update.mutate(desired)}>
      <p><strong>{pilot.repository_name}</strong></p>
      <p>{desired
        ? "此仓库的管理员可按任务手动运行 Agent。每次确认入队后，固定提交差异会发给该仓库生效的评审模型，可能产生费用。"
        : "关闭后停止接收此仓库的新 Agent 评审，已有比较与人工裁定仍可查看。"}</p>
      {update.error && <Alert type="error" showIcon title={update.error.message} />}
    </Modal>
  </>;
}
