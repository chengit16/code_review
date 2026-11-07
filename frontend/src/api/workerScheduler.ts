/** @description 独立调度容量契约；不改变模型配置或评审内容快照。 */
import { apiRequest } from "./client";

/** 保存时必须带读取版本；并发冲突由用户重新核对，禁止自动覆盖。 */
export interface WorkerSchedulerConfig {
  model_task_concurrency: number;
  version: number;
}

/** 读取期望容量，不把该数值当成 Worker 已应用的事实。 */
export function getWorkerSchedulerConfig(token: string, signal?: AbortSignal) {
  return apiRequest<WorkerSchedulerConfig>(token, "/api/worker-scheduler/config", { signal });
}

/** 仅保存明确提交的容量；不自动调高、排队或重试任何评审。 */
export function saveWorkerSchedulerConfig(token: string, config: WorkerSchedulerConfig) {
  return apiRequest<WorkerSchedulerConfig>(token, "/api/worker-scheduler/config", {
    method: "PUT", body: JSON.stringify(config),
  });
}
