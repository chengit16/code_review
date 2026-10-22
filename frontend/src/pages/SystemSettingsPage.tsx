/** @description 将模型、飞书和规则配置组合为管理员设置页；标签状态保存在 URL，服务端仍负责授权。 */

import type { KeyboardEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { FeishuHooksPage } from "./FeishuHooksPage";
import { ReviewRulesPage } from "./ReviewRulesPage";
import { SettingsPage } from "./SettingsPage";
import { PageHeader } from "../ui/PageHeader";

const tabs = [
  { id: "model", label: "Agent 模型" },
  { id: "feishu", label: "飞书通知" },
  { id: "rules", label: "审核规则" },
];

/** 配置切换采用自动激活，方向键和首尾键同时移动焦点与当前标签。 */
function handleTabKey(event: KeyboardEvent<HTMLAnchorElement>) {
  const links = Array.from(event.currentTarget.parentElement?.querySelectorAll<HTMLAnchorElement>("[role=tab]") ?? []);
  const current = links.indexOf(event.currentTarget);
  let next: number;
  switch (event.key) {
    case "ArrowRight": next = (current + 1) % links.length; break;
    case "ArrowLeft": next = (current - 1 + links.length) % links.length; break;
    case "Home": next = 0; break;
    case "End": next = links.length - 1; break;
    default: return;
  }
  event.preventDefault();
  links[next]?.focus();
  links[next]?.click();
}

/** 仅挂载当前配置面板，离开标签时清理该面板的表单及密钥草稿，不更改后台配置。 */
export function SystemSettingsPage({ token }: {
  /** 内存中的管理口令或会话；页面入口仅向管理员开放。 */ token: string;
}) {
  const [params] = useSearchParams();
  const tab = tabs.find((item) => item.id === params.get("tab"))?.id ?? "model";

  return <div className="page system-settings-page">
    <PageHeader title="系统设置" subtitle="集中管理评审模型、飞书通知与审核规则" />
    <div className="settings-tabs" role="tablist" aria-label="系统设置分类">
      {tabs.map((item) => {
        const target = new URLSearchParams(params);
        target.set("tab", item.id);
        return <Link key={item.id} id={`settings-tab-${item.id}`} role="tab" to={`?${target}`}
          aria-selected={tab === item.id} aria-controls={`settings-panel-${item.id}`}
          tabIndex={tab === item.id ? 0 : -1} onKeyDown={handleTabKey}
          className={`repository-editor-tab${tab === item.id ? " is-active" : ""}`}>
          {item.label}
        </Link>;
      })}
    </div>
    <div id={`settings-panel-${tab}`} role="tabpanel" aria-labelledby={`settings-tab-${tab}`} tabIndex={0}>
      {tab === "model" && <SettingsPage token={token} embedded />}
      {tab === "feishu" && <FeishuHooksPage token={token} embedded />}
      {tab === "rules" && <ReviewRulesPage token={token} embedded />}
    </div>
  </div>;
}
