/** @description 展示固定范围下的双路证据、覆盖与人工裁定，保留各自的覆盖口径。 */

import { App, Button, Collapse, Empty, Segmented, Space, Typography } from "antd";
import { useEffect, useRef, useState } from "react";

import type { AgentComparison, ComparisonFinding, FindingMatch } from "../../api/agentComparisons";
import { createCommandId } from "../../api/commandId";
import { Status } from "../../ui/Status";
import { formatTime, shortSha } from "../../ui/format";

import { CapabilityEvidence } from "./CapabilityEvidence";
import { ComparisonUsageDetails, EvidenceRows, FindingLocation } from "./ComparisonEngine";
import { ComparisonFindingDrawer } from "./ComparisonFindingDrawer";
import { evaluateFinding } from "./comparisonEdits";
import type { ComparisonEdit } from "./comparisonEdits";

const reasonLabels: Record<string, string> = {
  read_budget: "达到读取页数限制", model_budget: "达到模型预算限制", model_timeout: "模型响应超时",
  model_response: "模型响应未通过校验", model_unavailable: "模型网关不可用", input_unavailable: "固定 Git 输入不可用",
  input_changed: "固定差异快照不一致", source_changed: "初审来源已变化", mr_version_changed: "MR 版本已变化",
  model_config_changed: "模型配置已更新", model_config_invalid: "模型配置无效", not_enabled: "已关闭 Agent",
  ocr_rules_unavailable: "无法还原 OCR 初审规则",
  capability_unavailable: "方案已停用，或必需的取证步骤不可用",
  interrupted: "运行中断", cancelled: "已取消", no_text_diff: "没有文本差异",
};

const ruleSources: Record<string, string> = {
  custom: "项目配置", project: "仓库规则", global: "全局规则", system: "内置规则",
};

/** 展示两个引擎的固定查证材料；匹配必须由评审者确认。 */
export function ComparisonWorkspace({ comparison, canEdit, onEdit, onCurationVersion }: {
  comparison: AgentComparison; canEdit: boolean; onEdit: (edit: ComparisonEdit) => void;
  onCurationVersion: (version: number | null) => void;
}) {
  const [filter, setFilter] = useState<"all" | "agent">("all");
  const [evidence, setEvidence] = useState<ComparisonFinding | null>(null);
  const evidenceTrigger = useRef<HTMLElement>(null);
  useEffect(() => {
    const trigger = evidenceTrigger.current;
    if (evidence || !trigger) return;
    // 等抽屉释放焦点锁后再恢复入口焦点。
    const frame = requestAnimationFrame(() => {
      evidenceTrigger.current = null;
      trigger.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [evidence]);
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
  const unmatchedAgent = agent.findings.filter((item) => !matched.has(item.id));
  const displayedAgentFindings = filter === "all" ? agent.findings : unmatchedAgent;
  const suggestions = comparison.suggestions.filter((item) => [...item.ocr_ids, ...item.agent_ids].every((id) => !matched.has(id)));
  const all = new Map([...ocr.findings, ...agent.findings].map((item) => [item.id, item]));
  const evaluation = document.evaluations.find((item) => item.finding_id === evidence?.id);
  function showEvidence(finding: ComparisonFinding, trigger: HTMLElement) {
    evidenceTrigger.current = trigger;
    setEvidence(finding);
  }
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
        return item && <Button key={id} type="link" size="small" onClick={(event) => showEvidence(item, event.currentTarget)}>
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
        { label: "全部发现", value: "all" }, { label: `Agent 未匹配（${unmatchedAgent.length}）`, value: "agent" },
      ]} />
      <Space wrap size={6}>
        {curation.version > 0 && <span title={formatTime(curation.created_at)}>裁定 v{curation.version} · {curation.actor}</span>}
        {curation.version > 0 && <Button size="small" onClick={() => onCurationVersion(curation.version - 1)}>上一条裁定</Button>}
        {!latest && <Button size="small" type="primary" ghost onClick={() => onCurationVersion(null)}>回到最新裁定</Button>}
      </Space>
    </div>
    <div className={`agent-comparison-columns${filter === "agent" ? " agent-comparison-columns--single" : ""}`}>
      {filter === "all" && <section className="agent-engine" aria-label="阿里 OCR 发现">
        <header className="agent-engine-summary">
          <div className="agent-engine-title"><h3>阿里 OCR</h3><Status value={ocr.status} /></div>
          <div className="agent-engine-facts">
            <span><strong>{ocr.coverage ? `${ocr.coverage.completed}/${ocr.coverage.selected}` : "未知"}</strong> 文件完成</span>
            <span><strong>{ocr.findings.length}</strong> 条发现</span>
          </div>
        </header>
        <div className="agent-engine-results">
          {ocr.findings.length ? <EvidenceRows items={ocr.findings} evaluations={document.evaluations} onEvidence={showEvidence} />
            : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={ocr.status === "complete" && ocr.coverage && ocr.coverage.completed === ocr.coverage.selected ? "初审没有报告发现" : "暂无可展示的初审发现"} />}
        </div>
        <Collapse ghost size="small" items={[{ key: "data", label: "覆盖与用量", children: <>
          {ocr.coverage && <div className="agent-usage">复用 {ocr.coverage.reused} 个 · 失败 {ocr.coverage.failed} 个 · 豁免 {ocr.coverage.waived} 个</div>}
          <ComparisonUsageDetails usage={ocr.usage} />
        </> }]} />
      </section>}
      <section className="agent-engine" aria-label="自建 Agent 发现">
        <header className="agent-engine-summary">
          <div className="agent-engine-title">
            <h3>自建 Agent</h3><Status value={comparison.status} />
            <CapabilityEvidence comparison={comparison} coverage={totals} />
          </div>
          <div className="agent-engine-facts">
            <span><strong>{totals ? `${totals.reviewed}/${totals.total}` : "未知"}</strong> 条差异已核对</span>
            <span><strong>{displayedAgentFindings.length}</strong> 条{filter === "agent" ? "未匹配发现" : "发现"}</span>
          </div>
          {agent.reason && agent.reason !== "covered" && <p className="agent-comparison-reason">{reasonLabels[agent.reason] ?? `结束原因：${agent.reason}`}</p>}
        </header>
        <div className="agent-engine-results">
          {displayedAgentFindings.length > 0
            ? <EvidenceRows items={displayedAgentFindings} evaluations={document.evaluations} onEvidence={showEvidence} />
            : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={filter === "agent" && agent.findings.length > 0
              ? "没有未匹配的 Agent 发现" : comparison.status === "complete" ? "Agent 没有报告发现" : "暂无可展示的 Agent 发现"} />}
        </div>
        <div className="agent-engine-footer">
          <Collapse size="small" ghost items={[{ key: "data", label: "覆盖与用量", children: <>
            {totals && <div className="agent-usage">已交付 {totals.delivered} 条 · 排除 {agent.excluded_paths.length} 个文件</div>}
            <ComparisonUsageDetails usage={agent.usage} />
            {agent.files && (agent.files.length > 0 || agent.excluded_paths.length > 0) && <ul className="agent-coverage-files">
              {agent.files.map((file) => <li key={file.path}>
                <div>
                  <div>{file.path}</div>
                  {file.rule && <Typography.Text type="secondary" title={file.rule.sha256}>
                    规则 · {ruleSources[file.rule.source] ?? file.rule.source} · {file.rule.pattern} · {file.rule.sha256.slice(0, 12)}
                  </Typography.Text>}
                </div>
                <span>{file.reviewed}/{file.total} 已核对</span>
              </li>)}
              {agent.excluded_paths.map((path) => <li key={path}><span>{path}</span><span>无文本差异</span></li>)}
            </ul>}
          </> }]} />
        </div>
      </section>
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
    <ComparisonFindingDrawer comparison={comparison} finding={evidence} evaluation={evaluation}
      onClose={() => setEvidence(null)} onEvaluate={editable ? (finding) => {
        evidenceTrigger.current = null;
        onEdit(evaluateFinding(comparison, finding));
        setEvidence(null);
      } : undefined} />
  </>;
}
