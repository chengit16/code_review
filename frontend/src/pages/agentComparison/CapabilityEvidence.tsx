/** @description 以只读抽屉展示本次运行的配置、阶段、动作及固定证据。 */

import { Button, Card, Collapse, Descriptions, Drawer, Space, Table, Tag, Timeline } from "antd";
import { ListTree } from "lucide-react";
import { useState } from "react";

import { agentNodeLabels } from "../../api/agentCapabilities";
import type { AgentCapabilityEvent } from "../../api/agentCapabilities";
import type { AgentComparison } from "../../api/agentComparisons";
import { Status } from "../../ui/Status";
import { formatTime, shortSha } from "../../ui/format";
import { AgentWorkflow } from "./AgentWorkflow";

const statuses: Record<string, string> = {
  matched: "命中", skipped: "未命中", complete: "已获取", used: "已提供给本页",
  started: "调用已登记", failed: "失败",
};
const labels: Record<string, string> = { skill: "Skill", read_file: "补查文件", mcp: "MCP" };

/** 引用只显示 Worker 持久化的证据位置和摘录。 */
export function CapabilityEventDetails({ event }: { event: AgentCapabilityEvent }) {
  const proof = event.evidence;
  return <div className="agent-evidence">
    <p><strong>{event.source}</strong> · {statuses[event.status] ?? event.status} · 证据 #{event.id}</p>
    {proof?.path && <p>{proof.path} · 第 {proof.line} 行 · {shortSha(proof.commit ?? "")}</p>}
    {proof?.document && <p>{proof.document} · {proof.version ? `版本 ${proof.version}` : formatTime(event.created_at)}</p>}
    {proof?.message && <p>{proof.message}</p>}
    {proof?.excerpt && <pre>{proof.excerpt}</pre>}
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
  return <Table size="small" rowKey="id" dataSource={events} pagination={{ pageSize: 10, showSizeChanger: false }}
      scroll={{ x: 520 }} expandable={{ expandedRowRender: (event) => <CapabilityEventDetails event={event} />,
        rowExpandable: (event) => event.evidence !== null }} columns={[
        { title: "能力", render: (_, event) => labels[event.step] ?? event.step },
        { title: "来源", dataIndex: "source" },
        { title: "处理文件", render: (_, event) => event.path || "整次运行" },
        { title: "实际状态", render: (_, event) => statuses[event.status] ?? event.status },
      ]} />;
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
  if (!settings) return <p className="agent-comparison-reason">历史运行未记录能力配置</p>;

  return <>
    <Button className="agent-run-trigger" icon={<ListTree size={16} aria-hidden />} onClick={() => setOpen(true)}>
      查看本次 Agent 配置与执行
    </Button>
    <Drawer title="Agent 运行详情" open={open} destroyOnHidden onClose={() => setOpen(false)}
      size="min(720px, 100vw)" rootClassName="agent-run-drawer">
      <div className="agent-run-detail">
        <Card size="small" className="agent-run-summary">
          <div className="agent-run-summary-top">
            <Space size={6} wrap><Tag>Agent #{id}</Tag>{settings.trial && <Tag color="warning">试跑</Tag>}</Space>
            <Status value={status} />
          </div>
          <h3>{settings.name}</h3>
          <div className="agent-run-summary-facts">
            <span>方案 #{settings.scheme_id}</span>
            <span>OCR 初审第 {comparison.source_attempt} 次</span>
            {agent.usage.model && <span>{agent.usage.model}</span>}
          </div>
          <Collapse size="small" ghost className="agent-run-config" items={[{
            key: "config", label: "评审配置", children: <Descriptions size="small" column={1} items={[
              { key: "model", label: "模型档案", children: settings.model_profile_id
                ? `#${settings.model_profile_id} · 版本 ${settings.model_profile_version}` : "服务配置" },
              { key: "steps", label: "已配置步骤", children: ["读取差异", ...settings.steps.map((step) => agentNodeLabels[step]),
                "评审与证据校验", "保存结果"].join(" → ") },
              { key: "skill", label: "已选 Skill", children: settings.skills.join("、") || "未配置" },
              { key: "mcp", label: "已选 MCP", children: settings.mcp ?? "未配置" },
            ]} />,
          }]} />
        </Card>
        <section>
          <h3 className="agent-run-section-title">任务状态</h3>
          <AgentRunStatus comparison={comparison} coverage={coverage} />
        </section>
        {events.length > 0 && <Collapse size="small" destroyOnHidden items={[{
          key: "evidence", label: `能力证据 · ${events.length} 条`, children: <CapabilityEvents events={events} />,
        }]} />}
        <section>
          <h3 className="agent-run-section-title">工作流程</h3>
          <AgentWorkflow steps={agent.workflow_steps ?? []} status={status} />
        </section>
      </div>
    </Drawer>
  </>;
}
