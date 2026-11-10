/** @description 成功任务按需展开执行和费用，失败及部分覆盖保持显式；事实来自持久化任务。 */
import { Collapse } from "antd";

import type { ReviewJobDetail } from "../api/types";
import { CoverageReasons } from "./CoverageReasons";
import { JobExecution } from "./JobExecution";
import { ModelUsage } from "./ModelUsage";
import { ReviewFailureAnalysis } from "./ReviewFailureAnalysis";
import { ReviewRecoveryPanel } from "./ReviewRecoveryPanel";

/** 成功任务保留锚点和全部证据，折叠不改变失败恢复、调用或计费语义。 */
export function JobDiagnosticSections({ token, job, canEdit, expanded, onExpanded }: {
  /** 内存管理会话。 */ token: string;
  /** 当前任务完整事实。 */ job: ReviewJobDetail;
  /** 控制管理动作显示；后端仍负责授权。 */ canEdit: boolean;
  /** 由详情导航打开指定分区。 */ expanded: string[];
  /** 保留当前展开状态。 */ onExpanded: (keys: string[]) => void;
}) {
  const coverage = job.result?.manifest?.coverage;
  const excluded = job.result?.preview?.files.filter((file) => !file.will_review) ?? [];
  const execution = <section id="job-execution" className="job-detail-region" aria-label="执行与恢复">
        <JobExecution job={job} />
        {["partial", "failed"].includes(job.status) && <section aria-label="保留的初审故障诊断">{job.effective_document && <p className="coverage-note">以下为初审故障证据，不代表当前有效覆盖仍有这些失败；补审结论见后续独立版本。</p>}<ReviewFailureAnalysis analysis={job.failure_analysis} importedAt={job.failure_analysis_imported_at} /></section>}
        <CoverageReasons job={job} />
        <ReviewRecoveryPanel token={token} job={job} canEdit={canEdit} />
  </section>;
  const cost = <>      <div id="job-cost" className="job-insight-grid job-detail-region">
        <div>{job.effective_document && <p className="coverage-note">下方为初审单次用量，补审和全部历史用量见累计费用及独立批次。</p>}<ModelUsage result={job.result} /></div>
        <section className="section detail-insight-card coverage-section">
          <div className="section-head"><h2>{job.effective_document ? "初审覆盖情况（保留原记录）" : "覆盖情况"}</h2></div>
          {coverage ? <div className="coverage-grid"><div><strong>{coverage.selected.length}</strong><span>选中文件</span></div><div><strong>{coverage.completed.length + coverage.reused.length}</strong><span>完成 / 复用</span></div><div><strong>{coverage.failed.length}</strong><span>失败</span></div><div><strong>{coverage.waived.length}</strong><span>豁免</span></div></div> : <p className="empty-inline">尚无 OCR 覆盖结果</p>}
          {job.result?.preview && <p className="coverage-note">范围预览：{job.result.preview.reviewable_count} 个可审查文件，{excluded.length ? `排除 ${excluded.length} 个文件` : "没有排除文件"}</p>}
        </section>
      </div>
</>;
  if (job.status !== "complete") return <>{execution}{cost}</>;
  return <Collapse activeKey={expanded} onChange={(keys) => onExpanded(Array.isArray(keys) ? keys : [keys])} items={[
    { key: "execution", label: "执行明细与恢复记录", forceRender: true, children: execution },
    { key: "cost", label: "覆盖与费用明细", forceRender: true, children: cost },
  ]} />;
}
