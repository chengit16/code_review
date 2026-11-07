/** @description 迁移页面的只读查询反馈；失败不等于空数据，重试不执行写操作。 */
import { Alert, Button, Spin } from "antd";

/** 按查询单独恢复，缓存存在但刷新失败时仍明确标识不可靠状态。 */
export function ReadFeedback({ name, loading, error, onRetry }: {
  /** 需要恢复的查询名称。 */ name: string;
  /** 首次读取尚未完成。 */ loading: boolean;
  /** 包括后台刷新失败，不把旧缓存视为已确认事实。 */ error: Error | null;
  /** 只重新读取当前查询。 */ onRetry: () => void;
}) {
  if (error) return <Alert type="error" showIcon title={`${name}读取失败，状态未知`} description={error.message}
    action={<Button onClick={onRetry}>重新读取{name}</Button>} />;
  if (loading) return <div role="status"><Spin size="small" /> 正在读取{name}…</div>;
  return null;
}
