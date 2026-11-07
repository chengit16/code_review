/** @description 根据已保存配置与接收事实展示接入清单；不自动测试外部连接、不推断当前配置已验证。 */
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Progress, Tag } from "antd";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { ConnectionCheck, ModelConfiguration, NotificationTarget, Repository } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { ReadFeedback } from "../ui/ReadFeedback";

/** 首次接入可随时离开，未知状态不计作未配置或已完成；密钥仍由各管理页维护。 */
export function OnboardingPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const models = useQuery({ queryKey: ["model-profiles"], queryFn: ({ signal }) => apiRequest<ModelConfiguration[]>(token, "/api/model-profiles", { signal }) });
  const targets = useQuery({ queryKey: ["notification-targets"], queryFn: ({ signal }) => apiRequest<NotificationTarget[]>(token, "/api/notification-targets", { signal }) });
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: ({ signal }) => apiRequest<Repository[]>(token, "/api/repositories", { signal }) });
  // 只读轮询观察 Worker 测试结果，打开引导不发起外部调用。
  const checks = useQuery({ queryKey: ["connection-checks"], queryFn: ({ signal }) => apiRequest<ConnectionCheck[]>(token, "/api/connection-checks", { signal }), refetchInterval: 5000 });
  const queries = [{ name: "模型", query: models }, { name: "通知通道", query: targets }, { name: "仓库", query: repositories }, { name: "连接测试", query: checks }];
  const repos = repositories.data ?? [];
  const activeRepos = repos.filter((repo) => repo.enabled);
  const modelReady = models.isSuccess && Boolean(models.data.some((model) => model.enabled));
  const targetReady = targets.isSuccess && targets.data.length > 0;
  const repositoryReady = repositories.isSuccess && repos.length > 0;
  // 地址生成不是外部配置证据；接收记录也不代表当前版本已完成端到端验证。
  const received = repositories.isSuccess && activeRepos.length > 0 && activeRepos.every((repo) => Boolean(repo.last_webhook_at));
  const latest = (kind: ConnectionCheck["kind"], repositoryId: number | null) => checks.data
    ?.filter((check) => check.kind === kind && check.repository_id === repositoryId).sort((a, b) => b.id - a.id)[0];
  const latestChecks = [latest("model", null), ...activeRepos.flatMap((repo) => [latest("git", repo.id), latest("gitlab", repo.id), latest("feishu", repo.id)])];
  const recentPassed = checks.isSuccess && activeRepos.length > 0 && latestChecks.every((check) => check?.status === "passed");
  const known = queries.every(({ query }) => query.isSuccess);
  const complete = [modelReady, targetReady, repositoryReady, received].filter(Boolean).length;
  const steps = [
    { title: "配置评审模型", description: "保存并启用评审模型。配置存在不代表调用成功。", to: "/settings?tab=model", label: "前往模型设置", query: models, done: modelReady },
    { title: "配置飞书通知", description: "保存通知通道；发送测试需要在配置页明确操作。", to: "/settings?tab=feishu", label: "前往飞书设置", query: targets, done: targetReady },
    { title: "接入 GitLab 仓库", description: "维护访问凭据、目标分支和通知通道。", to: "/repositories", label: "前往项目配置", query: repositories, done: repositoryReady },
    { title: "配置 GitLab Webhook", description: received ? "启用仓库均有历史接收记录；不代表当前配置或评审链路已验证。" : "复制地址并在 GitLab 配置事件与 Secret；只有地址不能确认已接通。", to: "/repositories", label: "查看 Webhook 配置", query: repositories, done: received },
    { title: "验证连接", description: recentPassed ? "各目标最近测试记录通过；模型和飞书测试未绑定当前配置版本，仍需核实并完成一次端到端验证。" : "按目标查看最新测试。历史通过不能覆盖后续失败、排队或运行记录。", to: "/repositories", label: "查看连接测试", query: checks, done: false },
  ];
  return <div className="page setup-migration">
    <PageHeader title="首次接入引导" subtitle="先完成配置，再核对连接与实际评审；未知不等于未配置。" actions={<Link to="/" className="ant-btn ant-btn-default">稍后再做</Link>} />
    <Card size="small" className="setup-progress" aria-label="接入进度">
      {known ? <><strong>{complete} / 5</strong><span> 项已有配置或接收证据，最终连接仍需核实</span><Progress percent={complete * 20} showInfo={false} aria-label="接入完成进度" /></>
        : <p role="status">接入进度待确认：部分状态仍在读取或读取失败。</p>}
    </Card>
    <div className="setup-feedback">{queries.map(({ name, query }) => <ReadFeedback key={name} name={name} loading={query.isPending} error={query.error} onRetry={() => void query.refetch()} />)}</div>
    <ol className="setup-steps">{steps.map((step, index) => <li key={step.title}><Card size="small">
      <div className="setup-step-heading"><h2><span>{String(index + 1).padStart(2, "0")}</span>{step.title}</h2>
        <Tag color={step.query.isSuccess && step.done ? "success" : "default"}>{!step.query.isSuccess ? "状态待确认" : step.done ? index === 3 ? "有接收记录" : "已配置" : index === 4 ? "待核实" : "待完成"}</Tag></div>
      <p>{step.description}</p><Button href={step.to}>{step.label}</Button>
    </Card></li>)}</ol>
    <Alert type="info" showIcon title="配置、连接测试与真实评审是三类证据" description="这里不会自动调用模型、GitLab 或飞书；测试记录不证明所有当前配置已验证，也不代替端到端验收。" />
  </div>;
}
