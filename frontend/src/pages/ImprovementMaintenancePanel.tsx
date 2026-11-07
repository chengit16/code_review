/** @description 展示后台同步与自动归档事实及管理员策略；不把保存成功当成执行完成。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { getImprovementMaintenance, setImprovementMaintenance } from "../api/improvementMaintenance";
import type { MaintenanceStatus } from "../api/improvementMaintenance";
import { QueryState } from "../ui/QueryState";
import { formatTime } from "../ui/format";

const errorLabels: Record<string, string> = {
  source_conflict: "来源历史被修改、删除，或页面存在人工修改；需核对后继续同步，自动归档已跳过本轮。",
  source_unavailable: "台账来源无法读取或格式不合法，本轮自动归档已跳过。",
  archive_failed: "本轮自动归档失败，归档事务已回滚。",
};

/** 独立状态查询失败不阻断问题列表；每 30 秒刷新以跟随后台同步。 */
export function ImprovementMaintenancePanel({ token }: {
  /** 内存管理员会话，服务端继续验证权限。 */ token: string;
}) {
  const status = useQuery({ queryKey: ["improvement-maintenance"],
    queryFn: ({ signal }) => getImprovementMaintenance(token, signal), refetchInterval: 30_000 });
  return <details className="section"><summary>自动归档与台账同步{status.data && !status.isError ? ` · 自动归档${status.data.enabled ? "已开启" : "已关闭"}` : ""}</summary>
    <p className="muted">仅归档已解决、验证通过或不适用、部署确认或不适用、证据齐全且无遗留的内容。主题还须全部阶段完成、关联问题闭环。归档不删除内容，可随时恢复；恢复后重新计时。</p>
    <QueryState loading={status.isLoading} error={status.error} onRetry={() => void status.refetch()} />
    {status.data && !status.isError && <><p>台账同步：{status.data.source_configured ? "已配置，后台每 30 秒检查追加内容" : "未配置服务器来源"}；最近检查：{formatTime(status.data.last_checked_at)}；最近成功：{formatTime(status.data.last_success_at)}</p>
      {status.data.last_error_code && <p role="alert">{errorLabels[status.data.last_error_code] ?? "后台维护未完成，请检查监控进程。"}</p>}
      {status.data.last_result.sync.conflicts.length > 0 && <p>待核对来源：{status.data.last_result.sync.conflicts.join("、")}</p>}
      <p>上轮同步新增 {status.data.last_result.sync.created} 条、追加 {status.data.last_result.sync.updated} 版；归档问题 {status.data.last_result.archived_records} 条、主题 {status.data.last_result.archived_themes} 个。</p>
      <p>当前候选：问题 {status.data.candidate_records} 条、主题 {status.data.candidate_themes} 个（只读预览，未启用时不执行）。</p>
      <PolicyForm token={token} initial={status.data} />
    </>}
  </details>;
}

function PolicyForm({ token, initial }: { token: string; initial: MaintenanceStatus }) {
  // 后台刷新不覆盖未提交草稿或其读取版本；只有本次保存成功才推进版本。
  const [enabled, setEnabled] = useState(initial.enabled);
  const [days, setDays] = useState(String(initial.archive_after_days));
  const [version, setVersion] = useState(initial.version);
  const [feedback, setFeedback] = useState("");
  const client = useQueryClient();
  const save = useMutation({ mutationFn: () => setImprovementMaintenance(token, enabled, Number(days), version),
    onSuccess: (next) => {
      setVersion(next.version);
      setFeedback("策略已保存，后台下轮执行；不代表本轮已经归档。");
      void client.invalidateQueries({ queryKey: ["improvement-maintenance"] });
    } });
  return <form className="improvement-search improvement-maintenance-form" onSubmit={(event) => { event.preventDefault(); setFeedback(""); save.mutate(); }}>
    <label><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} disabled={save.isPending} />启用自动归档</label>
    <label>连续无更新天数<input type="number" min={1} max={3650} required value={days} onChange={(event) => setDays(event.target.value)} disabled={save.isPending} /></label>
    <button type="submit" className="button button-secondary" disabled={save.isPending}>保存归档策略</button>
    {save.error && <p role="alert">{save.error.message}；草稿已保留。请刷新页面并核对最新策略后再保存（刷新前自行保留草稿）。</p>}
    {feedback && <p role="status">{feedback}</p>}
  </form>;
}
