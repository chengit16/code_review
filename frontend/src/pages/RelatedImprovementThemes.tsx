/** @description 问题详情的优化主题反向索引；只读关联，不推断主题或问题状态。 */
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listImprovementThemes } from "../api/improvements";
import { QueryState } from "../ui/QueryState";

/** 展示当前问题关联的主题，超出首屏时跳到带编号筛选的完整列表。 */
export function RelatedImprovementThemes({ token, recordId }: {
  /** 管理员内存会话，服务端仍负责授权。 */ token: string;
  /** 当前已持久化的问题编号。 */ recordId: number;
}) {
  const themes = useQuery({
    queryKey: ["improvement-themes", "related", recordId],
    queryFn: ({ signal }) => listImprovementThemes(token, new URLSearchParams({ improvement_id: String(recordId), archive: "all" }), signal),
  });
  return <section className="section" aria-label="关联优化主题"><h2>关联优化主题</h2>
    <QueryState loading={themes.isLoading} error={themes.error} onRetry={() => void themes.refetch()} />
    {themes.data && <>{themes.data.total ? <ul className="theme-linked-issues">{themes.data.items.map((theme) => <li key={theme.id}><Link to={`/improvements/themes/${theme.id}`}>#{theme.id} · {theme.title}</Link>{theme.archived_at && <span className="status">已归档</span>}</li>)}</ul> : <p className="muted">尚未关联优化主题，可在优化历程中编辑主题并选择此记录。</p>}
      {themes.data.total > themes.data.items.length && <Link to={`/improvements?view=themes&theme_archive=all&theme_improvement_id=${recordId}`}>查看全部 {themes.data.total} 个关联主题</Link>}</>}
  </section>;
}
