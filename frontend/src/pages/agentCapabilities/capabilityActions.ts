/** @description 管理操作、查询缓存更新与后台检查轮询。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App } from "antd";

import { agentCatalogKey, getAgentCheck } from "../../api/agentCapabilities";

/** 完成一次管理操作后刷新受影响的配置。 */
export function useCapabilityAction() {
  const { message } = App.useApp();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (action: () => Promise<void>) => action(),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: agentCatalogKey });
      void client.invalidateQueries({ queryKey: ["agent-project"] });
      void client.invalidateQueries({ queryKey: ["agent-comparisons"] });
    },
    onError: (error) => void message.error(error.message),
  });
}

/** 仅在 Worker 尚未完成时轮询。 */
export function useCapabilityCheck(token: string, checkId: number | null) {
  return useQuery({
    queryKey: ["agent-capability-check", checkId],
    queryFn: ({ signal }) => getAgentCheck(token, checkId!, signal),
    enabled: checkId !== null,
    refetchInterval: ({ state }) =>
      state.data?.status === "complete" || state.data?.status === "failed" ? false : 1500,
  });
}
