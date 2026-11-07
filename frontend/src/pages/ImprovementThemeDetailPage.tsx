/** @description 优化主题当前历程和逐版快照，按主题内有序阶段展示结果与证据。 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { archiveActionLabels, getImprovementTheme, getImprovementThemeHistory } from "../api/improvements";
import type { ImprovementThemeContent, ImprovementThemeRecord } from "../api/improvements";
import { PageHeader } from "../ui/PageHeader";
import { Pagination } from "../ui/Pagination";
import { QueryState } from "../ui/QueryState";
import { formatTime } from "../ui/format";
import { ImprovementArchiveControl } from "./ImprovementArchiveControl";
import { ImprovementThemeEditor } from "./ImprovementThemeEditor";
import { categoryLabels, codeLabels, deploymentLabels, verificationLabels } from "./improvementFields";

const statuses = { planned: "待开始", active: "进行中", paused: "已暂停", completed: "已完成", deferred: "暂缓" };
const phaseStatuses = { planned: "待开始", active: "进行中", completed: "已完成", deferred: "暂缓" };

function ThemeFacts({ theme }: { /** 当前摘要或历史完整快照。 */ theme: ImprovementThemeContent }) {
  return <div className="theme-facts"><p>{categoryLabels[theme.category]} · {statuses[theme.status]} · {theme.scope}</p>
    <h3>总体目标</h3><p className="prewrap">{theme.objective}</p>
    <h3>背景与原因</h3><p className="prewrap">{theme.rationale || "尚未记录"}</p>
    <h3>整体结果</h3><p className="prewrap">{theme.outcome || "尚未记录"}</p>
    <ol className="theme-phase-list detailed">{theme.phases.map((phase, index) => <li className="theme-phase-fact" key={`${phase.title}-${index}`}>
      <div className="theme-phase-heading"><h3>阶段 {index + 1}：{phase.title}</h3><span className="status">{phaseStatuses[phase.status]}</span></div>
      <h4>阶段目标</h4><p className="prewrap">{phase.goal}</p><h4>处理办法</h4><p className="prewrap">{phase.solution || "尚未记录"}</p>
      <dl className="improvement-states"><div><dt>代码修改</dt><dd>{codeLabels[phase.code_state]}</dd></div><div><dt>本地验证</dt><dd>{verificationLabels[phase.verification_state]}</dd></div><div><dt>部署生效</dt><dd>{deploymentLabels[phase.deployment_state]}</dd></div></dl>
      <h4>验证证据</h4><p className="prewrap">{phase.validation_evidence || "尚未记录"}</p><h4>部署证据</h4><p className="prewrap">{phase.deployment_evidence || "尚未记录"}</p><h4>阶段遗留</h4><p className="prewrap">{phase.next_steps || "无"}</p>
    </li>)}</ol>
    <h3>遗留与下一步</h3><p className="prewrap">{theme.next_steps || "尚未记录"}</p>
    <h3>关联文档与证据</h3><p className="prewrap">{theme.references || "尚未记录"}</p>
  </div>;
}

/** 问题记录通过独立关系表关联；打开问题不改变其状态。 */
export function ImprovementThemeDetailPage({ token }: { /** 管理员内存会话。 */ token: string }) {
  const { id } = useParams();
  const themeId = Number(id);
  const [editing, setEditing] = useState<ImprovementThemeRecord | null>(null);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyPageSize, setHistoryPageSize] = useState(25);
  const [feedback, setFeedback] = useState("");
  const client = useQueryClient();
  const valid = Number.isInteger(themeId) && themeId > 0;
  const theme = useQuery({ queryKey: ["improvement-theme", themeId], queryFn: ({ signal }) => getImprovementTheme(token, themeId, signal), enabled: valid });
  const history = useQuery({ queryKey: ["improvement-theme-history", themeId, historyPage, historyPageSize], queryFn: ({ signal }) => getImprovementThemeHistory(token, themeId, historyPage, signal, historyPageSize), enabled: valid && Boolean(theme.data) });
  return <div className="page"><Link to="/improvements?view=themes">返回优化历程</Link>
    <PageHeader title={theme.data?.title ?? "优化主题"} subtitle={theme.data ? `主题 #${themeId} · 版本 ${theme.data.version} · 更新于 ${formatTime(theme.data.updated_at)}` : "读取持久化主题"} actions={theme.data && !theme.data.archived_at && <button className="button button-primary" type="button" disabled={theme.isError} onClick={() => { setFeedback(""); setEditing(theme.data ?? null); }}>编辑主题与阶段</button>} />
    {!valid ? <p className="form-error" role="alert">主题编号无效</p> : <QueryState loading={theme.isLoading} error={theme.error} onRetry={() => void theme.refetch()} />}
    {feedback && <p className="form-success" role="status">{feedback}</p>}
    {theme.data && <><ImprovementArchiveControl token={token} resource="themes" record={theme.data} disabled={Boolean(editing) || theme.isError} onSaved={() => { setHistoryPage(1); setFeedback("归档状态已保存，完整历史和关联仍保留。"); }} /><section className="section" aria-label="当前优化主题"><ThemeFacts theme={theme.data} /></section>
      <section className="section" aria-label="关联问题记录"><h2>关联问题记录（{theme.data.improvement_ids.length}）</h2>{theme.data.improvement_ids.length ? <ul className="theme-linked-issues">{theme.data.improvement_ids.map((issueId) => <li key={issueId}><Link to={`/improvements/${issueId}`}>查看问题记录 #{issueId}</Link></li>)}</ul> : <p className="muted">尚未关联问题记录</p>}</section>
      <section className="section" aria-label="优化历史"><h2>优化历史</h2><p className="muted">每次保存保留完整阶段快照和当时问题关联。</p><QueryState loading={history.isLoading} error={history.error} onRetry={() => void history.refetch()} />
        {history.data?.items.map((revision) => <details className="improvement-history-entry" key={revision.version}><summary>{archiveActionLabels[revision.action]} · 版本 {revision.version} · {revision.note} · {revision.actor} · {formatTime(revision.created_at)}</summary>{revision.archived_at && <p className="prewrap">当时已归档 · {revision.archived_by} · {formatTime(revision.archived_at)} · {revision.archive_reason}</p>}<ThemeFacts theme={revision.snapshot} /><p>当时关联问题：{revision.improvement_ids.length ? revision.improvement_ids.map((issueId) => `#${issueId}`).join("、") : "无"}</p></details>)}
        {history.data && <Pagination label="主题历史分页" total={history.data.total} page={historyPage} pageSize={historyPageSize} disabled={history.isFetching} onPage={setHistoryPage} onPageSize={(size) => { setHistoryPageSize(size); setHistoryPage(1); }} />}
      </section></>}
    {editing && <ImprovementThemeEditor key={editing.id} token={token} record={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); setHistoryPage(1); setFeedback("主题、阶段和问题关联已保存，旧版本已留存。"); void client.invalidateQueries({ queryKey: ["improvement-theme", themeId] }); void client.invalidateQueries({ queryKey: ["improvement-theme-history", themeId] }); void client.invalidateQueries({ queryKey: ["improvement-themes"] }); }} />}
  </div>;
}
