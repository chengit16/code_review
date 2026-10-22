/** @description 独立查看逐次报告与同提交发现变化；消失的发现不自动视为已修复。 */
import { useMutation } from "@tanstack/react-query";
import { Download, GitCompare } from "lucide-react";
import { useState } from "react";

import { apiRequest } from "../api/client";
import { downloadTaskReport } from "../api/tasks";
import type { ReviewComment, ReviewJobDetail } from "../api/types";
import { SelectField } from "../ui/SelectField";

interface Comparison { added: ReviewComment[]; removed: ReviewComment[]; unchanged_count: number; before_status: string; after_status: string }

/** 历史版本由用户选择；跨配置重审时可指定新的任务编号。 */
export function AttemptReports({ token, job }: {
  /** 内存口令。 */ token: string;
  /** 服务端尝试摘要。 */ job: ReviewJobDetail;
}) {
  const options = job.attempt_history.map((item) => ({ value: String(item.attempt_number), label: `第 ${item.attempt_number} 次 · ${item.status}` }));
  const [before, setBefore] = useState(options.at(-1)?.value ?? "1");
  const [after, setAfter] = useState(options[0]?.value ?? "1");
  const [other, setOther] = useState("");
  const download = useMutation({ mutationFn: () => downloadTaskReport(token, job.id, Number(before)) });
  const compare = useMutation({ mutationFn: () => apiRequest<Comparison>(token, `/api/jobs/${job.id}/comparison?before=${before}&after=${after}${other ? `&other_job_id=${other}` : ""}`) });
  if (!options.length) return null;
  return <section className="section attempt-report-section">
    <div className="section-head"><h2>历史报告与对比</h2><span>可下载任一次报告，或比较发现变化</span></div>
    <div className="attempt-toolbar">
      <SelectField label="基准尝试" value={before} onValueChange={setBefore} options={options} />
      <button className="icon-button attempt-download" title="下载此次报告与配置快照" aria-label="下载历史报告" disabled={download.isPending} onClick={() => download.mutate()}><Download size={16} /></button>
      <label>其他任务 ID（可选）<input type="number" min="1" value={other} onChange={(event) => setOther(event.target.value)} placeholder={String(job.id)} /></label>
      {other ? <label>对比尝试<input type="number" min="1" value={after} onChange={(event) => setAfter(event.target.value)} /></label> : <SelectField label="对比尝试" value={after} onValueChange={setAfter} options={options} />}
      <button className="button button-secondary" disabled={compare.isPending} onClick={() => compare.mutate()}><GitCompare size={16} />比较结果</button>
    </div>
    {(compare.error || download.error) && <p className="form-error" role="alert">{(compare.error || download.error)?.message}</p>}
    {compare.data && <div className="attempt-comparison" aria-live="polite"><div className="comparison-summary"><span>新增 <strong>{compare.data.added.length}</strong></span><span>不再出现 <strong>{compare.data.removed.length}</strong></span><span>保留 <strong>{compare.data.unchanged_count}</strong></span></div>{[{ label: "新增", items: compare.data.added }, { label: "不再出现", items: compare.data.removed }].map((group) => group.items.length > 0 && <div className="comparison-group" key={group.label}><h3>{group.label}</h3>{group.items.map((comment, index) => <p key={index}><strong>{comment.path}</strong><span>{comment.content}</span></p>)}</div>)}</div>}
  </section>;
}
