/** @description 将已保存的 Agent 动作按差异页归组，分页查看原始记录。 */

import { Collapse, Pagination, Tag } from "antd";
import { CheckCircle2, FileDiff, History, OctagonAlert, Play, RotateCcw } from "lucide-react";
import { useMemo, useState } from "react";

import type { RunStatus } from "../../api/agentComparisons";

const PAGE_SIZE = 8;
const actionLabels: Record<string, string> = {
  start: "准备评审", resume: "继续评审", request: "定位差异", read: "读取差异",
  prepare: "准备页内证据", verified: "校验结果", failed: "执行失败",
  stopped: "停止评审", finish: "结束评审",
};
const endingLabels: Record<string, string> = {
  covered: "已核对全部差异", no_text_diff: "没有可评审的文本差异",
  read_budget: "达到读取页数限制", model_budget: "达到模型预算限制",
  model_timeout: "模型响应超时", model_response: "模型响应未通过校验",
  model_unavailable: "模型网关不可用", invalid_read_request: "差异页请求超出计划",
  invalid_evidence: "证据校验失败", capability_unavailable: "必需的取证步骤不可用",
};

type Action = { stage: string; detail: string };
type Entry = { id: number; actions: Action[]; page: boolean };

function groupActions(steps: string[]): Entry[] {
  const entries: Entry[] = [];
  let currentPage: Entry | undefined;
  // 逐页请求是分组边界。保留未完成的最后一页及无法识别的历史动作。
  for (const [index, step] of steps.entries()) {
    const separator = step.indexOf(" · ");
    const stage = separator < 0 ? "" : step.slice(0, separator);
    const detail = separator < 0 ? step : step.slice(separator + 3);
    const action = { stage, detail };
    if (currentPage && ["read", "prepare", "verified", "failed", "stopped"].includes(stage)) {
      currentPage.actions.push(action);
      // 一页核对或失败后，下一次定位差异之前的故障是独立的运行记录。
      if (stage === "verified" || stage === "failed" || stage === "stopped") currentPage = undefined;
      continue;
    }
    const entry = { id: index, actions: [action], page: stage === "request" };
    entries.push(entry);
    currentPage = entry.page ? entry : undefined;
  }
  return entries.reverse();
}

function actionDetail({ stage, detail }: Action) {
  return ["finish", "stopped"].includes(stage) ? endingLabels[detail] ?? detail : detail;
}

function PageEntry({ entry, status }: { entry: Entry; status: RunStatus }) {
  const read = entry.actions.find((action) => action.stage === "read");
  const target = read?.detail.match(/^(.+) (块 \d+ \[\d+,\d+\)\/\d+，续读位置 .+)$/);
  const path = target?.[1];
  const outcome = entry.actions.at(-1);
  const verified = outcome?.stage === "verified";
  const stopped = outcome?.stage === "failed" || outcome?.stage === "stopped";
  return <Collapse size="small" ghost className="agent-workflow-page"
    styles={{ header: { padding: "8px" }, title: { minWidth: 0 } }} items={[{
    key: entry.id,
    label: <div className="agent-workflow-page-label">
      <FileDiff size={16} aria-hidden />
      <div>
        <strong title={path}>{path?.split("/").at(-1) ?? read?.detail ?? "差异页评审"}</strong>
        <small>{target?.[2] ?? entry.actions[0].detail}</small>
      </div>
      <Tag color={verified ? "success" : stopped ? "error" : undefined}>
        {verified ? "已核对" : stopped ? "未完成" : status === "running" ? "待核对" : "未核对"}
      </Tag>
    </div>,
    children: <ol className="agent-workflow-actions">{entry.actions.map((action, index) => (
      <li key={`${action.stage}:${index}`}>
        <span>{actionLabels[action.stage] ?? (action.stage || "运行记录")}</span>
        <span>{actionDetail(action)}</span>
      </li>
    ))}</ol>,
  }]} />;
}

function RunEntry({ action }: { action: Action }) {
  const Icon = action.stage === "start" ? Play : action.stage === "resume" ? RotateCcw
    : action.stage === "finish" && action.detail === "covered" ? CheckCircle2
    : ["failed", "stopped"].includes(action.stage) ? OctagonAlert : History;
  return <div className="agent-workflow-entry">
    <Icon size={16} aria-hidden />
    <div><strong>{actionLabels[action.stage] ?? (action.stage || "运行记录")}</strong>
      <small>{actionDetail(action)}</small></div>
  </div>;
}

/** 运行期间更新动作记录，保留用户选择的页码。 */
export function AgentWorkflow({ steps, status }: {
  /** 当前比较保存的顺序动作。 */ steps: string[];
  /** 当前比较状态，用于区分尚未核对与正在等待。 */ status: RunStatus;
}) {
  const [page, setPage] = useState(1);
  const entries = useMemo(() => groupActions(steps), [steps]);
  const current = Math.min(page, Math.max(1, Math.ceil(entries.length / PAGE_SIZE)));
  const offset = (current - 1) * PAGE_SIZE;

  if (!entries.length) return <p className="agent-run-note">暂无已保存的执行记录</p>;
  return <>
    <p className="agent-run-note">共 {entries.length.toLocaleString("zh-CN")} 条记录 · 最近记录在前</p>
    <ol className="agent-workflow-list">{entries.slice(offset, offset + PAGE_SIZE).map((entry) => (
      <li key={entry.id}>{entry.page ? <PageEntry entry={entry} status={status} />
        : <RunEntry action={entry.actions[0]} />}</li>
    ))}</ol>
    <Pagination aria-label="工作流程分页" size="small" current={current}
      total={entries.length} pageSize={PAGE_SIZE} hideOnSinglePage showSizeChanger={false}
      showLessItems onChange={setPage} />
  </>;
}
