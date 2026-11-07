/** @description 独立台账草稿；失败和版本冲突不清空输入，保存前不写入浏览器存储。 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useRef, useState } from "react";

import { createCommandId } from "../api/commandId";
import { createImprovement, updateImprovement } from "../api/improvements";
import type { ImprovementContent, ImprovementRecord } from "../api/improvements";
import { Modal } from "../ui/Modal";
import { SelectField } from "../ui/SelectField";
import { confirmDiscard, UnsavedChangesGuard } from "../ui/UnsavedChangesGuard";
import { categoryLabels, codeLabels, deploymentLabels, emptyImprovement, improvementTextFields, kindLabels, progressLabels, verificationLabels } from "./improvementFields";

function Choice<K extends string>({ label, value, labels, onChange }: {
  label: string; value: K; labels: Record<K, string>; onChange: (value: K) => void;
}) {
  return <SelectField label={label} value={value} options={Object.entries<string>(labels).map(([key, text]) => ({ value: key, label: text }))} onValueChange={(next) => { if (next in labels) onChange(next as K); }} />;
}

/** 编辑时固定读取版本；并发更新只允许人工核对，不提供静默覆盖按钮。 */
export function ImprovementEditor({ token, record, onClose, onSaved }: {
  /** 内存管理会话。 */ token: string;
  /** 缺省表示新建；编辑器挂载期间保持原版本。 */ record?: ImprovementRecord;
  /** 关闭前由编辑器判断草稿和保存状态。 */ onClose: () => void;
  /** 仅服务端确认保存后触发，由页面刷新摘要及历史。 */ onSaved: () => void;
}) {
  const client = useQueryClient();
  const [initial] = useState<ImprovementContent>(() => {
    if (!record) return emptyImprovement();
    return { title: record.title, kind: record.kind, category: record.category, status: record.status,
      scope: record.scope, description: record.description, analysis: record.analysis, solution: record.solution,
      code_state: record.code_state, verification_state: record.verification_state, validation_evidence: record.validation_evidence,
      deployment_state: record.deployment_state, deployment_evidence: record.deployment_evidence,
      next_steps: record.next_steps, references: record.references };
  });
  const [draft, setDraft] = useState(initial);
  const clientKey = useRef<string | null>(null);
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState(false);
  const dirty = !saved && (JSON.stringify(initial) !== JSON.stringify(draft) || Boolean(note));
  const mutation = useMutation({
    mutationFn: () => {
      if (record) return updateImprovement(token, record.id, draft, record.version, note);
      // 保存时才生成标识，随机源缺失由 Mutation 显示错误，不在渲染时丢失整个表单。
      clientKey.current ??= createCommandId();
      return createImprovement(token, draft, clientKey.current);
    },
    retry: false,
    // 只有事务成功才使复盘失效，失败和版本冲突不改变累计或活动计数。
    onSuccess: () => { void client.invalidateQueries({ queryKey: ["improvement-summary"] }); setSaved(true); onSaved(); },
  });
  const set = <K extends keyof ImprovementContent>(key: K, value: ImprovementContent[K]) => setDraft((previous) => ({ ...previous, [key]: value }));
  function close() { if (!mutation.isPending && confirmDiscard(dirty)) onClose(); }
  function required(key: string) {
    return key === "description" || (key === "solution" && draft.status === "resolved") ||
      (key === "validation_evidence" && draft.verification_state !== "not_run") ||
      (key === "deployment_evidence" && ["confirmed", "not_applicable"].includes(draft.deployment_state));
  }
  const invalidResolution = draft.status === "resolved" && !["passed", "not_applicable"].includes(draft.verification_state);
  return <Modal titleId="improvement-editor-title" onClose={close} className="modal-wide">
    <div className="modal-heading"><h2 id="improvement-editor-title">{record ? "编辑问题与改进" : "新增问题与改进"}</h2><button className="icon-button" type="button" aria-label="关闭" onClick={close} disabled={mutation.isPending}><X size={19} /></button></div>
    <form className="settings-form improvement-editor" onSubmit={(event) => { event.preventDefault(); if (!mutation.isPending && !invalidResolution) mutation.mutate(); }}>
      <p className="muted">只记录脱敏后的问题与证据，不填写密钥、完整 Webhook 地址、私有配置或敏感代码。每次保存保留历史快照。</p>
      <UnsavedChangesGuard dirty={dirty || mutation.isPending} />
      <fieldset disabled={mutation.isPending}>
        <label>标题<input required maxLength={160} value={draft.title} onChange={(event) => set("title", event.target.value)} /></label>
        <label>关联项目或功能<input required maxLength={120} value={draft.scope} onChange={(event) => set("scope", event.target.value)} /></label>
        <div className="improvement-form-grid">
          <Choice label="记录类型" value={draft.kind} labels={kindLabels} onChange={(value) => set("kind", value)} />
          <Choice label="分类" value={draft.category} labels={categoryLabels} onChange={(value) => set("category", value)} />
          <Choice label="处理进展" value={draft.status} labels={progressLabels} onChange={(value) => set("status", value)} />
          <Choice label="代码修改" value={draft.code_state} labels={codeLabels} onChange={(value) => set("code_state", value)} />
          <Choice label="本地验证" value={draft.verification_state} labels={verificationLabels} onChange={(value) => set("verification_state", value)} />
          <Choice label="部署生效" value={draft.deployment_state} labels={deploymentLabels} onChange={(value) => set("deployment_state", value)} />
        </div>
        {improvementTextFields.map((field) => <label key={field.key}>{field.label}<textarea rows={field.key === "description" ? 4 : 3} maxLength={field.max} required={required(field.key)} value={draft[field.key]} onChange={(event) => set(field.key, event.target.value)} /></label>)}
        {record && <label>本次进展说明<textarea required rows={2} maxLength={2000} value={note} onChange={(event) => setNote(event.target.value)} /></label>}
      </fieldset>
      {invalidResolution && <p className="form-error" role="alert">已解决需要通过的验证，或验证不适用的说明；不要求已经部署。</p>}
      {mutation.error && <p className="form-error" role="alert">{mutation.error.message}。草稿已保留；不确定是否保存时，请先核对列表或最新详情，避免重复建档。</p>}
      <div className="form-actions"><button type="button" className="button button-secondary" onClick={close} disabled={mutation.isPending}>取消</button><button type="submit" className="button button-primary" disabled={mutation.isPending || invalidResolution}>{mutation.isPending ? "正在保存…" : "保存记录"}</button></div>
    </form>
  </Modal>;
}
