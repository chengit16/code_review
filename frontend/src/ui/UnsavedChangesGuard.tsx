/** @description 配置草稿离开保护；只提示用户，不把表单或密钥持久化到浏览器。 */

import { useContext, useEffect } from "react";
import { UNSAFE_DataRouterContext, useBlocker } from "react-router-dom";

/** 弹窗关闭等非路由动作复用同一确认语义。 */
export function confirmDiscard(dirty: boolean) {
  return !dirty || window.confirm("有未保存的更改，离开会丢失这些内容。确定放弃并离开？");
}

function RouterGuard({ dirty }: { dirty: boolean }) {
  const blocker = useBlocker(({ currentLocation, nextLocation }) => dirty &&
    (currentLocation.pathname !== nextLocation.pathname || currentLocation.search !== nextLocation.search));
  useEffect(() => {
    if (blocker.state !== "blocked") return;
    if (confirmDiscard(true)) blocker.proceed(); else blocker.reset();
  }, [blocker]);
  return null;
}

/** 覆盖标签、侧栏、浏览器前后退和关闭刷新；独立组件测试不要求数据路由上下文。 */
export function UnsavedChangesGuard({ dirty }: {
  /** 只表示当前表单与已保存基线不同，不代表后台状态。 */ dirty: boolean;
}) {
  const router = useContext(UNSAFE_DataRouterContext);
  useEffect(() => {
    if (!dirty) return;
    const beforeUnload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    const beforeLogout = (event: Event) => { if (!confirmDiscard(true)) event.preventDefault(); };
    window.addEventListener("beforeunload", beforeUnload);
    window.addEventListener("workspace-before-logout", beforeLogout);
    return () => { window.removeEventListener("beforeunload", beforeUnload); window.removeEventListener("workspace-before-logout", beforeLogout); };
  }, [dirty]);
  return <>{router && <RouterGuard dirty={dirty} />}{dirty && <p className="unsaved-note" role="status">有未保存的更改，离开前请先保存。</p>}</>;
}
