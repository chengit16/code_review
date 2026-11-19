/** @description 旧预审入口按明确编号映射跳转，避免与普通任务数字编号碰撞。 */
import { useQuery } from "@tanstack/react-query";
import { Navigate, useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";

/** 兼容旧列表与旧详情书签。 */
export function PremergePage({ token }: { /** 内存管理凭据。 */ token: string }) {
  const [params] = useSearchParams();
  const legacyId = params.get("review") || params.get("id");
  const mapping = useQuery({ queryKey: ["premerge-mapping", legacyId], queryFn: ({ signal }) => apiRequest<{ job_id: number | null }>(token, `/api/premerge-reviews/${legacyId}`, { signal }), enabled: Boolean(legacyId) });
  const next = new URLSearchParams(params); next.set("source", "premerge"); next.delete("review"); next.delete("id"); next.delete("latest_only"); next.delete("actionable_only");
  if (legacyId && mapping.isPending) return <p role="status">正在定位历史评审任务…</p>;
  if (mapping.error) return <p role="alert">{mapping.error.message}</p>;
  return <Navigate replace to={mapping.data?.job_id ? `/jobs/${mapping.data.job_id}` : `/jobs?${next}`} />;
}
