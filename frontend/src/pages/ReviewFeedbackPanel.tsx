/**
 * @description 项目通知阈值与人工发现反馈统计。
 *
 * 阈值只影响飞书卡片的重点摘录；服务端保存并保护在途任务快照。
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { useState } from "react";

import { apiRequest } from "../api/client";
import type { ReviewFeedbackSummary } from "../api/types";
import { ListSelect as SelectField } from "../ui/ListControls";
import { ListTable } from "../ui/ListTable";
import { QueryState } from "../ui/QueryState";

type Severity = ReviewFeedbackSummary["minimum_severity"];

interface ReviewFeedbackPanelProps {
  /** 内存中的管理口令；服务端仍负责授权。 */
  token: string;
  /** 当前规则页选择的项目；null 展示全部项目统计。 */
  repositoryId: number | null;
}

/** 展示项目反馈分布并保存通知卡片的重点发现级别。 */
export function ReviewFeedbackPanel({ token, repositoryId }: ReviewFeedbackPanelProps) {
  const queryClient = useQueryClient();
  const summary = useQuery({
    queryKey: ["review-feedback-summary"],
    queryFn: () => apiRequest<ReviewFeedbackSummary[]>(token, "/api/review-feedback/summary"),
  });
  const [draft, setDraft] = useState<{ repositoryId: number; severity: Severity } | null>(null);
  const selected = summary.data?.find((item) => item.repository_id === repositoryId);
  const severity = draft?.repositoryId === repositoryId ? draft.severity : selected?.minimum_severity ?? "medium";
  const save = useMutation({
    mutationFn: () => apiRequest<{ minimum_severity: Severity }>(token, `/api/repositories/${repositoryId}/notification-policy`, {
      method: "PUT",
      body: JSON.stringify({ minimum_severity: severity }),
    }),
    onSuccess: () => {
      setDraft(null);
      void queryClient.invalidateQueries({ queryKey: ["review-feedback-summary"] });
    },
  });

  return <section className="section rule-workspace">
    <div className="section-head"><h2>发现价值反馈与通知</h2></div>
    <QueryState loading={summary.isLoading} error={summary.error} />
    {repositoryId !== null && selected && <div className="feedback-policy">
      <SelectField label="飞书重点发现最低级别" value={severity} onValueChange={(value) => setDraft({ repositoryId, severity: value as Severity })} options={[
        { value: "critical", label: "严重" }, { value: "high", label: "高危" },
        { value: "medium", label: "中危" }, { value: "low", label: "低危" },
      ]} />
      <button className="button button-primary" type="button" disabled={save.isPending || severity === selected.minimum_severity} onClick={() => save.mutate()}><Save size={16} />保存通知级别</button>
    </div>}
    {save.error && <p className="form-error" role="alert">{save.error.message}</p>}
    {save.isSuccess && <p className="form-success" role="status">通知级别已保存，后续评审将使用新配置</p>}
    <ListTable rowKey="repository_id" pagination={false} dataSource={repositoryId === null ? summary.data ?? [] : summary.data?.filter((item) => item.repository_id === repositoryId) ?? []} scroll={{ x: 650 }} loading={summary.isFetching} locale={{ emptyText: summary.error ? "无法读取项目反馈" : "暂无项目反馈" }} columns={[
      { title: "项目", dataIndex: "repository_name", key: "name" },
      { title: "已反馈", dataIndex: "total", key: "total" },
      { title: "有帮助", dataIndex: "helpful", key: "helpful" },
      { title: "误报", dataIndex: "false_positive", key: "false_positive" },
      { title: "忽略", dataIndex: "ignored", key: "ignored", render: (value?: number) => value ?? "待升级" },
      { title: "误报率", key: "rate", render: (_, item) => item.helpful + item.false_positive >= 5 ? `${Math.round(item.false_positive / (item.helpful + item.false_positive) * 100)}%` : "数据不足" },
    ]} /><p className="form-note">只统计有帮助、误报和忽略，不等于去重问题数；旧版修复标记不纳入价值评价。</p>
  </section>;
}
