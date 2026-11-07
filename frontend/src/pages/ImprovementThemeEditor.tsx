/** @description 优化主题与阶段草稿；阶段结果、验证、部署和关联问题分别记录。 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, X } from "lucide-react";
import { useRef, useState } from "react";
import type { FormEvent } from "react";

import { createCommandId } from "../api/commandId";
import { createImprovementTheme, updateImprovementTheme } from "../api/improvements";
import type { ImprovementPhase, ImprovementThemeContent, ImprovementThemeRecord } from "../api/improvements";
import { Modal } from "../ui/Modal";
import { SelectField } from "../ui/SelectField";
import { confirmDiscard, UnsavedChangesGuard } from "../ui/UnsavedChangesGuard";
import { categoryLabels, codeLabels, deploymentLabels, verificationLabels } from "./improvementFields";
import { ThemeProblemPicker } from "./ThemeProblemPicker";

type ThemeContentFields = Omit<ImprovementThemeContent, "phases">;
const initialTheme: ImprovementThemeContent = { title: "", category: "other", status: "planned", scope: "平台",
  objective: "", rationale: "", outcome: "", next_steps: "", references: "", phases: [] };
const phaseStatusLabels = { planned: "待开始", active: "进行中", completed: "已完成", deferred: "暂缓" };
const themeStatusLabels = { planned: "待开始", active: "进行中", paused: "已暂停", completed: "已完成", deferred: "暂缓" };

function Choice<K extends string>({ label, value, labels, onChange }: {
  label: string; value: K; labels: Record<K, string>; onChange: (value: K) => void;
}) {
  return <SelectField label={label} value={value} options={Object.entries<string>(labels).map(([key, text]) => ({ value: key, label: text }))} onValueChange={(next) => { if (next in labels) onChange(next as K); }} />;
}

/** 默认阶段明确显示未知执行状态，完成主题前须逐阶段补齐证据。 */
function emptyPhase(): ImprovementPhase {
  return { title: "", goal: "", status: "planned", solution: "", code_state: "unchanged",
    verification_state: "not_run", validation_evidence: "", deployment_state: "not_deployed",
    deployment_evidence: "", next_steps: "" };
}

function snapshot(record: ImprovementThemeRecord): ImprovementThemeContent {
  return { title: record.title, category: record.category, status: record.status, scope: record.scope,
    objective: record.objective, rationale: record.rationale, outcome: record.outcome,
    next_steps: record.next_steps, references: record.references, phases: record.phases };
}

/** 完整快照按主题版本保存；已存在记录的关系变化也保留在历史。 */
export function ImprovementThemeEditor({ token, record, onClose, onSaved }: {
  /** 管理员内存会话。 */ token: string;
  /** 缺省表示创建主题。 */ record?: ImprovementThemeRecord;
  /** 丢弃或保存成功后关闭。 */ onClose: () => void;
  /** 服务端确认事务提交后触发。 */ onSaved: (record: ImprovementThemeRecord) => void;
}) {
  const client = useQueryClient();
  const [initial] = useState(() => record ? snapshot(record) : initialTheme);
  const [draft, setDraft] = useState(initial);
  const [selected, setSelected] = useState<number[]>(record?.improvement_ids ?? []);
  const [initialLinks] = useState(record?.improvement_ids ?? []);
  const [note, setNote] = useState("");
  const clientKey = useRef<string | null>(null);
  const [saved, setSaved] = useState(false);
  const dirty = !saved && (JSON.stringify(initial) !== JSON.stringify(draft) ||
    JSON.stringify([...selected].sort()) !== JSON.stringify([...initialLinks].sort()) || Boolean(note));
  const mutation = useMutation({
    mutationFn: () => {
      if (record) return updateImprovementTheme(token, record.id, draft, selected, record.version, note);
      // 幂等键只在保存时生成一次；生成失败保留草稿，网络失败重试也不能换键。
      clientKey.current ??= createCommandId();
      return createImprovementTheme(token, draft, selected, clientKey.current);
    },
    retry: false,
    // 主题、阶段与关联成功提交后一起影响复盘；冲突时保留原缓存和草稿。
    onSuccess: (updated) => { void client.invalidateQueries({ queryKey: ["improvement-summary"] }); setSaved(true); onSaved(updated); },
  });
  function set<K extends keyof ThemeContentFields>(key: K, value: ThemeContentFields[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }
  function updatePhase(index: number, value: Partial<ImprovementPhase>) {
    setDraft((current) => ({ ...current, phases: current.phases.map((phase, position) =>
      position === index ? { ...phase, ...value } : phase) }));
  }
  function close() { if (!mutation.isPending && confirmDiscard(dirty)) onClose(); }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!mutation.isPending && !invalidCompletion) mutation.mutate();
  }
  const invalidCompletion = draft.status === "completed" && (!draft.outcome.trim() || !draft.phases.length ||
    draft.phases.some((phase) => phase.status !== "completed"));
  const textFields: { key: "objective" | "rationale" | "outcome" | "next_steps" | "references"; label: string }[] = [
    { key: "objective", label: "总体目标" }, { key: "rationale", label: "背景与原因" },
    { key: "outcome", label: "整体结果" }, { key: "next_steps", label: "遗留与下一步" },
    { key: "references", label: "关联文档、提交或外部证据" },
  ];
  return <Modal titleId="theme-editor-title" onClose={close} className="modal-wide theme-editor-modal">
    <div className="modal-heading"><h2 id="theme-editor-title">{record ? "编辑优化主题" : "新增优化主题"}</h2><button className="icon-button" type="button" aria-label="关闭" disabled={mutation.isPending} onClick={close}><X size={19} /></button></div>
    <form className="settings-form theme-editor" onSubmit={submit}>
      <p className="muted">主题串联优化目标和多个实施阶段。关联已有问题不会更改其状态；手动记录的证据不代表平台自动执行检查。</p>
      <UnsavedChangesGuard dirty={dirty || mutation.isPending} />
      <fieldset disabled={mutation.isPending}>
        <label>主题名称<input required maxLength={160} value={draft.title} onChange={(event) => set("title", event.target.value)} /></label>
        <div className="improvement-form-grid"><label>关联范围<input required maxLength={120} value={draft.scope} onChange={(event) => set("scope", event.target.value)} /></label>
          <Choice label="分类" value={draft.category} labels={categoryLabels} onChange={(value) => set("category", value)} />
          <Choice label="主题进展" value={draft.status} labels={themeStatusLabels} onChange={(value) => set("status", value)} /></div>
        {textFields.map((field) => <label key={field.key}>{field.label}<textarea rows={field.key === "objective" ? 3 : 2} maxLength={field.key === "references" ? 5000 : 10000} required={field.key === "objective" || (field.key === "outcome" && draft.status === "completed")} value={draft[field.key]} onChange={(event) => set(field.key, event.target.value)} /></label>)}
        <div className="theme-phases-heading"><h3>实施阶段</h3><button className="button button-secondary" type="button" disabled={draft.phases.length >= 50} onClick={() => setDraft((current) => ({ ...current, phases: [...current.phases, emptyPhase()] }))}><Plus size={16} />添加阶段</button></div>
        {draft.phases.map((phase, index) => <fieldset className="theme-phase" key={index}>
          <div className="theme-phase-heading"><h4>阶段 {index + 1}</h4><button className="icon-button" type="button" aria-label={`删除阶段 ${index + 1}`} onClick={() => setDraft((current) => ({ ...current, phases: current.phases.filter((_, position) => position !== index) }))}><Trash2 size={16} /></button></div>
          <label>阶段名称<input required maxLength={160} value={phase.title} onChange={(event) => updatePhase(index, { title: event.target.value })} /></label>
          <label>阶段目标<textarea required rows={2} maxLength={5000} value={phase.goal} onChange={(event) => updatePhase(index, { goal: event.target.value })} /></label>
          <div className="improvement-form-grid"><Choice label="阶段进展" value={phase.status} labels={phaseStatusLabels} onChange={(value) => updatePhase(index, { status: value })} />
            <Choice label="代码修改" value={phase.code_state} labels={codeLabels} onChange={(value) => updatePhase(index, { code_state: value })} />
            <Choice label="本地验证" value={phase.verification_state} labels={verificationLabels} onChange={(value) => updatePhase(index, { verification_state: value })} />
            <Choice label="部署生效" value={phase.deployment_state} labels={deploymentLabels} onChange={(value) => updatePhase(index, { deployment_state: value })} /></div>
          <label>处理办法<textarea rows={2} maxLength={10000} required={phase.status === "completed"} value={phase.solution} onChange={(event) => updatePhase(index, { solution: event.target.value })} /></label>
          <label>验证命令、结果与范围<textarea rows={2} maxLength={10000} required={phase.verification_state !== "not_run"} value={phase.validation_evidence} onChange={(event) => updatePhase(index, { validation_evidence: event.target.value })} /></label>
          <label>部署环境与生效证据<textarea rows={2} maxLength={10000} required={["confirmed", "not_applicable"].includes(phase.deployment_state)} value={phase.deployment_evidence} onChange={(event) => updatePhase(index, { deployment_evidence: event.target.value })} /></label>
          <label>该阶段遗留与下一步<textarea rows={2} maxLength={5000} value={phase.next_steps} onChange={(event) => updatePhase(index, { next_steps: event.target.value })} /></label>
        </fieldset>)}
        <ThemeProblemPicker token={token} selected={selected} onChange={setSelected} disabled={mutation.isPending} />
        {record && <label>本次进展说明<textarea required maxLength={2000} rows={2} value={note} onChange={(event) => setNote(event.target.value)} /></label>}
      </fieldset>
      {invalidCompletion && <p className="form-error" role="alert">主题完成需要整体结果，并且所有实施阶段都已完成。</p>}
      {mutation.error && <p className="form-error" role="alert">{mutation.error.message}。草稿保留；如果无法确认是否保存，请先读取主题和历史再重试。</p>}
      <div className="form-actions"><button type="button" className="button button-secondary" onClick={close} disabled={mutation.isPending}>取消</button><button type="submit" className="button button-primary" disabled={mutation.isPending || invalidCompletion}>{mutation.isPending ? "正在保存…" : "保存主题"}</button></div>
    </form>
  </Modal>;
}
