/** @description 以只读抽屉展示本次运行的配置、阶段、动作及固定证据。 */

import { Button, Card, Collapse, Descriptions, Drawer, Pagination, Segmented, Space, Tabs, Tag, Timeline } from "antd";
import { ListTree } from "lucide-react";
import { useState } from "react";

import { agentNodeLabels } from "../../api/agentCapabilities";
import type { AgentCapabilityEvent } from "../../api/agentCapabilities";
import type { AgentComparison } from "../../api/agentComparisons";
import { Status } from "../../ui/Status";
import { formatTime, shortSha } from "../../ui/format";
import { FindingCodeBlock } from "../FindingCodeBlock";
import { AgentWorkflow } from "./AgentWorkflow";

const statuses: Record<string, string> = {
  matched: "命中", skipped: "未命中", complete: "已获取", used: "已提供给本页",
  started: "调用已登记", failed: "失败",
};
const labels: Record<string, string> = { skill: "Skill", read_file: "补查文件", mcp: "MCP" };

/** 运行明细和单条发现统一使用已记录的能力状态。 */
export function capabilityStatusText(status: string): string {
  return statuses[status] ?? status;
}

function CapabilityEventDetails({ event }: { event: AgentCapabilityEvent }) {
  const proof = event.evidence;
  return <div className="agent-evidence">
    {proof?.path && <p>{proof.path}{proof.line != null && ` · 第 ${proof.line} 行`}
      {proof.commit && <span title={proof.commit}> · {shortSha(proof.commit)}</span>}</p>}
    {proof?.document && <p>{proof.document} · {proof.version ? `版本 ${proof.version}` : formatTime(event.created_at)}</p>}
    {proof?.message && <p>{proof.message}</p>}
    {proof?.excerpt && <FindingCodeBlock content={proof.excerpt} language="" caption={proof.document ? "文档摘录" : "代码摘录"} />}
    {proof?.sha256 && <p title={proof.sha256}>证据摘要 {proof.sha256.slice(0, 12)}</p>}
  </div>;
}

function AgentRunStatus({ comparison, coverage }: {
  comparison: AgentComparison;
  coverage: { reviewed: number; total: number } | undefined;
}) {
  const { status, created_at: createdAt, finished_at: finishedAt } = comparison;
  const active = status === "queued" || status === "running";
  const reviewDescription = coverage?.total
    ? `${coverage.reviewed.toLocaleString("zh-CN")} / ${coverage.total.toLocaleString("zh-CN")} 条差异已核对`
    : status === "queued" ? "等待 Worker 领取"
    : status === "running" ? "正在准备评审输入"
    : status === "skipped" ? "无可评审的文本差异" : "暂无可核对的覆盖记录";
  return <Timeline className="agent-run-timeline" styles={{ item: { minHeight: 38 } }} items={[
    { key: "queued", color: "green", content: <div className="agent-run-milestone">
      <strong>任务登记</strong><span>{formatTime(createdAt)}</span>
    </div> },
    { key: "review", color: status === "running" ? "blue" : status === "complete" ? "green" : "gray",
      loading: status === "running", content: <div className="agent-run-milestone">
        <strong>差异评审</strong><span>{reviewDescription}</span>
      </div> },
    { key: "result", color: active ? "gray" : status === "complete" ? "green" : status === "failed" ? "red" : "gray",
      content: <div className="agent-run-milestone">
        <strong>{active ? "等待结果" : "运行结束"}</strong>
        {!active && <><Status value={status} />{finishedAt && <span>{formatTime(finishedAt)}</span>}</>}
      </div> },
  ]} />;
}

function CapabilityEvents({ events }: { events: AgentCapabilityEvent[] }) {
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<"all" | "excerpt">("all");
  const pageSize = 8;
  const withExcerpt = events.filter((event) => event.evidence?.excerpt);
  const filtered = filter === "excerpt" && withExcerpt.length ? withExcerpt : events;
  const current = Math.min(page, Math.max(1, Math.ceil(filtered.length / pageSize)));
  const visible = filtered.slice((current - 1) * pageSize, current * pageSize);
  return <>
    {withExcerpt.length > 0 && <Segmented<"all" | "excerpt"> className="agent-run-event-filter" size="small" aria-label="筛选能力证据"
      value={filter} onChange={(value) => { setFilter(value); setPage(1); }}
      options={[{ value: "all", label: "全部记录" }, { value: "excerpt", label: `有摘录（${withExcerpt.length}）` }]} />}
    <ul className="agent-run-events">{visible.map((event) => {
      const summary = <div className="agent-run-event">
        <div><Tag>{labels[event.step] ?? event.step}</Tag><span>{capabilityStatusText(event.status)} · #{event.id}</span></div>
        <strong>{event.source}</strong>
        {event.path && event.path !== event.evidence?.path && <small>处理文件 {event.path}</small>}
      </div>;
      return <li key={event.id}>{event.evidence ? <Collapse size="small" ghost destroyOnHidden
        items={[{ key: event.id, label: summary, children: <CapabilityEventDetails event={event} /> }]} /> : summary}</li>;
    })}</ul>
    {filtered.length > pageSize && <Pagination size="small" current={current} pageSize={pageSize} total={filtered.length}
      showSizeChanger={false} onChange={setPage} />}
  </>;
}

/** 保留历史比较语义，同一次运行轮询时原位刷新抽屉。 */
export function CapabilityEvidence({ comparison, coverage }: {
  /** 双评审当前选择的固定运行版本。 */ comparison: AgentComparison;
  /** 已知覆盖范围，未冻结差异时为空。 */ coverage: { reviewed: number; total: number } | undefined;
}) {
  const [open, setOpen] = useState(false);
  const { agent, status, id } = comparison;
  const settings = agent.capabilities;
  const events = agent.capability_events ?? [];
  return <>
    <Button className="agent-run-trigger" size="small" type="link" aria-label="查看 Agent 运行详情"
      icon={<ListTree size={14} aria-hidden />} onClick={() => setOpen(true)}>
      运行详情
    </Button>
    <Drawer title="Agent 运行详情" open={open} destroyOnHidden onClose={() => setOpen(false)}
      size="min(720px, 100vw)" rootClassName="agent-run-drawer">
      <div className="agent-run-detail">
        <Card size="small" className="agent-run-summary">
          <div className="agent-run-summary-top">
            <Space size={6} wrap><Tag>Agent #{id}</Tag>{settings?.trial && <Tag color="warning">试跑</Tag>}</Space>
            <Status value={status} />
          </div>
          {settings && <h3>{settings.name}</h3>}
          <div className="agent-run-summary-facts">
            {settings && <span>方案 #{settings.scheme_id}</span>}
            <span>OCR 初审第 {comparison.source_attempt} 次</span>
            {agent.usage.model && <span>{agent.usage.model}</span>}
          </div>
          {settings ? <Collapse size="small" ghost className="agent-run-config" items={[{
            key: "config", label: "评审配置", children: <Descriptions layout="vertical" size="small" column={1} items={[
              { key: "model", label: "模型档案", children: settings.model_profile_id
                ? `#${settings.model_profile_id} · 版本 ${settings.model_profile_version}` : "服务配置" },
              { key: "steps", label: "已配置步骤", children: ["读取差异", ...settings.steps.map((step) => agentNodeLabels[step]),
                "评审与证据校验", "保存结果"].join(" → ") },
              { key: "skill", label: "已选 Skill", children: settings.skills.join("、") || "未配置" },
              { key: "mcp", label: "已选 MCP", children: settings.mcp ?? "未配置" },
            ]} />,
          }]} /> : <p className="agent-run-note">历史运行未记录能力配置</p>}
        </Card>
        <section>
          <h3 className="agent-run-section-title">任务状态</h3>
          <AgentRunStatus comparison={comparison} coverage={coverage} />
        </section>
        <Tabs size="small" items={[
          { key: "workflow", label: "工作流程", children: <AgentWorkflow steps={agent.workflow_steps ?? []} status={status} /> },
          ...(events.length > 0 ? [{ key: "evidence", label: `能力证据（${events.length}）`, children: <CapabilityEvents events={events} /> }] : []),
        ]} />
      </div>
    </Drawer>
  </>;
}
