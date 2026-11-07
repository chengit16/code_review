/** @description 展示持久化分层故障证据；不读取工件、不推断根因或触发重试。 */
import type { FailureAnalysis } from "../api/reviewDiagnostics";

/** 展示当前尝试的安全证据；旧结果缺少诊断时明确说明不做猜测。 */
export function ReviewFailureAnalysis({ analysis, importedAt }: {
  /** 服务端白名单投影；空值代表历史没有保存该能力。 */
  analysis: FailureAnalysis | null | undefined;
  /** 历史诊断的独立导入时间，不代表重新评审。 */ importedAt?: string | null;
}) {
  if (!analysis) return <section className="section"><h2>分层失败诊断</h2><p className="coverage-note">历史结果未保存分层诊断；需要受控历史诊断导入，单纯重启或刷新页面不会补齐。下方文件级 timeout 只说明超时，不能确定网关、模型、上下文或工具中的具体故障层。</p><p className="coverage-note">如原始工件仍在，可由管理员使用只读诊断工具核对请求、分组和计时，无需再次调用模型；只读报告不会自动回填本任务；管理员可预览后执行批量导入。工件也缺失时需明确保留未知，不能猜测详细原因。</p></section>;
  return <section className="section execution-panel" aria-label="分层失败诊断">
    <h2>分层失败诊断</h2>{importedAt && <p className="coverage-note">历史诊断导入于 {importedAt}；仅补充证据，没有重跑模型或修改初审结果。</p>}<p>{analysis.summary}</p>
    <p className="coverage-note">请求报告：{({ available: "可用", missing: "缺失", unsupported: "版本不兼容", malformed: "结构损坏", limited: "超限或截断" })[analysis.report_state]}；失败分组数：{analysis.failed_group_count ?? "未知"}。记录超时不等于确认网络或大文件是根因。</p>
    <ul>{analysis.signals.map((signal) => <li key={signal.code}>{signal.message} · {signal.count} 次 / 项</li>)}</ul>
    {analysis.groups.map((group) => <details key={group.group_id}><summary>{group.group_id} · {group.failed_count} 个文件未完成</summary><ul>{group.paths.map((path) => <li className="mono file-path" key={path}>{path}</li>)}</ul></details>)}
    <details><summary>失败请求证据 · {analysis.requests.length} 条</summary>
      {analysis.requests.map((request, index) => <article className="attempt-evidence" key={index}>
        <h3>{request.group_id ?? "分组关联未知"} · {({ plan_task: "计划阶段", main_task: "主审核阶段", unknown: "阶段未知" })[request.task_type]}</h3>
        {request.logical_request_id && <p className="mono file-path">逻辑请求 {request.logical_request_id}</p>}
        <p>请求序号 {request.request_no ?? "未知"} · {request.attempts} 次尝试 · HTTP {request.http_statuses.join(" / ") || "未知"}</p>
        <p>错误类别 {request.error_classes.join(" / ") || "未知"} · 阶段标签 {request.failure_phases.join(" / ") || "未知"}</p>
        <p>响应头计时（毫秒）：{request.duration_to_headers_ms.join(" / ") || "未知"}</p>
        <p>重试间隔（毫秒）：{request.observed_backoff_ms.join(" / ") || "未知"}</p>
      </article>)}
    </details>
    {analysis.notes.map((note) => <p className="coverage-note" key={note}>{note}</p>)}
  </section>;
}
