/** @description 一次裁定编辑绑定一个比较和起始版本。冲突后保留本地输入，并明确读取当前值。 */

import { useMutation } from "@tanstack/react-query";
import { Alert, Button, Input, InputNumber, Modal, Radio, Select, Space, Typography } from "antd";
import { useId, useState } from "react";

import { getAgentComparison, saveComparisonCuration } from "../../api/agentComparisons";
import type { AgentComparison, ComparisonFinding, CurationSnapshot, EvidenceSide, Verdict } from "../../api/agentComparisons";
import { ApiError } from "../../api/client";

import { applyComparisonEdit, savedEdit, verdictLabels } from "./comparisonEdits";
import type { ComparisonEdit } from "./comparisonEdits";

const editTitles = { evaluation: "裁定发现", match: "编辑同根因组", missed: "补录共同漏报" };

function choiceLabel(finding: ComparisonFinding) {
  return `${finding.path}${finding.line === null ? "" : `:${finding.line}`} · ${finding.title}`;
}

/** 修改一条裁定、同根因组或共同漏报；读写权限仍由服务端校验。 */
export function ComparisonEditDialog({ token, jobId, comparison, initial, onClose, onSaved }: {
  token: string; jobId: number; comparison: AgentComparison; initial: ComparisonEdit;
  onClose: () => void; onSaved: (snapshot: CurationSnapshot) => void;
}) {
  const key = useId();
  const [edit, setEdit] = useState(initial);
  const [basis, setBasis] = useState(comparison.curation);
  const [refreshed, setRefreshed] = useState(false);
  const existing = savedEdit(basis.document, edit);
  const save = useMutation({
    mutationFn: (remove: boolean) => saveComparisonCuration(token, jobId, comparison.id, basis.version,
      applyComparisonEdit(basis.document, edit, remove)),
    onSuccess: onSaved,
  });
  const refresh = useMutation({
    mutationFn: () => getAgentComparison(token, jobId, comparison.id, null),
    onSuccess: (latest) => {
      // 只更新已读的服务端基准，本地输入仍留在编辑框中。
      setBasis(latest.curation);
      setRefreshed(true);
      save.reset();
    },
  });
  const busy = save.isPending || refresh.isPending;
  const conflict = save.error instanceof ApiError && save.error.code === "curation_conflict";
  const canSave = edit.kind === "evaluation" || (edit.kind === "match"
    ? Boolean(edit.value.label.trim() && edit.value.ocr_ids.length && edit.value.agent_ids.length)
    : Boolean(edit.value.title.trim() && edit.value.path.trim()));
  const matches = basis.document.matches.filter((group) => edit.kind === "match" && group.id !== edit.value.id);
  const matchOptions = (findings: ComparisonFinding[], side: "ocr_ids" | "agent_ids") => findings.map((finding) => {
    const existingGroup = matches.find((group) => group[side].includes(finding.id));
    return { value: finding.id, label: `${choiceLabel(finding)}${existingGroup ? ` · ${existingGroup.label}` : ""}` };
  });
  function changeNote(note: string) {
    if (edit.kind === "evaluation") setEdit({ ...edit, value: { ...edit.value, note } });
    if (edit.kind === "missed") setEdit({ ...edit, value: { ...edit.value, note } });
  }
  return <Modal open title={editTitles[edit.kind]} onCancel={busy ? undefined : onClose} closable={!busy}
    mask={{ closable: !busy }} cancelButtonProps={{ disabled: busy }} confirmLoading={save.isPending}
    okText="保存裁定" okButtonProps={{ disabled: !canSave || conflict || refresh.isPending }} onOk={() => save.mutate(false)}>
    <div className="agent-editor-fields">
      {save.error && <Alert type="error" showIcon title={save.error.message} description={conflict ? "草稿已保留。读取最新裁定后，可以核对该条的当前值再保存。" : "草稿已保留。"}
        action={conflict ? <Button size="small" loading={refresh.isPending} onClick={() => refresh.mutate()}>读取最新裁定</Button> : undefined} />}
      {refresh.error && <Alert type="error" title={refresh.error.message} />}
      {refreshed && <Alert type="info" title={`已读取裁定 v${basis.version}`} description={existing && "verdict" in existing
        ? `该条当前为「${verdictLabels[existing.verdict]}」${existing.note ? ` · ${existing.note}` : ""}`
        : existing && "label" in existing ? `当前分组：${existing.label}`
          : existing && "title" in existing ? `当前漏报：${existing.title}` : "当前版本中没有这条裁定。"} />}
      {edit.kind === "evaluation" && <>
        <Typography.Text strong>{edit.finding.title}</Typography.Text>
        <fieldset><legend>证据是否支持发现</legend><Radio.Group value={edit.value.verdict}
          onChange={(event) => setEdit({ ...edit, value: { ...edit.value, verdict: event.target.value as Verdict } })}
          options={Object.entries(verdictLabels).map(([value, label]) => ({ value, label }))} /></fieldset>
        <label htmlFor={`${key}-value`}>是否值得处理</label>
        <Select id={`${key}-value`} value={edit.value.worth_fixing === null ? "unknown" : edit.value.worth_fixing ? "yes" : "no"}
          options={[{ value: "unknown", label: "待判断" }, { value: "yes", label: "值得处理" }, { value: "no", label: "无需处理" }]}
          onChange={(value) => setEdit({ ...edit, value: { ...edit.value, worth_fixing: value === "unknown" ? null : value === "yes" } })} />
      </>}
      {edit.kind === "match" && <>
        <label htmlFor={`${key}-label`}>共同根因</label><Input id={`${key}-label`} maxLength={200} value={edit.value.label}
          onChange={(event) => setEdit({ ...edit, value: { ...edit.value, label: event.target.value } })} />
        <label htmlFor={`${key}-ocr`}>OCR 发现</label><Select id={`${key}-ocr`} mode="multiple" optionFilterProp="label"
          value={edit.value.ocr_ids} options={matchOptions(comparison.ocr.findings, "ocr_ids")}
          onChange={(ids: string[]) => setEdit({ ...edit, value: { ...edit.value, ocr_ids: ids } })} />
        <label htmlFor={`${key}-agent`}>Agent 发现</label><Select id={`${key}-agent`} mode="multiple" optionFilterProp="label"
          value={edit.value.agent_ids} options={matchOptions(comparison.agent.findings, "agent_ids")}
          onChange={(ids: string[]) => setEdit({ ...edit, value: { ...edit.value, agent_ids: ids } })} />
        {matches.length > 0 && <Typography.Text type="secondary">选入已分组的发现会将它移到本组。原组若只剩单侧，会解除该组关系。</Typography.Text>}
      </>}
      {edit.kind === "missed" && <>
        <label htmlFor={`${key}-title`}>问题说明</label><Input id={`${key}-title`} maxLength={300} value={edit.value.title}
          onChange={(event) => setEdit({ ...edit, value: { ...edit.value, title: event.target.value } })} />
        <label htmlFor={`${key}-path`}>文件路径</label><Input id={`${key}-path`} maxLength={500} value={edit.value.path}
          onChange={(event) => setEdit({ ...edit, value: { ...edit.value, path: event.target.value } })} />
        <Space wrap>
          <label htmlFor={`${key}-side`}>代码侧</label><Select id={`${key}-side`} value={edit.value.side ?? "unknown"}
            options={[{ value: "unknown", label: "未记录" }, { value: "head", label: "新版" }, { value: "base", label: "旧版" }]}
            onChange={(value: EvidenceSide | "unknown") => setEdit({ ...edit, value: { ...edit.value, side: value === "unknown" ? null : value } })} />
          <label htmlFor={`${key}-line`}>行号</label><InputNumber id={`${key}-line`} min={1} precision={0} value={edit.value.line}
            onChange={(line) => setEdit({ ...edit, value: { ...edit.value, line } })} />
        </Space>
      </>}
      {edit.kind !== "match" && <><label htmlFor={`${key}-note`}>备注</label>
        <Input.TextArea id={`${key}-note`} rows={3} value={edit.value.note} maxLength={2000}
          onChange={(event) => changeNote(event.target.value)} /></>}
      {existing && <Button danger type="link" disabled={busy || conflict} onClick={() => save.mutate(true)}>
        {edit.kind === "match" ? "拆除分组" : "撤销这条裁定"}</Button>}
    </div>
  </Modal>;
}
