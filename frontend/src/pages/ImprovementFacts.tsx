/** @description 当前摘要和历史快照共用只读展示；用户文字仅按纯文本渲染。 */
import type { ImprovementContent } from "../api/improvements";
import { categoryLabels, codeLabels, deploymentLabels, improvementTextFields, kindLabels, progressLabels, verificationLabels } from "./improvementFields";

/** 三个交付维度并列展示，已解决不意味着生产已生效。 */
export function ImprovementStates({ record }: { /** 当前或历史的事实快照。 */ record: ImprovementContent }) {
  return <dl className="improvement-states">
    <div><dt>代码修改</dt><dd>{codeLabels[record.code_state]}</dd></div>
    <div><dt>本地验证</dt><dd>{verificationLabels[record.verification_state]}</dd></div>
    <div><dt>部署生效</dt><dd>{deploymentLabels[record.deployment_state]}</dd></div>
  </dl>;
}

/** 保留排查、无效尝试和下一步；缺失证据明确显示尚未记录。 */
export function ImprovementFacts({ record }: { /** 不含凭据或原始日志的人工记录。 */ record: ImprovementContent }) {
  return <div className="improvement-facts">
    <p>{kindLabels[record.kind]} · {categoryLabels[record.category]} · {progressLabels[record.status]} · {record.scope}</p>
    <ImprovementStates record={record} />
    <dl>{improvementTextFields.map((field) => <div key={field.key}><dt>{field.label}</dt><dd>{record[field.key] || "尚未记录"}</dd></div>)}</dl>
  </div>;
}
