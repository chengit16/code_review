/** @description 管理员显式归档和恢复；操作原因与读取版本固定，失败保留草稿，不更改业务结论。 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { changeImprovementArchive } from "../api/improvements";
import type { ArchiveMetadata } from "../api/improvements";
import { Modal } from "../ui/Modal";
import { confirmDiscard, UnsavedChangesGuard } from "../ui/UnsavedChangesGuard";
import { formatTime } from "../ui/format";

/** 当前归档事实与操作入口；服务端才是授权、版本和只读边界。 */
export function ImprovementArchiveControl({ token, resource, record, disabled, onSaved }: {
  /** 管理员内存会话。 */ token: string;
  /** 问题记录或主题，主题归档不级联问题。 */ resource: "records" | "themes";
  /** 当前事实；发起操作时另行固定版本。 */ record: ArchiveMetadata & { id: number; title: string; version: number };
  /** 编辑或读取失败期间禁止发起新操作。 */ disabled: boolean;
  /** 事务确认后提示并回到首屏历史。 */ onSaved: () => void;
}) {
  const client = useQueryClient();
  const [target, setTarget] = useState<typeof record | null>(null);
  const [reason, setReason] = useState("");
  const action = target?.archived_at ? "恢复" : "归档";
  const mutation = useMutation({
    mutationFn: () => {
      if (!target) throw new Error("未选择操作对象");
      return changeImprovementArchive(token, resource, target.id, !target.archived_at, target.version, reason.trim());
    },
    retry: false,
    onSuccess: async () => {
      // 归档影响列表、历史、反向关联、选择器和复盘；仅在服务端成功后刷新。
      await Promise.all(["improvements", "improvement", "improvement-history", "improvement-themes",
        "improvement-theme", "improvement-theme-history", "improvement-summary"].map((key) =>
        client.invalidateQueries({ queryKey: [key] })));
      setTarget(null); setReason(""); onSaved();
    },
  });
  function close() {
    if (!mutation.isPending && confirmDiscard(Boolean(reason.trim()))) setTarget(null);
  }
  return <section className="section improvement-archive" aria-label="归档管理">
    <h2>归档管理</h2>
    {record.archived_at ? <p className="prewrap">已归档 · {formatTime(record.archived_at)} · {record.archived_by}。归档原因：{record.archive_reason}。恢复后才能编辑。</p> : <p className="muted">未归档。归档仅收纳，不代表已解决或已部署；内容、历史与关联都会保留。</p>}
    <button className="button button-secondary" type="button" disabled={disabled || mutation.isPending} onClick={() => { mutation.reset(); setReason(""); setTarget({ ...record }); }}>{record.archived_at ? "恢复内容" : "归档内容"}</button>
    {target && <Modal titleId="archive-change-title" onClose={close} className="improvement-archive-modal">
      <div className="modal-heading"><h2 id="archive-change-title">{action}确认</h2></div>
      <div className="improvement-archive-body">
      <p className="prewrap">{resource === "themes" ? "主题" : "记录"} #{target.id} · {target.title} · 版本 {target.version}</p>
      <p>不会改变处理进展、代码修改、本地验证、部署状态或关联。归档后仍纳入复盘和待办；恢复不抹去归档历史。主题操作不级联问题。</p>
      <form className="settings-form" onSubmit={(event) => { event.preventDefault(); if (reason.trim() && !mutation.isPending) mutation.mutate(); }}>
        <UnsavedChangesGuard dirty={Boolean(reason.trim()) || mutation.isPending} />
        <label>{action}原因<textarea required maxLength={2000} rows={4} disabled={mutation.isPending} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        {mutation.error && <p className="form-error" role="alert">{mutation.error.message}。原因草稿已保留；如版本冲突，请先取消并刷新详情核对，不要直接重复提交。</p>}
        <div className="form-actions"><button className="button button-secondary" type="button" disabled={mutation.isPending} onClick={close}>取消</button><button className="button button-primary" type="submit" disabled={!reason.trim() || mutation.isPending}>{mutation.isPending ? "正在提交…" : `确认${action}`}</button></div>
      </form>
      </div>
    </Modal>}
  </section>;
}
