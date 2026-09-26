/** @description 展示 OCR 覆盖失败和豁免的安全原因字段，不回显原始模型内容。 */
import type { ReviewJobDetail } from "../api/types";

interface Item { item_id?: string; path?: string; classification?: string; reason?: string; message?: string }

function project(items: unknown[]): Item[] {
  return items.map((value) => {
    if (!value || typeof value !== "object") return {};
    const raw = value as Record<string, unknown>;
    return Object.fromEntries(["item_id", "path", "classification", "reason", "message"]
      .filter((key) => typeof raw[key] === "string")
      .map((key) => [key, String(raw[key]).slice(0, 500)])) as Item;
  });
}

/** 分类和原因来自 OCR manifest；缺失时明确标为未提供。 */
export function CoverageReasons({ job }: { /** 已鉴权的任务详情。 */ job: ReviewJobDetail }) {
  const coverage = job.result?.manifest?.coverage;
  const groups = [{ label: "失败文件", items: project(coverage?.failed ?? []) }, { label: "豁免文件", items: project(coverage?.waived ?? []) }];
  if (groups.every((group) => !group.items.length)) return null;
  return <section className="section"><div className="section-head"><h2>失败与豁免原因</h2></div>{groups.map((group) => group.items.length > 0 && <div key={group.label}><h3>{group.label}</h3><div className="table-scroll"><table><thead><tr><th>文件或项</th><th>分类</th><th>原因</th></tr></thead><tbody>{group.items.map((item, index) => <tr key={index}><td className="mono">{item.path ?? item.item_id ?? "未提供"}</td><td>{item.classification ?? "未提供"}</td><td>{item.reason ?? item.message ?? "未提供"}</td></tr>)}</tbody></table></div></div>)}</section>;
}
