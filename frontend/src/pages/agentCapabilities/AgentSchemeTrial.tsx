/** @description 预览历史任务命中范围，确认后独立运行草稿。 */

import { useQuery } from "@tanstack/react-query";
import { Alert, App, Button, Card, InputNumber, Space, Table } from "antd";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getSchemeTrials, previewScheme } from "../../api/agentCapabilities";
import { createAgentComparison, getAgentComparisons } from "../../api/agentComparisons";
import { createCommandId } from "../../api/commandId";
import { Status } from "../../ui/Status";
import { formatTime } from "../../ui/format";
import { useCapabilityAction, useCapabilityCheck } from "./capabilityActions";

/** 预览由 Worker 读取固定提交，用户另行确认试跑。 */
export function AgentSchemeTrial({ token, schemeId }: { token: string; schemeId: number }) {
  const [job, setJob] = useState<number | null>(null);
  const [checkId, setCheckId] = useState<number | null>(null);
  const action = useCapabilityAction();
  const check = useCapabilityCheck(token, checkId);
  const preview = check.data?.result;
  const { modal } = App.useApp();
  const navigate = useNavigate();
  const trials = useQuery({ queryKey: ["agent-scheme-trials", schemeId], staleTime: 0,
    queryFn: ({ signal }) => getSchemeTrials(token, schemeId, signal) });

  function trial() {
    if (!preview?.job_id) return;
    const jobId = preview.job_id;
    const requestKey = createCommandId();
    modal.confirm({
      title: `用方案 #${schemeId} 试跑任务 #${jobId}`,
      content: "会调用模型并产生独立的试跑记录。当前 OCR 初审继续作为对照。",
      okText: "确认试跑",
      onOk: async () => {
        const current = await getAgentComparisons(token, jobId, null);
        if (current.unavailable_reason || current.current_source_attempt === null) {
          const error = current.unavailable_reason ?? "没有可用的 OCR 初审";
          action.mutate(async () => { throw new Error(error); });
          return;
        }
        if (current.current_source_attempt !== preview.attempt) {
          action.mutate(async () => { throw new Error("OCR 初审已更新，请重新预览"); });
          return;
        }
        try {
          const created = await createAgentComparison(token, jobId, {
            source_attempt: current.current_source_attempt, previous_id: current.previous_id,
            request_key: requestKey, trial_scheme_id: schemeId,
          });
          navigate(`/jobs/${jobId}?agent_comparison=${created.id}#job-agent-comparison`);
        } catch (error) {
          action.mutate(async () => { throw error; });
          throw error;
        }
      },
    });
  }

  return <Card size="small" className="agent-trial" title="预览与试跑">
    <Space wrap>
      <InputNumber aria-label="评审任务编号" placeholder="任务编号" value={job} onChange={(value) => {
        setJob(value); setCheckId(null);
      }} min={1} precision={0} style={{ width: 120 }} />
      <Button disabled={!job} loading={action.isPending} onClick={() => {
        if (job) action.mutate(async () => setCheckId(
          (await previewScheme(token, schemeId, job)).id,
        ));
      }}>预览命中范围</Button>
      {check.data?.status === "complete" && <Button type="primary"
        disabled={preview?.mcp_authorized === false} onClick={trial}>试跑此方案</Button>}
    </Space>
    {(check.data?.status === "queued" || check.data?.status === "running" || (checkId && check.isPending))
      && <p role="status">Worker 正在准备预览…</p>}
    {check.error && <Alert type="error" showIcon title={check.error.message} />}
    {check.data?.status === "failed" && <Alert type="error" showIcon title={preview?.message} />}
    {preview?.mcp_authorized === false && <Alert type="warning" showIcon
      title="此任务所属仓库尚未获得该 MCP 工具授权" />}
    {preview?.rows && <>
      <p>OCR 初审第 {preview.attempt} 次 · {preview.path_count} 个文本文件{(preview.path_count ?? 0) > preview.rows.length ? "（预览前 300 个）" : ""}</p>
      <Table size="small" rowKey="path" dataSource={preview.rows} tableLayout="fixed"
        pagination={{ pageSize: 8, showSizeChanger: false }} columns={[
          { title: "文件", dataIndex: "path" },
          { title: "命中的能力", render: (_, row) => {
            const capabilities = [
              ...row.skills.map((skill) => `Skill · ${skill}`),
              ...row.files.map((file) => `补查 · ${file}`),
              ...(row.mcp ? [`MCP · ${row.mcp}`] : []),
            ];
            return capabilities.length ? <ul className="agent-trial-hits">
              {capabilities.map((item, index) => <li key={index}>{item}</li>)}
            </ul> : "无";
          } },
        ]} />
    </>}
    {trials.error && <Alert type="error" showIcon title={trials.error.message} />}
    {!!trials.data?.length && <Table size="small" rowKey="id" dataSource={trials.data}
      pagination={false} tableLayout="fixed" columns={[
        { title: "最近试跑", render: (_, row) => <Link
          to={`/jobs/${row.job_id}?agent_comparison=${row.id}#job-agent-comparison`}>
          任务 #{row.job_id} · Agent #{row.id}</Link> },
        { title: "状态", width: 80, render: (_, row) => <Status value={row.status} /> },
        { title: "入队时间", render: (_, row) => formatTime(row.created_at) },
      ]} />}
  </Card>;
}
