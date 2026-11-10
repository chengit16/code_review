/** @description 只读详情行的鼠标和键盘入口；隔离内部控件，不接管业务授权、URL 或写操作。 */
import type { HTMLAttributes } from "react";

const interactive = "a,button,input,label,select,textarea,summary,[role='button'],[role='checkbox'],[role='link'],[role='combobox'],[contenteditable='true']";

/** 保留表格行语义；Enter 打开详情，控件、文本选择和修饰键不触发整行导航。 */
export function detailRowProps(
  /** 调用页提供详情导航或抽屉打开动作，不用于写操作。 */ onOpen: () => void,
  /** 行焦点的可访问名称。 */ label: string,
): HTMLAttributes<HTMLTableRowElement> {
  return {
    className: "detail-entry-row", tabIndex: 0, "aria-label": label,
    onClick: (event) => {
      if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      if (event.target instanceof Element && event.target.closest(interactive)) return;
      if (window.getSelection()?.toString()) return;
      onOpen();
    },
    onKeyDown: (event) => {
      if (event.target !== event.currentTarget || event.key !== "Enter" || event.defaultPrevented || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      onOpen();
    },
  };
}
