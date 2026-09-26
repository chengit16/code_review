/** @description 管理台路由、会话与主导航；凭据只保留在内存中。 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Bot, GitMerge, GitPullRequest, LayoutDashboard, ListChecks, LogOut, Menu, MessageSquare, RefreshCw, ShieldCheck, X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { BrowserRouter, Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";

import { AccessScreen } from "./AccessScreen";
import { EventsPage } from "../pages/EventsPage";
import { JobsPage } from "../pages/JobsPage";
import { JobDetailPage } from "../pages/JobDetailPage";
import { OverviewPage } from "../pages/OverviewPage";
import { RepositoriesPage } from "../pages/RepositoriesPage";
import { ReviewRulesPage } from "../pages/ReviewRulesPage";
import { SettingsPage } from "../pages/SettingsPage";
import { FeishuHooksPage } from "../pages/FeishuHooksPage";
import { apiRequest } from "../api/client";
import type { Health } from "../api/types";

const navigation = [
  { heading: "工作台", links: [
    { to: "/", label: "运行概览", icon: LayoutDashboard, end: true },
    { to: "/events", label: "GitLab 事件", icon: GitMerge },
    { to: "/jobs", label: "评审任务", icon: Activity },
  ] },
  { heading: "接入配置", links: [
    { to: "/repositories", label: "项目配置", icon: GitPullRequest },
    { to: "/feishu", label: "飞书配置", icon: MessageSquare },
    { to: "/settings", label: "Agent 模型", icon: Bot },
    { to: "/review-rules", label: "审核规则", icon: ListChecks },
  ] },
];

function Brand() {
  return <div className="brand"><span className="brand-mark"><ShieldCheck size={21} /></span><span>Code Review<strong>管理台</strong></span></div>;
}

/** 窄屏使用带文字的抽屉导航；路由变化后把键盘焦点移回内容。 */
function Workspace({ token, onLogout }: { token: string; onLogout: () => void }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const sidebar = useRef<HTMLElement>(null);
  const sidebarClose = useRef<HTMLButtonElement>(null);
  const location = useLocation();
  const previousPath = useRef(location.pathname);

  useEffect(() => {
    if (previousPath.current === location.pathname) return;
    previousPath.current = location.pathname;
    setMenuOpen(false);
    document.getElementById("main-content")?.focus();
  }, [location.pathname]);

  useLayoutEffect(() => {
    if (menuOpen) sidebarClose.current?.focus();
  }, [menuOpen]);

  useEffect(() => {
    if (!menuOpen) return;
    const focusable = Array.from(sidebar.current?.querySelectorAll<HTMLElement>("button, a[href]") ?? []);
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMenuOpen(false);
        menuButton.current?.focus();
      } else if (event.key === "Tab" && focusable.length > 0) {
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [menuOpen]);

  return (
    <div className="app-shell">
      <header className="mobile-topbar"><Brand /><button ref={menuButton} className="icon-button" type="button" aria-label="打开导航" aria-expanded={menuOpen} aria-controls="sidebar-navigation" onClick={() => setMenuOpen(true)}><Menu size={21} /></button></header>
      {menuOpen && <button className="navigation-backdrop" type="button" aria-label="关闭导航" onClick={() => { setMenuOpen(false); menuButton.current?.focus(); }} />}
        <aside ref={sidebar} id="sidebar-navigation" className={`sidebar${menuOpen ? " is-open" : ""}`}>
          <div className="sidebar-heading"><Brand /><button ref={sidebarClose} className="icon-button sidebar-close" type="button" aria-label="关闭导航" onClick={() => { setMenuOpen(false); menuButton.current?.focus(); }}><X size={20} /></button></div>
          <nav aria-label="主导航">
            {navigation.map((group) => <div className="nav-group" key={group.heading}>
              <div className="nav-caption">{group.heading}</div>
              {group.links.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} title={label} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
                <Icon size={18} aria-hidden="true" /><span>{label}</span>
              </NavLink>)}
            </div>)}
          </nav>
          <div className="sidebar-bottom">
            <span className="connection-dot" /> 本地管理会话
            <button type="button" className="icon-button" onClick={onLogout} aria-label="退出管理台" title="退出管理台"><LogOut size={17} /></button>
          </div>
        </aside>
        <main id="main-content" className="main-area" tabIndex={-1}>
          <Routes>
            <Route path="/" element={<OverviewPage token={token} />} />
            <Route path="/repositories" element={<RepositoriesPage token={token} />} />
            <Route path="/webhooks" element={<Navigate to="/repositories" replace />} />
            <Route path="/feishu" element={<FeishuHooksPage token={token} />} />
            <Route path="/events" element={<EventsPage token={token} />} />
            <Route path="/jobs" element={<JobsPage token={token} />} />
            <Route path="/jobs/:id" element={<JobDetailPage token={token} />} />
            <Route path="/settings" element={<SettingsPage token={token} />} />
            <Route path="/review-rules" element={<ReviewRulesPage token={token} />} />
          </Routes>
        </main>
    </div>
  );
}

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
  if (access.isError) return <div className="access-screen"><div className="access-form" role="alert">
    <div className="access-symbol"><ShieldCheck size={30} /></div>
    <h1>无法连接管理服务</h1>
    <p className="access-copy">本地服务暂不可用，请确认服务已启动后重试。</p>
    <button className="button button-primary" type="button" onClick={() => void access.refetch()}><RefreshCw size={17} />重新连接</button>
  </div></div>;
  if (access.data?.auth_mode !== "dev" && !token) return <AccessScreen onAccess={setToken} />;

  function handleLogout() {
    queryClient.clear();
    setToken("");
  }

  return <BrowserRouter><Workspace token={token} onLogout={handleLogout} /></BrowserRouter>;
}
