/** @description 展示持久化变更统计与评审范围，不读取或展示完整代码 Diff。 */

import type { ReviewJobDetail } from "../api/types";
import { ListExcerpt } from "../ui/ListControls";
import { ListTable } from "../ui/ListTable";

/** 历史任务没有变更统计时，仍展示 OCR 预览中的文件。 */
export function JobFiles({ job }: { /** 已鉴权的任务详情。 */ job: ReviewJobDetail }) {
  let raw: unknown = [];
  let unreadable = false;
  try { raw = job.changed_files ? JSON.parse(job.changed_files) : []; } catch { unreadable = true; }
  const files: { path: string; added?: number; deleted?: number }[] = Array.isArray(raw)
    ? raw.filter((item): item is { path: string; added?: number; deleted?: number } => typeof item === "object" && item !== null && typeof item.path === "string") : [];
  const preview = job.result?.preview?.files ?? [];
  const paths = [...new Set([...files.map((f) => f.path), ...preview.map((f) => f.path)])];
  return <section className="section job-files-section"><div className="section-head"><h2>变更文件</h2><span>{paths.length} 个文件</span></div>{unreadable && <p className="attention-note">变更统计格式不可用，仅展示已保存的范围预览。</p>}<ListTable rowKey="path" dataSource={paths.map((path) => ({ path, stats: files.find((file) => file.path === path), scope: preview.find((file) => file.path === path) }))} pagination={false} scroll={{ x: 650 }} locale={{ emptyText: "尚无变更文件记录" }} columns={[
    { title: "文件", key: "path", render: (_, item) => <ListExcerpt text={item.path} /> },
    { title: "新增", key: "added", render: (_, item) => item.stats?.added ?? "未知" },
    { title: "删除", key: "deleted", render: (_, item) => item.stats?.deleted ?? "未知" },
    { title: "评审范围", key: "scope", render: (_, item) => <>{item.scope ? item.scope.will_review ? "纳入" : "排除" : "未记录"}{item.scope && !item.scope.will_review && <span className="list-secondary"><ListExcerpt text={item.scope.exclude_reason} /></span>}</> },
  ]} /></section>;
}
