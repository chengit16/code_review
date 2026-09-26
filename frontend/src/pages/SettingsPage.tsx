/** @description 管理 Agent 模型配置，密钥录入后不再从服务端回显。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../api/client";
import type { AuditEntry, ModelProfile } from "../api/types";
import { ConnectionChecks } from "../ui/ConnectionChecks";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { formatTime } from "../ui/format";

/** 已入队任务锁定模型版本，服务端会拒绝运行期间的配置更换。 */
export function SettingsPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["model-profile"], queryFn: () => apiRequest<ModelProfile>(token, "/api/model-profile") });
  const audit = useQuery({ queryKey: ["audit-logs"], queryFn: () => apiRequest<AuditEntry[]>(token, "/api/audit-logs"), refetchInterval: 10000 });
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  useEffect(() => {
    if (query.data) {
      setProvider(query.data.provider);
      setModel(query.data.model);
    }
  }, [query.data]);
  const save = useMutation({
    mutationFn: () => apiRequest<ModelProfile>(token, "/api/model-profile", {
      method: "PUT", body: JSON.stringify({ provider, model, api_key: apiKey || null }),
    }),
    onSuccess: () => { setApiKey(""); void queryClient.invalidateQueries({ queryKey: ["model-profile"] }); void queryClient.invalidateQueries({ queryKey: ["audit-logs"] }); },
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }
  return <div className="page"><PageHeader title="Agent 模型" subtitle="Open Code Review 的评审模型与连接测试" />
    <QueryState loading={query.isLoading} error={query.error} />
    {query.data && <section className="section settings-section"><div className="section-head"><h2>Agent 模型配置</h2><span>配置版本 {query.data.version}</span></div>
      <form className="settings-form" onSubmit={submit}>
        <label>Provider<input value={provider} onChange={(event) => setProvider(event.target.value)} required /></label>
        <label>Model<input value={model} onChange={(event) => setModel(event.target.value)} required /></label>
        <label>API key<input type="password" autoComplete="new-password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={query.data.has_api_key ? "已配置，留空则保留" : "输入模型密钥"} required={!query.data.has_api_key} /></label>
        {save.error && <p className="form-error" role="alert">{save.error.message}</p>}
        {save.isSuccess && !save.error && <p className="form-success" role="status">模型配置已保存</p>}
        <button className="button button-primary" type="submit" disabled={save.isPending}><Save size={16} />保存设置</button>
      </form>
      <ConnectionChecks token={token} kinds={["model"]} enabled={query.data.has_api_key && Boolean(query.data.model)} />
    </section>}
    <section className="section"><div className="section-head"><h2>管理操作</h2><span>最近 100 条</span></div><QueryState loading={audit.isLoading} error={audit.error} /><div className="table-scroll"><table><thead><tr><th>时间</th><th>操作</th><th>对象</th><th>结果</th></tr></thead><tbody>{audit.data?.map((entry) => <tr key={entry.id}><td>{formatTime(entry.created_at)}</td><td className="mono">{entry.action}</td><td>{entry.object_type}{entry.object_id !== null ? ` #${entry.object_id}` : ""}</td><td>{entry.outcome === "success" ? "成功" : entry.outcome}</td></tr>)}{audit.data?.length === 0 && <tr><td colSpan={4} className="empty-row">暂无管理操作</td></tr>}</tbody></table></div></section>
  </div>;
}
