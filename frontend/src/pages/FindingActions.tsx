/** @description 发现价值反馈的三种互斥选择；不修改问题处置，旧修复标记不冒充价值评价。 */
import { Button } from "antd";

/** 新评价仅表示价值，旧修复值保留为读取兼容。 */
export type FindingFeedbackChoice = "helpful" | "false_positive" | "ignored";
export type FindingVerdict = FindingFeedbackChoice | "fixed";

/** 价值反馈标签及业务边界；未评价与明确忽略分别统计。 */
export const findingFeedbackOptions = [
  { value: "helpful", label: "有帮助", title: "发现有价值，值得采纳；不代表代码已修复" },
  { value: "false_positive", label: "误报", title: "发现不成立或判断错误；不自动关闭跟进问题" },
  { value: "ignored", label: "忽略", title: "本次不采纳，不等于发现错误；不自动关闭跟进问题" },
] as const;

/** 当前三类价值反馈均表示发现已处理；无反馈及旧修复值仍按待反馈处理。 */
export function isFindingHandled(marked?: FindingVerdict): boolean {
  return marked === "helpful" || marked === "false_positive" || marked === "ignored";
}

/** 反馈的最小事实；服务端继续验证当前来源及管理员权限。 */
export interface FindingActionsProps {
  /** 原始发现索引，不使用筛选后的序号。 */ index: number;
  /** 当前人工评价，旧修复记录不选中任何价值按钮。 */ marked?: FindingVerdict;
  /** 终态、权限和在途请求共同决定是否可提交。 */ canSubmit: boolean;
  /** 选择新评价或再次点击撤销当前评价；成功后由调用方重读事实。 */ onFeedback: (index: number, verdict: FindingFeedbackChoice | null) => void;
}

/** 同时只选中一项；再次点击撤销为未评价，按钮不包含修复等问题处置。 */
export function FindingActions({ index, marked, canSubmit, onFeedback }: FindingActionsProps) {
  return <div className="finding-feedback"><div className="finding-actions" role="group" aria-label={`发现 ${index + 1} 的反馈`}>
    {findingFeedbackOptions.map(({ value, label, title }) => <Button key={value} aria-label={label} title={title}
      aria-pressed={marked === value} type={marked === value ? "primary" : "default"} disabled={!canSubmit}
      onClick={() => onFeedback(index, marked === value ? null : value)}>{label}</Button>)}
  </div>{marked === "fixed" && <small className="finding-feedback-legacy">旧版“已修复”标记不计入价值评价，请按需重新评价。</small>}</div>;
}
