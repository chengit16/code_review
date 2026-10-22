/** @description 统一管理配置弹窗的键盘焦点与关闭行为。 */

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

/** 约束可见控件的键盘焦点，关闭请求交给调用方判断草稿和保存状态。 */
export function Modal({ titleId, onClose, children, className = "" }: {
  /** 可见标题元素的标识。 */ titleId: string;
  /** Escape 或调用方关闭按钮触发，由调用方执行确认。 */ onClose: () => void;
  /** 弹窗内可访问内容。 */ children: ReactNode;
  /** 可选布局类，不改变关闭语义。 */ className?: string;
}) {
  const dialog = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const controls = () => Array.from(dialog.current?.querySelectorAll<HTMLElement>(
      "button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]",
    ) ?? []).filter((element) => element.getClientRects().length > 0);
    (dialog.current?.querySelector<HTMLElement>("input:not(:disabled)") ?? controls()[0] ?? dialog.current)?.focus();

    // 焦点只在当前弹窗内循环，关闭后还给触发操作的按钮。
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        // 下拉弹层位于 Portal 中，先让它消费 Escape，下一次按键再关闭弹窗。
        if (event.target instanceof Element && event.target.closest("[data-select-popup]")) return;
        event.preventDefault();
        onCloseRef.current();
      } else if (event.key === "Tab") {
        const items = controls();
        if (items.length === 0) {
          event.preventDefault();
          return;
        }
        const first = items[0];
        const last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, []);

  return <div className="modal-backdrop" role="presentation"><div ref={dialog} className={["modal", className].filter(Boolean).join(" ")} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>{children}</div></div>;
}
