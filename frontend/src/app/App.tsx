/** @description 管理台路由、会话与主导航；凭据只保留在内存中。 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, GitPullRequest, LayoutDashboard, LogOut, Menu, RefreshCw, Settings2, ShieldCheck, TriangleAlert, Users, X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { BrowserRouter, Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";

import { AccessScreen } from "./AccessScreen";
import { ConfigHistoryPage } from "../pages/ConfigHistoryPage";
import { JobsPage } from "../pages/JobsPage";
import { JobDetailPage } from "../pages/JobDetailPage";
import { OverviewPage } from "../pages/OverviewPage";
import { OperationsPage } from "../pages/OperationsPage";
import { PremergePage } from "../pages/PremergePage";
import { RepositoriesPage } from "../pages/RepositoriesPage";
import { ReviewIssuesPage } from "../pages/ReviewIssuesPage";
import { SystemSettingsPage } from "../pages/SystemSettingsPage";
import { UsersPage } from "../pages/UsersPage";
import { apiRequest } from "../api/client";
import type { Health } from "../api/types";

const navigation = [
  { heading: "工作台", links: [
    { to: "/", label: "运行概览", icon: LayoutDashboard, end: true },
    { to: "/jobs", label: "评审任务", icon: Activity },
    { to: "/issues", label: "待跟进问题", icon: TriangleAlert },
    { to: "/premerge", label: "合并前审查", icon: GitPullRequest },
  ] },
  { heading: "接入配置", links: [
    { to: "/repositories", label: "项目配置", icon: GitPullRequest },
    { to: "/settings", label: "系统设置", icon: Settings2 },
    { to: "/users", label: "访问权限", icon: Users },
  ] },
];

function Brand() {
  return <div className="brand"><span className="brand-mark"><ShieldCheck size={21} /></span><span>Code Review<strong>管理台</strong></span></div>;
}

/** 窄屏使用带文字的抽屉导航；路由变化后把键盘焦点移回内容。 */
function Workspace({ token, role, username, onLogout }: {
  token: string; role: "admin" | "reader"; username: string; onLogout: () => void;
}) {
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
            {navigation.filter((group) => role === "admin" || group.heading === "工作台").map((group) => <div className="nav-group" key={group.heading}>
              <div className="nav-caption">{group.heading}</div>
              {group.links.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} title={label} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
                <Icon size={18} aria-hidden="true" /><span>{label}</span>
              </NavLink>)}
            </div>)}
          </nav>
          <div className="sidebar-bottom">
            <span className="connection-dot" /> {username}{role === "reader" ? " · 只读" : ""}
            <button type="button" className="icon-button" onClick={onLogout} aria-label="退出管理台" title="退出管理台"><LogOut size={17} /></button>
          </div>
        </aside>
        <main id="main-content" className="main-area" tabIndex={-1}>
          <Routes>
            <Route path="/" element={<OverviewPage token={token} />} />
            <Route path="/repositories" element={role === "admin" ? <RepositoriesPage token={token} /> : <Navigate to="/" replace />} />
            <Route path="/webhooks" element={<Navigate to="/repositories" replace />} />
            <Route path="/feishu" element={role === "admin" ? <Navigate to="/settings?tab=feishu" replace /> : <Navigate to="/" replace />} />
            <Route path="/events" element={<Navigate to="/jobs" replace />} />
            <Route path="/jobs" element={<JobsPage token={token} canEdit={role === "admin"} />} />
            <Route path="/issues" element={<ReviewIssuesPage token={token} canEdit={role === "admin"} />} />
            <Route path="/effectiveness" element={<Navigate to={{ pathname: "/", search: location.search }} replace />} />
            <Route path="/premerge" element={<PremergePage token={token} />} />
            <Route path="/jobs/:id" element={<JobDetailPage token={token} canEdit={role === "admin"} />} />
            <Route path="/operations" element={role === "admin" ? <OperationsPage token={token} /> : <Navigate to="/" replace />} />
            <Route path="/settings" element={role === "admin" ? <SystemSettingsPage token={token} /> : <Navigate to="/" replace />} />
            <Route path="/review-rules" element={role === "admin" ? <Navigate to="/settings?tab=rules" replace /> : <Navigate to="/" replace />} />
            <Route path="/config-history" element={role === "admin" ? <ConfigHistoryPage token={token} /> : <Navigate to="/" replace />} />
            <Route path="/users" element={role === "admin" ? <UsersPage token={token} /> : <Navigate to="/" replace />} />
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
  const identity = useQuery({
    queryKey: ["auth-me", token],
    queryFn: () => apiRequest<{ id: number | null; username: string; role: "admin" | "reader" }>(token, "/api/auth/me"),
    enabled: access.data?.auth_mode === "dev" || Boolean(token),
    retry: false,
  });

  // 健康接口公开提供鉴权模式，开发模式可直接进入，生产模式才显示口令入口。
  if (access.isLoading) return <div className="access-screen"><p className="query-state">正在连接本地服务…</p></div>;
  if (access.isError) return <div className="access-screen"><div className="access-form" role="alert">
    <div className="access-symbol"><ShieldCheck size={30} /></div>
    <h1>无法连接管理服务</h1>
    <p className="access-copy">本地服务暂不可用，请确认服务已启动后重试。</p>
    <button className="button button-primary" type="button" onClick={() => void access.refetch()}><RefreshCw size={17} />重新连接</button>
  </div></div>;
  if (access.data?.auth_mode !== "dev" && (!token || identity.isError)) return <AccessScreen mode={access.data?.auth_mode === "users" ? "users" : "admin"} onAccess={setToken} />;
  if (identity.isLoading) return <div className="access-screen"><p className="query-state">正在验证管理会话…</p></div>;

  function handleLogout() {
    if (token.startsWith("session:")) void apiRequest(token, "/api/auth/logout", { method: "POST" }).catch(() => undefined);
    queryClient.clear();
    setToken("");
  }

  return <BrowserRouter><Workspace token={token} role={identity.data?.role ?? "reader"} username={identity.data?.username ?? ""} onLogout={handleLogout} /></BrowserRouter>;
}
