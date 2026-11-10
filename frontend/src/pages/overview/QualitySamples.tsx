/** @description 首页质量样本抽屉；地址栏保存条件，按需查询，关闭取消请求，不提供写反馈动作。 */
import { useQuery } from "@tanstack/react-query";
import { Button, Drawer, Select } from "antd";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { getQualityFindings } from "../../api/effectiveness";
import { ListTable } from "../../ui/ListTable";
import { QueryState } from "../../ui/QueryState";
import { formatCategory, formatSeverity } from "../../ui/format";

import { feedbackSeries } from "./qualityView";

/** 组件只在显式打开时挂载，查询键包含完整筛选与页码，无旧范围占位数据。 */
export function QualitySamples({ token, days, repositoryId }: {
  /** 内存会话，沿用 API 鉴权。 */ token: string;
  /** 默认 UTC 窗口。 */ days: number;
  /** 首页项目范围。 */ repositoryId: string;
}) {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("sample_page")) || 1);

  const feedback = params.get("sample_feedback") === "fixed" ? "unmarked" : params.get("sample_feedback") ?? "all";
  const category = params.get("sample_category");
  const severity = params.get("sample_severity") ?? "all";
  const scopedRepository = repositoryId || params.get("sample_repository");
  const query = new URLSearchParams({ days: String(days), feedback, page: String(page), page_size: "10" });
  if (scopedRepository) query.set("repository_id", scopedRepository);
  if (category) query.set("category", category);
  if (severity !== "all") query.set("severity", severity);
  if (params.get("sample_since")) query.set("since", params.get("sample_since") ?? "");
  if (params.get("sample_until")) query.set("until", params.get("sample_until") ?? "");
  const samples = useQuery({ queryKey: ["review-effectiveness", "findings", query.toString()],
    queryFn: ({ signal }) => getQualityFindings(token, query.toString(), signal) });
  function change(key: string, value: string) {
    const next = new URLSearchParams(params);
    next.delete("sample_page");
    if (value) next.set(key, value); else next.delete(key);
    setParams(next);
  }
  function close() {
    const next = new URLSearchParams(params);
    for (const key of [...next.keys()]) if (key.startsWith("sample_")) next.delete(key);
    setParams(next);
  }
  function clear() {
    const next = new URLSearchParams(params);
    for (const key of ["sample_status", "sample_feedback", "sample_category", "sample_repository", "sample_severity", "sample_page"]) next.delete(key);
    setParams(next);
  }
  return <Drawer open title="评审质量样本" onClose={close} size={1000} className="quality-samples">
    <p>同一有效发现集合 · 项目 {scopedRepository ? `#${scopedRepository}` : "全部"} · 类别 {category ? formatCategory(category) : "全部"}</p>
    <p className="quality-caption">来源窗口：{params.get("sample_since") ?? `近 ${days} 天`} 至 {params.get("sample_until") ?? "当前"}（不含终点，UTC）。样本为当前读取，当前状态或价值反馈变化后数量可能更新。</p>
    <div className="quality-sample-controls"><label>价值反馈 <Select aria-label="样本反馈" value={feedback} onChange={(value) => change("sample_feedback", value === "all" ? "" : value)} options={[{ value: "all", label: "全部反馈" }, ...feedbackSeries.map((series) => ({ value: series.feedback, label: series.label }))]} /></label>
      <label>级别 <Select aria-label="样本严重级别" value={severity} onChange={(value) => change("sample_severity", value === "all" ? "" : value)} options={[{ value: "all", label: "全部级别" }, ...["critical", "high", "medium", "low", "unclassified"].map((value) => ({ value, label: value === "unclassified" ? "未分级" : formatSeverity(value) }))]} /></label><Button onClick={clear}>清除样本筛选</Button></div>
    <QueryState loading={samples.isLoading} error={samples.error} onRetry={() => void samples.refetch()} />
    {samples.data && <><p role="status">共 {samples.data.total} 条发现{samples.isFetching ? "，正在刷新" : ""}</p><ListTable onOpenRow={(item) => navigate(`/jobs/${item.job_id}#job-result`)} rowLabel={(item) => `查看发现 ${item.finding_id} 的任务`} rowKey="finding_id" dataSource={samples.data.items} loading={samples.isFetching} pagination={{ current: page, pageSize: 10, total: samples.data.total, showSizeChanger: false, onChange: (value) => change("sample_page", String(value)) }} scroll={{ x: 800 }} locale={{ emptyText: "当前条件没有发现样本" }} columns={[
      { title: "发现 / 来源", key: "finding", render: (_, item) => <><p><Link aria-label={`查看任务 #${item.job_id}`} to={`/jobs/${item.job_id}#job-result`}>{item.excerpt}</Link></p><small>{item.path}</small><p><code>{item.finding_id}</code></p><small>{item.repository_name} · 第 {item.source_attempt} 次 · 版本 {item.revision}</small></> },
      { title: "类别 / 级别", key: "category", width: 130, render: (_, item) => <>{formatCategory(item.category)} / {item.severity === "unclassified" ? "未分级" : formatSeverity(item.severity)}</> },
      { title: "价值反馈", key: "feedback", width: 100, render: (_, item) => feedbackSeries.find((series) => series.feedback === item.feedback)?.label ?? "未评价" },

    ]} /></>}
    {params.has("sample_status") && <p>旧问题处置筛选已停用，此处按当前发现反馈展示。历史处置请进入历史问题与修复记录。</p>}
    <p className="quality-caption">此处只读。任务入口展示该任务当前结论；请核对样本所列来源身份与版本，重审后当前结论可能变化。</p>
  </Drawer>;
}
