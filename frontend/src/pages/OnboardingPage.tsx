/** @description 按项目展示可完成的连接准备清单；仅轮询已保存事实，不自动调用模型或发送消息。 */
import { useQuery } from "@tanstack/react-query";
import { Alert, Progress, Select, Tag } from "antd";
import { useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import { getEffectiveConfiguration } from "../api/services/setup";
import type { ConnectionCheck, ModelConfiguration, Repository } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { ReadFeedback } from "../ui/ReadFeedback";
import { RouteButton } from "../ui/RouteButton";
import { formatTime } from "../ui/format";

/** 平台准备与项目连接分开；历史任务不冒充当前版本的端到端验收。 */
export function OnboardingPage({ token }: { /** 内存管理会话。 */ token: string }) {
  const [params, setParams] = useSearchParams();
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: ({ signal }) => apiRequest<Repository[]>(token, "/api/repositories", { signal }) });
  const models = useQuery({ queryKey: ["model-profiles"], queryFn: ({ signal }) => apiRequest<ModelConfiguration[]>(token, "/api/model-profiles", { signal }) });
  const checks = useQuery({ queryKey: ["connection-checks"], queryFn: ({ signal }) => apiRequest<ConnectionCheck[]>(token, "/api/connection-checks", { signal }), refetchInterval: 5000 });
  const requested = Number(params.get("repository"));
  const repo = repositories.data?.find((item) => item.id === requested) ?? repositories.data?.[0];
  const effective = useQuery({ queryKey: ["effective-configuration", repo?.id], queryFn: ({ signal }) => getEffectiveConfiguration(token, repo?.id ?? 0, signal), enabled: Boolean(repo) });
  const passed = (kind: ConnectionCheck["kind"], match: (check: ConnectionCheck) => boolean) => {
    const latest = checks.data?.filter((check) => check.kind === kind && match(check)).sort((a, b) => b.id - a.id).find((check) => check.kind === kind && match(check));
    return latest?.status === "passed" && latest.config_current === true;
  };
  const model = effective.data?.model;
  const notificationReady = repo && (!repo.has_feishu_webhook || passed("feishu", (check) => check.repository_id === repo.id || (repo.feishu_target_id != null && check.notification_target_id === repo.feishu_target_id)));
  const connection = (section: string) => repo ? `/repositories?repository=${repo.id}&section=${section}` : "/repositories";
  const steps = [
    { title: "保存项目接入", done: Boolean(repo), description: repo ? `${repo.name} · ${repo.target_branch}${repo.enabled ? " · 接收已启用" : " · 接收已暂停，启用后才会自动处理事件"}` : "添加仓库，可从 HTTPS 地址获取项目资料，也可手动填写。", to: connection("connection"), action: repo ? "核对基础接入与 Webhook" : "添加仓库" },
    { title: "验证当前评审模型", done: Boolean(model?.complete && passed("model", (check) => check.model_profile_id === model.id)), description: model ? `${model.source === "project" ? "项目指定" : "继承全局默认"}：${model.name ?? "未配置"}。测试可能产生费用，保存和默认切换不会自动测试。` : "选择全局默认或项目指定模型，保存后测试该目标。", to: model?.complete ? "/settings?tab=model" : connection("review"), action: "配置或测试模型" },
    { title: "验证 Git 与 GitLab API", done: Boolean(repo && passed("git", (check) => check.repository_id === repo.id) && passed("gitlab", (check) => check.repository_id === repo.id)), description: "只认可当前连接字段的最近测试；修改地址、分支或令牌后需重新验证。", to: connection("connection"), action: "测试项目连接" },
    { title: "通知按需配置", done: Boolean(notificationReady), description: repo?.has_feishu_webhook ? "此项目选择了通知，请明确测试已保存目标；会向真实群发送消息。" : "此项目未选择通知，允许跳过；以后可在基础接入中关联通道。", to: repo?.feishu_target_id != null ? "/settings?tab=feishu" : connection("diagnosis"), action: repo?.has_feishu_webhook ? "测试通知通道" : "按需关联通知" },
  ];
  const known = repositories.isSuccess && models.isSuccess && checks.isSuccess && (!repo || effective.isSuccess);
  const complete = steps.filter((step) => step.done).length;
  return <div className="page setup-migration">
    <PageHeader title="项目接入清单" subtitle="平台配置可复用，每个项目独立验证；新项目不会清零其他项目进度。" actions={<RouteButton to="/repositories">返回项目配置</RouteButton>} />
    <div className="setup-feedback"><ReadFeedback name="项目" loading={repositories.isPending} error={repositories.error} onRetry={() => void repositories.refetch()} /><ReadFeedback name="模型" loading={models.isPending} error={models.error} onRetry={() => void models.refetch()} /><ReadFeedback name="连接测试" loading={checks.isPending} error={checks.error} onRetry={() => void checks.refetch()} />{repo && <ReadFeedback name="生效配置" loading={effective.isPending} error={effective.error} onRetry={() => void effective.refetch()} />}</div>
    <div className="row-actions"><RouteButton to="/settings?tab=model">平台模型准备{models.isSuccess ? `（${models.data.length} 个已保存）` : ""}</RouteButton><RouteButton to="/settings?tab=feishu">可选通知通道</RouteButton><RouteButton to="/settings?tab=rules">共用评审规则</RouteButton></div>
    <label className="setup-project-select">当前项目<Select virtual={false} aria-label="当前项目" value={repo?.id} placeholder="请先添加仓库" options={repositories.data?.map((item) => ({ value: item.id, label: item.name }))} onChange={(value) => { const next = new URLSearchParams(params); next.set("repository", String(value)); setParams(next); }} /></label>
    <section className="setup-progress" aria-label="连接准备进度"><strong>{known ? `${complete} / ${steps.length}` : "待确认"}</strong><span> 当前项目连接准备；不代表真实评审已经完成</span><Progress percent={known ? complete / steps.length * 100 : 0} showInfo={false} /></section>
    <ol className="setup-steps">{steps.map((step) => <li key={step.title}><section className="section"><div className="setup-step-heading"><h2>{step.title}</h2><Tag color={known && step.done ? "success" : "default"}>{!known ? "待确认" : step.done ? "已具备" : "待完成"}</Tag></div><p>{step.description}</p><RouteButton to={step.to}>{step.action}</RouteButton></section></li>)}</ol>
    <section className="section"><h2>最后：真实试运行与验收</h2><p>在 GitLab 配置 Webhook 地址、事件和 Secret，然后明确提交一次符合条件的合并或提交；会触发模型费用及已选择的通知。这里只展示保存的事实，不自动执行试评审。</p>
      <p>历史接收：{repo?.last_webhook_at ? formatTime(repo.last_webhook_at) : "尚无记录"}。最近任务：{effective.data?.latest_job ? <RouteButton to={`/jobs/${effective.data.latest_job.id}`}>查看 #{effective.data.latest_job.id} · {effective.data.latest_job.status}</RouteButton> : "尚无记录"}。</p>
      <Alert type="info" showIcon title={known && complete === steps.length ? "连接准备已完成，请继续核对真实试运行" : "配置、测试和实际评审是不同证据"} description="历史接收或历史任务不证明当前配置已完成端到端验收；请在任务详情核对对应提交、执行快照、覆盖范围与独立通知状态。" />
    </section>
  </div>;
}
