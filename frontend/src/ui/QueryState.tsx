/** @description 统一呈现列表加载与失败状态，避免各页静默空白。 */

/** 供页面在请求期间或出错时显示稳定高度的反馈。 */
export function QueryState({ loading, error, onRetry }: {
  /** 首次请求是否仍在进行。 */ loading: boolean;
  /** 请求失败时的原始错误。 */ error: Error | null;
  /** 重新查询，不重新执行评审、投递或其他写操作。 */ onRetry?: () => void;
}) {
  if (loading) return <div className="query-state" role="status">正在加载…</div>;
  if (error) return <div className="query-state query-state-error" role="alert"><span>{error.message}</span>{onRetry && <button className="button button-secondary" type="button" onClick={onRetry}>重新加载</button>}<small>查询失败不代表没有数据；重试只重新读取，不会重新执行任务。</small></div>;
  return null;
}
