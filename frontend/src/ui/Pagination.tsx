/** @description 列表统一分页；条数和页码由页面写入 URL，不扩大批量操作范围。 */
import { useState } from "react";

/** 在当前筛选范围内切页；加载和写入期间禁止改变范围。 */
export function Pagination({ label, total, page, pageSize, disabled, onPage, onPageSize }: {
  /** 分页区域的可访问名称。 */ label: string;
  /** 当前条件下的总条数。 */ total: number;
  /** 服务端返回或地址栏指定的页码。 */ page: number;
  /** 每页条数。 */ pageSize: number;
  /** 查询或批量写入期间锁定。 */ disabled: boolean;
  /** 切换到指定页。 */ onPage: (page: number) => void;
  /** 修改条数并重置页码。 */ onPageSize: (size: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return <div className="pagination" aria-label={label}>
    <span aria-live="polite">共 {total} 条 · 第 {page} / {pages} 页</span>
    <label className="pagination-size">每页<select aria-label="每页条数" value={pageSize} disabled={disabled} onChange={(event) => onPageSize(Number(event.target.value))}>{[25, 50, 100].map((size) => <option key={size} value={size}>{size} 条</option>)}</select></label>
    <button className="button button-secondary" aria-label="上一页" disabled={disabled || page <= 1} onClick={() => onPage(page - 1)}>上一页</button>
    <button className="button button-secondary" aria-label="下一页" disabled={disabled || page >= pages} onClick={() => onPage(page + 1)}>下一页</button>
    <PageJump key={`${page}-${pages}`} page={page} pages={pages} disabled={disabled} onPage={onPage} />
  </div>;
}

function PageJump({ page, pages, disabled, onPage }: { page: number; pages: number; disabled: boolean; onPage: (page: number) => void }) {
  const [target, setTarget] = useState(String(page));
  return <form className="pagination-jump" onSubmit={(event) => { event.preventDefault(); const next = Number(target); if (!disabled && Number.isInteger(next) && next >= 1 && next <= pages) onPage(next); }}>
    <label>跳至<input aria-label="跳转页码" type="number" min={1} max={pages} required value={target} disabled={disabled} onChange={(event) => setTarget(event.target.value)} />页</label><button className="button button-secondary" disabled={disabled || pages <= 1}>跳转</button>
  </form>;
}
