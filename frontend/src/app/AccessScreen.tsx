/** @description 本地管理口令入口；认证结果仅保留在本次页面会话内。 */

import { ArrowRight, ShieldCheck } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../api/client";

/** 验证管理口令后进入工作台，不向浏览器存储写入凭据。 */
export function AccessScreen({ onAccess, mode }: {
  /** 认证通过后设置内存会话。 */ onAccess: (token: string) => void;
  /** 当前服务端认证方式。 */ mode: "admin" | "users";
}) {
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "users") {
        const response = await apiRequest<{ token: string }>("", "/api/auth/login", {
          method: "POST", body: JSON.stringify({ username, password: token }),
        });
        onAccess(`session:${response.token}`);
      } else {
        await apiRequest<unknown>(token, "/api/repositories");
        onAccess(token);
      }
    } catch {
      setError(mode === "users" ? "用户名或密码无效" : "连接失败或管理口令无效");
    } finally {
      setBusy(false);
    }
  }

  return <div className="access-screen"><form className="access-form" onSubmit={handleSubmit}>
    <div className="access-symbol"><ShieldCheck size={30} /></div>
    <p className="eyebrow">运行控制台</p><h1>Code Review 管理台</h1>
    <p className="access-copy">{mode === "users" ? "使用管理账号登录。" : "请输入此设备的管理口令。"}</p>
    {mode === "users" && <><label htmlFor="username">用户名</label><input id="username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required /></>}
    <label htmlFor="admin-token">{mode === "users" ? "密码" : "管理口令"}</label>
    <input id="admin-token" type="password" autoComplete={mode === "users" ? "current-password" : "off"} value={token} onChange={(event) => setToken(event.target.value)} required />
    {error && <p className="form-error" role="alert">{error}</p>}
    <button className="button button-primary" type="submit" disabled={busy}>{busy ? "正在验证" : "进入管理台"}<ArrowRight size={17} /></button>
  </form></div>;
}
