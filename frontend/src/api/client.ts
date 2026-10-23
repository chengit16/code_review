/** @description 管理 API 的统一认证、错误映射和取消边界。 */

/** 服务端拒绝或网络边界失败时保留状态、稳定错误码和请求关联信息。 */
export class ApiError extends Error {
  /** 创建统一 API 错误；status 为 0 表示请求未收到 HTTP 响应。 */
  constructor(
    public readonly status: number,
    message: string,
    public readonly code?: string,
    public readonly requestId?: string,
  ) {
    super(message);
  }
}

/**
 * 请求同源管理 API。
 * 共享口令和账号会话只保留在 React 内存中；开发模式不发送空的认证头。
 */
export async function apiRequest<T>(
  token: string,
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const timeout = AbortSignal.timeout(30000);
  const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout;
  let response: Response;
  try {
    response = await fetch(path, {
      ...options,
      signal,
      headers: {
        ...(token.startsWith("session:") ? { Authorization: `Bearer ${token.slice(8)}` } :
          token ? { "X-Admin-Token": token } : {}),
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
    });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    if (timeout.aborted) throw new ApiError(0, "请求超时，请检查服务状态后重试。", "timeout");
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "无法连接管理服务，请确认服务已启动后重试。", "network");
  }
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    let code: string | undefined;
    try {
      const payload: unknown = await response.json();
      if (typeof payload === "object" && payload !== null && "detail" in payload) {
        const detail = payload.detail;
        if (typeof detail === "string") message = detail;
        else if (typeof detail === "object" && detail !== null) {
          if ("message" in detail && typeof detail.message === "string") message = detail.message;
          if ("code" in detail && typeof detail.code === "string") code = detail.code;
        }
      }
    } catch {
      // 非 JSON 错误仍保留 HTTP 状态，避免解析异常覆盖原始故障。
    }
    if (response.status === 401) message = "管理会话无效或已过期，请重新登录。";
    throw new ApiError(response.status, message, code, response.headers.get("x-request-id") ?? undefined);
  }
  if (response.status === 204) return undefined as T;
  try {
    return await response.json() as T;
  } catch {
    throw new ApiError(response.status, "服务响应格式无效，请重试或联系管理员。", "invalid_response",
      response.headers.get("x-request-id") ?? undefined);
  }
}
