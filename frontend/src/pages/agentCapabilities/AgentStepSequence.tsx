/** @description 以可换行的顺序展示方案中已配置的 Agent 步骤。 */

import { agentNodeLabels } from "../../api/agentCapabilities";
import type { AgentNode } from "../../api/agentCapabilities";
import "./agentCapabilities.css";

/** 基础步骤和可选步骤按实际执行顺序展示。 */
export function AgentStepSequence({ steps }: {
  /** 已配置的可选步骤，使用保存时的顺序。 */ steps: readonly AgentNode[];
}) {
  const labels = ["读取差异", ...steps.map((step) => agentNodeLabels[step]), "评审与证据校验", "保存结果"];
  return <ol className="agent-step-sequence" aria-label="执行顺序">
    {labels.map((label) => <li key={label}>{label}</li>)}
  </ol>;
}
