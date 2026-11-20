/** @description 展示运行所用能力、执行状态与有限的固定证据。 */

import { Collapse, Descriptions, Space, Table, Tag } from "antd";

import { agentNodeLabels } from "../../api/agentCapabilities";
import type { AgentCapabilityEvent } from "../../api/agentCapabilities";
import type { AgentComparison } from "../../api/agentComparisons";
import { formatTime, shortSha } from "../../ui/format";

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

/** 比较配置、命中和实际执行，旧数据保持缺失含义。 */
export function CapabilityEvidence({ agent }: { agent: AgentComparison["agent"] }) {
  const settings = agent.capabilities;
  const events = agent.capability_events ?? [];
  if (!settings) return <p className="agent-comparison-reason">历史运行未记录能力配置</p>;
  return <Collapse size="small" ghost items={[{ key: "capability", label: "查看本次 Agent 配置与执行", children: <>
    <Descriptions size="small" column={1} items={[
      { key: "scheme", label: "评审方案", children: <Space wrap>#{settings.scheme_id} · {settings.name}
        {settings.trial && <Tag color="orange">试跑</Tag>}</Space> },
      { key: "model", label: "模型档案", children: settings.model_profile_id
        ? `#${settings.model_profile_id} · 版本 ${settings.model_profile_version}` : "服务配置" },
      { key: "steps", label: "已配置步骤", children: ["读取差异", ...settings.steps.map((step) => agentNodeLabels[step]),
        "评审与证据校验", "保存结果"].join(" → ") },
      { key: "skill", label: "已选 Skill", children: settings.skills.join("、") || "未配置" },
      { key: "mcp", label: "已选 MCP", children: settings.mcp ?? "未配置" },
    ]} />
    {events.length > 0 && <Table size="small" rowKey="id" dataSource={events} pagination={{ pageSize: 10 }}
      scroll={{ x: 520 }} expandable={{ expandedRowRender: (event) => <CapabilityEventDetails event={event} />,
        rowExpandable: (event) => event.evidence !== null }} columns={[
        { title: "能力", render: (_, event) => labels[event.step] ?? event.step },
        { title: "来源", dataIndex: "source" },
        { title: "处理文件", render: (_, event) => event.path || "整次运行" },
        { title: "实际状态", render: (_, event) => statuses[event.status] ?? event.status },
      ]} />}
    {!!agent.workflow_steps?.length && <Collapse size="small" ghost items={[{
      key: "timeline", label: "查看执行时间线",
      children: <ol>{agent.workflow_steps.map((step, index) => <li key={`${index}:${step}`}>{step}</li>)}</ol>,
    }]} />}
  </> }]} />;
}
