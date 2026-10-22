/** @description 展示持久化变更统计与评审范围，不读取或展示完整代码 Diff。 */

import type { ReviewJobDetail } from "../api/types";

/** 历史任务没有变更统计时，仍展示 OCR 预览中的文件。 */
export function JobFiles({ job }: { /** 已鉴权的任务详情。 */ job: ReviewJobDetail }) {
  const raw: unknown = job.changed_files ? JSON.parse(job.changed_files) : [];
  const files: { path: string; added?: number; deleted?: number }[] = Array.isArray(raw)
    ? raw.filter((item): item is { path: string; added?: number; deleted?: number } => typeof item === "object" && item !== null && typeof item.path === "string") : [];
  const preview = job.result?.preview?.files ?? [];
  const paths = [...new Set([...files.map((f) => f.path), ...preview.map((f) => f.path)])];
  return <section className="section job-files-section"><div className="section-head"><h2>变更文件</h2><span>{paths.length} 个文件</span></div><div className="table-scroll"><table><thead><tr><th>文件</th><th>新增</th><th>删除</th><th>评审范围</th></tr></thead><tbody>{paths.map((path) => { const stats = files.find((f) => f.path === path); const scope = preview.find((f) => f.path === path); return <tr key={path}><td className="file-path mono" title={path}>{path}</td><td className="file-stat file-stat--added">{stats?.added ?? "未知"}</td><td className="file-stat file-stat--deleted">{stats?.deleted ?? "未知"}</td><td><span className={`scope-badge ${scope?.will_review ? "scope-badge--included" : scope ? "scope-badge--excluded" : ""}`}>{scope ? scope.will_review ? "纳入" : "排除" : "未记录"}</span>{scope && !scope.will_review && scope.exclude_reason && <small className="table-sub">{scope.exclude_reason}</small>}</td></tr>; })}{paths.length === 0 && <tr><td colSpan={4} className="empty-row">尚无变更文件记录</td></tr>}</tbody></table></div></section>;
}
