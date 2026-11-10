/** @description 添加项目时显式读取元数据；草稿变化即取消旧读取，不覆盖人工编辑，不自动保存仓库。 */
import { Button } from "antd";
import { useEffect, useRef, useState } from "react";

import { discoverRepository } from "../api/services/setup";
import type { RepositoryMetadata } from "../api/services/setup";

/** 临时令牌仅在表单内存及同源请求体中；失败保留手动路径。 */
export function RepositoryMetadataLookup({ token, remoteUrl, gitlabToken, draftVersion, onResolved }: {
  /** 内存管理会话。 */ token: string;
  /** 用户明确指定的 HTTPS 主机及项目。 */ remoteUrl: string;
  /** 仅供本次读取的新令牌。 */ gitlabToken: string;
  /** 任何手动字段变化都使在途结果过期。 */ draftVersion: number;
  /** 只在当前草稿仍未改变时回填。 */ onResolved: (value: RepositoryMetadata) => void;
}) {
  const request = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => () => { request.current?.abort(); }, [draftVersion]);
  async function lookup() {
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await discoverRepository(token, remoteUrl, gitlabToken, controller.signal);
      if (!controller.signal.aborted) { onResolved(result); setMessage("资料已带出，请核对后保存；尚未创建项目。"); }
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "获取失败，请手动填写");
    } finally { if (request.current === controller) setBusy(false); }
  }
  return <div className="wide"><p className="form-note">先填写地址与令牌，再获取项目资料；令牌只发送给你指定的 GitLab 主机。也可直接手动填写下方字段。</p>
    <Button disabled={!remoteUrl || !gitlabToken || busy} loading={busy} onClick={() => void lookup()}>获取项目资料</Button>
    {busy && <Button onClick={() => { request.current?.abort(); setBusy(false); }}>停止等待</Button>}
    {message && <p role="status" className="form-success">{message}</p>}{error && <p role="alert" className="form-error">{error}</p>}
  </div>;
}
