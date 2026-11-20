/** @description 双评审的只读发现抽屉，将结论和证据分开呈现，裁定由上层工作区处理。 */

import { Button, Collapse, Drawer, Tag, Typography } from "antd";
import { FileCode2, GitCommitHorizontal } from "lucide-react";

import type { AgentCapabilityEvent } from "../../api/agentCapabilities";
import type { AgentComparison, ComparisonFinding, Evaluation } from "../../api/agentComparisons";
import { formatTime, shortSha } from "../../ui/format";
import { FindingCodeBlock } from "../FindingCodeBlock";
import { FindingSections } from "../FindingDescription";
import { presentFindingContent } from "../findingContent";
import type { FindingContentSection } from "../findingContent";
import { capabilityStatusText } from "./CapabilityEvidence";
import { findingHeading } from "./ComparisonEngine";
import { verdictLabels } from "./comparisonEdits";
import "./comparisonFindingDrawer.css";

function FindingHeader({ comparison, finding, evaluation }: {
  comparison: AgentComparison; finding: ComparisonFinding; evaluation: Evaluation | undefined;
}) {
  const { ocr, severity, title } = findingHeading(finding);
  const side = finding.side;
  const location = finding.line == null ? "文件级"
    : `${side === "base" ? "旧版" : side === "head" ? "新版" : "记录"}第 ${finding.line} 行`;
  const commits = side === "base" ? [comparison.base_sha]
    : side === "head" ? [comparison.head_sha] : [comparison.base_sha, comparison.head_sha];

  return <header className="comparison-proof-header">
    <div className="comparison-proof-meta">
      <Tag color={ocr ? "default" : "blue"}>{ocr ? "阿里 OCR" : "自建 Agent"}</Tag>
      {severity && <Tag color={severity.color}>{severity.text}</Tag>}
      <span>比较 #{comparison.id}</span>
      {evaluation && <Tag>{verdictLabels[evaluation.verdict]}</Tag>}
    </div>
    <h2>{title}</h2>
    <div className="comparison-proof-location">
      <FileCode2 size={15} aria-hidden />
      <span>{finding.path} · {location}</span>
    </div>
    <div className="comparison-proof-version">
      <GitCommitHorizontal size={15} aria-hidden />
      <span>{side ? "提交" : "对照提交"}</span>
      <Typography.Text code title={commits.join(" → ")}>{commits.map(shortSha).join(" → ")}</Typography.Text>
    </div>
  </header>;
}

function ReferenceHeader({ event }: { event: AgentCapabilityEvent }) {
  const proof = event.evidence;
  const title = proof?.path?.split("/").at(-1) ?? proof?.document ?? event.source;
  return <div className="comparison-proof-reference-label">
    <strong title={proof?.path ?? event.source}>{title}</strong>
    <span>{proof?.document && "MCP · "}{proof?.line != null && `第 ${proof.line} 行 · `}{capabilityStatusText(event.status)} · 证据 #{event.id}</span>
  </div>;
}

function ReferenceBody({ event }: { event: AgentCapabilityEvent }) {
  const proof = event.evidence;
  if (!proof) return null;
  return <div className="comparison-proof-reference-body">
    {proof.path && <div>{proof.path}{proof.commit && <> · <code title={proof.commit}>{shortSha(proof.commit)}</code></>}</div>}
    {proof.document && <div>{proof.version ? `文档版本 ${proof.version}` : `检索时间 ${formatTime(event.created_at)}`}</div>}
    {event.source !== proof.path && event.source !== proof.document && <div>来源 {event.source}</div>}
    {proof.message && <p>{proof.message}</p>}
    {proof.excerpt && <FindingCodeBlock content={proof.excerpt} language="" caption={proof.document ? "文档摘录" : "代码摘录"} />}
    {proof.sha256 && <small title={proof.sha256}>证据摘要 {proof.sha256.slice(0, 12)}</small>}
  </div>;
}

function EvidenceMaterials({ excerpt, sections, references }: {
  excerpt: string; sections: FindingContentSection[]; references: AgentCapabilityEvent[];
}) {
  const attachments = references.filter((event) => event.evidence);
  const methods = references.filter((event) => !event.evidence);
  if (!excerpt && !sections.length && !references.length) return null;

  return <section className="comparison-proof-materials">
    <h3 className="comparison-proof-heading">证据材料</h3>
    {(excerpt || sections.length > 0) && <Collapse size="small" items={[{
      key: "basis", label: "代码依据",
      children: <div className="comparison-proof-reference-body">
        {excerpt && <FindingCodeBlock content={excerpt} language="" caption="定位代码" />}
        {sections.length > 0 && <FindingSections numbered={false} sections={sections.map((section) => ({ ...section, label: null }))} />}
      </div>,
    }]} />}
    {references.length > 0 && <div className="comparison-proof-references">
      <h4>补充证据 <span>{references.length}</span></h4>
      {attachments.length > 0 && <Collapse size="small" destroyOnHidden styles={{ title: { minWidth: 0 } }}
        items={attachments.map((event) => ({
          key: event.id, label: <ReferenceHeader event={event} />, children: <ReferenceBody event={event} />,
        }))} />}
      {methods.map((event) => <div className="comparison-proof-method" key={event.id}>
        <Tag>{event.step === "skill" ? "Skill" : "执行记录"}</Tag><ReferenceHeader event={event} />
      </div>)}
    </div>}
  </section>;
}

/** 两路发现使用同一阅读顺序，取得实际引用后才显示对应材料。 */
export function ComparisonFindingDrawer({ comparison, finding, evaluation, onClose, onEvaluate }: {
  /** 供当前发现使用的固定提交和引用。 */ comparison: AgentComparison;
  /** 当前选中的发现，空值关闭抽屉。 */ finding: ComparisonFinding | null;
  /** 当前修订中的人工裁定。 */ evaluation?: Evaluation;
  /** 清除查看状态。 */ onClose: () => void;
  /** 可编辑版本由上层提供裁定入口。 */ onEvaluate?: (finding: ComparisonFinding) => void;
}) {
  const sections = finding ? presentFindingContent(finding.content) : [];
  if (finding?.impact) sections.push(...presentFindingContent(`实际后果：${finding.impact}`, { keepSuggestionClauses: true }));
  const overview = sections.filter((section) => section.label !== "代码依据" && section.label !== "修复建议");
  overview.push(...sections.filter((section) => section.label === "修复建议"));
  const citations = new Set(finding?.capability_refs);
  const references = comparison.agent.capability_events?.filter((event) => citations.has(event.id)) ?? [];

  return <Drawer open={finding !== null} destroyOnHidden title="固定版本证据" size="min(744px, 100vw)"
    rootClassName="comparison-proof-drawer" onClose={onClose} focusable={{ focusTriggerAfterClose: false }}
    extra={finding && onEvaluate && <Button type="primary" onClick={() => onEvaluate(finding)}>裁定发现</Button>}>
    {finding && <article className="comparison-proof" key={finding.id}>
      <FindingHeader comparison={comparison} finding={finding} evaluation={evaluation} />
      {overview.length > 0 && <section>
        <h3 className="comparison-proof-heading">问题与影响</h3>
        <FindingSections sections={overview} numbered={false} heading="h4" />
      </section>}
      <EvidenceMaterials excerpt={finding.excerpt} sections={sections.filter((section) => section.label === "代码依据")} references={references} />
      {evaluation && (evaluation.worth_fixing !== null || evaluation.note) && <section>
        <h3 className="comparison-proof-heading">人工裁定</h3>
        {evaluation.worth_fixing !== null && <Tag>{evaluation.worth_fixing ? "值得处理" : "无需处理"}</Tag>}
        {evaluation.note && <p className="comparison-proof-note">{evaluation.note}</p>}
      </section>}
    </article>}
  </Drawer>;
}
