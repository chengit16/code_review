/** @description 统一呈现列表加载与失败状态，避免各页静默空白。 */

/** 供页面在请求期间或出错时显示稳定高度的反馈。 */
export function QueryState({ loading, error }: {
  /** 首次请求是否仍在进行。 */ loading: boolean;
  /** 请求失败时的原始错误。 */ error: Error | null;
}) {
  if (loading) return <div className="query-state" role="status">正在加载…</div>;
  if (error) return <div className="query-state query-state-error" role="alert">{error.message}</div>;
  return null;
}
