/** @description 本地管理口令入口；认证结果仅保留在本次页面会话内。 */

import { ArrowRight, ShieldCheck } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../api/client";

/** 验证管理口令后进入工作台，不向浏览器存储写入凭据。 */
export function AccessScreen({ onAccess }: { /** 认证通过后设置内存会话。 */ onAccess: (token: string) => void }) {
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await apiRequest<unknown>(token, "/api/repositories");
      onAccess(token);
    } catch {
      setError("连接失败或管理口令无效");
    } finally {
      setBusy(false);
    }
  }

  return <div className="access-screen"><form className="access-form" onSubmit={handleSubmit}>
    <div className="access-symbol"><ShieldCheck size={30} /></div>
    <p className="eyebrow">运行控制台</p><h1>Code Review 管理台</h1>
    <p className="access-copy">请输入此设备的管理口令。</p>
    <label htmlFor="admin-token">管理口令</label>
    <input id="admin-token" type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} required />
    {error && <p className="form-error" role="alert">{error}</p>}
    <button className="button button-primary" type="submit" disabled={busy}>{busy ? "正在验证" : "进入管理台"}<ArrowRight size={17} /></button>
  </form></div>;
}
