/** @description 平台列表与详情之间只携带白名单筛选，不接受外部返回地址或敏感正文。 */

const allowed = new Set(["view", "page", "page_size", "status", "kind", "category", "q", "archive",
  "theme_page", "theme_page_size", "theme_status", "theme_category", "theme_q", "theme_archive", "theme_improvement_id"]);

function clean(params: URLSearchParams) {
  const safe = new URLSearchParams();
  for (const [key, value] of params) if (allowed.has(key) && value.length <= 200) safe.set(key, value);
  return safe;
}

/** 列表进入详情时保存查询上下文，不保存任意路径。 */
export function listReturnSearch(params: URLSearchParams): string {
  return `?${new URLSearchParams({ list: clean(params).toString() })}`;
}

/** 返回固定站内列表；主题与记录缺少来源参数时使用各自默认视图。 */
export function listReturnTarget(search: string, themes = false): string {
  const source = new URLSearchParams(search).get("list");
  const params = source ? clean(new URLSearchParams(source)) : new URLSearchParams();
  if (themes) params.set("view", "themes");
  else params.delete("view");
  return `/improvements${params.size ? `?${params}` : ""}`;
}
