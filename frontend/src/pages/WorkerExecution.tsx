/** @description 展示单协调器执行槽与心跳；不从心跳推断任务完成，也不提供抢占或增加并发操作。 */
import { formatTime } from "../ui/format";
import type { SchedulerSnapshot } from "../api/reviewExecution";

const lanes: Record<string, string> = { model: "模型评审", ingress: "事件与 Git 准备", delivery: "通知与行内发布" };
const tasks: Record<string, string> = { review: "合并后评审", review_recovery: "失败子集补审", recovery_notification: "补审补充通知", premerge: "合并前审查", model_check: "模型诊断", event: "事件展开", backfill: "补审扫描", git_check: "Git/GitLab 诊断", rule_preview: "规则预览", notification: "飞书通知", publication: "行内发布", feishu_check: "飞书诊断" };
const states: Record<string, string> = { idle: "空闲", running: "执行中", stopped: "已停止", interrupted: "执行中断" };

/** 仅展示持久化事实；历史缺失和心跳过期不能显示成健康或自动抢占。 */
export function WorkerExecution({ snapshot }: { /** 旧版 API 可能不提供执行槽。 */ snapshot?: SchedulerSnapshot }) {
  return <section className="section execution-panel"><div className="section-head"><h2>Worker 调度与执行槽</h2></div>
    <p>模型任务并发 {snapshot?.model_task_concurrency ?? "未知"} · 模型诊断与评审共用模型槽；事件和投递独立执行。</p>
    {!snapshot?.slots.length ? <p className="coverage-note">尚无新版协调器执行记录，不能据此确认解耦已在本机生效。</p> : <div className="execution-grid">{snapshot.slots.map((slot) => <article key={slot.lane}><h3>{lanes[slot.lane] ?? slot.lane}</h3><p>{states[slot.state] ?? slot.state}{slot.state === "running" ? ` · ${tasks[slot.task_kind ?? ""] ?? "任务"} #${slot.task_id}` : ""}</p><p>心跳 {formatTime(slot.heartbeat_at)}</p>{!["stopped", "interrupted"].includes(slot.state) && slot.heartbeat_age_seconds > 15 && <p className="attention-note">协调心跳过期，执行状态待核实；不会自动抢占或重复评审。</p>}</article>)}</div>}
    <p className="coverage-note">解耦不代表后续短评审可以越过前序评审；同仓库顺序仍保留。中断恢复以进程锁为栅栏，不仅凭过期心跳重新执行。</p>
  </section>;
}
