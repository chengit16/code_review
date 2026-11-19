/** @description 新增编辑共用仓库接入控件；仅保存草稿，身份和分支由服务端 Worker 核验。 */
import { Alert, Button, Input, Select, Space, Spin } from "antd";
import { useEffect, useRef, useState } from "react";

import { apiRequest } from "../api/client";
import { createRepositoryQuery, queryRepositoryBranches, waitRepositoryQuery } from "../api/services/setup";
import type { RepositoryMetadata } from "../api/services/setup";

/** 识别结果绑定临时会话，服务端在保存时复核引用。 */
export interface ResolvedRepository extends RepositoryMetadata {
  /** 当前草稿的短期查询引用。 */ query_session_id: string;
}

/** 地址与凭据变化后取消旧查询；编辑时保留已选分支，不从默认值覆盖。 */
export function RepositoryConnectionFields({ token, remoteUrl, gitlabToken, branches, repositoryId, disabled, onRemote, onToken, onBranches, onResolved }: {
  /** 内存管理会话。 */ token: string;
  /** 当前 HTTPS 仓库地址。 */ remoteUrl: string;
  /** 新凭据；编辑留空保留服务器凭据。 */ gitlabToken: string;
  /** 当前选择，远端失败仍保留。 */ branches: string[];
  /** 编辑身份；新增省略。 */ repositoryId?: number;
  /** 保存期间冻结控件。 */ disabled: boolean;
  /** 更新地址并使旧身份引用失效。 */ onRemote: (value: string) => void;
  /** 更新凭据并使旧身份引用失效。 */ onToken: (value: string) => void;
  /** 仅从候选分支中选择。 */ onBranches: (value: string[]) => void;
  /** 回填后台识别的隐藏身份字段。 */ onResolved: (value: ResolvedRepository) => void;
}) {
  const branchKey = branches.join("\n");
  const [session, setSession] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [search, setSearch] = useState("");
  const [options, setOptions] = useState<{ value: string; label: string }[]>([]);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const [loadingBranches, setLoadingBranches] = useState(false);
  const [branchError, setBranchError] = useState("");
  const [branchRevision, setBranchRevision] = useState(0);
  const callback = useRef(onResolved);
  const branchRequest = useRef<AbortController | null>(null);
  useEffect(() => { callback.current = onResolved; }, [onResolved]);
  // 地址或凭据变更只影响当前连接查询；分支和通知草稿变更不会重复发送 Token。
  useEffect(() => {
    const controller = new AbortController();
    let created = "";
    setSession(""); setOptions([]); setNextPage(null); setError(""); setBusy(false); setLoadingBranches(false);
    if (!remoteUrl || (!gitlabToken && !repositoryId)) return;
    const timer = setTimeout(() => {
      setBusy(true);
      void (async () => {
        try {
          const queued = await createRepositoryQuery(token, remoteUrl, gitlabToken, repositoryId, controller.signal);
          created = queued.session_id;
          if (controller.signal.aborted) {
            void apiRequest(token, `/api/repository-query-sessions/${created}`, { method: "DELETE" }).catch(() => undefined);
            return;
          }
          const metadata = await waitRepositoryQuery<RepositoryMetadata>(token, queued.id, controller.signal);
          if (!controller.signal.aborted) { setSession(created); callback.current({ ...metadata, query_session_id: created }); }
        } catch (failure) {
          if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "仓库识别失败");
        } finally { if (!controller.signal.aborted) setBusy(false); }
      })();
    }, 650);
    return () => {
      clearTimeout(timer); controller.abort(); branchRequest.current?.abort();
      if (created) void apiRequest(token, `/api/repository-query-sessions/${created}`, { method: "DELETE" }).catch(() => undefined);
    };
  }, [token, remoteUrl, gitlabToken, repositoryId, revision]);
  useEffect(() => {
    branchRequest.current?.abort();
    if (!session) return;
    const controller = new AbortController(); branchRequest.current = controller; setLoadingBranches(false);
    const timer = setTimeout(() => {
      setLoadingBranches(true); setBranchError("");
      void queryRepositoryBranches(token, session, search, 1, controller.signal).then(async (result) => {
        // 默认分支可能不在第一页；单独远程核验当前值，不能用本地标签伪造候选。
        const missing = !search ? branchKey.split("\n").filter(Boolean).filter((branch) => !result.items.some((item) => item.name === branch)) : [];
        const extra = [];
        for (const branch of missing) {
          const selected = await queryRepositoryBranches(token, session, branch, 1, controller.signal);
          extra.push(...selected.items.filter((item) => item.name === branch));
        }
        if (!controller.signal.aborted) { setOptions([...result.items, ...extra].map((item) => ({ value: item.name, label: item.name }))); setNextPage(result.next_page); }

      }).catch((failure: unknown) => {
        if (!controller.signal.aborted) setBranchError(failure instanceof Error ? failure.message : "分支加载失败");
      }).finally(() => { if (!controller.signal.aborted) setLoadingBranches(false); });
    }, 300);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [token, session, search, branchRevision, branchKey]);
  async function loadMore() {
    if (!nextPage || loadingBranches || !session) return;
    const controller = new AbortController(); branchRequest.current = controller;
    setLoadingBranches(true); setBranchError("");
    try {
      const result = await queryRepositoryBranches(token, session, search, nextPage, controller.signal);
      if (!controller.signal.aborted) { setOptions((current) => [...new Map([...current, ...result.items.map((item) => ({ value: item.name, label: item.name }))].map((item) => [item.value, item])).values()]); setNextPage(result.next_page); }
    } catch (failure) { if (!controller.signal.aborted) setBranchError(failure instanceof Error ? failure.message : "分支加载失败"); }
    finally { if (!controller.signal.aborted) setLoadingBranches(false); }
  }
  return <>
    <label className="wide">仓库地址<Input type="url" value={remoteUrl} onChange={(event) => onRemote(event.target.value)} required disabled={disabled} placeholder="https://gitlab.example.com/team/project.git" /></label>
    <label className="wide">GitLab Token<Input.Password value={gitlabToken} onChange={(event) => onToken(event.target.value)} required={!repositoryId} disabled={disabled} autoComplete="new-password" placeholder={repositoryId ? "留空保留已有 Token" : "填写项目访问 Token"} /></label>
    <div className="wide"><Space><span role="status">{busy ? <><Spin size="small" /> 正在识别仓库</> : session ? "仓库已识别" : "填写地址与 Token 后自动识别"}</span><Button size="small" disabled={disabled || busy || !remoteUrl} onClick={() => setRevision((value) => value + 1)}>重新获取</Button></Space>{error && <Alert type="error" title={error} showIcon />}</div>
    <label className="wide">目标分支<Select aria-label="目标分支" classNames={{ popup: { root: "repository-branch-popup" } }} onInputKeyDown={(event) => { if (event.key === "Escape") event.stopPropagation(); }} mode="multiple" maxCount={20} maxTagCount="responsive" value={branches} disabled={disabled || !session} loading={loadingBranches} showSearch={{ filterOption: false, onSearch: setSearch }} onChange={onBranches} options={options} placeholder="搜索并选择目标分支，可多选" notFoundContent={loadingBranches ? <Spin size="small" /> : branchError || "未找到分支"} popupRender={(menu) => <>{menu}{nextPage && <Button block type="text" loading={loadingBranches} onClick={() => void loadMore()}>加载更多分支</Button>}</>} /></label>
    <p className="form-note wide">可选择 1–20 个远程分支；合并前 MR 和 Push 评审均按所选分支接收。</p>
    {branchError && <div className="wide"><Alert type="warning" title={branchError} showIcon /><Button size="small" onClick={() => setBranchRevision((value) => value + 1)} disabled={disabled}>重试分支查询</Button></div>}
  </>;
}
