/** @description 展示当前保存配置及来源，不读取远端文件、不修改配置、不宣称在途任务已应用。 */
import { useQuery } from "@tanstack/react-query";
import { Descriptions } from "antd";

import { getEffectiveConfiguration } from "../api/services/setup";
import { QueryState } from "../ui/QueryState";
import { RouteButton } from "../ui/RouteButton";
import { formatTime } from "../ui/format";

/** 后续任务摘要与项目草稿分开；只展示已保存事实。 */
export function EffectiveConfiguration({ token, repositoryId }: {
  /** 内存管理员会话。 */ token: string;
  /** 当前项目身份。 */ repositoryId: number;
}) {
  const query = useQuery({ queryKey: ["effective-configuration", repositoryId], queryFn: ({ signal }) => getEffectiveConfiguration(token, repositoryId, signal) });
  const data = query.data;
  return <section className="section"><h3>后续任务的当前配置</h3><QueryState loading={query.isPending} error={query.error} onRetry={() => void query.refetch()} />
    {data && <><Descriptions size="small" column={1} items={[
      { key: "model", label: "模型", children: `${data.model.name || "未配置"} · ${data.model.model || "待补全"}（${data.model.source === "project" ? "项目指定" : "继承全局默认"}）` },
      { key: "timeout", label: "超时", children: `${data.timeout_seconds.value} 秒（${data.timeout_seconds.source === "project" ? "项目覆盖" : "部署配置"}）` },
      { key: "limits", label: "限制", children: `文件：${data.max_files ?? "不限制"} · Token：${data.max_tokens_budget ?? "不限制"}` },
      { key: "rules", label: "规则", children: `项目页面${data.rules.project_configured ? "已配置" : "未配置"}；全局页面${data.rules.global_configured ? "已配置" : "未配置"}。仓库文件：${data.rules.repository_file}` },
      { key: "change", label: "基础接入最近保存", children: data.repository_change ? formatTime(data.repository_change.created_at) : "无版本记录" },
    ]} /><p className="form-note">规则优先级：项目页面 → 仓库 rule.json → 全局页面 → OCR 内置；路径规则首条命中；不代表全部叠加。参数、模型及规则的详细变更分别查看对应版本。已运行任务保持原快照。</p>
      <RouteButton to={`/settings?tab=rules&repository=${repositoryId}`}>查看本项目规则与预览</RouteButton></>}
  </section>;
}
