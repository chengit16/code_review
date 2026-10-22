/** @description 合并前审查的只读投影与结果校验；无法解析或缺少覆盖证明时不推断无问题。 */
import type { ReviewComment } from "./types";

/** 合并前一个 MR 版本的服务端事实，不包含凭据。 */
export interface PremergeReview {
  id: number; repository_id: number; repository_name: string; mr_iid: number;
  head_sha: string; status: string; result_json: string | null;
  changed_files?: string | null; context_json?: string | null;
  error: string | null; created_at: string;
}

/** 独立于合并后任务的版本状态。 */
export const premergeLabels: Record<string, string> = { queued: "排队中", running: "审查中", complete: "完成", partial: "部分完成", skipped: "无可审查文件", failed: "失败", superseded: "已失效" };

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function coverageIds(value: unknown): string[] | null {
  if (!Array.isArray(value)) return null;
  if (!value.every((item) => object(item) && typeof item.item_id === "string" && item.item_id.length > 0)) return null;
  return value.map((item: Record<string, unknown>) => String(item.item_id));
}

/** 安全解析发现与完整覆盖证明；旧数据不完整时保留未知结论。 */
export function parsePremergeResult(text: string | null) {
  const comments: ReviewComment[] = [];
  try {
    const raw: unknown = text ? JSON.parse(text) : null;
    if (!object(raw) || !Array.isArray(raw.comments)) return { comments, valid: false, completeCoverage: false };
    for (const item of raw.comments) {
      if (!object(item) || typeof item.path !== "string" || typeof item.content !== "string") return { comments: [], valid: false, completeCoverage: false };
      comments.push({ path: item.path, content: item.content,
        start_line: typeof item.start_line === "number" ? item.start_line : undefined,
        severity: typeof item.severity === "string" ? item.severity : undefined });
    }
    const manifest = object(raw.manifest) ? raw.manifest : null;
    const coverage = manifest && object(manifest.coverage) ? manifest.coverage : null;
    // 覆盖必须逐项对应，不能仅凭终态标签或空失败数组推断全部文件已审查。
    const selected = coverageIds(coverage?.selected);
    const completed = coverageIds(coverage?.completed);
    const reused = coverageIds(coverage?.reused);
    const completeCoverage = manifest?.terminal_state === "complete" && coverage !== null &&
      selected !== null && completed !== null && reused !== null &&
      new Set(selected).size === selected.length &&
      completed.length + reused.length === selected.length &&
      new Set([...completed, ...reused]).size === selected.length &&
      [...completed, ...reused].every((path) => selected.includes(path)) &&
      Array.isArray(coverage.failed) && coverage.failed.length === 0 &&
      Array.isArray(coverage.waived) && coverage.waived.length === 0;
    return { comments, valid: true, completeCoverage };
  } catch {
    return { comments, valid: false, completeCoverage: false };
  }
}
