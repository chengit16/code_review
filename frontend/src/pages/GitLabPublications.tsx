/** @description 查看 GitLab 行内评论的独立结果和重试；飞书状态保持分离。 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "antd";

import { apiRequest } from "../api/client";
import type { ReviewJobDetail } from "../api/types";
import { ListExcerpt } from "../ui/ListControls";
import { ListTable } from "../ui/ListTable";
import { Status } from "../ui/Status";

/** 旧任务可主动准备评论，失败与不可定位结果逐条重试。 */
export function GitLabPublications({ token, job }: {
  /** 内存口令。 */ token: string;
  /** 已鉴权的任务详情。 */ job: ReviewJobDetail;
}) {
  const client = useQueryClient();
  const refresh = () => void client.invalidateQueries({ queryKey: ["job", String(job.id)] });
  const prepare = useMutation({ mutationFn: () => apiRequest(token, `/api/jobs/${job.id}/gitlab-publications/prepare`, { method: "POST" }), onSuccess: refresh });
  const retry = useMutation({ mutationFn: (id: number) => apiRequest(token, `/api/gitlab-publications/${id}/retry`, { method: "POST" }), onSuccess: refresh });
  if (job.mr_iid < 1 || !["complete", "partial"].includes(job.status)) return null;
  return <section className="section"><div className="section-head"><h2>GitLab 行内评论</h2><Button disabled={prepare.isPending} onClick={() => prepare.mutate()}>准备发布</Button></div>{(prepare.error || retry.error) && <p role="alert" className="form-error">{(prepare.error || retry.error)?.message}</p>}<ListTable rowKey="id" dataSource={job.publications ?? []} pagination={false} scroll={{ x: 650 }} locale={{ emptyText: "暂无行内发布记录" }} columns={[
    { title: "发现", key: "finding", render: (_, item) => `#${item.comment_index + 1}` },
    { title: "尝试", key: "attempt", render: (_, item) => `第 ${item.attempt_number} 次` },
    { title: "状态", key: "status", render: (_, item) => <Status value={item.status} /> },
    { title: "诊断", key: "error", render: (_, item) => <ListExcerpt text={item.error} /> },
    { title: "操作", key: "action", render: (_, item) => ["failed", "skipped"].includes(item.status) && <Button type="link" aria-label={`重试行内评论 ${item.id}`} disabled={retry.isPending} onClick={() => retry.mutate(item.id)}>重试</Button> },
  ]} /></section>;
}
