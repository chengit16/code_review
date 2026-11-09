/** @description 跟进问题的互斥处置按钮；确认目标冻结，失败保留说明，不以反馈冒充处置事实。 */
import { Alert, Button, Input, Modal } from "antd";
import { useState } from "react";

import type { IssueActionStatus, IssueBatchTarget } from "../api/reviewIssues";

import type { FindingDisposition } from "./useFindingDisposition";

/** 卡片动作的最小事实与回调；授权与提交结果由服务端负责。 */
export interface IssueStateActionsProps {
  /** 原始发现索引，筛选不改变它。 */ index: number;
  /** 已解析到当前问题的持久化编号。 */ issueId?: number;
  /** 最新服务端状态；缺失或合并时不能独立处置。 */ issueStatus?: IssueActionStatus | "merged";
  /** 任务可编辑且没有在途请求时允许动作。 */ canSubmit: boolean;
  /** 可选的独立处置入口；成功后由调用方刷新事实，失败须拒绝 Promise。 */ onDisposition?: (input: FindingDisposition) => Promise<unknown>;
  /** 确认打开或关闭时通知列表保留目标卡片，避免轮询筛选卸载说明草稿。 */ onConfirmationChange?: (isOpen: boolean) => void;
  /** 侧栏可指定名称；默认以发现原始索引命名。 */ groupLabel?: string;
}

/** 四种当前状态互斥显示；显式切换后才提交，历史评价不作为当前状态。 */
export function IssueStateActions({ index, issueId, issueStatus, canSubmit, onDisposition, onConfirmationChange, groupLabel }: IssueStateActionsProps) {
  const [confirmation, setConfirmation] = useState<{ target: IssueBatchTarget; status: IssueActionStatus } | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const disabled = !canSubmit || saving;
  const labels = { open: "待处理", fixed: "已修复", ignored: "已忽略", false_positive: "误报" };
  const confirmLabels = { open: "确认恢复", fixed: "确认修复", ignored: "确认忽略", false_positive: "确认误报" };

  function confirmDisposition(status: IssueActionStatus) {
    if (disabled || !onDisposition || !issueId || !issueStatus || issueStatus === "merged") return;
    setConfirmation({ target: { id: issueId, expected_status: issueStatus }, status });
    setNote("");
    setError("");
    onConfirmationChange?.(true);
  }

  async function submit() {
    if (!confirmation || !onDisposition || disabled) return;
    setSaving(true);
    setError("");
    try {
      await onDisposition({ ...confirmation, note: note.trim() || `跟进问题：人工标记${labels[confirmation.status]}，保留历史评价` });
      setConfirmation(null);
      setNote("");
      onConfirmationChange?.(false);
    } catch (reason) {
      setError(`${reason instanceof Error ? reason.message : "处理失败"}。未自动重试，请刷新核对问题状态；说明已保留。`);
    } finally {
      setSaving(false);
    }
  }

  return <div className="finding-actions" role="group" aria-label={groupLabel ?? `发现 ${index + 1} 的当前状态`}>
    {(["open", "fixed", "ignored", "false_positive"] as const).map((value) => <Button key={value}
      aria-label={labels[value]} aria-pressed={issueStatus === value} type={issueStatus === value ? "primary" : "default"}
      disabled={disabled || !onDisposition || !issueId || !issueStatus || issueStatus === "merged"}
      onClick={() => { if (issueStatus !== value) confirmDisposition(value); }}>{labels[value]}</Button>)}
    <Modal open={Boolean(confirmation)} title={confirmation ? `将问题改为${labels[confirmation.status]}？` : "修改当前状态"}
      okText={confirmation ? confirmLabels[confirmation.status] : "确认"} cancelText="取消" confirmLoading={saving}
      okButtonProps={{ disabled, "aria-label": confirmation ? confirmLabels[confirmation.status] : "确认" }} cancelButtonProps={{ disabled: saving }} closable={!saving} mask={{ closable: !saving }} keyboard={!saving}
      onCancel={() => { if (!saving) { setConfirmation(null); onConfirmationChange?.(false); } }} onOk={() => void submit()}>
      <p>跟进问题 #{confirmation?.target.id} · {confirmation?.status === "ignored" ? "本次决定不处理，不代表发现有误。" : confirmation?.status === "false_positive" ? "人工确认发现不成立，不会计入已忽略或已修复。" : confirmation?.status === "fixed" ? "人工确认代码已经修复，不代表系统已验证修复。" : "重新打开此问题，后续继续跟进。"}</p>
      <p>关联此问题的其他任务将同步显示新状态。此操作保留历史评价和处理记录，不会修改代码。</p>
      <label className="finding-note-field">处理说明（选填）<Input.TextArea aria-label="处理说明（选填）" value={note} maxLength={500} rows={3} disabled={saving} onChange={(event) => setNote(event.target.value)} /></label>
      {error && <Alert type="error" showIcon title={error} role="alert" />}
    </Modal>
  </div>;
}
