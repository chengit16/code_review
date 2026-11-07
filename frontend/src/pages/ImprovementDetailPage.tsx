/** @description 台账详情与逐次历史；编辑失败不破坏快照，部署状态始终单列。 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { archiveActionLabels, getImprovement, getImprovementHistory } from "../api/improvements";
import type { ImprovementRecord } from "../api/improvements";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { formatTime } from "../ui/format";
import { ImprovementArchiveControl } from "./ImprovementArchiveControl";
import { ImprovementEditor } from "./ImprovementEditor";
import { ImprovementFacts } from "./ImprovementFacts";
import { RelatedImprovementThemes } from "./RelatedImprovementThemes";

/** 当前摘要和历史独立查询；历史失败不妨碍阅读已有摘要。 */
export function ImprovementDetailPage({ token }: { /** 内存管理员会话。 */ token: string }) {
  const { id } = useParams();
  const recordId = Number(id);
  const [editing, setEditing] = useState<ImprovementRecord | null>(null);
  const [feedback, setFeedback] = useState("");
  const [historyPage, setHistoryPage] = useState(1);
  const client = useQueryClient();
  const valid = Number.isInteger(recordId) && recordId > 0;
  const detail = useQuery({ queryKey: ["improvement", recordId], queryFn: ({ signal }) => getImprovement(token, recordId, signal), enabled: valid });
  const history = useQuery({ queryKey: ["improvement-history", recordId, historyPage], queryFn: ({ signal }) => getImprovementHistory(token, recordId, historyPage, signal), enabled: valid && Boolean(detail.data) });
  return <div className="page">
    <Link to="/improvements">返回问题与改进</Link>
    <PageHeader title={detail.data?.title ?? "记录详情"} subtitle={detail.data ? `记录 #${recordId} · 版本 ${detail.data.version} · 更新于 ${formatTime(detail.data.updated_at)}` : "读取持久化记录"} actions={detail.data && !detail.data.archived_at && <button className="button button-primary" type="button" disabled={detail.isError} onClick={() => { setFeedback(""); setEditing(detail.data ?? null); }}>编辑并追加进展</button>} />
    {!valid ? <p className="form-error" role="alert">记录编号无效</p> : <QueryState loading={detail.isLoading} error={detail.error} onRetry={() => void detail.refetch()} />}
    {feedback && <p className="form-success" role="status">{feedback}</p>}
    {detail.data && <><ImprovementArchiveControl token={token} resource="records" record={detail.data} disabled={Boolean(editing) || detail.isError} onSaved={() => { setHistoryPage(1); setFeedback("归档状态已保存，完整历史和关联仍保留。"); }} /><section className="section" aria-label="当前记录"><h2>当前记录</h2><ImprovementFacts record={detail.data} /></section>
      <RelatedImprovementThemes token={token} recordId={recordId} />
      <section className="section" aria-label="处理与改进历史"><h2>处理与改进历史</h2><p className="muted">每次保存追加完整快照；不覆盖当时的排查结论、验证和部署证据。</p>
        <QueryState loading={history.isLoading} error={history.error} onRetry={() => void history.refetch()} />
        {history.data?.items.map((revision) => <details className="improvement-history-entry" key={revision.version}><summary>{archiveActionLabels[revision.action]} · 版本 {revision.version} · {revision.note} · {revision.actor} · {formatTime(revision.created_at)}</summary><h3>{revision.snapshot.title}</h3>{revision.archived_at && <p className="prewrap">当时已归档 · {revision.archived_by} · {formatTime(revision.archived_at)} · {revision.archive_reason}</p>}<ImprovementFacts record={revision.snapshot} /></details>)}
        {history.data && <div className="pagination"><span>共 {history.data.total} 次记录 · 第 {historyPage} 页</span><button className="button button-secondary" type="button" disabled={historyPage <= 1 || history.isFetching} onClick={() => setHistoryPage(historyPage - 1)}>上一页历史</button><button className="button button-secondary" type="button" disabled={historyPage * history.data.page_size >= history.data.total || history.isFetching} onClick={() => setHistoryPage(historyPage + 1)}>下一页历史</button></div>}
      </section></>}
    {editing && <ImprovementEditor key={editing.id} token={token} record={editing} onClose={() => setEditing(null)} onSaved={() => {
      setEditing(null); setFeedback("进展已保存，旧记录已保留在历史中。"); setHistoryPage(1);
      void client.invalidateQueries({ queryKey: ["improvement", recordId] });
      void client.invalidateQueries({ queryKey: ["improvement-history", recordId] });
      void client.invalidateQueries({ queryKey: ["improvements"] });
    }} />}
  </div>;
}
