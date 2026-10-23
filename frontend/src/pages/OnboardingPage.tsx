/** @description 汇总首次接入清单；配置仍由各自管理页和服务端持久化。 */

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Check, Circle, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { ConnectionCheck, ModelConfiguration, NotificationTarget, Repository } from "../api/types";
import { PageHeader } from "../ui/PageHeader";

const steps = [
  { id: "model", title: "配置评审模型", description: "添加模型并启用，连接测试通过后即可用于评审。", to: "/settings?tab=model", label: "前往模型设置" },
  { id: "feishu", title: "配置飞书通知", description: "保存群机器人地址，并发送一次连接测试。", to: "/settings?tab=feishu", label: "前往飞书设置" },
  { id: "repository", title: "接入 GitLab 仓库", description: "保存仓库访问凭据、目标分支和通知通道。", to: "/repositories", label: "前往项目配置" },
  { id: "webhook", title: "配置 GitLab Webhook", description: "将项目页面生成的回调地址和 Secret 配置到 GitLab。", to: "/repositories", label: "查看 Webhook 配置" },
  { id: "verify", title: "验证连接", description: "确认模型、飞书及仓库 Git / GitLab 测试均通过。", to: "/repositories", label: "查看连接测试" },
] as const;

/** 首次接入提示可随时离开；每次打开都根据服务端事实重算进度。 */
export function OnboardingPage({ token }: { token: string }) {
  const models = useQuery({ queryKey: ["model-profiles"], queryFn: () => apiRequest<ModelConfiguration[]>(token, "/api/model-profiles") });
  const targets = useQuery({ queryKey: ["notification-targets"], queryFn: () => apiRequest<NotificationTarget[]>(token, "/api/notification-targets") });
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  const checks = useQuery({ queryKey: ["connection-checks"], queryFn: () => apiRequest<ConnectionCheck[]>(token, "/api/connection-checks"), refetchInterval: 5000 });
  const activeModel = models.data?.some((model) => Boolean(model.enabled));
  const hasTarget = Boolean(targets.data?.length);
  const repos = repositories.data ?? [];
  const recent = checks.data ?? [];
  const passed = (kind: ConnectionCheck["kind"], repositoryId?: number) => recent.some((check) => check.kind === kind && check.status === "passed" && (repositoryId === undefined || check.repository_id === repositoryId));
  const webhookReady = repos.some((repo) => Boolean(repo.webhook_url) && repo.enabled);
  const statuses = [Boolean(activeModel), hasTarget, repos.length > 0, webhookReady, Boolean(activeModel && passed("model") && passed("feishu") && repos.length && repos.every((repo) => passed("git", repo.id) && passed("gitlab", repo.id)))];
  const complete = statuses.filter(Boolean).length;
  const loading = models.isLoading || targets.isLoading || repositories.isLoading || checks.isLoading;

  return <div className="page onboarding-page">
    <PageHeader title="首次接入引导" subtitle="按清单完成配置；可随时退出，回来后会从已完成的位置继续。" actions={<Link className="button button-secondary" to="/">稍后再做</Link>} />
    <section className="onboarding-progress" aria-label="接入进度">
      <div><strong>{complete} / {steps.length}</strong><span>项已完成</span></div>
      <progress value={complete} max={steps.length} aria-label="接入完成进度" />
    </section>
    {loading && <p className="query-state" role="status">正在读取接入状态…</p>}
    {(models.error || targets.error || repositories.error || checks.error) && <p className="form-error" role="alert">{(models.error || targets.error || repositories.error || checks.error)?.message}</p>}
    <ol className="onboarding-steps">
      {steps.map((step, index) => <li key={step.id} className={statuses[index] ? "is-complete" : ""}>
        <span className="onboarding-step-icon" aria-hidden="true">{statuses[index] ? <Check size={18} /> : <Circle size={18} />}</span>
        <div className="onboarding-step-copy"><h2>{step.title}</h2><p>{step.description}</p>{step.id === "model" && activeModel && <small>已有启用模型</small>}{step.id === "feishu" && hasTarget && <small>已配置 {targets.data?.length} 个通知通道</small>}{step.id === "repository" && repos.length > 0 && <small>已接入 {repos.length} 个仓库</small>}{step.id === "webhook" && webhookReady && <small>已生成回调地址，请在 GitLab 中确认事件订阅</small>}{step.id === "verify" && statuses[index] && <small>最近连接测试均已通过</small>}</div>
        <Link className="button button-secondary onboarding-action" to={step.to}>{step.label}<ArrowRight size={16} /></Link>
      </li>)}
    </ol>
    {complete === steps.length && <p className="form-success" role="status">接入清单已完成。建议先使用测试仓库完成一次端到端验证。</p>}
    <p className="onboarding-note"><ExternalLink size={15} />接入状态以服务端已保存配置和最近连接测试为准，不会在浏览器中保存密钥或配置草稿。</p>
  </div>;
}
