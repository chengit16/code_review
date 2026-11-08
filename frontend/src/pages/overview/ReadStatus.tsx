/** @description 独立资源的最近成功读取时间；不冒充后端快照时间。 */
import { ListTime } from "../../ui/ListControls";

/** 展示成功时间与刷新状态；轮询变化不进入实时播报区。 */
export function ReadStatus({ updatedAt, fetching, label }: {
  /** TanStack Query 的成功读取时间。 */ updatedAt: number;
  /** 当前是否有请求。 */ fetching: boolean;
  /** 独立资源名称。 */ label: string;
}) {
  return <span className="overview-read">{label} · {updatedAt > 0 ? <>成功读取于 <ListTime value={new Date(updatedAt).toISOString()} /></> : "尚未成功读取"}{fetching && " · 正在读取"}</span>;
}
