/** @description 展示服务端累计耗时、范围分析和逐次执行；不读取工件或推断缺失时间。 */
import type { ReviewJob, ReviewJobDetail } from "../api/types";
import { Status } from "../ui/Status";
import { formatCost, formatDuration, formatSeverity, formatTime } from "../ui/format";

/** 服务端秒数的可读展示，未知不以零代替。 */
export function secondsText(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "未知";
  const seconds = Math.max(0, Math.floor(value));
  if (seconds >= 3600) return `${Math.floor(seconds / 3600)} 小时 ${Math.floor(seconds % 3600 / 60)} 分`;
  if (seconds >= 60) return `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`;
  return `${seconds} 秒`;
}

/** 状态原因优先于发现数，失败、取消、跳过不暗示零问题通过。 */
export function resultText(job: ReviewJob): string {
  if (job.effective_conclusion) {
    const version = job.effective_conclusion;
    return `补审版本 ${version.revision} · 完成 / 复用 ${(version.coverage?.completed ?? 0) + (version.coverage?.reused ?? 0)}/${version.coverage?.selected ?? "未知"} · ${version.finding_count} 条发现 · 剩余失败 ${version.coverage?.failed ?? "未知"}`;
  }
  if (["partial", "failed"].includes(job.status) && job.failure_summary) return job.failure_summary;
  const excluded = job.scope_analysis?.excluded_count ?? 0;
  const filterNote = excluded > 0 ? ` · 纯换行策略排除 ${excluded} 个文件，非原始全范围模型覆盖` : "";
  if (job.status === "complete" && job.finding_count != null) return `${job.finding_count} 条发现${job.highest_severity ? ` · 最高：${formatSeverity(job.highest_severity)}` : ""} · ${job.reason?.message ?? "OCR 已完成选中范围"}${filterNote}`;
  if (job.reason) return job.reason.message;
  return ({ queued: "等待 Worker", running: "正在执行，等待最终结果", failed: "评审失败，未确认完整覆盖", skipped: "无可审查文件，未调用模型", cancelled: "已取消，未确认完整覆盖", partial: "部分覆盖完成" } as Record<string, string>)[job.status] ?? `${job.finding_count ?? 0} 条发现`;
}

/** 列表时间以累计执行为主，排队期间不继续增长执行秒数。 */
export function JobTimeFacts({ job, compact = false }: {
  /** 只读服务端任务事实。 */ job: ReviewJob;
  /** 任务列表仅展示主要耗时和次数，详情仍保留完整时间口径。 */ compact?: boolean;
}) {
  const timing = job.timing;
  if (!compact) return <div className="execution-facts"><span>初审累计执行 {secondsText(timing?.cumulative_execution_seconds)}{timing && !timing.execution_complete ? "（历史不完整）" : ""}</span><small>首次排队 {secondsText(timing?.first_queue_seconds)}</small><small>总历时 {secondsText(timing?.total_elapsed_seconds)} · 初审 {job.attempts} 次 / 补审执行 {job.recovery_execution_count ?? 0} 次</small></div>;
  if (job.status === "queued" && job.attempts === 0) return <div className="execution-facts"><span>已排队 {secondsText(timing?.first_queue_seconds)}</span><small>尚未执行</small></div>;
  return <div className="execution-facts"><span>初审执行 {secondsText(timing?.cumulative_execution_seconds)}{timing && !timing.execution_complete ? "（历史不完整）" : ""}</span><small>初审 {job.attempts} 次 · 补审 {job.recovery_execution_count ?? 0} 次</small></div>;
}

/** 列表累计费用明确标记未知部分，旧服务端响应保留单次费用兼容。 */
export function JobCostFacts({ job }: { /** 包含累计费用与完整性标志。 */ job: ReviewJob }) {
  const usage = job.cumulative_usage;
  if (!usage) return <>{formatCost(job.estimated_cost)}</>;
  return <>{usage.known_costs.length ? usage.known_costs.map((cost) => formatCost(cost)).join(" + ") : "未知"}<small className="table-sub">{usage.cost_complete ? "累计估算" : "仅已知部分，费用不完整"}</small></>;
}

/** 展示不同时间口径、换行分析及累计用量，分析未完成时不推断可免审。 */
export function JobExecution({ job }: { /** 已鉴权的完整任务事实。 */ job: ReviewJobDetail }) {
  const time = job.timing;
  const scope = job.scope_analysis;
  const usage = job.cumulative_usage;
  return <section className="section execution-panel"><div className="section-head"><h2>耗时与范围诊断</h2></div>
    <p className="execution-reason">{resultText(job)}</p>
    <dl className="execution-grid">{[["初审累计执行", secondsText(time?.cumulative_execution_seconds)], ["本次 / 最后执行", secondsText(time?.latest_execution_seconds)], ["首次排队", secondsText(time?.first_queue_seconds)], ["重试退避", secondsText(time?.retry_backoff_seconds)], ["重试就绪后等待", secondsText(time?.retry_ready_wait_seconds)], ["总历时", secondsText(time?.total_elapsed_seconds)]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    <p className="coverage-note">{time?.execution_complete ? "这里的耗时仅含初审各次尝试，不含补审、排队与退避；补审起止见独立历史。" : "部分初审历史时间缺失，仅包含已知初审尝试，不含补审。"}</p>
    {scope && <div className="scope-analysis"><h3>固定范围预检</h3><p>原始变更 {scope.original_count ?? "未知"} 个文件 · 已分析 {scope.checked_count} 个 · 确认仅换行 {scope.newline_only_count} 个 · 策略排除 {scope.excluded_count} 个</p><p>OCR 候选 {scope.ocr_candidate_count ?? job.result?.preview?.reviewable_count ?? "未知"} 个 · OCR 规则排除 {scope.ocr_excluded_count ?? job.result?.preview?.excluded_count ?? "未知"} 个</p><p>{scope.filter_reason}。{scope.status !== "complete" && "预检受限或不可用，未确认文件仍保持纳入。"}</p>{(scope.newline_only_paths ?? []).length > 0 && <details><summary>查看仅换行文件（实际策略排除 {scope.excluded_count} 个）</summary><ul>{scope.newline_only_paths?.map((path) => <li key={path} className="mono file-path">{path}</li>)}</ul></details>}</div>}
    {usage && <div><h3>累计用量与费用</h3><p>已知 Token：{usage.known_tokens?.total_tokens.toLocaleString("zh-CN") ?? "未知"} · 已知用量 {usage.known_usage_attempts}/{usage.total_attempts} 次</p><JobCostFacts job={job} />{!usage.usage_complete && <p className="attention-note">存在未知用量；超时没有最终结果不等于没有费用。</p>}</div>}
  </section>;
}

/** 逐次起止、重试决定及阶段来自持久化事实；保留历史成功后取消的独立记录。 */
export function AttemptTimeline({ job }: { /** 含尝试和阶段记录的只读详情。 */ job: ReviewJobDetail }) {
  return <details className="advanced-panel"><summary>执行记录 · {job.attempt_history.length} 次</summary><section className="section attempt-history-card"><h2>逐次执行</h2>{job.attempt_history.map((attempt) => {
    // 恢复时间不是进程实际结束时间，不能把停机间隔显示成精确执行耗时。
    const interrupted = ["interrupted", "interrupted_cancelled"].includes(attempt.reason_code ?? "") || Boolean(attempt.error?.startsWith("Worker 中断"));
    return <article className="attempt-evidence" key={attempt.id}><h3>第 {attempt.attempt_number} 次 <Status value={attempt.status} /></h3><p>开始 {formatTime(attempt.started_at ?? null)} · {interrupted ? "恢复记录时间" : "结束"} {formatTime(attempt.finished_at)}</p><p>执行 {attempt.started_at && !interrupted ? formatDuration(attempt.started_at, attempt.finished_at) : "未知"} · 就绪 {formatTime(attempt.scheduled_at ?? null)}</p><p>{attempt.retry_ready_at ? `已安排重试，最早 ${formatTime(attempt.retry_ready_at)}` : "未安排自动重试，或旧记录未保存调度证据"}</p><p>{attempt.error ?? "无错误摘要"}</p>{job.stage_timings?.filter((stage) => stage.attempt_number === attempt.attempt_number).map((stage) => <p key={`${stage.stage}-${stage.started_at}`}>{stage.stage}：{formatTime(stage.started_at)} → {formatTime(stage.finished_at)} · {interrupted ? "中断恢复，实际阶段耗时未知" : formatDuration(stage.started_at, stage.finished_at)}</p>)}</article>;
  })}{!job.attempt_history.length && <p>暂无已结束尝试</p>}</section></details>;
}
