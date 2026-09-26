/** @description 管理台路由、会话与主导航；凭据只保留在内存中。 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Bot, GitMerge, GitPullRequest, LayoutDashboard, LogOut, ShieldCheck, Webhook } from "lucide-react";
import { useState } from "react";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";

import { AccessScreen } from "./AccessScreen";
import { EventsPage } from "../pages/EventsPage";
import { JobsPage } from "../pages/JobsPage";
import { JobDetailPage } from "../pages/JobDetailPage";
import { OverviewPage } from "../pages/OverviewPage";
import { RepositoriesPage } from "../pages/RepositoriesPage";
import { SettingsPage } from "../pages/SettingsPage";
import { FeishuHooksPage } from "../pages/FeishuHooksPage";
import { apiRequest } from "../api/client";
import type { Health } from "../api/types";

const navigation = [
  { to: "/", label: "概览", icon: LayoutDashboard, end: true },
  { to: "/repositories", label: "项目配置", icon: GitPullRequest },
  { to: "/feishu", label: "飞书 Hook", icon: Webhook },
  { to: "/events", label: "合并事件", icon: GitMerge },
  { to: "/jobs", label: "评审任务", icon: Activity },
  { to: "/settings", label: "Agent 模型", icon: Bot },
];

/** 管理台入口；退出时清除敏感查询缓存。 */
export function App() {
  const [token, setToken] = useState("");
  const queryClient = useQueryClient();
  const access = useQuery({
    queryKey: ["access-health"],
    queryFn: () => apiRequest<Health>("", "/api/health"),
    retry: false,
    staleTime: Infinity,
  });

  // 健康接口公开提供鉴权模式，开发模式可直接进入，生产模式才显示口令入口。
  if (access.isLoading) return <div className="access-screen"><p className="query-state">正在连接本地服务…</p></div>;
  if (access.data?.auth_mode !== "dev" && !token) return <AccessScreen onAccess={setToken} />;

  function handleLogout() {
    queryClient.clear();
    setToken("");
  }

  return (
    <BrowserRouter>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="brand"><span className="brand-mark"><ShieldCheck size={21} /></span><span>Code Review<strong>管理台</strong></span></div>
          <div className="nav-caption">工作区</div>
          <nav aria-label="主导航">
            {navigation.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
                <Icon size={18} aria-hidden="true" /><span>{label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <span className="connection-dot" /> 本地管理会话
            <button type="button" className="icon-button" onClick={handleLogout} aria-label="退出管理台" title="退出管理台"><LogOut size={17} /></button>
          </div>
        </aside>
        <main className="main-area">
          <Routes>
            <Route path="/" element={<OverviewPage token={token} />} />
            <Route path="/repositories" element={<RepositoriesPage token={token} />} />
            <Route path="/feishu" element={<FeishuHooksPage token={token} />} />
            <Route path="/events" element={<EventsPage token={token} />} />
            <Route path="/jobs" element={<JobsPage token={token} />} />
            <Route path="/jobs/:id" element={<JobDetailPage token={token} />} />
            <Route path="/settings" element={<SettingsPage token={token} />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
