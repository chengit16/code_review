/** @description 列表分页使用 Ant Design 控件；页码仍由 URL 管理，加载或确认期间锁定。 */
import { Button, Input, Select } from "antd";
import { useId, useState } from "react";

/** 保留 25/50/100、明确跳页与可访问名称，不改其他存量列表的分页契约。 */
export function ListPagination({ label = "列表分页", total, page, pageSize, disabled, onPage, onPageSize }: {
  /** 分页区域名称，不包含业务权限。 */ label?: string;
  /** 未确认的总量显示未知，不伪装为零。 */ total: number | undefined;
  /** 服务端或 URL 页码。 */ page: number;
  /** 每页条数。 */ pageSize: number;
  /** 查询或写入中禁止更改范围。 */ disabled: boolean;
  /** 由父页更新 URL。 */ onPage: (page: number) => void;
  /** 更新条数且重置页码。 */ onPageSize: (size: number) => void;
}) {
  const id = useId();
  const pages = Math.max(1, Math.ceil((total ?? 0) / pageSize));
  return <nav className="jobs-pagination" aria-label={label}>
    <span aria-live="polite">{total === undefined ? "总量待确认" : `共 ${total} 条 · 第 ${page} / ${pages} 页`}</span>
    <div className="jobs-pagination-controls"><label htmlFor={id}>每页</label><Select virtual={false} id={id} aria-label="每页条数" value={pageSize} disabled={disabled} onChange={onPageSize} options={[25, 50, 100].map((size) => ({ value: size, label: `${size} 条` }))} />
      <Button aria-label="上一页" disabled={disabled || page <= 1} onClick={() => onPage(page - 1)}>上一页</Button>
      <Button aria-label="下一页" disabled={disabled || page >= pages} onClick={() => onPage(page + 1)}>下一页</Button></div>
    <PageJump key={`${page}-${pages}`} page={page} pages={pages} disabled={disabled} onPage={onPage} />
  </nav>;
}
function PageJump({ page, pages, disabled, onPage }: { page: number; pages: number; disabled: boolean; onPage: (page: number) => void }) {
  const [target, setTarget] = useState(String(page));
  return <form className="jobs-pagination-jump" onSubmit={(event) => { event.preventDefault(); const next = Number(target); if (!disabled && Number.isInteger(next) && next >= 1 && next <= pages) onPage(next); }}>
    <label>跳至<Input aria-label="跳转页码" type="number" min={1} max={pages} required value={target} disabled={disabled} onChange={(event) => setTarget(event.target.value)} />页</label><Button htmlType="submit" disabled={disabled || pages <= 1}>跳转</Button>
  </form>;
}
