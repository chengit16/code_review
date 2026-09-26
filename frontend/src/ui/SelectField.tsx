/**
 * @description 管理台通用下拉选择，统一弹层与键盘交互。
 *
 * 使用 Radix 管理焦点、方向键和弹层定位；页面只负责选项与业务值。
 */

import * as Select from "@radix-ui/react-select";
import { Check, ChevronDown, ChevronUp } from "lucide-react";
import { useId } from "react";

/** 下拉选项；空值由占位文字表达，需要可选的“无”时请使用非空哨兵值。 */
export interface SelectOption {
  /** 提交给调用方的非空值。 */
  value: string;
  /** 在触发器与弹层中显示的文字。 */
  label: string;
  /** 禁止选择时为 true。 */
  disabled?: boolean;
}

/** 受控下拉的输入与回调。 */
export interface SelectFieldProps {
  /** 可见字段名，也是辅助技术读取的标签。 */
  label: string;
  /** 当前值；空字符串显示占位文字。 */
  value: string;
  /** 用户选择后同步调用方状态。 */
  onValueChange: (value: string) => void;
  /** 所有选项必须使用非空且唯一的值。 */
  options: readonly SelectOption[];
  /** 尚未选择时显示的文字。 */
  placeholder?: string;
  /** 原生表单字段名。 */
  name?: string;
  /** 表单提交前必须选择非空值。 */
  required?: boolean;
  /** 数据未就绪时阻止操作。 */
  disabled?: boolean;
  /** 页面布局需要的附加类名。 */
  className?: string;
}

/** 弹层进入 Portal，避免在模态框和表格容器里被裁切。 */
export function SelectField({
  label,
  value,
  onValueChange,
  options,
  placeholder = "请选择",
  name,
  required = false,
  disabled = false,
  className = "",
}: SelectFieldProps) {
  const id = useId();

  return (
    <div className={`select-field ${className}`.trim()}>
      <label htmlFor={id}>{label}</label>
      <Select.Root
        name={name}
        value={value}
        onValueChange={onValueChange}
        required={required}
        disabled={disabled}
      >
        <Select.Trigger id={id} className="select-trigger" type="button">
          <Select.Value placeholder={placeholder} />
          <Select.Icon className="select-chevron"><ChevronDown size={17} aria-hidden="true" /></Select.Icon>
        </Select.Trigger>
        <Select.Portal>
          <Select.Content className="select-content" data-select-popup position="popper" align="start" sideOffset={6} collisionPadding={8}>
            <Select.ScrollUpButton className="select-scroll-button"><ChevronUp size={16} aria-hidden="true" /></Select.ScrollUpButton>
            <Select.Viewport className="select-viewport">
              {options.map((option) => (
                <Select.Item key={option.value} value={option.value} disabled={option.disabled} className="select-option">
                  <Select.ItemIndicator className="select-indicator"><Check size={16} aria-hidden="true" /></Select.ItemIndicator>
                  <Select.ItemText>{option.label}</Select.ItemText>
                </Select.Item>
              ))}
            </Select.Viewport>
            <Select.ScrollDownButton className="select-scroll-button"><ChevronDown size={16} aria-hidden="true" /></Select.ScrollDownButton>
          </Select.Content>
        </Select.Portal>
      </Select.Root>
    </div>
  );
}
