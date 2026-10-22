/** @description 展示独立的 GitLab 回调与管理入口；部署地址来自受保护的服务接口。 */

import { useQuery } from "@tanstack/react-query";

import { apiRequest } from "../api/client";
import { QueryState } from "../ui/QueryState";

/** 核对运行中的入口地址，避免把管理详情链接配置为只转发 Webhook 的隧道。 */
export function ServiceAddresses({ token }: { /** 内存中的管理凭据。 */ token: string }) {
  const query = useQuery({ queryKey: ["service-addresses"], queryFn: () => apiRequest<{ webhook_url: string; management_url: string }>(token, "/api/service-addresses") });
  return <section className="section operation-card service-address-card"><div className="section-head"><h2>服务入口</h2></div>
    <QueryState loading={query.isLoading} error={query.error} />
    {query.data && <dl className="service-addresses"><div><dt>GitLab 回调</dt><dd className="mono">{query.data.webhook_url}</dd></div><div><dt>管理入口</dt><dd className="mono">{query.data.management_url}</dd></div></dl>}
  </section>;
}
