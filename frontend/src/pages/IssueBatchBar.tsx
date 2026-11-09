/** @description 展示当前页问题批量操作；不发送请求或推断服务端权限。 */
import { Button, Checkbox, Input } from "antd";

import type { IssueActionStatus } from "../api/reviewIssues";

import { issueActionLabels } from "./useIssueBatch";

/** 受控批量操作栏，确认与持久化由页面业务 Hook 执行。 */
export function IssueBatchBar({ count, allSelected, disabled, pending, note, onNote, onSelectAll, onClear, onSubmit }: {
  /** 当前页已勾选的有效问题数。 */ count: number;
  /** 当前页可选行是否全部选中。 */ allSelected: boolean;
  /** 列表未就绪或无可选项时禁用。 */ disabled: boolean;
  /** 提交和刷新完成前禁止重复操作。 */ pending: boolean;
  /** 统一处理说明草稿，冲突时保留。 */ note: string;
  /** 仅更新说明草稿。 */ onNote: (value: string) => void;
  /** 仅选择当前页，不包含隐藏页。 */ onSelectAll: (checked: boolean) => void;
  /** 清空当前选择，不修改服务端记录。 */ onClear: () => void;
  /** 触发二次确认后提交；服务端仍校验管理员权限。 */ onSubmit: (status: IssueActionStatus) => void;
}) {
  return <section className="issue-batch-bar" aria-label="批量处理问题">
    <div className="issue-batch-selection">
      <Checkbox className="issue-select-all" checked={allSelected} disabled={disabled || pending} onChange={(event) => onSelectAll(event.target.checked)}>全选本页可处理问题</Checkbox>
      <span aria-live="polite">已选 <strong>{count}</strong> 条</span>
      <Button type="link" disabled={!count || pending} onClick={onClear}>清空选择</Button>
      <small>仅处理当前页勾选项，已合并问题不可选</small>
    </div>
    <div className="issue-batch-actions">
      <label>批量处理说明<Input value={note} maxLength={500} disabled={pending} placeholder="可选，将记录到每条问题" onChange={(event) => onNote(event.target.value)} /></label>
      {(["fixed", "ignored", "false_positive", "open"] as const).map((value) => <Button key={value} disabled={disabled || pending || !count} onClick={() => onSubmit(value)}>{pending ? "处理中…" : `批量${issueActionLabels[value]}`}</Button>)}
    </div>
  </section>;
}
