/**
 * @description 项目列表中的 Webhook 令牌查看与复制
 *
 * 只在管理员主动操作时请求单个令牌，不把明文放进仓库列表缓存。
 */

import { Copy, Eye, EyeOff } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { apiRequest } from "../api/client";
import type { WebhookTokenResponse } from "../api/types";

interface WebhookTokenCellProps {
  /** 当前管理会话口令，开发模式为空。 */
  token: string;
  /** 令牌所属项目 ID。 */
  repositoryId: number;
  /** 用于操作按钮的可访问名称。 */
  repositoryName: string;
}

/** 明文仅保留在当前行的组件内存中，离开页面或修改项目后即清除。 */
export function WebhookTokenCell({ token, repositoryId, repositoryName }: WebhookTokenCellProps) {
  const [webhookToken, setWebhookToken] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const request = useRef<AbortController | null>(null);

  useEffect(() => () => request.current?.abort(), []);

  async function loadToken(action: "reveal" | "copy") {
    const controller = new AbortController();
    request.current = controller;
    setPending(true);
    setError("");
    setNotice("");
    try {
      const result = await apiRequest<WebhookTokenResponse>(
        token,
        `/api/repositories/${repositoryId}/webhook-token`,
        { cache: "no-store", signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      if (action === "copy") {
        await navigator.clipboard.writeText(result.webhook_token);
        setNotice("已复制");
      } else {
        setWebhookToken(result.webhook_token);
      }
    } catch (cause) {
      if (!controller.signal.aborted) {
        setError(cause instanceof Error ? cause.message : "读取令牌失败");
      }
    } finally {
      if (!controller.signal.aborted) setPending(false);
      if (request.current === controller) request.current = null;
    }
  }

  function handleReveal() {
    if (webhookToken !== null) {
      setWebhookToken(null);
      setNotice("");
      setError("");
      return;
    }
    void loadToken("reveal");
  }

  async function handleCopy() {
    if (webhookToken === null) {
      await loadToken("copy");
      return;
    }
    try {
      await navigator.clipboard.writeText(webhookToken);
      setNotice("已复制");
      setError("");
    } catch {
      setError("复制失败，请手动选择令牌");
    }
  }

  return (
    <div className="webhook-token">
      <div className="webhook-token-controls">
        {webhookToken === null ? (
          <span className="webhook-token-mask" aria-label="令牌已隐藏">••••••••</span>
        ) : (
          <input className="webhook-token-value mono" aria-label={`${repositoryName} 的 Webhook Token`} value={webhookToken} readOnly onFocus={(event) => event.target.select()} />
        )}
        <button className="icon-button" type="button" title={webhookToken === null ? "查看 Webhook Token" : "隐藏 Webhook Token"} aria-label={`${webhookToken === null ? "查看" : "隐藏"} ${repositoryName} 的 Webhook Token`} onClick={handleReveal} disabled={pending}>
          {webhookToken === null ? <Eye size={16} /> : <EyeOff size={16} />}
        </button>
        <button className="icon-button" type="button" title="复制 Webhook Token" aria-label={`复制 ${repositoryName} 的 Webhook Token`} onClick={() => void handleCopy()} disabled={pending}>
          <Copy size={16} />
        </button>
      </div>
      {pending && <span className="webhook-token-message" role="status">读取中</span>}
      {notice && <span className="webhook-token-message" role="status">{notice}</span>}
      {error && <span className="webhook-token-message form-error" role="alert">{error}</span>}
    </div>
  );
}
