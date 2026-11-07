/** @description 平台复盘只读契约；当前累计与按北京时间分日的活动窗口分开，不触发检查或部署。 */
import { apiRequest } from "./client";
import type { ImprovementContent } from "./improvements";

/** 当前实体分布，枚举缺项由服务端补零。 */
export interface ImprovementDistribution {
  /** 当前实体总数，不是窗口内新增数。 */ total: number;
  /** 当前进展计数。 */ by_status: Record<string, number>;
  /** 当前分类计数。 */ by_category: Record<string, number>;
  /** 独立代码修改状态。 */ by_code_state: Record<string, number>;
  /** 独立本地验证状态。 */ by_verification_state: Record<string, number>;
  /** 独立部署状态，人工确认不等于自动核验。 */ by_deployment_state: Record<string, number>;
}

/** 自然日活动，初始版本不计入追加进展。 */
export interface ImprovementActivityDay {
  /** 北京时间日期 YYYY-MM-DD。 */ date: string;
  /** 新增台账记录数。 */ records_created: number;
  /** 台账新增后成功保存的历史版本数。 */ record_updates: number;
  /** 新增优化主题数。 */ themes_created: number;
  /** 主题新增后成功保存的历史版本数。 */ theme_updates: number;
}

/** 待办分组，互相允许重叠，不可相加当成独立记录数。 */
export interface ImprovementAttentionGroup {
  /** 完整筛选下的总条数。 */ total: number;
  /** 最久未更新的前十条；只投影定位信息。 */ items: { id: number; title: string; status: string; updated_at: string; archived_at: string | null }[];
}

/** 同一数据库快照的复盘结果；分类分别按记录和主题当前值筛选。 */
export interface ImprovementSummary {
  /** 读取时刻，供用户识别数据新鲜度。 */ generated_at: string;
  /** 活动日期使用的服务端时区。 */ timezone: string;
  /** 活动窗口首日，含当日。 */ start_date: string;
  /** 活动窗口末日，含当日。 */ end_date: string;
  /** 当前分类，null 表示全部。 */ category: ImprovementContent["category"] | null;
  /** 当前分类已归档记录数，累计和待办仍包含它们。 */ archived_records: number;
  /** 当前分类已归档主题数。 */ archived_themes: number;
  /** 台账当前累计与关联覆盖；关联按记录编号去重。 */ records: ImprovementDistribution & { by_kind: Record<string, number>; linked_records: number };
  /** 主题及其阶段分别计数。 */ themes: { total: number; by_status: Record<string, number>; by_category: Record<string, number>; phases: ImprovementDistribution };
  /** 零活动日也返回，顺序为日期升序。 */ activity: ImprovementActivityDay[];
  /** 未解决台账，包含暂缓。 */ unresolved: ImprovementAttentionGroup;
  /** 验证失败/受阻，或代码已改但未验证。 */ verification_attention: ImprovementAttentionGroup;
  /** 本地通过但部署未确认，不包含部署不适用。 */ deployment_pending: ImprovementAttentionGroup;
  /** 未完成主题，包含暂停与暂缓。 */ unfinished_themes: ImprovementAttentionGroup;
}

/** 仅发起管理员只读查询，时间窗影响活动而不裁剪当前累计。 */
export function getImprovementSummary(token: string, params: URLSearchParams, signal?: AbortSignal) {
  return apiRequest<ImprovementSummary>(token, `/api/improvement-summary?${params}`, { signal });
}
