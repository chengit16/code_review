/** @description 兼容 HTTP 域名的主动复制；不缓存内容，失败不显示成功，临时节点用完即清除。 */

/** 优先异步剪贴板；不可用或被拒绝时尝试浏览器复制命令，仍失败则交由界面提示手动选择。 */
export async function copyText(text: string): Promise<void> {
  if (typeof navigator.clipboard?.writeText === "function") {
    try { await navigator.clipboard.writeText(text); return; } catch { /* 权限或用户激活失效时尝试受控兼容路径。 */ }
  }
  if (typeof document.execCommand !== "function") throw new Error("浏览器不允许自动复制，请手动选择内容复制。");
  const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const selection = document.getSelection();
  const ranges = selection ? Array.from({ length: selection.rangeCount }, (_, index) => selection.getRangeAt(index).cloneRange()) : [];
  const input = document.createElement("textarea");
  input.value = text; input.readOnly = true; input.tabIndex = -1;
  input.setAttribute("aria-label", "临时复制内容");
  input.style.cssText = "position:fixed;left:0;top:0;width:1px;height:1px;opacity:0;pointer-events:none";
  document.body.append(input);
  try {
    input.focus({ preventScroll: true }); input.select();
    if (!document.execCommand("copy")) throw new Error("复制失败，请手动选择内容复制。");
  } finally {
    // 令牌不在隐藏节点中残留；恢复此前焦点和文本选择，不改变编辑草稿。
    input.value = ""; input.remove(); previous?.focus({ preventScroll: true });
    selection?.removeAllRanges(); ranges.forEach((range) => selection?.addRange(range));
  }
}
