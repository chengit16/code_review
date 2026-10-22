/** @description 展示 OCR 返回的实际 Token 用量与按运行时单价计算的预估费用。 */

import type { ReviewJobDetail } from "../api/types";

/** 缺失的用量或单价保持“未提供”，不从预算、模型名称或当前配置推算历史费用。 */
export function ModelUsage({ result }: { /** 当前尝试的服务端安全结果。 */ result: ReviewJobDetail["result"] }) {
  const usage = result?.usage;
  if (!result) return null;
  const cost = result.estimated_cost;
  const total = usage?.total_tokens ?? (
    usage?.input_tokens != null && usage.output_tokens != null
      ? usage.input_tokens + usage.output_tokens : null
  );
  const formatTokens = (value: number | null | undefined) => value == null ? "未提供" : value.toLocaleString("zh-CN");
  const formatMoney = (value: string) => {
    const amount = Number(value);
    // 极小但非零的估算不能因界面四舍五入显示为零。
    if (amount > 0 && amount < 0.000001) return "<0.000001";
    return amount.toLocaleString("zh-CN", {
      minimumFractionDigits: 4, maximumFractionDigits: 6,
    });
  };
  const costText = cost ? formatMoney(cost.total) : null;
  return <section className="section detail-insight-card model-usage"><div className="section-head"><h2>模型用量</h2></div>
    <div className="model-usage-grid">
      <div><span>输入 Token</span><strong>{formatTokens(usage?.input_tokens)}</strong></div>
      <div><span>输出 Token</span><strong>{formatTokens(usage?.output_tokens)}</strong></div>
      <div><span>合计 Token</span><strong>{formatTokens(total)}</strong></div>
      <div><span>预估费用</span><strong>{cost && costText ? `${costText.startsWith("<") ? "<" : ""}${cost.currency === "CNY" ? "¥" : "$"}${costText.replace(/^</, "")}` : "未提供"}</strong></div>
    </div>
    <p className="model-usage-note">{cost ? "按本次评审开始时的输入、输出单价估算；实际账单可能包含缓存、阶梯价或其他计费项。" : "OCR 未返回完整输入、输出用量，或本次评审未配置单价，无法估算费用。"}</p>
  </section>;
}
