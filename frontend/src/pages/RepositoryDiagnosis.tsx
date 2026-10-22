/** @description 项目接入诊断：组合已保存配置、验证结果与事件事实；打开页面不触发外部测试。 */
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { ModelConfiguration, NotificationTarget, Repository } from "../api/types";
import { ConnectionChecks } from "../ui/ConnectionChecks";
import { QueryState } from "../ui/QueryState";
import { formatTime } from "../ui/format";

interface Readiness { repository_id: number; status: string; git: string; gitlab: string }
interface EventRecord { id: number; mr_iid: number; status: string; error: string | null; job_count: number; latest_job_id: number | null; created_at: string }
const checkLabels: Record<string, string> = { passed: "最近测试成功", failed: "最近测试失败", queued: "测试排队中", running: "测试进行中", untested: "尚未测试" };
const eventLabels: Record<string, string> = { queued: "等待 Worker", processing: "处理中", done: "处理结束", needs_attention: "需要核查" };

/** 只展示当前已保存配置，草稿需先保存；各测试按钮由用户主动触发，服务端负责授权。 */
export function RepositoryDiagnosis({ token, repository, targets }: {
  /** 内存凭据。 */ token: string;
  /** 已保存项目，不含 Token。 */ repository: Repository;
  /** 已加载的通知目标，仅用于解释关联状态。 */ targets: NotificationTarget[];
}) {
  const readiness = useQuery({ queryKey: ["repository-readiness"], queryFn: () => apiRequest<Readiness[]>(token, "/api/repository-readiness"), refetchInterval: 10000 });
  const models = useQuery({ queryKey: ["model-profiles"], queryFn: () => apiRequest<ModelConfiguration[]>(token, "/api/model-profiles") });
  const limits = useQuery({ queryKey: ["project-limits", repository.id], queryFn: () => apiRequest<{ model_profile_id: number | null }>(token, `/api/repositories/${repository.id}/limits`) });
  const events = useQuery({ queryKey: ["repository-events", repository.id], queryFn: ({ signal }) => apiRequest<{ items: EventRecord[]; total: number }>(token, `/api/event-search?repository_id=${repository.id}&page_size=5`, { signal }), refetchInterval: 15000 });
  const state = readiness.data?.find((item) => item.repository_id === repository.id);
  const model = limits.data?.model_profile_id ? models.data?.find((item) => item.id === limits.data?.model_profile_id) : models.data?.find((item) => item.enabled);
  const target = targets.find((item) => item.id === repository.feishu_target_id);
  const error = readiness.error || models.error || limits.error || events.error;
  return <div className="repository-diagnosis">
    <p className="coverage-note">以下检查基于已保存配置。打开此页不会调用 GitLab、模型或飞书；测试会由独立 Worker 执行。</p>
    <QueryState loading={readiness.isLoading || models.isLoading || limits.isLoading || events.isLoading} error={error} onRetry={() => { void readiness.refetch(); void models.refetch(); void limits.refetch(); void events.refetch(); }} />
    <dl className="diagnosis-checklist">
      <div><dt>事件接收</dt><dd>{repository.enabled ? "已启用" : "已暂停"} · MR {repository.enable_merge_requests ? "开启" : "关闭"} · 默认分支 Push {repository.enable_default_branch_pushes ? "开启" : "关闭"}</dd></div>
      <div><dt>Git / GitLab API</dt><dd>{state ? `${checkLabels[state.git] ?? state.git} / ${checkLabels[state.gitlab] ?? state.gitlab}` : "读取中"}{state?.status === "needs_check" && <small>当前配置尚未完成验证；旧版本测试成功不代表当前配置有效。</small>}</dd></div>
      <div><dt>Webhook</dt><dd>{repository.last_webhook_at ? `最近通过验证：${formatTime(repository.last_webhook_at)}` : "尚无通过验证的回调记录"}<small>回调通过验证不代表一定生成任务；仍需符合事件类型、分支和去重条件。</small></dd></div>
      <div><dt>评审模型</dt><dd>{models.error || limits.error ? "状态读取失败" : models.isLoading || limits.isLoading ? "读取中" : model ? `${model.name} · ${limits.data?.model_profile_id ? "项目指定" : "继承全局"}` : "未找到可用模型"}<small>已配置不等于调用成功；项目模型覆盖在“评审参数”中修改。</small><Link to="/settings?tab=model">管理模型 →</Link></dd></div>
      <div><dt>飞书通知</dt><dd>{target?.name ?? (repository.has_feishu_webhook ? "使用项目独立通知配置" : "未关联通知配置")}<small>通知独立重试，失败时无需重新调用模型评审。</small><Link to="/settings?tab=feishu">管理通知 →</Link></dd></div>
    </dl>
    <ConnectionChecks token={token} kinds={["git", "gitlab"]} repositoryId={repository.id} />
    <section className="section diagnosis-events"><div className="section-head"><h3>最近接收事件</h3><Link to={`/jobs?repository_id=${repository.id}`}>查看项目任务 →</Link></div>
      {events.data?.items.map((event) => <article key={event.id}><strong>#{event.id} · {event.mr_iid > 0 ? `MR !${event.mr_iid}` : "默认分支 Push"}</strong><span>{eventLabels[event.status] ?? event.status} · {formatTime(event.created_at)}</span>{event.error && <p className="form-error">{event.error}</p>}{event.latest_job_id ? <Link to={`/jobs/${event.latest_job_id}`}>已生成 {event.job_count} 个任务，查看最新任务 →</Link> : <p>尚未生成任务。{event.status === "queued" || event.status === "processing" ? "请检查 Worker 是否运行并等待处理。" : "请核对事件处理原因、目标分支及重复提交；不要反复触发相同事件。"}</p>}</article>)}
      {!events.isLoading && !events.error && events.data?.total === 0 && <p className="empty-inline">尚无已入库事件。请在 GitLab 核对回调地址、Secret、事件勾选与目标分支；未收到回调和收到但被忽略是两种情况。</p>}
    </section>
  </div>;
}
