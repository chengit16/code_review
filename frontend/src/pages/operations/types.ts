/** @description 运行监控只读契约；初审执行与有效结论分别建模，旧接口缺字段不推断为零。 */
import type { PerformanceGroup, SchedulerSnapshot } from "../../api/reviewExecution";

/** 现有监控接口的聚合事实，不表示所有队列或完整恢复验证。 */
export interface OperationsSnapshot {
  /** 协调器持久化快照，可能缺失或过期。 */ scheduler?: SchedulerSnapshot;
  /** 近七天固定分组，不支持前端合成总体分位数。 */ performance_7d?: PerformanceGroup[];
  /** 初审原始执行状态；旧 API 可缺失。 */ execution_jobs?: Record<string, number>;
  /** 当前有效结论状态，不能当实时执行状态。 */ jobs: Record<string, number>;
  /** 事件当前状态。 */ events: Record<string, number>;
  /** 初审通知当前状态。 */ deliveries: Record<string, number>;
  /** 补审通知当前状态。 */ recovery_deliveries?: Record<string, number>;
  /** 补审当前状态。 */ recovery_jobs?: Record<string, number>;
  /** 初审全历史整批重试次数。 */ retry_count: number;
  /** 旧版近七天成功任务均值，不含补审。 */ average_review_seconds: number;
  /** 旧版均值样本数。 */ review_count_7d: number;
  /** 最早待处理初审时间。 */ oldest_pending_at: string | null;
  /** 数据目录所在磁盘空闲字节。 */ disk_free_bytes: number;
  /** 已删除项目遗留目录候选数。 */ orphan_artifacts: number;
  /** 数据库副本检查与配对配置存在性，不代表完整恢复演练。 */ backup: { last_at: string | null; healthy: boolean; age_seconds: number | null };
  /** 原始告警摘要可能含历史问题，禁止解析文本猜测动作。 */ alerts: string[];
}
