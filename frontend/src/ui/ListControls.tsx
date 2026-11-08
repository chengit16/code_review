/** @description 通用列表导航、筛选与时间展示；不决定业务状态口径，不读取密钥或执行业务命令。 */
import { Button, Input, Popover, Select, Tag } from "antd";
import { useId, useState } from "react";
import type { ReactNode } from "react";

import type { SelectFieldProps } from "./SelectField";
import { formatTime } from "./format";

/** 状态数量来自调用方的全范围查询；缺失数量保持未知而非零。 */
export function ListStatusNav({ value, labels, counts, onChange, disabled, label = "列表状态" }: {
  /** 当前 URL 状态；all 表示普通全部范围。 */ value: string;
  /** 本业务独立状态名称。 */ labels: Record<string, string>;
  /** 查询成功后的全范围分面；未提供表示未知，字典内省略状态表示零。 */ counts?: Record<string, number>;
  /** 由父页同步 URL 并重置分页。 */ onChange: (value: string) => void;
  /** 写入确认或范围冻结时禁止变化。 */ disabled?: boolean;
  /** 导航的可访问名称。 */ label?: string;
}) {
  return <nav className="list-status-nav" aria-label={label}>{Object.entries(labels).map(([key, text]) => <Button
    key={key} type={value === key ? "primary" : "text"} aria-pressed={value === key} disabled={disabled}
    onClick={() => onChange(key)}>{text} <span className="list-status-count">{counts ? counts[key] ?? 0 : "—"}</span>
  </Button>)}</nav>;
}

/** 与存量筛选接口兼容的 Ant Design 选择器；隐藏字段仅用于当前表单提交。 */
export function ListSelect({ label, value, onValueChange, options, name, required, disabled, placeholder, className }: SelectFieldProps) {
  const id = useId();
  return <div className={`list-select ${className ?? ""}`}><label htmlFor={id}>{label}</label>
    <Select id={id} aria-label={label} value={value || undefined} onChange={onValueChange}
      options={[...options]} virtual={false} disabled={disabled} placeholder={placeholder} />
    {name && <input type="hidden" name={name} value={value} required={required} />}
  </div>;
}

/** 文本输入只在提交后参与查询；URL 更新时由调用方 key 重建草稿。 */
export function ListSearch({ label, value, onSearch, disabled, placeholder }: {
  /** 可见且可访问的搜索名称。 */ label: string;
  /** 已生效的 URL 查询值。 */ value: string;
  /** 提交裁剪后的搜索条件。 */ onSearch: (value: string) => void;
  /** 确认期间锁定输入。 */ disabled?: boolean;
  /** 搜索范围提示。 */ placeholder?: string;
}) {
  const [draft, setDraft] = useState(value);
  return <form className="list-search" onSubmit={(event) => { event.preventDefault(); onSearch(draft.trim()); }}>
    <label>{label}<Input aria-label={label} value={draft} maxLength={200} placeholder={placeholder}
      disabled={disabled} onChange={(event) => setDraft(event.target.value)} /></label>
    <Button htmlType="submit" disabled={disabled}>搜索</Button>
  </form>;
}

/** 已生效条件始终可见；清除只修改调用方指定的命名空间。 */
export function ListConditions({ items, onClear, disabled = false }: {
  /** 非空的已生效条件及中文名称。 */ items: { key: string; label: string; value: string }[];
  /** 清除单一条件，由页面维护 URL。 */ onClear: (key: string) => void;
  /** 写操作期间不允许切换查询范围。 */ disabled?: boolean;
}) {
  return <div className="list-conditions">{items.filter((item) => item.value && item.value !== "all").map((item) =>
    <Tag key={item.key} closable={{ disabled, "aria-label": `清除${item.label}筛选` }} onClose={() => onClear(item.key)}>{item.label}：{item.value}</Tag>)}</div>;
}

/** 使用设备本地时区；跨年显示年份，触控与键盘可读取完整时间及时区。 */
export function ListTime({ value }: { /** SQLite 持久化时间；缺失不补零。 */ value: string | null | undefined }) {
  if (!value) return <>—</>;
  const date = new Date(value.includes("T") ? value : `${value.replace(" ", "T")}Z`);
  if (Number.isNaN(date.getTime())) return <>{value}</>;
  const full = `${formatTime(value)} · ${Intl.DateTimeFormat().resolvedOptions().timeZone}`;
  const short = date.toLocaleString("zh-CN", { ...(date.getFullYear() !== new Date().getFullYear() ? { year: "numeric" } : {}), month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
  return <Popover content={full} trigger={["click", "hover", "focus"]}><button type="button" className="list-time" aria-label={full}><time dateTime={date.toISOString()}>{short}</time></button></Popover>;
}

/** 长正文默认只显示短摘要；完整证据通过明确入口按需展开。 */
export function ListExcerpt({ text, limit = 90 }: { /** 已脱敏的可见正文。 */ text: string | null | undefined; /** 摘要字符数。 */ limit?: number }) {
  if (!text) return <>—</>;
  return text.length <= limit ? <span className="list-excerpt">{text}</span> : <details className="list-excerpt"><summary>{text.slice(0, limit)}… <span>展开全文</span></summary><p>{text}</p></details>;
}

/** 常用筛选与高级内容共用布局，不控制业务表单状态。 */
export function ListToolbar({ children, advanced }: { /** 常用筛选。 */ children: ReactNode; /** 低频筛选或范围切换。 */ advanced?: ReactNode }) {
  return <>{children && <div className="list-toolbar">{children}</div>}{advanced && <details className="list-advanced"><summary>更多筛选</summary><div className="list-toolbar">{advanced}</div></details>}</>;
}
