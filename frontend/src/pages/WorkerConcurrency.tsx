/** @description 管理员调整单 Worker 模型任务总容量；草稿与轮询分离，冲突不自动重放。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Collapse, Input } from "antd";
import { useState } from "react";

import { ApiError } from "../api/client";
import { getWorkerSchedulerConfig, saveWorkerSchedulerConfig } from "../api/workerScheduler";
import type { WorkerSchedulerConfig } from "../api/workerScheduler";
import type { SchedulerSnapshot } from "../api/reviewExecution";
import { QueryState } from "../ui/QueryState";

/** 在开始编辑时冻结版本，刷新只更新服务端事实，不覆盖未保存输入。 */
export function WorkerConcurrency({ token, active = true, execution }: {
  /** 内存管理会话。 */ token: string;
  /** 隐藏视图保留草稿但停止后台读取。 */ active?: boolean;
  /** 独立轮询的调度快照，不与配置读取假装同一事务。 */ execution?: SchedulerSnapshot;
}) {
  const client = useQueryClient();
  const config = useQuery({ queryKey: ["worker-scheduler-config"], enabled: active, queryFn: ({ signal }) => getWorkerSchedulerConfig(token, signal), refetchInterval: active ? 10000 : false });
  const [draft, setDraft] = useState<{ value: string; version: number } | null>(null);
  const save = useMutation({ retry: false, mutationFn: (payload: WorkerSchedulerConfig) => saveWorkerSchedulerConfig(token, payload), onSuccess: (result) => {
    setDraft(null);
    client.setQueryData(["worker-scheduler-config"], result);
    void client.invalidateQueries({ queryKey: ["operations"] });
  } });
  const value = draft?.value ?? String(config.data?.model_task_concurrency ?? "");
  const number = Number(value);
  const valid = value.trim() !== "" && Number.isInteger(number) && number >= 1 && number <= 10;
  const conflict = save.error instanceof ApiError && save.error.status === 409;
  return <div className="coverage-note">
    <dl className="operations-capacity-facts"><div><dt>Worker 已应用</dt><dd>{execution?.applied_concurrency ?? "未知"}</dd></div><div><dt>模型执行中</dt><dd>{execution?.running_model_tasks ?? "未知"}</dd></div></dl>
    {execution?.draining && <p className="attention-note">正在排空，等待在途任务自然结束；不会强行中断。</p>}
    {config.data && execution?.applied_version != null && config.data.version !== execution.applied_version && <p className="attention-note">配置版本与 Worker 快照尚未对齐，等待后续刷新确认；两者独立读取。</p>}
    <QueryState loading={config.isLoading} error={config.error} />
    {config.data && <form className="operations-concurrency-form" onSubmit={(event) => {
      event.preventDefault();
      if (valid && draft && !save.isPending && !conflict) save.mutate({ model_task_concurrency: number, version: draft.version });
    }}>
      <label htmlFor="worker-capacity">模型任务并发上限（1～10）</label><Input id="worker-capacity" type="number" min={1} max={10} step={1} value={value} disabled={save.isPending} onChange={(event) => {
        if (!config.data) return;
        setDraft({ value: event.target.value, version: draft?.version ?? config.data.version });
        if (!conflict) save.reset();
      }} />
      <p>当前已保存上限 {config.data.model_task_concurrency} · 配置版本 {config.data.version}{draft ? " · 有未保存草稿" : ""}</p>
      <Button type="primary" htmlType="submit" loading={save.isPending} disabled={!draft || !valid || save.isPending || conflict}>保存并发上限</Button>
      {draft && <Button disabled={save.isPending} onClick={() => { setDraft(null); save.reset(); void config.refetch(); }}>放弃草稿并刷新配置</Button>}
    </form>}
    {save.isSuccess && <p role="status">配置已保存，等待 Worker 确认应用；不代表已开始或完成评审。</p>}
    {save.error && <p className="form-error" role="alert">{save.error.message}。草稿保留，不会自动重放。</p>}
    <p>默认 1，可自由设置 1～10。调高后可自动领取更多已排队任务并产生模型费用；调低只等待在途任务结束，不强行中断。同仓库串行，只有不同仓库可并行；模型诊断也占总配额。</p>
    <Collapse size="small" items={[{ key: "capacity-help", label: "并发与费用说明", children: <p>任务并发不等于 OCR 内部并发；单任务内部默认 4 路、可由既有配置覆盖。较高上限会增加内存、磁盘及模型额度压力，不保证提速，也不自动扩大补审预算。建议逐步调高，关注限流、超时和费用。</p> }]} />
  </div>;
}
