/** @description 管理员调整单 Worker 模型任务总容量；草稿与轮询分离，冲突不自动重放。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError } from "../api/client";
import { getWorkerSchedulerConfig, saveWorkerSchedulerConfig } from "../api/workerScheduler";
import type { WorkerSchedulerConfig } from "../api/workerScheduler";
import { QueryState } from "../ui/QueryState";

/** 在开始编辑时冻结版本，刷新只更新服务端事实，不覆盖未保存输入。 */
export function WorkerConcurrency({ token }: { /** 内存管理会话。 */ token: string }) {
  const client = useQueryClient();
  const config = useQuery({ queryKey: ["worker-scheduler-config"], queryFn: ({ signal }) => getWorkerSchedulerConfig(token, signal), refetchInterval: 10000 });
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
    <QueryState loading={config.isLoading} error={config.error} />
    {config.data && <form className="alert-settings" onSubmit={(event) => {
      event.preventDefault();
      if (valid && draft && !save.isPending && !conflict) save.mutate({ model_task_concurrency: number, version: draft.version });
    }}>
      <label>模型任务并发上限（1～10）<input type="number" min={1} max={10} step={1} value={value} disabled={save.isPending} onChange={(event) => {
        if (!config.data) return;
        setDraft({ value: event.target.value, version: draft?.version ?? config.data.version });
        if (!conflict) save.reset();
      }} /></label>
      <button className="button button-primary" disabled={!draft || !valid || save.isPending || conflict}>保存并发上限</button>
      {draft && <button type="button" className="button button-secondary" disabled={save.isPending} onClick={() => { setDraft(null); save.reset(); void config.refetch(); }}>放弃草稿并刷新配置</button>}
    </form>}
    {save.isSuccess && <p role="status">配置已保存，等待 Worker 确认应用；不代表已开始或完成评审。</p>}
    {save.error && <p className="form-error" role="alert">{save.error.message}。草稿保留，不会自动重放。</p>}
    <p>默认 1，可自由设置 1～10。调高后可自动领取更多已排队任务并产生模型费用；调低只等待在途任务结束，不强行中断。同仓库串行，只有不同仓库可并行；模型诊断也占总配额。</p>
    <p>任务并发不等于 OCR 内部并发；单任务内部默认 4 路、可由既有配置覆盖。较高上限会增加内存、磁盘及模型额度压力，不保证提速，也不自动扩大补审预算。建议逐步调高，关注限流、超时和费用。</p>
  </div>;
}
