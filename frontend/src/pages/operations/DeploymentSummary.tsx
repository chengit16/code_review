/** @description 部署白名单摘要仅供管理员核对 API 进程，不读取凭据、不修改部署或自动重启。 */
import { useQuery } from "@tanstack/react-query";
import { Card, Collapse, Descriptions } from "antd";

import { apiRequest } from "../../api/client";
import { QueryState } from "../../ui/QueryState";

interface Summary {
  auth_mode: string; ocr_command: string; timeout_seconds: number;
  ocr_internal_concurrency: number; model_task_concurrency: number;
  review_language: string; effort: string; source: string; restart: string;
}

/** 隐藏维护视图时停止查询；不以 API 摘要代替 Worker 实际应用状态。 */
export function DeploymentSummary({ token, active }: {
  /** 内存管理员会话。 */ token: string;
  /** 仅当前可见视图发起读取。 */ active: boolean;
}) {
  const query = useQuery({ queryKey: ["deployment-summary"], enabled: active, queryFn: ({ signal }) => apiRequest<Summary>(token, "/api/deployment-summary", { signal }) });
  const data = query.data;
  return <Card title="部署配置" className="operations-deployment"><QueryState loading={query.isPending} error={query.error} onRetry={() => void query.refetch()} />
    {data && <><Descriptions column={1} size="small" items={[
      { key: "auth", label: "认证", children: data.auth_mode === "dev" ? "开发模式" : "受保护模式" },
      { key: "command", label: "OCR 命令", children: data.ocr_command },
      { key: "timeout", label: "默认超时", children: `${data.timeout_seconds} 秒` },
      { key: "tasks", label: "模型任务并发上限", children: data.model_task_concurrency },
      { key: "internal", label: "单任务内部并发", children: data.ocr_internal_concurrency },
      { key: "language", label: "评审语言 / 推理力度", children: `${data.review_language} / ${data.effort}` },
    ]} /><Collapse ghost size="small" items={[{ key: "source", label: "配置来源与应用方式", children: <><p>默认超时可由项目覆盖；实际任务并发见「运行与并发」，与单任务内部并发分别设置。</p><p>{data.source}</p><p>{data.restart}</p></> }]} /></>}
  </Card>;
}
