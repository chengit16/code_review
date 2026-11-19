/** @description 评审规则编辑布局；只维护草稿交互，保存、删除与离开保护由父页处理。 */
import { Button, Checkbox, Empty, Input, Tag } from "antd";
import { ArrowDown, ArrowUp, Plus, Save, Trash2 } from "lucide-react";
import { useId } from "react";
import type { FormEvent } from "react";

import type { ReviewRuleDocument } from "../api/types";

/** 规则正文作为主要工作区，路径过滤在桌面并排显示；不发起预览或远端调用。 */
export function ReviewRuleEditor({ value, includeText, excludeText, scopeName, configured, busy, saving, error, feedback,
  onChange, onIncludeChange, onExcludeChange, onSubmit, onDelete }: {
  /** 当前范围的规则草稿，不含服务端配置标识。 */ value: ReviewRuleDocument;
  /** 每行一条的纳入模式草稿。 */ includeText: string;
  /** 每行一条的排除模式草稿。 */ excludeText: string;
  /** 保存栏显示的当前范围名称。 */ scopeName: string;
  /** 已存在配置时才允许删除；不代表当前草稿已保存。 */ configured: boolean;
  /** 保存、删除或恢复期间冻结所有编辑控件。 */ busy: boolean;
  /** 保存请求进行中，控制主按钮反馈。 */ saving: boolean;
  /** 本地校验或服务端写入错误，失败保留草稿。 */ error?: string;
  /** 已完成操作的反馈，不代表后续评审已使用该配置。 */ feedback: string;
  /** 整体替换规则草稿；只修改本地状态。 */ onChange: (value: ReviewRuleDocument) => void;
  /** 修改纳入文本，不立即规范化或写入。 */ onIncludeChange: (value: string) => void;
  /** 修改排除文本，不立即规范化或写入。 */ onExcludeChange: (value: string) => void;
  /** 校验并保存仍由父页执行。 */ onSubmit: (event: FormEvent) => void;
  /** 请求删除配置，由父页确认目标与副作用。 */ onDelete: () => void;
}) {
  const fieldId = useId();
  function update(index: number, patch: Partial<ReviewRuleDocument["rules"][number]>) {
    onChange({ ...value, rules: value.rules.map((entry, position) => position === index ? { ...entry, ...patch } : entry) });
  }
  function move(index: number, offset: number) {
    const rules = [...value.rules];
    [rules[index], rules[index + offset]] = [rules[index + offset], rules[index]];
    onChange({ ...value, rules });
  }
  return <form className="rules-editor-form" onSubmit={onSubmit}>
    <div className="rules-editor-grid">
      <section className="rules-editor-main" aria-label="规则条目编辑">
        <div className="rules-section-heading"><div><h3>规则条目 <Tag>{value.rules.length}</Tag></h3><p>按顺序维护文件匹配模式和审核要求</p></div>
          <Button icon={<Plus size={16} />} disabled={busy} onClick={() => onChange({ ...value, rules: [...value.rules, { path: "", rule: "", merge_system_rule: true }] })}>添加规则</Button>
        </div>
        {value.rules.length === 0 && <div className="rules-editor-empty"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前范围尚无自定义条目" /><p>添加规则，或在路径过滤中设置文件范围。</p></div>}
        <div className="rules-editor-list">{value.rules.map((entry, index) => <article className="rules-entry" aria-label={`规则 ${index + 1}`} key={index}>
          <header className="rules-entry-heading"><strong>规则 {index + 1}</strong><div className="rules-entry-actions">
            <Button type="text" icon={<ArrowUp size={16} />} aria-label={`上移规则 ${index + 1}`} title="上移规则" disabled={busy || index === 0} onClick={() => move(index, -1)} />
            <Button type="text" icon={<ArrowDown size={16} />} aria-label={`下移规则 ${index + 1}`} title="下移规则" disabled={busy || index === value.rules.length - 1} onClick={() => move(index, 1)} />
            <Button type="text" danger icon={<Trash2 size={16} />} aria-label={`删除规则 ${index + 1}`} title="删除规则" disabled={busy} onClick={() => onChange({ ...value, rules: value.rules.filter((_, position) => position !== index) })} />
          </div></header>
          <div className="rules-entry-path"><label htmlFor={`${fieldId}-path-${index}`}>文件路径模式</label><Input id={`${fieldId}-path-${index}`} value={entry.path} disabled={busy} onChange={(event) => update(index, { path: event.target.value })} placeholder="例如 src/**/*.go" /></div>
          <div className="rules-entry-body"><label htmlFor={`${fieldId}-body-${index}`}>审核内容</label><Input.TextArea id={`${fieldId}-body-${index}`} autoSize={{ minRows: 7, maxRows: 18 }} value={entry.rule} disabled={busy} onChange={(event) => update(index, { rule: event.target.value })} placeholder="说明要检查的内容、判断依据和输出要求。" /></div>
          <Checkbox checked={entry.merge_system_rule} disabled={busy} onChange={(event) => update(index, { merge_system_rule: event.target.checked })}>同时保留 OCR 内置语言规则</Checkbox>
        </article>)}</div>
      </section>
      <aside className="rules-path-panel" aria-label="路径过滤">
        <div className="rules-section-heading"><div><h3>路径过滤</h3><p>每行一个路径模式</p></div></div>
        <div className="rules-path-field"><label htmlFor={`${fieldId}-include`}>额外纳入的路径</label><Input.TextArea id={`${fieldId}-include`} autoSize={{ minRows: 3, maxRows: 8 }} value={includeText} disabled={busy} onChange={(event) => onIncludeChange(event.target.value)} placeholder="**/*.test.ts" /></div>
        <div className="rules-path-field"><label htmlFor={`${fieldId}-exclude`}>排除的路径</label><Input.TextArea id={`${fieldId}-exclude`} autoSize={{ minRows: 5, maxRows: 10 }} value={excludeText} disabled={busy} onChange={(event) => onExcludeChange(event.target.value)} placeholder={"**/node_modules/**\n**/dist/**\n**/generated/**"} /></div>
        <p className="rules-path-note">规则条目和路径过滤将一并保存到当前配置范围。</p>
      </aside>
    </div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {feedback && <p className="form-success" role="status">{feedback}</p>}
    <footer className="rules-save-bar"><div><strong>{scopeName}</strong><span>{value.rules.length} 条规则 · 保存后用于后续评审</span></div>
      <div className="rules-save-actions"><Button type="text" danger icon={<Trash2 size={16} />} disabled={!configured || busy} onClick={onDelete}>删除配置</Button><Button type="primary" htmlType="submit" icon={<Save size={16} />} loading={saving} disabled={busy}>保存规则</Button></div>
    </footer>
  </form>;
}
