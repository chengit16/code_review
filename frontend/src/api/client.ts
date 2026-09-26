/** @description 管理 API 的统一认证、错误映射和取消边界。 */

/** 服务端拒绝请求时保留 HTTP 状态与可展示原因。 */
export class ApiError extends Error {
  /** 创建包含 HTTP 状态码的业务错误。 */
  constructor(public readonly status: number, message: string) {
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
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(token.startsWith("session:") ? { Authorization: `Bearer ${token.slice(8)}` } :
        token ? { "X-Admin-Token": token } : {}),
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const payload: unknown = await response.json();
      if (typeof payload === "object" && payload !== null && "detail" in payload) {
        const detail = payload.detail;
        if (typeof detail === "string") message = detail;
      }
    } catch {
      // 非 JSON 错误仍保留 HTTP 状态，避免解析异常覆盖原始故障。
    }
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<T>;
}
