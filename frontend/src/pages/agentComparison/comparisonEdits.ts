/** @description 将单项人工修改应用到指定裁定版本；冲突后不覆盖其他人的无关修改。 */

import type { AgentComparison, ComparisonFinding, CurationDocument, Evaluation, FindingMatch, MissedFinding } from "../../api/agentComparisons";

export type ComparisonEdit =
  | { kind: "evaluation"; finding: ComparisonFinding; value: Evaluation }
  | { kind: "match"; value: FindingMatch }
  | { kind: "missed"; value: MissedFinding };

export const verdictLabels = { valid: "成立", invalid: "不成立", insufficient: "证据不足" } as const;

/** 使用当前快照中的同身份裁定，首次编辑默认待确认。 */
export function evaluateFinding(comparison: AgentComparison, finding: ComparisonFinding): ComparisonEdit {
  const value = comparison.curation.document.evaluations.find((entry) => entry.finding_id === finding.id);
  return { kind: "evaluation", finding, value: value ?? {
    finding_id: finding.id, verdict: "insufficient", worth_fixing: null, note: "",
  } };
}

function updateById<T>(items: T[], item: T, identity: (value: T) => string, remove: boolean): T[] {
  const id = identity(item);
  if (remove) return items.filter((value) => identity(value) !== id);
  return items.some((value) => identity(value) === id)
    ? items.map((value) => identity(value) === id ? item : value) : [...items, item];
}

/** 保存仅变更所选评审对象，其余对象沿用对应的服务端版本。 */
export function applyComparisonEdit(document: CurationDocument, edit: ComparisonEdit, remove: boolean): CurationDocument {
  if (edit.kind === "evaluation") return {
    ...document, evaluations: updateById(document.evaluations, edit.value, (item) => item.finding_id, remove),
  };
  if (edit.kind === "match") {
    const retained = remove ? document.matches : document.matches.map((entry) =>
      entry.id === edit.value.id ? entry : {
        ...entry,
        ocr_ids: entry.ocr_ids.filter((id) => !edit.value.ocr_ids.includes(id)),
        agent_ids: entry.agent_ids.filter((id) => !edit.value.agent_ids.includes(id)),
      }).filter((entry) => entry.ocr_ids.length && entry.agent_ids.length);
    return { ...document, matches: updateById(retained, edit.value, (item) => item.id, remove) };
  }
  return { ...document, missed: updateById(document.missed, edit.value, (item) => item.id, remove) };
}

/** 给冲突后重新载入的版本定位同一条裁定，用户可以比对后再保存。 */
export function savedEdit(document: CurationDocument, edit: ComparisonEdit) {
  if (edit.kind === "evaluation") return document.evaluations.find((item) => item.finding_id === edit.value.finding_id);
  if (edit.kind === "match") return document.matches.find((item) => item.id === edit.value.id);
  return document.missed.find((item) => item.id === edit.value.id);
}
