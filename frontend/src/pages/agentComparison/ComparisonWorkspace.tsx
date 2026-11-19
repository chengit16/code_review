/** @description 展示固定范围下的双路证据、覆盖与人工裁定，保留各自的覆盖口径。 */

import { App, Button, Card, Collapse, Drawer, Empty, Segmented, Space, Tag, Typography } from "antd";
import { useState } from "react";

import type { AgentComparison, ComparisonFinding, ComparisonUsage, Evaluation, FindingMatch } from "../../api/agentComparisons";
import { createCommandId } from "../../api/commandId";
import { Status } from "../../ui/Status";
import { formatTime, shortSha } from "../../ui/format";

import { FindingDescription } from "../FindingDescription";
import { evaluateFinding, verdictLabels } from "./comparisonEdits";
import type { ComparisonEdit } from "./comparisonEdits";

const reasonLabels: Record<string, string> = {
  read_budget: "达到读取页数限制", model_budget: "达到模型预算限制", model_timeout: "模型响应超时",
  model_response: "模型响应未通过校验", model_unavailable: "模型网关不可用", input_unavailable: "固定 Git 输入不可用",
  input_changed: "固定差异快照不一致", source_changed: "初审来源已变化", mr_version_changed: "MR 版本已变化",
  model_config_changed: "模型配置已更新", model_config_invalid: "模型配置无效", not_enabled: "已关闭 Agent",
  interrupted: "运行中断", cancelled: "已取消", no_text_diff: "没有文本差异",
};

function FindingLocation({ finding }: { finding: Pick<ComparisonFinding, "side" | "path" | "line"> }) {
  return <span className="agent-comparison-location">
    {finding.path}{finding.line === null ? " · 文件级" : ` · ${finding.side === "base" ? "旧版" : finding.side === "head" ? "新版" : "记录"}第 ${finding.line} 行`}
  </span>;
}

function Usage({ usage }: { usage: ComparisonUsage }) {
  return <div className="agent-usage">
    {usage.model && <span>{usage.model}</span>}
    <span>{usage.input_tokens !== null && usage.output_tokens !== null
      ? `输入 ${usage.input_tokens.toLocaleString()} · 输出 ${usage.output_tokens.toLocaleString()} Token` : "用量未记录"}</span>
    {usage.unknown_calls > 0 && <Tag color="warning">{usage.unknown_calls} 次用量未知</Tag>}
    <span>{usage.cost === null ? "费用未知" : `估算费用 ${usage.currency ?? ""} ${usage.cost}`}</span>
  </div>;
}

function EvidenceRows({ items, evaluations, onEvidence }: {
  items: ComparisonFinding[]; evaluations: Evaluation[]; onEvidence: (finding: ComparisonFinding) => void;
}) {
  const files = new Map<string, ComparisonFinding[]>();
  const byId = new Map(evaluations.map((item) => [item.finding_id, item]));
  for (const item of items) files.set(item.path, [...(files.get(item.path) ?? []), item]);
  return <div className="agent-finding-files">{Array.from(files, ([path, findings]) => <section key={path}>
    <h4>{path}</h4>
    <ul>{findings.map((finding) => <li key={finding.id}>
      <div><strong>{finding.title}</strong><FindingLocation finding={finding} /></div>
      <Space size={4} wrap>
        {byId.has(finding.id) && <Tag>{verdictLabels[byId.get(finding.id)?.verdict ?? "insufficient"]}</Tag>}
        <Button size="small" type="link" aria-label={`查看证据：${finding.title}`} onClick={() => onEvidence(finding)}>查看证据</Button>
      </Space>
    </li>)}</ul>
  </section>)}</div>;
}

/** 展示两个引擎的固定查证材料；匹配必须由评审者确认。 */
export function ComparisonWorkspace({ comparison, canEdit, onEdit, onCurationVersion }: {
  comparison: AgentComparison; canEdit: boolean; onEdit: (edit: ComparisonEdit) => void;
  onCurationVersion: (version: number | null) => void;
}) {
  const [filter, setFilter] = useState<"all" | "agent">("all");
  const [evidence, setEvidence] = useState<ComparisonFinding | null>(null);
  const { message } = App.useApp();
  const { agent, ocr, curation } = comparison;
  const { document } = curation;
  const latest = curation.version === comparison.latest_curation_version;
  const editable = canEdit && latest && !["queued", "running"].includes(comparison.status);
  const totals = agent.files?.reduce((current, file) => ({
    reviewed: current.reviewed + file.reviewed, delivered: current.delivered + file.delivered,
    total: current.total + file.total,
  }), { reviewed: 0, delivered: 0, total: 0 });
  const matched = new Set(document.matches.flatMap((item) => [...item.ocr_ids, ...item.agent_ids]));
  const agentOnly = agent.findings.filter((item) => !matched.has(item.id));
  const suggestions = comparison.suggestions.filter((item) => [...item.ocr_ids, ...item.agent_ids].every((id) => !matched.has(id)));
  const all = new Map([...ocr.findings, ...agent.findings].map((item) => [item.id, item]));
  const evaluation = document.evaluations.find((item) => item.finding_id === evidence?.id);
  function addRecord(kind: "match" | "missed") {
    try {
      const id = `${kind}:${createCommandId()}`;
      onEdit(kind === "match" ? { kind, value: { id, label: "", ocr_ids: [], agent_ids: [] } }
        : { kind, value: { id, title: "", path: "", side: null, line: null, note: "" } });
    } catch (error) {
      void message.error(error instanceof Error ? error.message : "无法生成裁定标识");
    }
  }
  function renderGroup(group: FindingMatch, suggest: boolean) {
    return <li key={group.id} className="agent-curation-row">
      <div><strong>{group.label}</strong><div className="agent-match-links">{[...group.ocr_ids, ...group.agent_ids].map((id) => {
        const item = all.get(id);
        return item && <Button key={id} type="link" size="small" onClick={() => setEvidence(item)}>
          {id.startsWith("ocr:") ? "OCR" : "Agent"} {item.line ? `· ${item.line} 行` : "· 文件级"}
        </Button>;
      })}</div></div>
      {editable && <Button size="small" onClick={() => onEdit({ kind: "match", value: group })}>{suggest ? "核对匹配" : "编辑分组"}</Button>}
    </li>;
  }
  return <>
    <div className="agent-comparison-scope">
      <span>固定范围 <Typography.Text code title={comparison.base_sha}>{shortSha(comparison.base_sha)}</Typography.Text> → <Typography.Text code title={comparison.head_sha}>{shortSha(comparison.head_sha)}</Typography.Text></span>
      <span>OCR 初审第 {comparison.source_attempt} 次 · Agent #{comparison.id}</span>
    </div>
    <div className="agent-comparison-controls">
      <Segmented aria-label="发现筛选" value={filter} onChange={setFilter} options={[
        { label: "全部发现", value: "all" }, { label: `Agent 独有（${agentOnly.length}）`, value: "agent" },
      ]} />
      <Space wrap size={6}>
        {curation.version > 0 && <span title={formatTime(curation.created_at)}>裁定 v{curation.version} · {curation.actor}</span>}
        {curation.version > 0 && <Button size="small" onClick={() => onCurationVersion(curation.version - 1)}>上一条裁定</Button>}
        {!latest && <Button size="small" type="primary" ghost onClick={() => onCurationVersion(null)}>回到最新裁定</Button>}
      </Space>
    </div>
    <div className={`agent-comparison-columns${filter === "agent" ? " agent-comparison-columns--single" : ""}`}>
      {filter === "all" && <Card size="small" title="阿里 OCR" extra={<Status value={ocr.status} />}>
        <div className="agent-coverage"><strong>{ocr.coverage ? `${ocr.coverage.completed}/${ocr.coverage.selected}` : "未知"}</strong> 文件完成
          {ocr.coverage && <span>复用 {ocr.coverage.reused} · 失败 {ocr.coverage.failed} · 豁免 {ocr.coverage.waived}</span>}</div>
        <Usage usage={ocr.usage} />
        {ocr.findings.length ? <EvidenceRows items={ocr.findings} evaluations={document.evaluations} onEvidence={setEvidence} />
          : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={ocr.status === "complete" && ocr.coverage && ocr.coverage.completed === ocr.coverage.selected ? "初审没有报告发现" : "暂无可展示的初审发现"} />}
      </Card>}
      <Card size="small" title="自建 Agent" extra={<Status value={comparison.status} />}>
        <div className="agent-coverage"><strong>{totals ? `${totals.reviewed}/${totals.total}` : "未知"}</strong> 条差异已核对
          {totals && <span>已交付 {totals.delivered} 条 · 排除 {agent.excluded_paths.length} 个文件</span>}</div>
        <Usage usage={agent.usage} />
        {agent.reason && agent.reason !== "covered" && <p className="agent-comparison-reason">{reasonLabels[agent.reason] ?? `结束原因：${agent.reason}`}</p>}
        {agent.files && (agent.files.length > 0 || agent.excluded_paths.length > 0) && <Collapse size="small" ghost
          items={[{ key: "scope", label: "查看文件覆盖", children: <ul className="agent-coverage-files">
            {agent.files.map((file) => <li key={file.path}><span>{file.path}</span><span>{file.reviewed}/{file.total} 已核对</span></li>)}
            {agent.excluded_paths.map((path) => <li key={path}><span>{path}</span><span>无文本差异</span></li>)}
          </ul> }]} />}
        {(filter === "all" ? agent.findings : agentOnly).length > 0
          ? <EvidenceRows items={filter === "all" ? agent.findings : agentOnly} evaluations={document.evaluations} onEvidence={setEvidence} />
          : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={filter === "agent" && agent.findings.length > 0
            ? "没有未匹配的 Agent 发现" : comparison.status === "complete" ? "Agent 没有报告发现" : "暂无可展示的 Agent 发现"} />}
      </Card>
    </div>
    <section className="agent-human-review" aria-label="人工整理">
      <div className="agent-comparison-controls"><h3>人工整理</h3>{editable && <Space wrap>
        {ocr.findings.length > 0 && agent.findings.length > 0 && <Button size="small" onClick={() => addRecord("match")}>建立同根因组</Button>}
        <Button size="small" onClick={() => addRecord("missed")}>补录共同漏报</Button>
      </Space>}</div>
      {document.matches.length > 0 && <><h4>已确认同根因</h4><ul>{document.matches.map((item) => renderGroup(item, false))}</ul></>}
      {suggestions.length > 0 && <><h4>同位置待核对</h4><ul>{suggestions.map((item) => renderGroup(item, true))}</ul></>}
      {document.missed.length > 0 && <><h4>共同漏报</h4><ul>{document.missed.map((item) => <li key={item.id} className="agent-curation-row">
        <div><strong>{item.title}</strong><FindingLocation finding={item} />{item.note && <p>{item.note}</p>}</div>
        {editable && <Button size="small" onClick={() => onEdit({ kind: "missed", value: item })}>编辑漏报</Button>}
      </li>)}</ul></>}
      {!document.matches.length && !suggestions.length && !document.missed.length && <p>暂无匹配或共同漏报记录。</p>}
    </section>
    <Drawer open={evidence !== null} title="固定版本证据" size="min(620px, 100vw)" onClose={() => setEvidence(null)}
      extra={editable && evidence ? <Button type="primary" onClick={() => { onEdit(evaluateFinding(comparison, evidence)); setEvidence(null); }}>裁定发现</Button> : null}>
      {evidence && <div className="agent-evidence">
        <div><Tag>{evidence.id.startsWith("ocr:") ? "阿里 OCR" : "自建 Agent"}</Tag>比较 #{comparison.id}</div>
        <h3>{evidence.title}</h3><FindingLocation finding={evidence} />
        <Typography.Text code>{evidence.side === "base" ? comparison.base_sha : evidence.side === "head" ? comparison.head_sha : `${shortSha(comparison.base_sha)} → ${shortSha(comparison.head_sha)}`}</Typography.Text>
        {evidence.excerpt && <pre>{evidence.excerpt}</pre>}
        <FindingDescription content={evidence.content} />
        {evidence.impact && <p><strong>影响</strong> {evidence.impact}</p>}
        {evaluation && <div><Tag>{verdictLabels[evaluation.verdict]}</Tag>{evaluation.worth_fixing !== null && <Tag>{evaluation.worth_fixing ? "值得处理" : "无需处理"}</Tag>}{evaluation.note && <p>{evaluation.note}</p>}</div>}
      </div>}
    </Drawer>
  </>;
}
