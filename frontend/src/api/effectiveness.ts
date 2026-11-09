/** @description 项目首页的同源业务统计契约与只读服务；缺少新增聚合不补零。 */
import { apiRequest } from "./client";

/** 当前开放问题的固定分级；未识别级别统一为未分级。 */
export type SeverityLevel = "critical" | "high" | "medium" | "low" | "unclassified";

/** 当前发现反馈，不与问题处置状态混算。 */
export type FeedbackKind = "helpful" | "false_positive" | "ignored" | "unmarked";

/** 同一有效发现集合的互斥计数。 */
export interface QualityCounts {
  /** 有效发现总数。 */ total: number;
  /** 当前认可反馈。 */ helpful: number;
  /** 当前误报反馈。 */ false_positive: number;
  /** 明确不采纳，不等于误报或未评价。 */ ignored: number;
  /** 没有有效价值评价的发现；旧版“已修复”值归入此类。 */ unmarked: number;
}

/** 当前问题状态投影到有效发现集合；未知不冒充待处理或已关闭。 */
export interface DispositionCounts {
  /** 同范围有效发现总条数。 */ total: number;
  /** 待处理条数。 */ open: number;
  /** 人工已修复条数。 */ fixed: number;
  /** 人工决定不处理的条数。 */ ignored: number;
  /** 人工确认发现不成立的条数。 */ false_positive: number;
  /** 关联缺失或状态无法解析的条数。 */ unknown: number;
}

/** 质量汇总和样本使用相同闭开窗口，统计不返回正文。 */
export interface ReviewQuality {
  /** 新服务的当前处置集合；缺失时提示升级，不用历史评价替代。 */
  dispositions?: {
    summary: DispositionCounts;
    trend: Array<DispositionCounts & { day: string }>;
    categories: Array<DispositionCounts & { name: string }>;
    projects: Array<DispositionCounts & { id: number; name: string }>;
  };
  /** 本期质量计数。 */ summary: QualityCounts;
  /** 发现产生日分组，反馈是当前结果。 */ trend: Array<QualityCounts & { day: string }>;
  /** 全部类别，在界面分页而非静默截断。 */ categories: Array<QualityCounts & { name: string }>;
  /** 当前范围内有发现的项目。 */ projects: Array<QualityCounts & { id: number; name: string }>;
  /** 缺少可靠来源的记录，非零时必须提示待核实。 */ unavailable_sources: number;
  /** UTC 窗口起点（含）。 */ since: string;
  /** UTC 窗口终点（不含）。 */ until: string;
}

/** 分页样本白名单，身份和版本可核对，不提供批量写入。 */
export interface QualityFinding {
  /** 稳定发现身份。 */ finding_id: string;
  /** 所属任务。 */ job_id: number;
  /** 来源项目。 */ repository_id: number;
  /** 项目名称。 */ repository_name: string;
  /** 根尝试版本。 */ source_attempt: number;
  /** 有效补审版本，初审为零。 */ revision: number;
  /** 补审批次，初审为空。 */ recovery_id: number | null;
  /** 原始评论索引。 */ comment_index: number;
  /** 来源 UTC 时间。 */ generated_at: string;
  /** 发现类别，不使用问题最新类别替代。 */ category: string;
  /** 来源级别。 */ severity: string;
  /** 文件路径。 */ path: string;
  /** 最多 160 字摘要，仅在用户展开样本后读取。 */ excerpt: string;
  /** 关联问题，旧数据可能缺失。 */ issue_id: number | null;
  /** 关联问题的当前处置。 */ issue_status: string | null;
  /** 当前人工反馈。 */ feedback: FeedbackKind;
}

/** 同一 SQLite 读取快照；项目作用所有数据，时间只裁剪期间指标。 */
export interface EffectivenessSnapshot {
  /** UTC 自然日窗口。 */ days: number;
  /** 期间流量及当前存量，不能混算为处置率。 */
  summary: {
    reviews: number; failed_reviews: number; generated: number; published: number;
    new_issues: number; new_still_open: number; fixed: number; ignored: number;
    open_now: number; feedback_marked: number; false_positive: number;
  };
  /** 当前开放问题，兼容尚未提供分级的旧 API。 */
  current_issues?: { open_count: number; severity_counts: Record<SeverityLevel, number> };
  /** 逐日新增及当前仍标记修复的问题。 */ trend: Array<{ day: string; new: number; fixed: number }>;
  /** 本期出现次数前二十类，不等同于全部当前问题分布。 */
  categories: Array<{ category: string; generated: number; issues: number; open_issues: number }>;
  /** 按当前开放问题降序排列；新增字段在旧 API 中可能缺失。 */
  projects: Array<{ id: number; name: string; open_issues: number; new_issues: number;
    fixed_issues: number; generated: number; published: number;
    reviews?: number; critical_issues?: number; high_issues?: number }>;
  /** 新接口提供同集合质量统计，旧服务缺失时不可补零。 */ quality?: ReviewQuality;
  /** 当前全部问题编号计数，不受时间筛选影响。 */
  current_status_counts?: { open: number; fixed: number; ignored: number; false_positive?: number; merged: number };
}

/** 仅按用户展开后的显式条件读取短摘要，支持取消与统一会话鉴权。 */
export function getQualityFindings(token: string, query: string, signal?: AbortSignal) {
  return apiRequest<{ items: QualityFinding[]; total: number; page: number; page_size: number }>(token,
    `/api/review-effectiveness/findings?${query}`, { signal });
}

/** 取消、鉴权及错误由统一 Client 处理，查询不触发评审或外部调用。 */
export function getEffectiveness(token: string, query: string, signal?: AbortSignal) {
  return apiRequest<EffectivenessSnapshot>(token, `/api/review-effectiveness?${query}`, { signal });
}
