/** @description 任务详情的双评审入口。地址记住选择，后台变更不会替换正在复核的历史版本。 */

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, App, Button, Modal, Select, Skeleton, Space, Tag } from "antd";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { createAgentComparison, getAgentComparison, getAgentComparisons } from "../../api/agentComparisons";
import type { AgentComparison, ComparisonCreate, CurationSnapshot } from "../../api/agentComparisons";
import { ApiError } from "../../api/client";
import { createCommandId } from "../../api/commandId";
import { formatTime } from "../../ui/format";

import { AgentPilotControl } from "./AgentPilotControl";
import { ComparisonEditDialog } from "./ComparisonEditDialog";
import { ComparisonWorkspace } from "./ComparisonWorkspace";
import type { ComparisonEdit } from "./comparisonEdits";
import "./agentComparison.css";

const statusLabels = {
  queued: "排队中", running: "运行中", complete: "已完成", partial: "部分完成",
  failed: "失败", skipped: "已跳过", cancelled: "已取消",
};

function selectedId(raw: string | null) {
  const value = Number(raw);
  return Number.isSafeInteger(value) && value > 0 ? value : null;
}

/** 提供 OCR 基线、比较选择和明确确认的单侧入队。 */
export function AgentComparisonPanel({ token, jobId, canEdit }: { token: string; jobId: number; canEdit: boolean }) {
  const location = useLocation();
  const navigate = useNavigate();
  const params = new URLSearchParams(location.search);
  const { message } = App.useApp();
  const [draft, setDraft] = useState<ComparisonCreate | null>(null);
  const client = useQueryClient();
  useEffect(() => {
    if (location.hash === "#job-agent-comparison") {
      document.getElementById("job-agent-comparison")?.scrollIntoView?.({ block: "start" });
    }
  }, [location.hash]);
  const index = useInfiniteQuery({
    queryKey: ["agent-comparisons", jobId], initialPageParam: null as number | null,
    queryFn: ({ signal, pageParam }) => getAgentComparisons(token, jobId, pageParam, signal),
    getNextPageParam: (last) => last.next_before_id,
    refetchInterval: ({ state }) => state.data?.pages[0]?.active_id ? 3000 : 15000,
  });
  const current = index.data?.pages[0];
  const runs = Array.from(new Map(index.data?.pages.flatMap((page) => page.items.map((row) => [row.id, row] as const))).values());
  const selected = selectedId(params.get("agent_comparison")) ?? runs[0]?.id ?? null;
  function selectComparison(id: number | null) {
    const next = new URLSearchParams(params);
    if (id === null) next.delete("agent_comparison");
    else next.set("agent_comparison", String(id));
    navigate({ pathname: location.pathname, search: next.toString(), hash: location.hash },
      { preventScrollReset: true, state: location.state });
  }
  const enqueue = useMutation({
    mutationFn: (body: ComparisonCreate) => createAgentComparison(token, jobId, body),
    onSuccess: ({ id }) => {
      setDraft(null);
      selectComparison(id);
      void client.invalidateQueries({ queryKey: ["agent-comparisons", jobId] });
    },
  });
  const selectedLoaded = selected !== null && runs.some((entry) => entry.id === selected);
  const options = runs.map((entry) => ({ value: entry.id,
    label: `Agent #${entry.id} · OCR ${entry.source_attempt} · ${statusLabels[entry.status]}`,
    title: formatTime(entry.created_at) }));
  if (selected !== null && !selectedLoaded) options.push({ value: selected, label: `Agent #${selected}`, title: "指定历史比较" });
  const canRun = canEdit && current?.current_source_attempt != null && !current.unavailable_reason;
  return <section id="job-agent-comparison" className="job-detail-region agent-comparison" aria-labelledby="job-agent-comparison-title">
    <div className="agent-comparison-main-heading">
      <div><h2 id="job-agent-comparison-title">双评审对比</h2><p>阿里 OCR 初审与自建 Agent</p></div>
      {canEdit && current && <Space wrap>
        {current.pilot.enabled && <Button type="primary" disabled={!canRun} onClick={() => {
          if (current.current_source_attempt === null) return;
          enqueue.reset();
          try {
            setDraft({ source_attempt: current.current_source_attempt, previous_id: current.previous_id,
              request_key: createCommandId() });
          } catch (error) {
            void message.error(error instanceof Error ? error.message : "无法生成本次请求标识");
          }
        }}>{current.previous_id === null ? "运行 Agent" : "重跑 Agent"}</Button>}
        {current.pilot.manageable && <AgentPilotControl token={token} jobId={jobId} pilot={current.pilot} />}
      </Space>}
    </div>
    {index.isPending && <Skeleton active paragraph={{ rows: 2 }} />}
    {index.error && <Alert type="error" showIcon title={index.error.message}
      action={<Button size="small" onClick={() => void index.refetch()}>重试读取</Button>} />}
    {current && selected === null && <div className="agent-comparison-empty">
      <Tag>仅 OCR</Tag><span>{current.unavailable_reason ?? "当前初审尚未运行 Agent"}</span>
      <a href="#job-result">查看 OCR 初审发现</a>
    </div>}
    {selected !== null && <>
      <div className="agent-comparison-controls">
        <Select aria-label="比较版本" className="agent-version-select" popupMatchSelectWidth={false} value={selected}
          options={options} onChange={(id) => selectComparison(id)} />
        <div className="agent-history-actions">
          {index.hasNextPage && <Button size="small" loading={index.isFetchingNextPage} onClick={() => void index.fetchNextPage()}>加载更早版本</Button>}
          {!selectedLoaded && runs.length > 0 && <Button size="small" onClick={() => selectComparison(null)}>回到最新比较</Button>}
        </div>
      </div>
      {canEdit && current?.unavailable_reason && <p className="agent-comparison-reason">{current.unavailable_reason}</p>}
      <ComparisonSelection key={selected} id={selected} canEdit={canEdit} jobId={jobId} token={token} />
    </>}
    <Modal open={draft !== null} title={draft?.previous_id == null ? "运行自建 Agent" : "单侧重跑 Agent"}
      okText="确认入队" confirmLoading={enqueue.isPending} closable={!enqueue.isPending}
      mask={{ closable: !enqueue.isPending }} cancelButtonProps={{ disabled: enqueue.isPending }}
      onCancel={enqueue.isPending ? undefined : () => setDraft(null)} onOk={() => draft && enqueue.mutate(draft)}>
      <p>对任务 #{jobId} 的 OCR 初审第 {draft?.source_attempt} 次运行 Agent。{draft?.previous_id != null ? `保留比较 #${draft.previous_id} 及其裁定。` : ""}</p>
      <p>Worker 会发送固定提交差异给配置的模型，可能产生费用。OCR 与通知沿用原记录。</p>
      {enqueue.error && <Alert type="error" showIcon title={enqueue.error.message}
        description={enqueue.error instanceof ApiError && enqueue.error.status === 409
          ? "请关闭此窗口并核对当前版本。" : "可用原请求键再确认一次，找回已经登记的结果。"} />}
    </Modal>
  </section>;
}

function ComparisonSelection({ token, jobId, id, canEdit }: { token: string; jobId: number; id: number; canEdit: boolean }) {
  const [version, setVersion] = useState<number | null>(null);
  const [edit, setEdit] = useState<ComparisonEdit | null>(null);
  const client = useQueryClient();
  const key = ["agent-comparison", jobId, id, version] as const;
  const query = useQuery({
    queryKey: key, queryFn: ({ signal }) => getAgentComparison(token, jobId, id, version, signal),
    refetchInterval: ({ state }) => state.data?.status === "queued" || state.data?.status === "running" ? 3000 : false,
  });
  const comparison = query.data;
  function onSaved(curation: CurationSnapshot) {
    if (version !== null) {
      setVersion(null);
    } else {
      client.setQueryData<AgentComparison>(key, (old) => old && { ...old, curation, latest_curation_version: curation.version });
    }
    setEdit(null);
    void client.invalidateQueries({ queryKey: ["agent-comparison", jobId, id] });
  }
  if (query.isPending) return <Skeleton active paragraph={{ rows: 3 }} />;
  return <>
    {query.error && <Alert type="error" showIcon title={query.error.message}
      action={<Button size="small" onClick={() => void query.refetch()}>重试读取</Button>} />}
    {comparison && <ComparisonWorkspace comparison={comparison} canEdit={canEdit} onCurationVersion={setVersion} onEdit={setEdit} />}
    {comparison && edit && <ComparisonEditDialog token={token} jobId={jobId} comparison={comparison} initial={edit}
      onClose={() => setEdit(null)} onSaved={onSaved} />}
  </>;
}
