/** @description 按文件展示单路评审发现，固定位置和原始身份用于打开证据。 */

import { Button, Space, Tag } from "antd";

import type { ComparisonFinding, ComparisonUsage, Evaluation } from "../../api/agentComparisons";
import { formatCategory, formatSeverity } from "../../ui/format";
import { verdictLabels } from "./comparisonEdits";

const severityTones: Record<string, string> = { low: "default", medium: "gold", high: "orange", critical: "red" };

/** 将持久化标题中已有的分类和严重级别呈现为可扫描的字段。 */
export function findingHeading(finding: ComparisonFinding) {
  const ocr = finding.id.startsWith("ocr:");
  const parts = ocr ? null : finding.title.match(/^\[(low|medium|high|critical)\]\s+(.+)$/s);
  return {
    ocr, title: ocr ? formatCategory(finding.title) : parts?.[2] ?? finding.title,
    severity: parts ? { text: formatSeverity(parts[1]), color: severityTones[parts[1]] } : null,
  };
}

/** 同一文件分组内可省略已展示的路径。 */
export function FindingLocation({ finding, includePath = true }: {
  /** 发现或共同漏报的固定位置。 */ finding: Pick<ComparisonFinding, "side" | "path" | "line">;
  /** 文件分组内设为 false，只保留行号及版本。 */ includePath?: boolean;
}) {
  const line = finding.line === null ? "文件级"
    : `${finding.side === "base" ? "旧版" : finding.side === "head" ? "新版" : "记录"}第 ${finding.line} 行`;
  return <span className="agent-comparison-location">{includePath ? `${finding.path} · ` : ""}{line}</span>;
}

/** 使用当前运行已记录的用量，保留缺失账单的语义。 */
export function ComparisonUsageDetails({ usage }: {
  /** 单路评审实际保存的用量。 */ usage: ComparisonUsage;
}) {
  return <div className="agent-usage">
    {usage.model && <span>{usage.model}</span>}
    <span>{usage.input_tokens !== null && usage.output_tokens !== null
      ? `输入 ${usage.input_tokens.toLocaleString()} · 输出 ${usage.output_tokens.toLocaleString()} Token` : "用量未记录"}</span>
    {usage.unknown_calls > 0 && <Tag color="warning">{usage.unknown_calls} 次用量未知</Tag>}
    <span>{usage.cost === null ? "费用未知" : `估算费用 ${usage.currency ?? ""} ${usage.cost}`}</span>
  </div>;
}

/** 按路径分组；裁定标签取自当前选中的裁定修订。 */
export function EvidenceRows({ items, evaluations, onEvidence }: {
  /** 本列所展示的发现。 */ items: ComparisonFinding[];
  /** 当前裁定修订中的单条结论。 */ evaluations: Evaluation[];
  /** 打开固定证据，并传入用于恢复键盘焦点的入口。 */ onEvidence: (finding: ComparisonFinding, trigger: HTMLElement) => void;
}) {
  const files = new Map<string, ComparisonFinding[]>();
  const byId = new Map(evaluations.map((item) => [item.finding_id, item]));
  for (const item of items) {
    const group = files.get(item.path);
    if (group) group.push(item);
    else files.set(item.path, [item]);
  }
  return <div className="agent-finding-files">{Array.from(files, ([path, findings]) => <section key={path}>
    <h4 title={path}><strong>{path.split("/").at(-1)}</strong><span>{path}</span></h4>
    <ul>{findings.map((finding) => {
      const { title, severity } = findingHeading(finding);
      const evaluation = byId.get(finding.id);
      return <li key={finding.id}>
        <div className="agent-finding-label">
          <strong>{title}</strong>
          <Space size={4} wrap>
            <FindingLocation finding={finding} includePath={false} />
            {severity && <Tag color={severity.color}>{severity.text}</Tag>}
            {evaluation && <Tag>{verdictLabels[evaluation.verdict]}</Tag>}
          </Space>
        </div>
        <Button size="small" type="link" aria-label={`查看证据：${finding.title}`}
          onClick={(event) => onEvidence(finding, event.currentTarget)}>查看证据</Button>
      </li>;
    })}</ul>
  </section>)}</div>;
}
