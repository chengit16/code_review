/** @description 统一展示事件、评审和通知的状态语义。 */

const labels: Record<string, string> = {
  queued: "排队中",
  running: "运行中",
  done: "已处理",
  complete: "已完成",
  partial: "部分完成",
  failed: "失败",
  skipped: "已跳过",
  needs_attention: "需要处理",
  pending: "待发送",
  sent: "已发送",
  passed: "已通过",
  configured: "已配置",
  unconfigured: "未配置",
  stopped: "未运行",
  unknown: "未知",
};

/** 对状态使用稳定尺寸和颜色，避免动态内容改变表格行高。 */
export function Status({ value }: { /** 后端状态原值。 */ value: string }) {
  return <span className={`status status--${value}`}>{labels[value] ?? value}</span>;
}
